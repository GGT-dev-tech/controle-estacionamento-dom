import pytest


@pytest.fixture(autouse=True)
def _sem_redis(monkeypatch):
    from redis import RedisError

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))


async def test_sync_processa_lote_com_sucesso_e_falha(client_as_admin):
    await client_as_admin.post("/vagas", json={"id": "S2-01", "numero": "01", "andar": "S2"})

    resp = await client_as_admin.post(
        "/movimentacoes/sync",
        json={
            "operacoes": [
                {
                    "id": 1,
                    "tipo": "entrada",
                    "payload": {
                        "vaga_id": "S2-01",
                        "nome": "Ana",
                        "placa": "AAA1111",
                        "veiculo": "Onix",
                        "tipo_cliente": "rotativo",
                    },
                },
                {
                    "id": 2,
                    "tipo": "entrada",
                    "payload": {
                        "vaga_id": "S2-99-INEXISTENTE",
                        "nome": "Bruno",
                        "placa": "BBB2222",
                        "veiculo": "HB20",
                        "tipo_cliente": "visitante",
                    },
                },
            ]
        },
    )
    assert resp.status_code == 200
    resultados = {r["id"]: r for r in resp.json()["resultados"]}
    assert resultados[1]["sucesso"] is True
    assert resultados[2]["sucesso"] is False

    vaga = (await client_as_admin.get("/vagas/S2-01")).json()
    assert vaga["status"] == "ocupada"


async def test_sync_com_payload_invalido_nao_derruba_o_lote(client_as_admin):
    await client_as_admin.post("/vagas", json={"id": "S2-02", "numero": "02", "andar": "S2"})

    resp = await client_as_admin.post(
        "/movimentacoes/sync",
        json={
            "operacoes": [
                {"id": 1, "tipo": "saida", "payload": {}},  # falta vaga_id
                {
                    "id": 2,
                    "tipo": "entrada",
                    "payload": {
                        "vaga_id": "S2-02",
                        "nome": "Carla",
                        "placa": "CCC3333",
                        "veiculo": "Onix",
                        "tipo_cliente": "mensalista",
                    },
                },
            ]
        },
    )
    assert resp.status_code == 200
    resultados = {r["id"]: r for r in resp.json()["resultados"]}
    assert resultados[1]["sucesso"] is False
    assert resultados[2]["sucesso"] is True
