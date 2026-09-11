import asyncio
import logging
import re
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.cliente import Cliente
from app.models.ocupante import Ocupante, TipoCliente
from app.models.reserva import Reserva
from app.models.vaga import StatusVaga, Vaga
from app.models.veiculo import Veiculo
from app.schemas.movimentacao import EntradaCreate
from app.schemas.reserva import ReservaCreate
from app.services.sync import (
    ConflitoOperacaoError,
    PermissaoNegadaError,
    RecursoNaoEncontradoError,
    aplicar_cancelamento,
    aplicar_entrada,
    aplicar_reserva,
)
from app.services.whatsapp_estado import definir_estado, limpar_estado, obter_estado

logger = logging.getLogger(__name__)

RESERVA_DURACAO_PADRAO = timedelta(hours=2)
_MAX_TENTATIVAS_ENVIO = 3
_ESPERA_ANTES_DE_TENTAR_DE_NOVO_SEGUNDOS = 3.0


def normalizar_telefone(bruto: str) -> str:
    """Normaliza para dígitos com DDD, sem código do país (ex.: '11999998888').

    Aceita o remoteJid cru da Evolution API (ex.: '5511999998888@s.whatsapp.net'),
    o telefone já sem o sufixo, ou um número digitado manualmente (com +, espaços,
    hífens etc.). Usado tanto para gravar `Cliente.telefone` quanto para consultar.
    """
    apenas_digitos = "".join(c for c in bruto.split("@")[0] if c.isdigit())
    if apenas_digitos.startswith("55") and len(apenas_digitos) in (12, 13):
        apenas_digitos = apenas_digitos[2:]

    if len(apenas_digitos) == 10:
        # Celular brasileiro sem o "nono dígito" — o WhatsApp às vezes referencia o
        # número no formato antigo de 8 dígitos (DDD + 8), mesmo quando a pessoa manda
        # mensagem normalmente. O cadastro sempre grava com o nono dígito (DDD + 9 dígitos,
        # 11 no total, como digitado no formulário) — sem essa normalização, a busca por
        # Cliente.telefone nunca bate e um cliente cadastrado é tratado como desconhecido.
        apenas_digitos = apenas_digitos[:2] + "9" + apenas_digitos[2:]

    return apenas_digitos


async def enviar_mensagem(telefone: str, texto: str) -> bool:
    """telefone: aceita tanto o formato sem código do país (ex.: '11999998888', como vem
    do cadastro/reserva) quanto o remoteJid cru do webhook (ex.: '5511999998888', com país
    e às vezes sem o nono dígito) — normaliza aqui, na borda de saída, antes de montar o
    JID de destino. Sem isso, chamadas vindas do fluxo do bot (que carregam o telefone cru
    do webhook adiante) duplicavam o "55" (`5555...`), gerando um número inválido e a
    mensagem nunca saía — mesmo com o resto do fluxo funcionando perfeitamente.

    Tenta até 3 vezes antes de desistir, com espera crescente entre elas: confirmado em
    produção que o WhatsApp/Evolution API rejeita (400) envios mesmo pra números válidos e
    ativos quando há atividade simultânea (rate limiting) — e que 2 tentativas com 3s fixos
    às vezes não é o bastante se a janela de limite ainda não abriu.
    """
    if not settings.evolution_api_url:
        logger.warning("Evolution API não configurada — mensagem não enviada.")
        return False

    numero = normalizar_telefone(telefone)
    url = f"{settings.evolution_api_url}/message/sendText/{settings.evolution_instance_name}"
    payload = {"number": f"55{numero}@s.whatsapp.net", "text": texto}
    headers = {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}

    for tentativa in range(1, _MAX_TENTATIVAS_ENVIO + 1):
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                return True
            except Exception:
                if tentativa < _MAX_TENTATIVAS_ENVIO:
                    espera = _ESPERA_ANTES_DE_TENTAR_DE_NOVO_SEGUNDOS * tentativa
                    logger.warning(
                        "Falha ao enviar mensagem WhatsApp (tentativa %d/%d) — tentando de novo em %.0fs.",
                        tentativa,
                        _MAX_TENTATIVAS_ENVIO,
                        espera,
                    )
                    await asyncio.sleep(espera)
                else:
                    logger.exception(
                        "Falha ao enviar mensagem WhatsApp (após %d tentativas)", _MAX_TENTATIVAS_ENVIO
                    )
    return False


