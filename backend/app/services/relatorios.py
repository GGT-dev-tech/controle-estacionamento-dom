from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movimentacao import Movimentacao
from app.models.vaga import StatusVaga, Vaga
from app.services.email import enviar_relatorio_diario


async def montar_relatorio_diario(db: AsyncSession) -> dict:
    agora = datetime.utcnow()
    inicio_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)

    total_vagas = (
        await db.execute(select(func.count()).select_from(Vaga).where(Vaga.ativo.is_(True)))
    ).scalar_one()

    contagem_status = dict(
        (
            await db.execute(select(Vaga.status, func.count()).where(Vaga.ativo.is_(True)).group_by(Vaga.status))
        ).all()
    )

    entradas_hoje = (
        await db.execute(
            select(func.count()).select_from(Movimentacao).where(
                Movimentacao.tipo == "entrada", Movimentacao.timestamp >= inicio_dia
            )
        )
    ).scalar_one()

    saidas_hoje = (
        await db.execute(
            select(Movimentacao).where(Movimentacao.tipo == "saida", Movimentacao.timestamp >= inicio_dia)
        )
    ).scalars().all()

    tempos = [m.tempo_permanencia_min for m in saidas_hoje if m.tempo_permanencia_min is not None]
    tempo_medio_min = round(sum(tempos) / len(tempos)) if tempos else None

    return {
        "data": agora,
        "total_vagas": total_vagas,
        "livres": contagem_status.get(StatusVaga.livre, 0),
        "ocupadas": contagem_status.get(StatusVaga.ocupada, 0),
        "reservadas": contagem_status.get(StatusVaga.reservada, 0),
        "manutencao": contagem_status.get(StatusVaga.manutencao, 0),
        "entradas_hoje": entradas_hoje,
        "saidas_hoje": len(saidas_hoje),
        "tempo_medio_permanencia_min": tempo_medio_min,
    }


async def disparar_relatorio_diario(db: AsyncSession, destinatarios: list[str]) -> bool:
    if not destinatarios:
        return False
    relatorio = await montar_relatorio_diario(db)
    return await enviar_relatorio_diario(destinatarios, relatorio)


async def montar_historico_diario(db: AsyncSession, dias: int) -> list[dict]:
    """Série de entradas/saídas por dia, para os últimos `dias` dias (incluindo hoje) — usada nos gráficos."""
    hoje = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    historico: list[dict] = []

    for offset in range(dias - 1, -1, -1):
        dia_inicio = hoje - timedelta(days=offset)
        dia_fim = dia_inicio + timedelta(days=1)

        entradas = (
            await db.execute(
                select(func.count()).select_from(Movimentacao).where(
                    Movimentacao.tipo == "entrada",
                    Movimentacao.timestamp >= dia_inicio,
                    Movimentacao.timestamp < dia_fim,
                )
            )
        ).scalar_one()

        saidas = (
            await db.execute(
                select(Movimentacao).where(
                    Movimentacao.tipo == "saida",
                    Movimentacao.timestamp >= dia_inicio,
                    Movimentacao.timestamp < dia_fim,
                )
            )
        ).scalars().all()

        tempos = [m.tempo_permanencia_min for m in saidas if m.tempo_permanencia_min is not None]

        historico.append(
            {
                "data": dia_inicio.date().isoformat(),
                "entradas": entradas,
                "saidas": len(saidas),
                "tempo_medio_permanencia_min": round(sum(tempos) / len(tempos)) if tempos else None,
            }
        )

    return historico
