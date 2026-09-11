from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cliente import Cliente
from app.models.movimentacao import Movimentacao
from app.models.ocupante import Ocupante
from app.models.reserva import Reserva
from app.models.vaga import StatusVaga, Vaga
from app.models.veiculo import Veiculo
from app.schemas.movimentacao import EntradaCreate
from app.schemas.reserva import ReservaCreate
from app.security.audit import registrar_auditoria
from app.services.redis_cache import invalidate_vagas_cache
from app.services.ws_manager import notificar_vaga_atualizada


class RecursoNaoEncontradoError(Exception):
    """A vaga/reserva referenciada pela operação não existe (ou está inativa)."""


class ConflitoOperacaoError(Exception):
    """A operação viola uma regra de negócio (ex.: vaga já ocupada)."""


class PermissaoNegadaError(Exception):
    """Quem chamou não é dono do recurso (reserva/ocupação) e não é staff — ex.: um
    cliente tentando cancelar a reserva de outro, ou ocupar por cima da reserva alheia
    sem estar fisicamente lá (placa não bate)."""


async def _telefone_por_placa(db: AsyncSession, placa: str) -> str | None:
    """Acha o telefone do dono cadastrado de um veículo pela placa — usado pra confirmar
    ocupação/liberação por WhatsApp sem exigir um campo de telefone na entrada/saída
    (que não tem isso hoje). Sem veículo cadastrado com essa placa, não há pra quem avisar."""
    veiculo = (await db.execute(select(Veiculo).where(Veiculo.placa == placa))).scalar_one_or_none()
    if not veiculo:
        return None
    cliente = await db.get(Cliente, veiculo.cliente_id)
    return cliente.telefone if cliente else None


async def _cliente_do_operador(db: AsyncSession, operador_sub: str) -> Cliente | None:
    """None quando quem chama não tem cadastro de cliente próprio — é como diferenciamos
    staff/operador (EntradaModal, Admin — mantém a prioridade de corrigir o que observou
    fisicamente em qualquer vaga) de um cliente self-service (só pode agir sobre o que é
    seu — impede um cliente "tomar" a vaga/reserva/ocupação de outro cliente, seja pelo
    app ou pelo bot do WhatsApp).

    O bot passa um sub sintético "whatsapp:<telefone>" (não tem Auth0) — sem tratar esse
    caso à parte, ele nunca bateria com Cliente.auth0_sub e todo mundo que usa o bot seria
    tratado como staff sem restrição nenhuma, furando a mesma proteção que existe pro app.
    """
    if operador_sub.startswith("whatsapp:"):
        # Import local: whatsapp.py -> sync.py fecharia um ciclo se importado no topo.
        from app.services.whatsapp import normalizar_telefone

        telefone = normalizar_telefone(operador_sub.removeprefix("whatsapp:"))
        return (await db.execute(select(Cliente).where(Cliente.telefone == telefone))).scalar_one_or_none()

    return (await db.execute(select(Cliente).where(Cliente.auth0_sub == operador_sub))).scalar_one_or_none()


