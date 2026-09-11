from datetime import datetime, timedelta

import pytest


@pytest.fixture(autouse=True)
def _sem_redis(monkeypatch):
    from redis import RedisError

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))


async def _criar_vaga(client, vaga_id: str = "S2-49") -> None:
    resp = await client.post("/vagas", json={"id": vaga_id, "numero": "49", "andar": "S2"})
    assert resp.status_code == 201


async def _criar_reserva(client, vaga_id: str = "S2-49", placa: str | None = None, telefone: str = "11999998888") -> dict:
    """Cria a reserva ANTES de qualquer mock de enviar_mensagem estar ativo — a própria
    criação já dispara uma notificação de confirmação (notificar_reserva_criada), que não
    tem relação com o que estamos testando aqui (compensação por sobreposição física)."""
    inicio = datetime.utcnow() + timedelta(minutes=1)
    fim = inicio + timedelta(hours=2)
    payload = {
        "vaga_id": vaga_id,
        "nome": "Cliente Reserva",
        "telefone": telefone,
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
    }
    if placa:
        payload["placa"] = placa
    resp = await client.post("/reservas", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def test_entrada_com_placa_da_reserva_conclui_silenciosamente(client_as_admin, monkeypatch):
    await _criar_vaga(client_as_admin)
    await _criar_reserva(client_as_admin, placa="ABC1234")

    from app.services import notificacoes

    chamado = False

    async def _fake_enviar(*args, **kwargs):
        nonlocal chamado
        chamado = True
        return True

    monkeypatch.setattr(notificacoes, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post(
        "/movimentacoes/entrada",
        json={
            "vaga_id": "S2-49",
            "nome": "Dono da Reserva",
            "placa": "abc1234",
            "veiculo": "Fiat Argo",
            "tipo_cliente": "mensalista",
        },
    )
    assert resp.status_code == 201
    assert chamado is False  # é a própria reserva sendo cumprida — sem notificação

    reservas = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})).json()
    assert reservas[0]["status"] == "concluida"


async def test_entrada_com_placa_diferente_cancela_reserva_notifica_e_audita(client_as_admin, monkeypatch):
    await _criar_vaga(client_as_admin)
    await _criar_reserva(client_as_admin, placa="ABC1234", telefone="11988887777")

    from app.services import notificacoes

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(notificacoes, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post(
        "/movimentacoes/entrada",
        json={
            "vaga_id": "S2-49",
            "nome": "Outra Pessoa",
            "placa": "ZZZ9999",
            "veiculo": "Onix",
            "tipo_cliente": "visitante",
        },
    )
    assert resp.status_code == 201

    reservas = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})).json()
    assert reservas[0]["status"] == "cancelada"

    assert len(enviados) == 1
    assert enviados[0][0] == "11988887777"
    assert "cancelada" in enviados[0][1]

    audit = (await client_as_admin.get("/admin/audit-logs")).json()
    assert any(a["acao"] == "reserva_sobreposta_fisicamente" and a["recurso"] == "reserva" for a in audit)


async def test_reserva_sem_placa_e_sempre_tratada_como_sobreposta(client_as_admin, monkeypatch):
    """Reservas feitas pelo bot do WhatsApp hoje não coletam placa — sem como confirmar
    identidade, a política segura é sempre tratar como sobreposição."""
    await _criar_vaga(client_as_admin)
    await _criar_reserva(client_as_admin, placa=None, telefone="11977776666")

    from app.services import notificacoes

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(notificacoes, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post(
        "/movimentacoes/entrada",
        json={
            "vaga_id": "S2-49",
            "nome": "Quem Chegou",
            "placa": "QQQ1111",
            "veiculo": "HB20",
            "tipo_cliente": "rotativo",
        },
    )
    assert resp.status_code == 201
    assert len(enviados) == 1

    reservas = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})).json()
    assert reservas[0]["status"] == "cancelada"


async def test_compensacao_tambem_ocorre_via_sync_offline(client_as_admin, monkeypatch):
    """Prova o insight chave da Fase 4: aplicar_entrada é a mesma função para entrada
    ao vivo e para sync atrasado — a compensação funciona nos dois sem lógica duplicada."""
    await _criar_vaga(client_as_admin)
    await _criar_reserva(client_as_admin, placa="ABC1234", telefone="11955554444")

    from app.services import notificacoes

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(notificacoes, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post(
        "/movimentacoes/sync",
        json={
            "operacoes": [
                {
                    "id": 1,
                    "tipo": "entrada",
                    "payload": {
                        "vaga_id": "S2-49",
                        "nome": "Quem Chegou Offline",
                        "placa": "QQQ1111",
                        "veiculo": "HB20",
                        "tipo_cliente": "rotativo",
                    },
                }
            ]
        },
    )
    assert resp.status_code == 200
    assert resp.json()["resultados"][0]["sucesso"] is True
    assert len(enviados) == 1

    reservas = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})).json()
    assert reservas[0]["status"] == "cancelada"