async def processar_mensagem(telefone: str, mensagem: str, db: AsyncSession) -> str:
    """Entrypoint único do bot: primeiro checa se há uma conversa em andamento (Redis);
    senão, tenta iniciar o fluxo de reserva por texto livre; senão, cai nos /comandos de hoje.
    """
    estado = await obter_estado(telefone)
    if estado:
        # Um comando "/" a qualquer momento sai do fluxo atual e começa do zero — sem
        # isso, um erro no meio de uma conversa (ex.: número fora do intervalo) deixava o
        # cliente sem saída: tudo que ele mandasse dali pra frente era interpretado como
        # parte do fluxo antigo (inclusive "/ajuda"), nunca como um comando de verdade.
        if mensagem.strip().startswith("/"):
            await limpar_estado(telefone)
            return await processar_comando(telefone, mensagem, db)

        step = estado.get("step")
        if step == "escolhendo_vaga":
            return await _apos_escolher_vaga_numerada(telefone, mensagem, estado, db)
        if step == "escolhendo_veiculo":
            return await _apos_escolher_veiculo(telefone, mensagem.strip(), estado, db)
        if step == "escolhendo_tempo":
            return await _apos_escolher_tempo(telefone, mensagem.strip(), estado, db)
        if step == "confirmando_reserva":
            return await _confirmar_extensao_reserva(telefone, mensagem.strip().lower(), estado.get("reserva_id"), db)
        await limpar_estado(telefone)  # estado desconhecido/corrompido — não trava o usuário

    msg = mensagem.strip().lower()
    if not msg.startswith("/"):
        if "reservar" in msg:
            return await _iniciar_fluxo_vaga(telefone, db, "reservar")
        if "ocupar" in msg:
            return await _iniciar_fluxo_vaga(telefone, db, "ocupar")

    return await processar_comando(telefone, mensagem, db)


async def _reserva_ativa_do_telefone(telefone: str, db: AsyncSession) -> Reserva | None:
    telefone_norm = normalizar_telefone(telefone)
    return (
        await db.execute(select(Reserva).where(Reserva.telefone == telefone_norm, Reserva.status == "ativa"))
    ).scalars().first()


def _texto_lista_vagas(vaga_ids: list[str], acao: str) -> str:
    verbo = "reservar" if acao == "reservar" else "ocupar"
    linhas = [f"🅿️ *Vagas disponíveis* — responda só com o *número* da vaga que quer {verbo}:", ""]
    linhas += [f"{i}. {vaga_id}" for i, vaga_id in enumerate(vaga_ids, start=1)]
    return "\n".join(linhas)


async def _atualizar_lista_de_vagas(telefone: str, db: AsyncSession, acao: str) -> list[str]:
    """Busca as vagas livres agora (não a lista antiga guardada no estado) e regrava o
    estado com os índices atualizados. Chamado toda vez que mostramos a lista de novo —
    inclusive num retry — porque, com duas pessoas no fluxo ao mesmo tempo, a vaga que
    era a opção 3 pode já ter sido ocupada/reservada por outra enquanto uma delas decidia;
    mostrar a lista antiga deixaria o número "certo" apontando pra algo que não existe mais.
    """
    vagas = (
        await db.execute(
            select(Vaga)
            .where(Vaga.ativo.is_(True), Vaga.status == StatusVaga.livre)
            .order_by(Vaga.andar, Vaga.numero)
        )
    ).scalars().all()
    vaga_ids = [vaga.id for vaga in vagas]
    await definir_estado(telefone, {"step": "escolhendo_vaga", "vagas": vaga_ids, "acao": acao})
    return vaga_ids


