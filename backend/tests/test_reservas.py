from datetime import datetime, timedelta

import pytest


@pytest.fixture(autouse=True)
def _sem_redis(monkeypatch):
    from redis import RedisError

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))


async def _criar_vaga(client, vaga_id="G2-10"):
    resp = await client.post("/vagas", json={"id": vaga_id, "numero": "10", "andar": "G2"})
    assert resp.status_code == 201


async def test_fluxo_reserva_e_cancelamento(client_as_admin):
    await _criar_vaga(client_as_admin)

    inicio = datetime.utcnow() + timedelta(hours=1)
    fim = inicio + timedelta(hours=2)

    resp_reserva = await client_as_admin.post(
        "/reservas",
        json={
            "vaga_id": "G2-10",
            "nome": "Maria Souza",
            "telefone": "11999998888",
            "inicio": inicio.isoformat(),
            "fim": fim.isoformat(),
        },
    )
    assert resp_reserva.status_code == 201
    reserva_id = resp_reserva.json()["id"]

    vaga = (await client_as_admin.get("/vagas/G2-10")).json()
    assert vaga["status"] == "reservada"
    assert vaga["reserva_ativa"]["nome"] == "Maria Souza"

    # Não pode reservar uma vaga já reservada
    resp_conflito = await client_as_admin.post(
        "/reservas",
        json={"vaga_id": "G2-10", "nome": "Outra", "inicio": inicio.isoformat(), "fim": fim.isoformat()},
    )
    assert resp_conflito.status_code == 409

    resp_cancelar = await client_as_admin.post(f"/reservas/{reserva_id}/cancelar")
    assert resp_cancelar.status_code == 200
    assert resp_cancelar.json()["status"] == "cancelada"

    vaga_livre = (await client_as_admin.get("/vagas/G2-10")).json()
    assert vaga_livre["status"] == "livre"


async def test_reserva_com_fim_antes_do_inicio_e_invalida(client_as_admin):
    await _criar_vaga(client_as_admin, "G2-11")
    inicio = datetime.utcnow() + timedelta(hours=2)
    fim = inicio - timedelta(hours=1)

    resp = await client_as_admin.post(
        "/reservas",
        json={"vaga_id": "G2-11", "nome": "Teste", "inicio": inicio.isoformat(), "fim": fim.isoformat()},
    )
    assert resp.status_code == 422


async def test_expirar_vencidas_requer_cron_secret_e_libera_vaga(client_as_admin, db_session, monkeypatch):
    from app.config import settings
    from app.models.reserva import Reserva
    from app.models.vaga import StatusVaga, Vaga

    monkeypatch.setattr(settings, "cron_secret", "segredo-cron")
    await _criar_vaga(client_as_admin, "G2-12")

    async with db_session() as session:
        vaga = await session.get(Vaga, "G2-12")
        vaga.status = StatusVaga.reservada
        session.add(
            Reserva(
                vaga_id="G2-12",
                nome="Cliente Vencido",
                telefone="11988887777",
                inicio=datetime.utcnow() - timedelta(hours=3),
                fim=datetime.utcnow() - timedelta(hours=1),
                status="ativa",
                canal="webapp",
                criado_em=datetime.utcnow() - timedelta(hours=3),
            )
        )
        await session.commit()

    resp_sem_header = await client_as_admin.post("/reservas/expirar-vencidas")
    assert resp_sem_header.status_code == 404

    resp = await client_as_admin.post("/reservas/expirar-vencidas", headers={"X-Cron-Secret": "segredo-cron"})
    assert resp.status_code == 200
    assert resp.json()["expiradas"] == 1

    vaga_depois = (await client_as_admin.get("/vagas/G2-12")).json()
    assert vaga_depois["status"] == "livre"
