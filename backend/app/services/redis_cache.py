import logging

from redis import RedisError
from redis import asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

VAGAS_CACHE_TTL_SEGUNDOS = 30
_VAGAS_CACHE_PREFIX = "vagas:list:"

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def get_vagas_cache(andar: str | None) -> str | None:
    """Cache é uma otimização — se o Redis estiver indisponível, segue sem cache."""
    try:
        return await get_redis().get(f"{_VAGAS_CACHE_PREFIX}{andar or 'todas'}")
    except RedisError:
        logger.warning("Redis indisponível ao ler cache de vagas — seguindo sem cache.")
        return None


async def set_vagas_cache(andar: str | None, payload_json: str) -> None:
    try:
        await get_redis().set(f"{_VAGAS_CACHE_PREFIX}{andar or 'todas'}", payload_json, ex=VAGAS_CACHE_TTL_SEGUNDOS)
    except RedisError:
        logger.warning("Redis indisponível ao gravar cache de vagas — seguindo sem cache.")


async def invalidate_vagas_cache() -> None:
    try:
        r = get_redis()
        keys = [key async for key in r.scan_iter(f"{_VAGAS_CACHE_PREFIX}*")]
        if keys:
            await r.delete(*keys)
    except RedisError:
        logger.warning("Redis indisponível ao invalidar cache de vagas.")