async def _iniciar_fluxo_vaga(telefone: str, db: AsyncSession, acao: str) -> str:
    """acao: "reservar" ou "ocupar" — mesma lista numerada de vagas livres nos dois casos,
    só muda o que acontece depois de escolher (pergunta o tempo, ou ocupa direto).

    Pra "ocupar": se já existe uma reserva ativa em nome do cliente, confirma a chegada
    nela direto (é a mesma coisa que "confirmar chegada" no app) — nem precisa escolher
    vaga, já que ele só tem uma reservada.
    """
    if acao == "ocupar":
        reserva_propria = await _reserva_ativa_do_telefone(telefone, db)
        if reserva_propria:
            _cliente, veiculos = await _veiculos_do_cliente(telefone, db)
            placa = reserva_propria.placa or (veiculos[0].placa if len(veiculos) == 1 else None)
            if placa:
                return await _ocupar_vaga(reserva_propria.vaga_id, telefone, db, placa_escolhida=placa)
            return (
                f"Você tem uma reserva ativa na vaga {reserva_propria.vaga_id}. Envie "
                f"*/ocupar {reserva_propria.vaga_id}* para confirmar a chegada."
            )

    vaga_ids = await _atualizar_lista_de_vagas(telefone, db, acao)
    if not vaga_ids:
        await limpar_estado(telefone)
        return "😕 Não há vagas livres no momento. Tente novamente mais tarde."

    return _texto_lista_vagas(vaga_ids, acao)


async def _apos_escolher_vaga_numerada(telefone: str, texto: str, estado: dict, db: AsyncSession) -> str:
    """A lista de _iniciar_fluxo_vaga é numerada — aceita o número da opção (o caminho
    principal, bem mais rápido de digitar que o código da vaga) ou o código da vaga direto
    (pra quem já sabe de cor), sem precisar reiniciar a conversa se digitar do outro jeito.
    """
    texto = texto.strip()
    vagas_listadas: list[str] = estado.get("vagas", [])
    acao = estado.get("acao", "reservar")

    if not vagas_listadas:
        await limpar_estado(telefone)
        return "❌ Essa lista expirou. Envie *reservar* ou *ocupar* para ver as vagas disponíveis de novo."

    if texto.isdigit():
        indice = int(texto)
        if not (1 <= indice <= len(vagas_listadas)):
            # A lista pode ter mudado desde que foi mostrada (outra pessoa ocupou/reservou
            # enquanto esse cliente decidia) — reenvia atualizada em vez de só reclamar do número.
            vaga_ids = await _atualizar_lista_de_vagas(telefone, db, acao)
            if not vaga_ids:
                await limpar_estado(telefone)
                return "😕 Não há mais vagas livres no momento. Tente novamente mais tarde."
            return "❌ Número inválido. A lista pode ter mudado — aqui está atualizada:\n\n" + _texto_lista_vagas(
                vaga_ids, acao
            )
        vaga_id = vagas_listadas[indice - 1]
    else:
        vaga_id = texto.upper()

    return await _apos_escolher_vaga(telefone, vaga_id, db, acao)


async def _veiculos_do_cliente(telefone: str, db: AsyncSession) -> tuple[Cliente | None, list[Veiculo]]:
    cliente = (
        await db.execute(select(Cliente).where(Cliente.telefone == normalizar_telefone(telefone)))
    ).scalar_one_or_none()
    if not cliente:
        return None, []
    veiculos = (
        await db.execute(select(Veiculo).where(Veiculo.cliente_id == cliente.id).order_by(Veiculo.criado_em))
    ).scalars().all()
    return cliente, list(veiculos)


