import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.cliente import Cliente
from app.services.whatsapp import enviar_mensagem, normalizar_telefone, processar_mensagem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["WhatsApp"])


def _extrair_texto(mensagem: dict) -> str:
    """Mensagem de texto simples vem em message.conversation; uma resposta/reply (ou
    mensagem com preview de link) vem em message.extendedTextMessage.text — formato
    diferente do Baileys/Evolution API. Sem cobrir os dois, boa parte das mensagens reais
    (qualquer resposta a uma mensagem anterior) seria silenciosamente ignorada."""
    if texto := mensagem.get("conversation"):
        return texto.strip()
    return mensagem.get("extendedTextMessage", {}).get("text", "").strip()


@router.post("/whatsapp/{secret}")
async def receber_mensagem(secret: str, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Recebe eventos da Evolution API. O segredo no path garante que só a Evolution API (configurada
    com esta URL exata) consiga chamar este endpoint — retorna 404 para qualquer segredo incorreto,
    para não revelar sequer que o endpoint existe.
    """
    if not settings.whatsapp_webhook_secret or secret != settings.whatsapp_webhook_secret:
        raise HTTPException(status_code=404)

    payload = await request.json()

    if payload.get("event") != "messages.upsert":
        return {"status": "ignored"}

    # A Evolution API v2 manda `data` como o objeto da MENSAGEM em si (com "key"/"message"
    # direto), não como {"messages": [...]}; algumas configurações antigas/lote ainda usam
    # essa segunda forma — cobre as duas. Sem isso, o loop nunca roda: toda mensagem recebida
    # (inclusive comandos como /ajuda) era silenciosamente ignorada, mesmo com o webhook
    # corretamente configurado e chegando até aqui.
    data = payload.get("data") or {}
    mensagens = data.get("messages")
    if mensagens is None:
        mensagens = [data] if data.get("key") else []

    for msg in mensagens:
        if msg.get("key", {}).get("fromMe"):
            continue

        telefone = msg.get("key", {}).get("remoteJid", "").replace("@s.whatsapp.net", "")
        texto = _extrair_texto(msg.get("message", {}))

        if not telefone or not texto:
            continue

        cliente = (
            await db.execute(
                select(Cliente).where(Cliente.telefone == normalizar_telefone(telefone), Cliente.ativo.is_(True))
            )
        ).scalar_one_or_none()
        if not cliente:
            # Só responde a comandos explícitos de números não cadastrados (evita virar
            # um "chatbot" para qualquer mensagem recebida no número real conectado).
            if texto.startswith("/"):
                await enviar_mensagem(
                    telefone, "Este serviço é exclusivo para clientes cadastrados. Fale com a administração."
                )
            continue

        resposta = await processar_mensagem(telefone, texto, db)
        await enviar_mensagem(telefone, resposta)

    return {"status": "ok"}
