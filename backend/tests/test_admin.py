import pytest


@pytest.fixture(autouse=True)
def _sem_redis(monkeypatch):
    from redis import RedisError

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))


@pytest.fixture(autouse=True)
def _segredo_interno(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth0_action_secret", "segredo-interno")


async def test_dominios_cru_e_verificar(client_as_admin):
    resp_add = await client_as_admin.post("/admin/dominios", json={"dominio": "DomPagamentos.com"})
    assert resp_add.status_code == 201
    assert resp_add.json()["dominio"] == "dompagamentos.com"

    resp_dup = await client_as_admin.post("/admin/dominios", json={"dominio": "dompagamentos.com"})
    assert resp_dup.status_code == 409

    resp_lista = await client_as_admin.get("/admin/dominios")
    assert resp_lista.status_code == 200
    assert [d["dominio"] for d in resp_lista.json()] == ["dompagamentos.com"]

    resp_verificar_sem_segredo = await client_as_admin.get("/admin/dominios/dompagamentos.com/verificar")
    assert resp_verificar_sem_segredo.status_code == 404

    resp_verificar = await client_as_admin.get(
        "/admin/dominios/dompagamentos.com/verificar", headers={"X-Internal-Secret": "segredo-interno"}
    )
    assert resp_verificar.status_code == 200
    assert resp_verificar.json() == {"autorizado": True}

    resp_verificar_outro = await client_as_admin.get(
        "/admin/dominios/outro.com/verificar", headers={"X-Internal-Secret": "segredo-interno"}
    )
    assert resp_verificar_outro.json() == {"autorizado": False}

    resp_remover = await client_as_admin.delete("/admin/dominios/dompagamentos.com")
    assert resp_remover.status_code == 204

    resp_verificar_apos_remover = await client_as_admin.get(
        "/admin/dominios/dompagamentos.com/verificar", headers={"X-Internal-Secret": "segredo-interno"}
    )
    assert resp_verificar_apos_remover.json() == {"autorizado": False}


async def test_admins_cru_e_verificar(client_as_admin):
    resp_add = await client_as_admin.post("/admin/admins", json={"email": "Gustavo@DomPagamentos.com"})
    assert resp_add.status_code == 201
    assert resp_add.json()["email"] == "gustavo@dompagamentos.com"

    resp_verificar = await client_as_admin.get(
        "/admin/admins/gustavo@dompagamentos.com/verificar", headers={"X-Internal-Secret": "segredo-interno"}
    )
    assert resp_verificar.json() == {"admin": True}

    resp_verificar_outro = await client_as_admin.get(
        "/admin/admins/outra@dompagamentos.com/verificar", headers={"X-Internal-Secret": "segredo-interno"}
    )
    assert resp_verificar_outro.json() == {"admin": False}

    resp_remover = await client_as_admin.delete("/admin/admins/gustavo@dompagamentos.com")
    assert resp_remover.status_code == 204

    resp_remover_inexistente = await client_as_admin.delete("/admin/admins/gustavo@dompagamentos.com")
    assert resp_remover_inexistente.status_code == 404


async def test_gestao_de_dominios_requer_admin(client_as_operador):
    resp = await client_as_operador.get("/admin/dominios")
    assert resp.status_code == 403


async def test_audit_logs_registrados_e_listados(client_as_admin):
    await client_as_admin.post("/vagas", json={"id": "S2-80", "numero": "80", "andar": "S2"})

    resp = await client_as_admin.get("/admin/audit-logs")
    assert resp.status_code == 200
    logs = resp.json()
    assert any(log["acao"] == "criar_vaga" for log in logs)


async def test_audit_logs_requer_admin(client_as_operador):
    resp = await client_as_operador.get("/admin/audit-logs")
    assert resp.status_code == 403