async def _apos_escolher_vaga(telefone: str, vaga_id: str, db: AsyncSession, acao: str = "reservar") -> str:
    """Depois que o cliente escolheu a vaga: se tiver mais de um veículo cadastrado,
    pergunta qual antes de confirmar; senão, segue direto (0 ou 1 veículo) — pra "ocupar"
    é sempre preciso ter pelo menos um veículo com placa (é o que identifica o carro
    fisicamente na vaga); "reservar" sem veículo cadastrado ainda funciona (sem placa).

    Só confere aqui se a vaga existe — sem isso, uma vaga inexistente só seria percebida
    depois de escolher a duração, um vai-e-vem sem necessidade. Se ela existe mas já não
    está livre, não intercepta: o conflito real (concorrência) só é resolvido com segurança
    mais à frente, em aplicar_reserva/aplicar_entrada (SELECT FOR UPDATE) — uma leitura sem
    lock aqui só serviria pra mostrar uma mensagem antecipada, potencialmente já desatualizada.
    """
    vaga = await db.get(Vaga, vaga_id)
    if not vaga or not vaga.ativo:
        await limpar_estado(telefone)
        return f"❌ Vaga {vaga_id} não encontrada."

    _cliente, veiculos = await _veiculos_do_cliente(telefone, db)

    if acao == "ocupar" and not veiculos:
        await limpar_estado(telefone)
        return "❌ Você ainda não tem um veículo cadastrado — adicione um em Meu Cadastro no app antes de ocupar por aqui."

    if len(veiculos) > 1:
        await definir_estado(telefone, {"step": "escolhendo_veiculo", "vaga_id": vaga_id, "acao": acao})
        linhas = [f"🚗 Você tem {len(veiculos)} veículos cadastrados — qual vai usar na vaga {vaga_id}?", ""]
        linhas += [f"• {v.placa} — {v.veiculo}" for v in veiculos]
        return "\n".join(linhas)

    placa_auto = veiculos[0].placa if len(veiculos) == 1 else None
    if acao == "ocupar":
        if not placa_auto:
            await limpar_estado(telefone)
            return "❌ Seu veículo não tem placa cadastrada — adicione uma em Meu Cadastro antes de ocupar por aqui."
        await limpar_estado(telefone)
        return await _ocupar_vaga(vaga_id, telefone, db, placa_escolhida=placa_auto)

    return await _perguntar_tempo(telefone, vaga_id, placa_auto, db)


async def _apos_escolher_veiculo(telefone: str, texto: str, estado: dict, db: AsyncSession) -> str:
    vaga_id = estado.get("vaga_id", "")
    acao = estado.get("acao", "reservar")
    if not vaga_id:
        await limpar_estado(telefone)
        return "❌ Algo deu errado. Envie *reservar* ou *ocupar* para começar de novo."

    _cliente, veiculos = await _veiculos_do_cliente(telefone, db)
    placa_digitada = "".join(c for c in texto.upper() if c.isalnum())
    escolhido = next((v for v in veiculos if v.placa == placa_digitada), None)
    if not escolhido:
        return (
            "❌ Não reconheci essa placa entre seus veículos cadastrados. Envie a placa "
            "exatamente como está cadastrada (ou */ajuda* para recomeçar)."
        )

    if acao == "ocupar":
        if not escolhido.placa:
            await limpar_estado(telefone)
            return "❌ Esse veículo não tem placa cadastrada — adicione uma em Meu Cadastro antes de ocupar por aqui."
        await limpar_estado(telefone)
        return await _ocupar_vaga(vaga_id, telefone, db, placa_escolhida=escolhido.placa)

    return await _perguntar_tempo(telefone, vaga_id, escolhido.placa, db)


async def _perguntar_tempo(telefone: str, vaga_id: str, placa: str | None, db: AsyncSession) -> str:
    await definir_estado(telefone, {"step": "escolhendo_tempo", "vaga_id": vaga_id, "placa": placa})
    return (
        f"⏱ Quase lá! Por quanto tempo deseja reservar a vaga {vaga_id}?\n\n"
        "Responda com o número da opção:\n"
        "1️⃣ - 15 minutos\n"
        "2️⃣ - 30 minutos\n"
        "3️⃣ - 1 hora\n"
        "4️⃣ - 2 horas"
    )

