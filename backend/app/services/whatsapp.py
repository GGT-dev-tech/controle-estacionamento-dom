import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.cliente import Cliente
from app.models.ocupante import Ocupante
from app.models.reserva import Reserva
from app.models.vaga import StatusVaga, Vaga
from app.models.veiculo import Veiculo
from app.schemas.reserva import ReservaCreate
from app.services.sync import ConflitoOperacaoError, RecursoNaoEncontradoError, aplicar_cancelamento, aplicar_reserva
from app.services.whatsapp_estado import definir_estado, limpar_estado, obter_estado

logger = logging.getLogger(__name__)

RESERVA_DURACAO_PADRAO = timedelta(hours=2)


def normalizar_telefone(bruto: str) -> str:
    """Normaliza para dígitos com DDD, sem código do país (ex.: '11999998888').

    Aceita o remoteJid cru da Evolution API (ex.: '5511999998888@s.whatsapp.net'),
    o telefone já sem o sufixo, ou um número digitado manualmente (com +, espaços,
    hífens etc.). Usado tanto para gravar `Cliente.telefone` quanto para consultar.
    """
    apenas_digitos = "".join(c for c in bruto.split("@")[0] if c.isdigit())
    if apenas_digitos.startswith("55") and len(apenas_digitos) in (12, 13):
        return apenas_digitos[2:]
    return apenas_digitos


