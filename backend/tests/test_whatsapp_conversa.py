import pytest
from sqlalchemy import select

from app.models.cliente import Cliente
from app.models.ocupante import TipoCliente
from app.models.vaga import StatusVaga, Vaga
from app.models.veiculo import Veiculo


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


async def _criar_veiculo(db_session, telefone: str, placa: str, veiculo: str) -> None:
    async with db_session() as db:
        cliente = (await db.execute(select(Cliente).where(Cliente.telefone == telefone))).scalar_one()
        db.add(Veiculo(cliente_id=cliente.id, placa=placa, veiculo=veiculo))
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


async def test_segunda_tentativa_de_reserva_na_mesma_vaga_recebe_mensagem_de_conflito(
    client_as_admin, db_session, monkeypatch
):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session, telefone="11999998888")
    await _criar_cliente(db_session, telefone="11988887777")
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    # Dois clientes diferentes iniciam a conversa e escolhem a MESMA vaga.
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511988887777", "reservar"))

    resp1 = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "S2-49")
    )
    resp2 = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511988887777", "S2-49")
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert "reservada" in enviados[-2][1]
    assert "reservada por outra pessoa" in enviados[-1][1]


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


async def test_reserva_com_cadastro_mas_sem_veiculo_usa_nome_do_cadastro_sem_placa(
    client_as_admin, db_session, monkeypatch
):
    """Cliente cadastrado (ex.: só pelo admin) mas sem veículo ainda: nome já vem do
    cadastro, mas não há placa pra escolher sozinho — igual antes da Fase B."""
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "S2-49"))

    reservas = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})).json()
    assert reservas[0]["placa"] is None
    assert reservas[0]["nome"] == "Cliente Teste"


async def test_reserva_conversacional_usa_veiculo_cadastrado_automaticamente(
    client_as_admin, db_session, monkeypatch
):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_veiculo(db_session, "11999998888", "ABC1234", "Fiat Argo")
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

    reservas = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})).json()
    assert reservas[0]["placa"] == "ABC1234"
    assert reservas[0]["nome"] == "Cliente Teste"


async def test_reserva_com_dois_veiculos_pergunta_qual_usar_e_confirma_com_a_escolha(
    client_as_admin, db_session, monkeypatch
):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_veiculo(db_session, "11999998888", "ABC1234", "Fiat Argo")
    await _criar_veiculo(db_session, "11999998888", "XYZ5678", "Onix")
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    resp_vaga = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "S2-49")
    )
    assert resp_vaga.status_code == 200
    assert "ABC1234" in enviados[-1][1] and "XYZ5678" in enviados[-1][1]

    resp_placa = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "XYZ5678")
    )
    assert resp_placa.status_code == 200
    assert "reservada" in enviados[-1][1]

    reservas = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})).json()
    assert reservas[0]["placa"] == "XYZ5678"


async def test_placa_invalida_ao_escolher_veiculo_pede_de_novo(client_as_admin, db_session, monkeypatch):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_veiculo(db_session, "11999998888", "ABC1234", "Fiat Argo")
    await _criar_veiculo(db_session, "11999998888", "XYZ5678", "Onix")
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "S2-49"))

    resp_errada = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "QQQ0000")
    )
    assert resp_errada.status_code == 200
    assert "Não reconheci" in enviados[-1][1]

    resp_certa = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "ABC1234")
    )
    assert resp_certa.status_code == 200
    assert "reservada" in enviados[-1][1]

    reservas = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})).json()
    assert reservas[0]["placa"] == "ABC1234"


async def test_comando_classico_reservar_tambem_pergunta_veiculo_se_tiver_mais_de_um(
    client_as_admin, db_session, monkeypatch
):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_veiculo(db_session, "11999998888", "ABC1234", "Fiat Argo")
    await _criar_veiculo(db_session, "11999998888", "XYZ5678", "Onix")
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "/reservar S2-49")
    )
    assert resp.status_code == 200
    assert "ABC1234" in enviados[-1][1] and "XYZ5678" in enviados[-1][1]