async def _apos_escolher_tempo(telefone: str, texto: str, estado: dict, db: AsyncSession) -> str:
    vaga_id = estado.get("vaga_id")
    placa = estado.get("placa")
    if not vaga_id:
        await limpar_estado(telefone)
        return "❌ Algo deu errado com sua reserva. Envie *reservar* para começar de novo."

    txt = texto.lower().strip()
    duracao = None

    # Strict matching for options 1, 2, 3, 4 to avoid conflict with "1 hora" or "2 horas"
    if txt == "1" or re.fullmatch(r"15\s*m(?:in(?:uto(?:s)?)?)?", txt):
        duracao = timedelta(minutes=15)
    elif txt == "2" or re.fullmatch(r"30\s*m(?:in(?:uto(?:s)?)?)?", txt):
        duracao = timedelta(minutes=30)
    elif txt == "3" or re.fullmatch(r"1\s*h(?:ora(?:s)?)?", txt):
        duracao = timedelta(hours=1)
    elif txt == "4" or re.fullmatch(r"2\s*h(?:ora(?:s)?)?", txt):
        duracao = timedelta(hours=2)
    else:
        return (
            "❌ Opção inválida. Responda com 1, 2, 3 ou 4 correspondente ao tempo desejado "
            "(ou */ajuda* para recomeçar)."
        )

    await limpar_estado(telefone)
    return await _reservar_vaga(vaga_id, telefone, db, placa_escolhida=placa, duracao=duracao)

async def _dados_reserva_do_cliente(telefone: str, db: AsyncSession) -> tuple[str, str | None, str | None]:
    """(nome, placa, email) a partir do cadastro (Cliente + Veiculo) pra preencher a
    reserva sozinho. Sem cadastro, ou com 2+ veículos ainda sem escolha, cai no
    comportamento antigo (nome genérico, sem placa) — quem chama decide se pergunta antes."""
    cliente, veiculos = await _veiculos_do_cliente(telefone, db)
    if not cliente:
        return f"WhatsApp {telefone}", None, None
    placa_auto = veiculos[0].placa if len(veiculos) == 1 else None
    return cliente.nome, placa_auto, cliente.email


def _argumento(mensagem: str) -> str:
    """Tudo depois do comando (ex.: "/r s2-49" -> "s2-49"; "/r" sozinho -> "")."""
    partes = mensagem.strip().split(maxsplit=1)
    return partes[1].strip() if len(partes) > 1 else ""


async def processar_comando(telefone: str, mensagem: str, db: AsyncSession) -> str:
    msg = mensagem.strip().lower()
    comando = msg.split(maxsplit=1)[0] if msg else ""
    argumento = _argumento(mensagem)

    # Atalhos curtos (/r, /v, /c, /s, /a) ao lado dos nomes completos — digitar o comando
    # inteiro toda vez (ex.: "/reservar") é mais atrito do que precisa pra quem já conhece o bot.
    if comando in ("/vagas", "/v"):
        andar = "S2" if "s2" in msg else ("G2" if "g2" in msg else None)
        return await _listar_vagas(andar, db)
    if comando in ("/reservar", "/r"):
        if argumento:
            return await _apos_escolher_vaga(telefone, argumento.upper(), db, "reservar")
        return await _iniciar_fluxo_vaga(telefone, db, "reservar")
    if comando in ("/ocupar", "/o"):
        if argumento:
            return await _apos_escolher_vaga(telefone, argumento.upper(), db, "ocupar")
        return await _iniciar_fluxo_vaga(telefone, db, "ocupar")
    if comando in ("/cancelar", "/c") and argumento:
        return await _cancelar_reserva(argumento.upper(), telefone, db)
    if comando in ("/status", "/s") and argumento:
        return await _status_placa(argumento.upper(), db)
    if comando in ("/ajuda", "/a", "/menu"):
        return _ajuda()
    return "❓ Comando não reconhecido. Envie */ajuda* para ver os comandos."


_EMOJI_STATUS = {"livre": "🟢", "ocupada": "🔴", "reservada": "🟡", "manutencao": "⚫"}


