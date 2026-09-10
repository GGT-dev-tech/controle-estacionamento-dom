"""Verificação pontual: cria uma Vaga com todos os campos e confere o round-trip do
Enum (status) e do Boolean (ativo) contra o banco real. Usado manualmente para validar
compatibilidade MySQL/PostgreSQL — não faz parte da suíte pytest (não precisa de mock)."""

import asyncio

from sqlalchemy import select

from app.database import SessionLocal
from app.models.vaga import StatusVaga, Vaga


async def main() -> None:
    async with SessionLocal() as db:
        vaga_id = "SMOKE-TEST-1"
        existente = await db.get(Vaga, vaga_id)
        if existente:
            await db.delete(existente)
            await db.commit()

        vaga = Vaga(id=vaga_id, numero="1", andar="SMOKE", posicao="fundo", status=StatusVaga.reservada, ativo=True)
        db.add(vaga)
        await db.commit()

        recarregada = (await db.execute(select(Vaga).where(Vaga.id == vaga_id))).scalar_one()
        assert recarregada.status == StatusVaga.reservada, f"esperava reservada, veio {recarregada.status!r}"
        assert recarregada.ativo is True, f"esperava True, veio {recarregada.ativo!r}"

        recarregada.ativo = False
        await db.commit()
        confirmada = (await db.execute(select(Vaga).where(Vaga.id == vaga_id))).scalar_one()
        assert confirmada.ativo is False, f"esperava False, veio {confirmada.ativo!r}"

        await db.delete(confirmada)
        await db.commit()

    print("OK: Enum e Boolean fazem round-trip corretamente.")


if __name__ == "__main__":
    asyncio.run(main())
