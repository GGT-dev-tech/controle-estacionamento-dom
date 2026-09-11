from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movimentacao import Movimentacao
from app.models.ocupante import Ocupante
from app.models.reserva import Reserva
from app.models.vaga import StatusVaga, Vaga
from app.schemas.movimentacao import EntradaCreate
from app.schemas.reserva import ReservaCreate
from app.security.audit import registrar_auditoria
from app.services.redis_cache import invalidate_vagas_cache
from app.services.ws_manager import notificar_vaga_atualizada


class RecursoNaoEncontradoError(Exception):
    """A vaga/reserva referenciada pela operação não existe (ou está inativa)."""


class ConflitoOperacaoError(Exception):
    """A operação viola uma regra de negócio (ex.: vaga já ocupada)."""


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
    if vaga.status == StatusVaga.reservada:
        reservas_ativas = (
            await db.execute(select(Reserva).where(Reserva.vaga_id == vaga.id, Reserva.status == "ativa"))
        ).scalars().all()
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

    for reserva in reservas_sobrepostas:
        # Import local: notificacoes.py -> whatsapp.py -> sync.py fecharia um ciclo se
        # importado no topo do módulo.
        from app.services.notificacoes import notificar_reserva_sobreposta

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
        await db.execute(select(Reserva).where(Reserva.status == "ativa", Reserva.fim < agora))
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
            select(Reserva).where(
                Reserva.status == "ativa",
                Reserva.fim > agora,
                Reserva.fim <= limite,
                Reserva.lembrete_enviado.is_(False),
            )
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
