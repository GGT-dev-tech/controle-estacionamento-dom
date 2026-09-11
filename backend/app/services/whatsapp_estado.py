import json
import logging

from redis import RedisError

from app.services.redis_cache import get_redis

logger = logging.getLogger(__name__)

_ESTADO_PREFIX = "whatsapp:conversa:"
ESTADO_TTL_SEGUNDOS = 300  # conversa abandonada expira sozinha em 5 min


def _chave(telefone: str) -> str:
    return f"{_ESTADO_PREFIX}{telefone}"


async def obter_estado(telefone: str) -> dict | None:
    """Estado é uma otimização de UX — se o Redis estiver indisponível, a conversa
    simplesmente não avança (o cliente recomeça do zero), sem derrubar o webhook."""
    try:
        bruto = await get_redis().get(_chave(telefone))
    except RedisError:
        logger.warning("Redis indisponível ao ler estado de conversa do WhatsApp.")
        return None
    return json.loads(bruto) if bruto else None


async def definir_estado(telefone: str, estado: dict, ttl: int = ESTADO_TTL_SEGUNDOS) -> None:
    try:
        await get_redis().set(_chave(telefone), json.dumps(estado), ex=ttl)
    except RedisError:
        logger.warning("Redis indisponível ao gravar estado de conversa do WhatsApp.")


async def limpar_estado(telefone: str) -> None:
    try:
        await get_redis().delete(_chave(telefone))
    except RedisError:
        logger.warning("Redis indisponível ao limpar estado de conversa do WhatsApp.")