async def aplicar_entrada(db: AsyncSession, payload: EntradaCreate, operador_sub: str) -> Movimentacao:
    # SELECT ... FOR UPDATE (portável entre PostgreSQL e MySQL/InnoDB): trava a linha da
    # vaga até o commit, fechando a janela de corrida entre duas confirmações simultâneas.
    vaga = (
        await db.execute(select(Vaga).where(Vaga.id == payload.vaga_id).with_for_update())
    ).scalar_one_or_none()
    if not vaga or not vaga.ativo:
        raise RecursoNaoEncontradoError("Vaga não encontrada.")
    if vaga.status not in (StatusVaga.livre, StatusVaga.reservada):
        raise ConflitoOperacaoError("Vaga não está disponível para ocupação.")

    reservas_ativas: list[Reserva] = []
    if vaga.status == StatusVaga.reservada:
        reservas_ativas = (
            await db.execute(select(Reserva).where(Reserva.vaga_id == vaga.id, Reserva.status == "ativa"))
        ).scalars().all()

        cliente_atuando = await _cliente_do_operador(db, operador_sub)
        if cliente_atuando:
            # Um cliente self-service só pode ocupar por cima da reserva de OUTRO cliente
            # se a placa bater (confirmando que é o próprio carro reservado chegando) —
            # sem isso, qualquer cliente logado poderia "tomar" pelo app a vaga reservada
            # de outra pessoa, sem estar fisicamente lá. Staff/operador (sem Cliente
            # próprio, ex.: EntradaModal) mantém a prioridade de corrigir o que observou.
            de_outro_sem_confirmar = any(
                reserva.telefone != cliente_atuando.telefone
                and not (reserva.placa and reserva.placa == payload.placa.upper())
                for reserva in reservas_ativas
            )
            if de_outro_sem_confirmar:
                raise PermissaoNegadaError(
                    f"A vaga {vaga.id} está reservada por outro cliente — "
                    "só quem reservou (ou a administração) pode ocupá-la agora."
                )

    agora = datetime.utcnow()

    ocupante = Ocupante(
        vaga_id=vaga.id,
        nome=payload.nome,
        placa=payload.placa.upper(),
        veiculo=payload.veiculo,
        tipo_cliente=payload.tipo_cliente,
        observacoes=payload.observacoes,
        hora_entrada=agora,
        operador_id=operador_sub,
    )
    db.add(ocupante)

    # Prioridade para o físico: uma entrada (ao vivo ou vinda de sync offline atrasado)
    # sempre vence uma reserva ativa. Se a placa bate com a da reserva, é quem reservou
    # chegando — reserva cumprida, silenciosamente. Caso contrário (placa diferente, ou
    # reserva sem placa registrada, ex.: feita via WhatsApp), não dá pra confirmar que é a
    # mesma pessoa: a reserva é cancelada (não "concluída") e o cliente é avisado.
    reservas_sobrepostas: list[Reserva] = []
    for reserva in reservas_ativas:
        if reserva.placa and reserva.placa == payload.placa.upper():
            reserva.status = "concluida"
        else:
            reserva.status = "cancelada"
            reservas_sobrepostas.append(reserva)

    vaga.status = StatusVaga.ocupada

    movimentacao = Movimentacao(
        vaga_id=vaga.id,
        tipo="entrada",
        placa=payload.placa.upper(),
        motorista=payload.nome,
        veiculo=payload.veiculo,
        timestamp=agora,
        operador_id=operador_sub,
    )
    db.add(movimentacao)

    await db.commit()
    await db.refresh(movimentacao)
    await invalidate_vagas_cache()
    await notificar_vaga_atualizada(vaga.id, vaga.status.value)

    # Import local: notificacoes.py -> whatsapp.py -> sync.py fecharia um ciclo se
    # importado no topo do módulo.
    from app.services.notificacoes import notificar_entrada_confirmada, notificar_reserva_sobreposta

    telefone = await _telefone_por_placa(db, payload.placa.upper())
    if telefone:
        await notificar_entrada_confirmada(telefone, vaga.id)

    for reserva in reservas_sobrepostas:
        await notificar_reserva_sobreposta(reserva)
        await registrar_auditoria(db, operador_sub, "reserva_sobreposta_fisicamente", "reserva", str(reserva.id))

    return movimentacao