async def enviar_mensagem(telefone: str, texto: str) -> bool:
    """telefone: apenas dígitos com DDD, ex: '11999998888'."""
    if not settings.evolution_api_url:
        logger.warning("Evolution API não configurada — mensagem não enviada.")
        return False

    url = f"{settings.evolution_api_url}/message/sendText/{settings.evolution_instance_name}"
    payload = {"number": f"55{telefone}@s.whatsapp.net", "text": texto}
    headers = {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return True
        except Exception:
            logger.exception("Falha ao enviar mensagem WhatsApp")
            return False


async def processar_mensagem(telefone: str, mensagem: str, db: AsyncSession) -> str:
    """Entrypoint único do bot: primeiro checa se há uma conversa em andamento (Redis);
    senão, tenta iniciar o fluxo de reserva por texto livre; senão, cai nos /comandos de hoje.
    """
    estado = await obter_estado(telefone)
    if estado:
        step = estado.get("step")
        if step == "escolhendo_vaga":
            return await _apos_escolher_vaga(telefone, mensagem.strip().upper(), db)
        if step == "escolhendo_veiculo":
            return await _apos_escolher_veiculo(telefone, mensagem.strip(), estado.get("vaga_id", ""), db)
        await limpar_estado(telefone)  # estado desconhecido/corrompido — não trava o usuário

    msg = mensagem.strip().lower()
    if not msg.startswith("/") and "reservar" in msg:
        return await _iniciar_fluxo_reserva(telefone, db)

    return await processar_comando(telefone, mensagem, db)


async def _iniciar_fluxo_reserva(telefone: str, db: AsyncSession) -> str:
    vagas = (
        await db.execute(
            select(Vaga)
            .where(Vaga.ativo.is_(True), Vaga.status == StatusVaga.livre)
            .order_by(Vaga.andar, Vaga.numero)
        )
    ).scalars().all()

    if not vagas:
        return "😕 Não há vagas livres no momento. Tente novamente mais tarde."

    await definir_estado(telefone, {"step": "escolhendo_vaga"})

    linhas = ["🅿️ *Vagas disponíveis* — responda com o código da vaga que deseja reservar:", ""]
    linhas += [f"🟢 {vaga.id}" for vaga in vagas]
    return "\n".join(linhas)


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


async def _apos_escolher_vaga(telefone: str, vaga_id: str, db: AsyncSession) -> str:
    """Depois que o cliente escolheu a vaga: se tiver mais de um veículo cadastrado,
    pergunta qual antes de confirmar; senão, reserva direto (0 ou 1 veículo)."""
    _cliente, veiculos = await _veiculos_do_cliente(telefone, db)

    if len(veiculos) > 1:
        await definir_estado(telefone, {"step": "escolhendo_veiculo", "vaga_id": vaga_id})
        linhas = [f"🚗 Você tem {len(veiculos)} veículos cadastrados — qual vai usar na vaga {vaga_id}?", ""]
        linhas += [f"• {v.placa} — {v.veiculo}" for v in veiculos]
        return "\n".join(linhas)

    await limpar_estado(telefone)
    return await _reservar_vaga(vaga_id, telefone, db)


async def _apos_escolher_veiculo(telefone: str, texto: str, vaga_id: str, db: AsyncSession) -> str:
    if not vaga_id:
        await limpar_estado(telefone)
        return "❌ Algo deu errado com sua reserva. Envie *reservar* para começar de novo."

    _cliente, veiculos = await _veiculos_do_cliente(telefone, db)
    placa_digitada = "".join(c for c in texto.upper() if c.isalnum())
    escolhido = next((v for v in veiculos if v.placa == placa_digitada), None)
    if not escolhido:
        return "❌ Não reconheci essa placa entre seus veículos cadastrados. Envie a placa exatamente como está cadastrada."

    await limpar_estado(telefone)
    return await _reservar_vaga(vaga_id, telefone, db, placa_escolhida=escolhido.placa)


async def _dados_reserva_do_cliente(telefone: str, db: AsyncSession) -> tuple[str, str | None, str | None]:
    """(nome, placa, email) a partir do cadastro (Cliente + Veiculo) pra preencher a
    reserva sozinho. Sem cadastro, ou com 2+ veículos ainda sem escolha, cai no
    comportamento antigo (nome genérico, sem placa) — quem chama decide se pergunta antes."""
    cliente, veiculos = await _veiculos_do_cliente(telefone, db)
    if not cliente:
        return f"WhatsApp {telefone}", None, None
    placa_auto = veiculos[0].placa if len(veiculos) == 1 else None
    return cliente.nome, placa_auto, cliente.email


async def processar_comando(telefone: str, mensagem: str, db: AsyncSession) -> str:
    msg = mensagem.strip().lower()

    if msg in ("/vagas", "/vagas s2", "/vagas g2"):
        andar = "S2" if "s2" in msg else ("G2" if "g2" in msg else None)
        return await _listar_vagas(andar, db)
    if msg.startswith("/reservar "):
        return await _apos_escolher_vaga(telefone, mensagem[10:].strip().upper(), db)
    if msg.startswith("/cancelar "):
        return await _cancelar_reserva(mensagem[10:].strip().upper(), telefone, db)
    if msg.startswith("/status "):
        return await _status_placa(mensagem[8:].strip().upper(), db)
    if msg == "/ajuda":
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
    vaga_id: str, telefone: str, db: AsyncSession, placa_escolhida: str | None = None
) -> str:
    inicio = datetime.utcnow()
    fim = inicio + RESERVA_DURACAO_PADRAO
    nome, placa_auto, email = await _dados_reserva_do_cliente(telefone, db)
    payload = ReservaCreate(
        vaga_id=vaga_id,
        nome=nome,
        telefone=telefone,
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
        return "Desculpe, essa vaga acabou de ser reservada por outra pessoa. Por favor, escolha outra."
    return f"✅ Vaga {vaga_id} reservada até {fim:%H:%M}. Envie */cancelar {vaga_id}* para desistir."


async def _cancelar_reserva(vaga_id: str, telefone: str, db: AsyncSession) -> str:
    reserva = (
        await db.execute(
            select(Reserva).where(
                Reserva.vaga_id == vaga_id, Reserva.status == "ativa", Reserva.telefone == telefone
            )
        )
    ).scalar_one_or_none()
    if not reserva:
        return f"❌ Nenhuma reserva ativa sua encontrada para a vaga {vaga_id}."
    try:
        await aplicar_cancelamento(db, reserva.id, f"whatsapp:{telefone}")
    except (RecursoNaoEncontradoError, ConflitoOperacaoError) as e:
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
        "*/vagas* — Ver vagas disponíveis\n"
        "*/vagas S2* — Vagas do Subsolo 2\n"
        "*/vagas G2* — Vagas da Garagem 2\n"
        "*/reservar S2-49* — Reservar vaga por 2h\n"
        "*reservar* — inicia uma reserva por conversa (escolha a vaga na lista)\n"
        "*/cancelar S2-49* — Cancelar sua reserva\n"
        "*/status ABC1234* — Verificar placa\n\n"
        "_Dom Pagamentos • Estacionamento_"
    )
