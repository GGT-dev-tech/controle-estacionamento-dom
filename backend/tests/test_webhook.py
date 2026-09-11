import pytest


@pytest.fixture(autouse=True)
def _sem_redis(monkeypatch):
    from redis import RedisError

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))


@pytest.fixture(autouse=True)
def _segredo_webhook(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "whatsapp_webhook_secret", "segredo-correto")


def _payload(texto: str, from_me: bool = False) -> dict:
    return {
        "event": "messages.upsert",
        "data": {
            "messages": [
                {
                    "key": {"remoteJid": "11999998888@s.whatsapp.net", "fromMe": from_me},
                    "message": {"conversation": texto},
                }
            ]
        },
    }


async def test_webhook_com_segredo_incorreto_retorna_404(client_as_admin):
    resp = await client_as_admin.post("/webhook/whatsapp/segredo-errado", json=_payload("/ajuda"))
    assert resp.status_code == 404


async def test_webhook_recusa_numero_nao_cadastrado(client_as_admin, monkeypatch):
    from app.routers import webhook_whatsapp

    enviados = []

    async def _fake_enviar_mensagem(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar_mensagem)

    resp = await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("/ajuda"))
    assert resp.status_code == 200
    assert len(enviados) == 1
    assert "exclusivo para clientes cadastrados" in enviados[0][1]


async def test_webhook_processa_comando_e_responde(client_as_admin, db_session, monkeypatch):
    from app.models.cliente import Cliente
    from app.models.ocupante import TipoCliente
    from app.routers import webhook_whatsapp

    async with db_session() as db:
        db.add(Cliente(nome="Cliente Teste", telefone="11999998888", tipo_cliente=TipoCliente.mensalista))
        await db.commit()

    enviados = []

    async def _fake_enviar_mensagem(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar_mensagem)

    resp = await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("/ajuda"))
    assert resp.status_code == 200
    assert len(enviados) == 1
    assert enviados[0][0] == "11999998888"
    assert "Comandos" in enviados[0][1]


async def test_webhook_ignora_mensagem_propria(client_as_admin, monkeypatch):
    from app.routers import webhook_whatsapp

    chamado = False

    async def _fake_enviar_mensagem(telefone, texto):
        nonlocal chamado
        chamado = True
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar_mensagem)

    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("/ajuda", from_me=True)
    )
    assert resp.status_code == 200
    assert chamado is False


async def test_webhook_ignora_evento_diferente(client_as_admin):
    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json={"event": "connection.update", "data": {}}
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}
