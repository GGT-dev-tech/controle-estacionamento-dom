import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.config import settings
from app.database import get_db
from app.models.movimentacao import Movimentacao
from app.security.auth import require_role
from app.services.email_templates import template_relatorio_diario
from app.services.relatorios import disparar_relatorio_diario, montar_historico_diario, montar_relatorio_diario

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


@router.get("/diario")
async def obter_relatorio_diario(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> dict:
    return await montar_relatorio_diario(db)


@router.get("/historico")
async def obter_historico(
    dias: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> list[dict]:
    return await montar_historico_diario(db, dias)


@router.post("/diario/enviar")
async def enviar_relatorio_diario_endpoint(
    db: AsyncSession = Depends(get_db),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
) -> dict:
    """Disparado por uma tarefa agendada externa (ex.: Railway Cron) uma vez por dia."""
    if not settings.cron_secret or x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=404)

    destinatarios = [e.strip() for e in settings.relatorio_destinatarios.split(",") if e.strip()]
    enviado = await disparar_relatorio_diario(db, destinatarios)
    return {"enviado": enviado, "destinatarios": len(destinatarios)}


@router.get("/diario/pdf")
async def exportar_relatorio_diario_pdf(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> Response:
    relatorio = await montar_relatorio_diario(db)
    pdf_bytes = HTML(string=template_relatorio_diario(relatorio)).write_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=relatorio_{relatorio['data']:%Y-%m-%d}.pdf"},
    )


@router.get("/movimentacoes/csv")
async def exportar_movimentacoes_csv(
    dias: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> Response:
    desde = datetime.utcnow() - timedelta(days=dias)
    movimentacoes = (
        await db.execute(
            select(Movimentacao).where(Movimentacao.timestamp >= desde).order_by(Movimentacao.timestamp.desc())
        )
    ).scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["data_hora", "tipo", "vaga_id", "placa", "motorista", "veiculo", "tempo_permanencia_min", "operador_id"]
    )
    for m in movimentacoes:
        writer.writerow(
            [
                m.timestamp.isoformat(),
                m.tipo,
                m.vaga_id,
                m.placa,
                m.motorista,
                m.veiculo,
                m.tempo_permanencia_min if m.tempo_permanencia_min is not None else "",
                m.operador_id,
            ]
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=movimentacoes_{dias}dias.csv"},
    )
