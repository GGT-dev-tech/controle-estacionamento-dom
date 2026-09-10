import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.routers import admin, movimentacoes, relatorios, reservas, vagas, webhook_whatsapp, ws

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
async def health() -> dict:
    return {"status": "ok"}


app.include_router(vagas.router)
app.include_router(reservas.router)
app.include_router(movimentacoes.router)
app.include_router(relatorios.router)
app.include_router(admin.router)
app.include_router(webhook_whatsapp.router)
app.include_router(ws.router)