async def _listar_vagas(andar: str | None, db: AsyncSession) -> str:
    query = select(Vaga).where(Vaga.ativo.is_(True))
    if andar:
        query = query.where(Vaga.andar == andar)
    vagas = (await db.execute(query.order_by(Vaga.andar, Vaga.numero))).scalars().all()

    if not vagas:
        return "Nenhuma vaga cadastrada."

    linhas = [f"🅿️ *Vagas{f' — {andar}' if andar else ''}*", ""]
    for vaga in vagas:
        linhas.append(f"{_EMOJI_STATUS.get(vaga.status.value, '•')} {vaga.id} — {vaga.status.value}")
    return "\n".join(linhas)


async def _reservar_vaga(
    vaga_id: str, telefone: str, db: AsyncSession, placa_escolhida: str | None = None, duracao: timedelta | None = None
) -> str:
    inicio = datetime.utcnow()
    fim = inicio + (duracao if duracao else RESERVA_DURACAO_PADRAO)
    nome, placa_auto, email = await _dados_reserva_do_cliente(telefone, db)
    payload = ReservaCreate(
        vaga_id=vaga_id,
        nome=nome,
        # Normalizado (sem código do país) — mesmo formato que uma reserva feita pelo app
        # grava (Cliente.telefone). Sem isso, Reserva.telefone ficava no formato bruto do
        # webhook só pras reservas feitas pelo bot, e qualquer busca por telefone (ex.:
        # achar a reserva ativa do cliente pra "/ocupar" sem argumento) não encontrava.
        telefone=normalizar_telefone(telefone),
        email=email,
        placa=placa_escolhida or placa_auto,
        inicio=inicio,
        fim=fim,
        canal="whatsapp",
    )
    try:
        await aplicar_reserva(db, payload, f"whatsapp:{telefone}")
    except RecursoNaoEncontradoError:
        return f"❌ Vaga {vaga_id} não encontrada."
    except ConflitoOperacaoError:
        # Concorrência real: outra pessoa reservou essa vaga entre a listagem e a
        # confirmação — mostra a lista atualizada em vez de deixar o cliente sem saída.
        vaga_ids = await _atualizar_lista_de_vagas(telefone, db, "reservar")
        if not vaga_ids:
            await limpar_estado(telefone)
            return "😕 Essa vaga acabou de ser reservada por outra pessoa, e não há mais vagas livres agora."
        return (
            "😕 Essa vaga acabou de ser reservada por outra pessoa. Aqui está a lista atualizada:\n\n"
            + _texto_lista_vagas(vaga_ids, "reservar")
        )
    return f"✅ Vaga {vaga_id} reservada até {fim:%H:%M}. Envie */cancelar {vaga_id}* para desistir."


async def _ocupar_vaga(vaga_id: str, telefone: str, db: AsyncSession, placa_escolhida: str) -> str:
    """Ocupa direto (sem passar por reserva) — usada tanto por "ocupar uma vaga livre"
    quanto por "confirmar chegada" numa vaga já reservada em nome do próprio cliente (o
    placa_escolhida batendo com a reserva já resolve isso do lado de aplicar_entrada, que
    dá prioridade ao físico e conclui a reserva silenciosamente quando a placa bate)."""
    cliente, veiculos = await _veiculos_do_cliente(telefone, db)
    nome = cliente.nome if cliente else f"WhatsApp {telefone}"
    tipo_cliente = cliente.tipo_cliente if cliente else TipoCliente.visitante
    veiculo_escolhido = next((v for v in veiculos if v.placa == placa_escolhida), None)
    nome_veiculo = veiculo_escolhido.veiculo if veiculo_escolhido else "Veículo"

    payload = EntradaCreate(
        vaga_id=vaga_id,
        nome=nome,
        placa=placa_escolhida,
        veiculo=nome_veiculo,
        tipo_cliente=tipo_cliente,
    )
    try:
        await aplicar_entrada(db, payload, f"whatsapp:{telefone}")
    except RecursoNaoEncontradoError:
        return f"❌ Vaga {vaga_id} não encontrada."
    except (ConflitoOperacaoError, PermissaoNegadaError) as e:
        # Concorrência real: outra pessoa ocupou/reservou essa vaga entre a listagem e a
        # confirmação (ou ela é de outro cliente) — mostra a lista atualizada em vez de
        # deixar o cliente sem saída.
        vaga_ids = await _atualizar_lista_de_vagas(telefone, db, "ocupar")
        if not vaga_ids:
            await limpar_estado(telefone)
            return f"❌ {e}"
        return f"❌ {e}\n\nAqui está a lista atualizada:\n\n" + _texto_lista_vagas(vaga_ids, "ocupar")
    return f"✅ Vaga {vaga_id} ocupada. Envie */ajuda* para ver os outros comandos."