async def aplicar_saida(db: AsyncSession, vaga_id: str, operador_sub: str) -> Movimentacao:
    vaga = await db.get(Vaga, vaga_id)
    if not vaga:
        raise RecursoNaoEncontradoError("Vaga não encontrada.")
    if vaga.status != StatusVaga.ocupada:
        raise ConflitoOperacaoError("Vaga não está ocupada.")

    ocupante = (
        await db.execute(select(Ocupante).where(Ocupante.vaga_id == vaga.id))
    ).scalar_one_or_none()
    if not ocupante:
        raise ConflitoOperacaoError("Nenhum ocupante registrado para esta vaga.")

    cliente_atuando = await _cliente_do_operador(db, operador_sub)
    if cliente_atuando:
        # Mesma lógica de aplicar_entrada: um cliente self-service só libera o veículo
        # que é dele (confere pela placa); staff/operador sem Cliente próprio continua
        # podendo liberar qualquer vaga (correção manual, Admin).
        veiculo_do_ocupante = (
            await db.execute(
                select(Veiculo).where(Veiculo.placa == ocupante.placa, Veiculo.cliente_id == cliente_atuando.id)
            )
        ).scalar_one_or_none()
        if not veiculo_do_ocupante:
            raise PermissaoNegadaError(
                f"A vaga {vaga_id} está ocupada por outro veículo — "
                "só o dono do veículo (ou a administração) pode liberá-la."
            )

    agora = datetime.utcnow()
    tempo_permanencia_min = int((agora - ocupante.hora_entrada).total_seconds() // 60)

    movimentacao = Movimentacao(
        vaga_id=vaga.id,
        tipo="saida",
        placa=ocupante.placa,
        motorista=ocupante.nome,
        veiculo=ocupante.veiculo,
        timestamp=agora,
        operador_id=operador_sub,
        tempo_permanencia_min=tempo_permanencia_min,
    )
    db.add(movimentacao)

    await db.delete(ocupante)
    vaga.status = StatusVaga.livre

    await db.commit()
    await db.refresh(movimentacao)
    await invalidate_vagas_cache()
    await notificar_vaga_atualizada(vaga.id, vaga.status.value)

    from app.services.notificacoes import notificar_saida_confirmada

    telefone = await _telefone_por_placa(db, movimentacao.placa)
    if telefone:
        await notificar_saida_confirmada(telefone, vaga.id, tempo_permanencia_min)

    return movimentacao


async def aplicar_reserva(db: AsyncSession, payload: ReservaCreate, operador_sub: str) -> Reserva:
    # Mesmo lock de aplicar_entrada — sem isso, duas reservas concorrentes na mesma vaga
    # (ex.: WhatsApp x operador) poderiam ambas passar pela checagem de status antes do commit.
    vaga = (
        await db.execute(select(Vaga).where(Vaga.id == payload.vaga_id).with_for_update())
    ).scalar_one_or_none()
    if not vaga or not vaga.ativo:
        raise RecursoNaoEncontradoError("Vaga não encontrada.")
    if vaga.status != StatusVaga.livre:
        raise ConflitoOperacaoError("Vaga não está livre para reserva.")

    reserva = Reserva(**payload.model_dump(), status="ativa", criado_em=datetime.utcnow())
    db.add(reserva)
    vaga.status = StatusVaga.reservada

    await db.commit()
    await db.refresh(reserva)
    await invalidate_vagas_cache()
    await notificar_vaga_atualizada(vaga.id, vaga.status.value)
    return reserva


async def aplicar_cancelamento(db: AsyncSession, reserva_id: int, operador_sub: str) -> Reserva:
    reserva = await db.get(Reserva, reserva_id)
    if not reserva:
        raise RecursoNaoEncontradoError("Reserva não encontrada.")
    if reserva.status != "ativa":
        raise ConflitoOperacaoError("Reserva não está ativa.")

    cliente_atuando = await _cliente_do_operador(db, operador_sub)
    if cliente_atuando and reserva.telefone != cliente_atuando.telefone:
        raise PermissaoNegadaError(
            "Essa reserva não é sua — só quem reservou (ou a administração) pode cancelar."
        )

    reserva.status = "cancelada"

    vaga = await db.get(Vaga, reserva.vaga_id)
    if vaga and vaga.status == StatusVaga.reservada:
        outras_ativas = (
            await db.execute(
                select(Reserva).where(
                    Reserva.vaga_id == vaga.id, Reserva.status == "ativa", Reserva.id != reserva.id
                )
            )
        ).scalars().all()
        if not outras_ativas:
            vaga.status = StatusVaga.livre

    await db.commit()
    await db.refresh(reserva)
    await invalidate_vagas_cache()
    if vaga:
        await notificar_vaga_atualizada(vaga.id, vaga.status.value)
    return reserva


async def expirar_reservas_vencidas(db: AsyncSession) -> list[Reserva]:
    """Marca como 'expirada' toda reserva ativa cujo horário de fim já passou, liberando a vaga
    de volta para 'livre' quando não há outra reserva ativa para ela. Pensado para ser chamado
    periodicamente por uma tarefa agendada (ex.: Railway Cron).
    """
    agora = datetime.utcnow()
    vencidas = (
        await db.execute(
            select(Reserva)
            .where(Reserva.status == "ativa", Reserva.fim < agora)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()

    if not vencidas:
        return []

    vagas_liberadas: list[Vaga] = []
    for reserva in vencidas:
        reserva.status = "expirada"
        vaga = await db.get(Vaga, reserva.vaga_id)
        if vaga and vaga.status == StatusVaga.reservada:
            outras_ativas = (
                await db.execute(
                    select(Reserva).where(
                        Reserva.vaga_id == vaga.id, Reserva.status == "ativa", Reserva.id != reserva.id
                    )
                )
            ).scalars().all()
            if not outras_ativas:
                vaga.status = StatusVaga.livre
                vagas_liberadas.append(vaga)

    await db.commit()
    for reserva in vencidas:
        await db.refresh(reserva)

    if vagas_liberadas:
        await invalidate_vagas_cache()
        for vaga in vagas_liberadas:
            await notificar_vaga_atualizada(vaga.id, vaga.status.value)

    return list(vencidas)


async def lembrar_reservas_proximas_do_vencimento(db: AsyncSession, janela_minutos: int = 10) -> list[Reserva]:
    """Reservas ativas cujo fim está dentro da janela e ainda não receberam lembrete.
    Marca lembrete_enviado=True para não repetir — pensado para ser chamado com mais
    frequência que expirar_reservas_vencidas (ex.: a cada 5 min, via Railway Cron).
    """
    agora = datetime.utcnow()
    limite = agora + timedelta(minutes=janela_minutos)

    proximas = (
        await db.execute(
            select(Reserva)
            .where(
                Reserva.status == "ativa",
                Reserva.fim > agora,
                Reserva.fim <= limite,
                Reserva.lembrete_enviado.is_(False),
            )
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()

    if not proximas:
        return []

    for reserva in proximas:
        reserva.lembrete_enviado = True

    await db.commit()
    for reserva in proximas:
        await db.refresh(reserva)

    return list(proximas)

async def reset_diario(db: AsyncSession) -> int:
    """Força todas as vagas reservadas/ocupadas para livre e expira as reservas,
    ideal para rodar na madrugada garantindo um estado limpo para o dia seguinte."""
    agora = datetime.utcnow()
    
    # 1. Expira todas as reservas ativas
    ativas = (
        await db.execute(select(Reserva).where(Reserva.status == "ativa"))
    ).scalars().all()
    
    for reserva in ativas:
        reserva.status = "expirada"
        reserva.fim = agora
        
    # 2. Força todas as vagas (que não sejam manutenção) para livre
    vagas = (
        await db.execute(select(Vaga).where(Vaga.status.in_([StatusVaga.reservada, StatusVaga.ocupada])))
    ).scalars().all()
    
    for vaga in vagas:
        vaga.status = StatusVaga.livre
        
    # 3. Limpa ocupantes
    ocupantes = (await db.execute(select(Ocupante))).scalars().all()
    for ocupante in ocupantes:
        await db.delete(ocupante)

    await db.commit()
    await invalidate_vagas_cache()
    
    return len(vagas)
