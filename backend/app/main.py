import logging

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from redis import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.routers import admin, movimentacoes, relatorios, reservas, vagas, webhook_whatsapp, ws
from app.services import redis_cache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="Estacionamento Dom Pagamentos API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

if settings.is_production:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[settings.api_host])


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health", tags=["Health"])
async def health(response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    """Checagem real de disponibilidade — usada pelo healthcheck do Railway e por
    monitoramento externo (ex.: UptimeRobot). Retorna 503 se algum backend estiver fora."""
    resultado = {"status": "ok", "database": "ok", "redis": "ok"}

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        resultado["database"] = "erro"
        resultado["status"] = "degradado"

    try:
        await redis_cache.get_redis().ping()
    except RedisError:
        resultado["redis"] = "erro"
        resultado["status"] = "degradado"

    if resultado["status"] != "ok":
        response.status_code = 503
    return resultado


app.include_router(vagas.router)
app.include_router(reservas.router)
app.include_router(movimentacoes.router)
app.include_router(relatorios.router)
app.include_router(admin.router)
app.include_router(webhook_whatsapp.router)
app.include_router(ws.router)