_RESPOSTAS_AFIRMATIVAS = {"sim", "s", "confirmo", "confirmar", "yes"}


async def _confirmar_extensao_reserva(
    telefone: str, texto: str, reserva_id: int | None, db: AsyncSession
) -> str:
    """Resposta ao lembrete de vencimento (notificar_reserva_proxima_do_vencimento). Uma
    resposta afirmativa estende o prazo pelo mesmo intervalo original e permite um novo
    lembrete mais à frente; qualquer outra resposta só confirma que, sem chegar, a
    expiração automática (expirar_reservas_vencidas) segue seu curso normalmente."""
    await limpar_estado(telefone)
    if not reserva_id:
        return "Ok."

    reserva = await db.get(Reserva, reserva_id)
    if not reserva or reserva.status != "ativa":
        return "Essa reserva não está mais ativa."

    if texto in _RESPOSTAS_AFIRMATIVAS:
        duracao_original = reserva.fim - reserva.inicio
        reserva.fim = reserva.fim + duracao_original
        reserva.lembrete_enviado = False
        await db.commit()
        return f"✅ Reserva da vaga {reserva.vaga_id} estendida até {reserva.fim:%H:%M}."

    return "Tudo bem — se não chegar até o horário combinado, a vaga é liberada automaticamente."


async def _cancelar_reserva(vaga_id: str, telefone: str, db: AsyncSession) -> str:
    reserva = (
        await db.execute(
            select(Reserva).where(
                Reserva.vaga_id == vaga_id,
                Reserva.status == "ativa",
                Reserva.telefone == normalizar_telefone(telefone),
            )
        )
    ).scalar_one_or_none()
    if not reserva:
        return f"❌ Nenhuma reserva ativa sua encontrada para a vaga {vaga_id}."
    try:
        await aplicar_cancelamento(db, reserva.id, f"whatsapp:{telefone}")
    except (RecursoNaoEncontradoError, ConflitoOperacaoError, PermissaoNegadaError) as e:
        return f"❌ {e}"
    return f"✅ Reserva da vaga {vaga_id} cancelada."


async def _status_placa(placa: str, db: AsyncSession) -> str:
    ocupante = (await db.execute(select(Ocupante).where(Ocupante.placa == placa))).scalar_one_or_none()
    if not ocupante:
        return f"🔎 Nenhum veículo com placa {placa} está estacionado no momento."
    return f"🚗 {placa} está na vaga {ocupante.vaga_id} desde {ocupante.hora_entrada:%H:%M}."


def _ajuda() -> str:
    return (
        "🅿️ *Dom Estacionamento — Comandos*\n\n"
        "*/vagas* (ou */v*) — Ver vagas disponíveis\n"
        "*/vagas S2* — Vagas do Subsolo 2\n"
        "*/vagas G2* — Vagas da Garagem 2\n"
        "*/reservar* (ou */r*) — lista as vagas livres numeradas, responda só com o número\n"
        "*/reservar S2-49* — Reservar direto pelo código (escolhe o tempo em seguida)\n"
        "*/ocupar* (ou */o*) — ocupa uma vaga livre agora, ou confirma a chegada se você já "
        "tem uma reserva ativa\n"
        "*/ocupar S2-49* — Ocupar direto pelo código\n"
        "*/cancelar S2-49* (ou */c S2-49*) — Cancelar sua reserva\n"
        "*/status ABC1234* (ou */s ABC1234*) — Verificar placa\n\n"
        "_Dom Pagamentos • Estacionamento_"
    )
