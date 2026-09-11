from datetime import datetime, timedelta

import pytest


@pytest.fixture(autouse=True)
def _sem_redis(monkeypatch):
    """Evita depender de um Redis real durante os testes — o cache falha aberto."""
    from redis import RedisError

    async def _raise(*args, **kwargs):
        raise RedisError("Redis indisponível nos testes")

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))


async def _criar_vaga(client, vaga_id="S2-49"):
    resp = await client.post("/vagas", json={"id": vaga_id, "numero": "49", "andar": "S2"})
    assert resp.status_code == 201
    return resp.json()


async def test_fluxo_entrada_e_saida(client_as_admin):
    await _criar_vaga(client_as_admin)

    resp_entrada = await client_as_admin.post(
        "/movimentacoes/entrada",
        json={
            "vaga_id": "S2-49",
            "nome": "Priscilo Barros",
            "placa": "abc1234",
            "veiculo": "Fiat Argo",
            "tipo_cliente": "mensalista",
        },
    )
    assert resp_entrada.status_code == 201
    assert resp_entrada.json()["placa"] == "ABC1234"

    vaga = (await client_as_admin.get("/vagas/S2-49")).json()
    assert vaga["status"] == "ocupada"
    assert vaga["ocupante"]["nome"] == "Priscilo Barros"

    # Não pode ocupar de novo enquanto já está ocupada
    resp_conflito = await client_as_admin.post(
        "/movimentacoes/entrada",
        json={
            "vaga_id": "S2-49",
            "nome": "Outra Pessoa",
            "placa": "XYZ9999",
            "veiculo": "Onix",
            "tipo_cliente": "visitante",
        },
    )
    assert resp_conflito.status_code == 409

    resp_saida = await client_as_admin.post("/movimentacoes/saida", json={"vaga_id": "S2-49"})
    assert resp_saida.status_code == 201
    assert resp_saida.json()["tempo_permanencia_min"] is not None

    vaga_livre = (await client_as_admin.get("/vagas/S2-49")).json()
    assert vaga_livre["status"] == "livre"
    assert vaga_livre["ocupante"] is None


async def test_operador_nao_pode_criar_vaga(client_as_operador):
    resp = await client_as_operador.post("/vagas", json={"id": "S2-50", "numero": "50", "andar": "S2"})
    assert resp.status_code == 403


async def test_sync_reserva_com_datetime_timezone_aware_como_o_frontend_manda(client_as_admin):
    # Reproduz o segundo ponto do bug de produção: o mesmo payload aware (Z-suffixed)
    # vindo da fila offline (Dexie) via /movimentacoes/sync, não só do POST /reservas direto.
    await _criar_vaga(client_as_admin, "S2-51")

    inicio = datetime.utcnow() + timedelta(hours=1)
    fim = inicio + timedelta(hours=2)

    resp = await client_as_admin.post(
        "/movimentacoes/sync",
        json={
            "operacoes": [
                {
                    "id": 1,
                    "tipo": "reserva",
                    "payload": {
                        "vaga_id": "S2-51",
                        "nome": "Cliente Offline",
                        "telefone": "11999996666",
                        "inicio": inicio.isoformat() + "Z",
                        "fim": fim.isoformat() + "Z",
                    },
                }
            ]
        },
    )
    assert resp.status_code == 200
    resultado = resp.json()["resultados"][0]
    assert resultado["sucesso"] is True

    vaga = (await client_as_admin.get("/vagas/S2-51")).json()
    assert vaga["status"] == "reservada"
