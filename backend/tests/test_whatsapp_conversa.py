import pytest

from app.models.cliente import Cliente
from app.models.ocupante import TipoCliente
from app.models.vaga import StatusVaga, Vaga


@pytest.fixture(autouse=True)
def _redis_fake(monkeypatch):
    """Ao contrário do resto do app (cache é fail-open), a máquina de estados da
    conversa precisa de um Redis funcional de verdade — usamos um fake em memória."""
    import fakeredis.aioredis

    from app.services import whatsapp_estado

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(whatsapp_estado, "get_redis", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def _segredo_webhook(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "whatsapp_webhook_secret", "segredo-correto")


async def _criar_cliente(db_session, telefone: str = "11999998888") -> None:
    async with db_session() as db:
        db.add(Cliente(nome="Cliente Teste", telefone=telefone, tipo_cliente=TipoCliente.mensalista))
        await db.commit()


async def _criar_vaga(db_session, vaga_id: str = "S2-49") -> None:
    andar, numero = vaga_id.split("-", 1)
    async with db_session() as db:
        db.add(Vaga(id=vaga_id, numero=numero, andar=andar, status=StatusVaga.livre))
        await db.commit()


def _payload(telefone_com_55: str, texto: str) -> dict:
    return {
        "event": "messages.upsert",
        "data": {
            "messages": [
                {
                    "key": {"remoteJid": f"{telefone_com_55}@s.whatsapp.net", "fromMe": False},
                    "message": {"conversation": texto},
                }
            ]
        },
    }


async def test_reservar_por_texto_livre_lista_vagas_e_seta_estado(client_as_admin, db_session, monkeypatch):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar")
    )
    assert resp.status_code == 200
    assert len(enviados) == 1
    assert "S2-49" in enviados[0][1]

    from app.services.whatsapp_estado import obter_estado

    # o estado é indexado pelo telefone "bruto" (como chega do remoteJid), igual ao
    # resto de services/whatsapp.py — só Cliente.telefone é normalizado (Fase 1)
    assert await obter_estado("5511999998888") == {"step": "escolhendo_vaga"}


async def test_fluxo_completo_reservar_conversa_confirma_vaga(client_as_admin, db_session, monkeypatch):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "S2-49")
    )
    assert resp.status_code == 200
    assert "reservada" in enviados[-1][1]

    from app.services.whatsapp_estado import obter_estado

    assert await obter_estado("5511999998888") is None  # estado limpo após confirmar


async def test_escolher_vaga_inexistente_durante_a_conversa_avisa_e_limpa_estado(
    client_as_admin, db_session, monkeypatch
):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "S2-99")
    )
    assert resp.status_code == 200
    assert "não encontrada" in enviados[-1][1]

    from app.services.whatsapp_estado import obter_estado

    assert await obter_estado("5511999998888") is None


async def test_numero_nao_cadastrado_nao_ativa_fluxo_de_texto_livre(client_as_admin, monkeypatch):
    from app.routers import webhook_whatsapp

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511900000000", "reservar")
    )
    assert resp.status_code == 200
    assert enviados == []
