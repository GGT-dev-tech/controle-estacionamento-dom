import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.whatsapp import enviar_mensagem, processar_comando

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["WhatsApp"])


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

    for msg in payload.get("data", {}).get("messages", []):
        if msg.get("key", {}).get("fromMe"):
            continue

        telefone = msg.get("key", {}).get("remoteJid", "").replace("@s.whatsapp.net", "")
        texto = msg.get("message", {}).get("conversation", "").strip()

        if telefone and texto.startswith("/"):
            resposta = await processar_comando(telefone, texto, db)
            await enviar_mensagem(telefone, resposta)

    return {"status": "ok"}
