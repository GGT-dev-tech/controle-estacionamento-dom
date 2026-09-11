"""Um cliente self-service não pode interferir na reserva/ocupação de OUTRO cliente
(cancelar a reserva alheia, ocupar por cima dela sem estar fisicamente lá, ou liberar o
veículo de outra pessoa) — só quem é dono do recurso, ou staff/admin (sem Cliente próprio,
ex.: EntradaModal/Admin), pode agir. Ver services/sync.py: _cliente_do_operador."""

from datetime import datetime, timedelta

import pytest

ROLE_CLAIM = "https://estacionamento.dom/role"
_CLIENTE_A = {"sub": "google-oauth2|cliente-a-teste", ROLE_CLAIM: "operador"}
_CLIENTE_B = {"sub": "google-oauth2|cliente-b-teste", ROLE_CLAIM: "operador"}


def _autenticar_como(usuario: dict) -> None:
    from app.main import app
    from app.security.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: usuario


@pytest.fixture(autouse=True)
def _sem_redis(monkeypatch):
    from redis import RedisError

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))


async def _criar_vaga(client, vaga_id: str) -> None:
    resp = await client.post("/vagas", json={"id": vaga_id, "numero": vaga_id.split("-")[1], "andar": "S2"})
    assert resp.status_code == 201


async def _cliente_a_reserva(client, vaga_id: str) -> int:
    _autenticar_como(_CLIENTE_A)
    await client.post("/clientes/me", json={"nome": "Cliente A", "telefone": "11911110000"})
    await client.post("/clientes/me/veiculos", json={"placa": "AAA1111", "veiculo": "Onix"})

    inicio = datetime.utcnow() + timedelta(minutes=1)
    fim = inicio + timedelta(hours=1)
    resp = await client.post(
        "/reservas",
        json={
            "vaga_id": vaga_id,
            "nome": "Cliente A",
            "telefone": "11911110000",
            "placa": "AAA1111",
            "inicio": inicio.isoformat(),
            "fim": fim.isoformat(),
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_cliente_nao_ocupa_por_cima_da_reserva_de_outro_cliente(client_as_admin):
    await _criar_vaga(client_as_admin, "S2-70")
    await _cliente_a_reserva(client_as_admin, "S2-70")

    _autenticar_como(_CLIENTE_B)
    await client_as_admin.post("/clientes/me", json={"nome": "Cliente B", "telefone": "11922220000"})
    resp = await client_as_admin.post(
        "/movimentacoes/entrada",
        json={
            "vaga_id": "S2-70",
            "nome": "Cliente B",
            "placa": "BBB2222",
            "veiculo": "Gol",
            "tipo_cliente": "rotativo",
        },
    )
    assert resp.status_code == 403

    vaga = (await client_as_admin.get("/vagas/S2-70")).json()
    assert vaga["status"] == "reservada"
    assert vaga["reserva_ativa"]["telefone"] == "11911110000"


async def test_cliente_nao_cancela_reserva_de_outro_cliente(client_as_admin):
    await _criar_vaga(client_as_admin, "S2-71")
    reserva_id = await _cliente_a_reserva(client_as_admin, "S2-71")

    _autenticar_como(_CLIENTE_B)
    await client_as_admin.post("/clientes/me", json={"nome": "Cliente B", "telefone": "11922220000"})
    resp = await client_as_admin.post(f"/reservas/{reserva_id}/cancelar")
    assert resp.status_code == 403

    vaga = (await client_as_admin.get("/vagas/S2-71")).json()
    assert vaga["status"] == "reservada"


async def test_cliente_nao_libera_veiculo_de_outro_cliente(client_as_admin):
    await _criar_vaga(client_as_admin, "S2-72")

    _autenticar_como(_CLIENTE_A)
    await client_as_admin.post("/clientes/me", json={"nome": "Cliente A", "telefone": "11911110000"})
    await client_as_admin.post("/clientes/me/veiculos", json={"placa": "AAA1111", "veiculo": "Onix"})
    resp_entrada = await client_as_admin.post(
        "/movimentacoes/entrada",
        json={
            "vaga_id": "S2-72",
            "nome": "Cliente A",
            "placa": "AAA1111",
            "veiculo": "Onix",
            "tipo_cliente": "rotativo",
        },
    )
    assert resp_entrada.status_code == 201

    _autenticar_como(_CLIENTE_B)
    await client_as_admin.post("/clientes/me", json={"nome": "Cliente B", "telefone": "11922220000"})
    resp_saida = await client_as_admin.post("/movimentacoes/saida", json={"vaga_id": "S2-72"})
    assert resp_saida.status_code == 403

    vaga = (await client_as_admin.get("/vagas/S2-72")).json()
    assert vaga["status"] == "ocupada"


async def test_dono_da_reserva_consegue_confirmar_chegada_e_admin_continua_com_prioridade(client_as_admin):
    """Confirma que a proteção não bloqueia o dono de verdade, nem o admin/staff
    (sem Cliente próprio) — a prioridade física de corrigir qualquer vaga continua."""
    await _criar_vaga(client_as_admin, "S2-73")
    await _cliente_a_reserva(client_as_admin, "S2-73")

    # O próprio Cliente A confirma a chegada com o carro que reservou — placa bate,
    # deveria funcionar mesmo sendo "cliente" (não staff).
    resp_propria = await client_as_admin.post(
        "/movimentacoes/entrada",
        json={
            "vaga_id": "S2-73",
            "nome": "Cliente A",
            "placa": "AAA1111",
            "veiculo": "Onix",
            "tipo_cliente": "rotativo",
        },
    )
    assert resp_propria.status_code == 201

    # Admin (sem Cliente próprio) consegue liberar qualquer vaga — prioridade de staff mantida.
    _autenticar_como({"sub": "auth0|admin-teste", ROLE_CLAIM: "admin"})
    resp_saida_admin = await client_as_admin.post("/movimentacoes/saida", json={"vaga_id": "S2-73"})
    assert resp_saida_admin.status_code == 201
