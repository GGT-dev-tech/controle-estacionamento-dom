"""Zerar a ocupação/reserva das vagas à meia-noite (horário de Brasília), pra sempre
começar o dia com todas as vagas livres — pedido explícito do usuário."""

from datetime import datetime, timedelta

import pytest
from redis import RedisError


class _FakeRedis:
    def __init__(self) -> None:
        self._dados: dict[str, str] = {}

    async def get(self, chave: str) -> str | None:
        return self._dados.get(chave)

    async def set(self, chave: str, valor: str, ex: int | None = None) -> None:
        self._dados[chave] = valor


async def _criar_vaga(client, vaga_id: str) -> None:
    resp = await client.post("/vagas", json={"id": vaga_id, "numero": vaga_id.split("-")[1], "andar": "G2"})
    assert resp.status_code == 201


async def test_reset_diario_expira_reservas_libera_vagas_e_remove_ocupantes(client_as_admin, db_session, monkeypatch):
    from app.models.ocupante import Ocupante, TipoCliente
    from app.models.reserva import Reserva
    from app.models.vaga import StatusVaga, Vaga
    from app.services import sync

    monkeypatch.setattr(sync, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))

    await _criar_vaga(client_as_admin, "G2-70")
    await _criar_vaga(client_as_admin, "G2-71")
    await _criar_vaga(client_as_admin, "G2-72")  # permanece livre, controle

    async with db_session() as session:
        vaga_reservada = await session.get(Vaga, "G2-70")
        vaga_reservada.status = StatusVaga.reservada
        vaga_ocupada = await session.get(Vaga, "G2-71")
        vaga_ocupada.status = StatusVaga.ocupada
        session.add(
            Reserva(
                vaga_id="G2-70",
                nome="Cliente",
                telefone="11999990000",
                inicio=datetime.utcnow() - timedelta(hours=1),
                fim=datetime.utcnow() + timedelta(hours=5),  # bem longe do vencimento
                status="ativa",
                canal="webapp",
                criado_em=datetime.utcnow() - timedelta(hours=1),
            )
        )
        session.add(
            Ocupante(
                vaga_id="G2-71",
                nome="Outro Cliente",
                placa="ABC1234",
                veiculo="Onix",
                tipo_cliente=TipoCliente.visitante,
                hora_entrada=datetime.utcnow(),
                operador_id="auth0|admin-teste",
            )
        )
        await session.commit()

    async with db_session() as session:
        liberadas = await sync.reset_diario(session)
    assert liberadas == 2

    vaga_70 = (await client_as_admin.get("/vagas/G2-70")).json()
    vaga_71 = (await client_as_admin.get("/vagas/G2-71")).json()
    vaga_72 = (await client_as_admin.get("/vagas/G2-72")).json()
    assert vaga_70["status"] == "livre"
    assert vaga_71["status"] == "livre"
    assert vaga_72["status"] == "livre"

    async with db_session() as session:
        from sqlalchemy import select

        reserva = (await session.execute(select(Reserva).where(Reserva.vaga_id == "G2-70"))).scalar_one()
        assert reserva.status == "expirada"
        ocupantes = (await session.execute(select(Ocupante))).scalars().all()
        assert ocupantes == []


async def test_resetar_diario_se_virou_o_dia_nao_repete_no_mesmo_dia(client_as_admin, db_session, monkeypatch):
    from app.models.vaga import StatusVaga, Vaga
    from app.services import sync

    fake = _FakeRedis()
    monkeypatch.setattr(sync, "get_redis", lambda: fake)

    await _criar_vaga(client_as_admin, "G2-73")
    async with db_session() as session:
        vaga = await session.get(Vaga, "G2-73")
        vaga.status = StatusVaga.ocupada
        await session.commit()

    async with db_session() as session:
        primeira = await sync.resetar_diario_se_virou_o_dia(session)
    assert primeira == 1

    # A vaga volta a ficar ocupada só pra provar que o segundo ciclo não mexeu nela.
    async with db_session() as session:
        vaga = await session.get(Vaga, "G2-73")
        vaga.status = StatusVaga.ocupada
        await session.commit()

    async with db_session() as session:
        segunda = await sync.resetar_diario_se_virou_o_dia(session)
    assert segunda is None

    vaga_depois = (await client_as_admin.get("/vagas/G2-73")).json()
    assert vaga_depois["status"] == "ocupada"  # não foi resetada de novo


async def test_resetar_diario_se_virou_o_dia_sem_redis_nao_reseta(db_session, monkeypatch):
    """Sem Redis pra marcar "já rodou hoje", o reset é pulado (em vez de rodar a cada
    ciclo do scheduler o dia inteiro) — o endpoint manual continua disponível como
    alternativa nesse meio-tempo."""
    from app.services import sync

    monkeypatch.setattr(sync, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))

    async with db_session() as session:
        resultado = await sync.resetar_diario_se_virou_o_dia(session)
    assert resultado is None


async def test_endpoint_reset_diario_exige_cron_secret(client_as_admin, db_session, monkeypatch):
    from app.config import settings
    from app.models.vaga import StatusVaga, Vaga

    monkeypatch.setattr(settings, "cron_secret", "segredo-cron")
    await _criar_vaga(client_as_admin, "G2-74")

    async with db_session() as session:
        vaga = await session.get(Vaga, "G2-74")
        vaga.status = StatusVaga.ocupada
        await session.commit()

    resp_sem_header = await client_as_admin.post("/reservas/reset-diario")
    assert resp_sem_header.status_code == 404

    resp = await client_as_admin.post("/reservas/reset-diario", headers={"X-Cron-Secret": "segredo-cron"})
    assert resp.status_code == 200
    assert resp.json()["vagas_resetadas"] == 1

    vaga_depois = (await client_as_admin.get("/vagas/G2-74")).json()
    assert vaga_depois["status"] == "livre"
