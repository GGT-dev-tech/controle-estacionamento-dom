from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.cliente import Cliente
from app.models.ocupante import TipoCliente
from app.models.reserva import Reserva
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
    assert await obter_estado("5511999998888") == {
        "step": "escolhendo_vaga",
        "vagas": ["S2-49"],
        "acao": "reservar",
    }


async def test_reservar_escolhendo_pelo_numero_da_lista(client_as_admin, db_session, monkeypatch):
    """Caminho principal da lista numerada: responde só com o número, não o código da
    vaga — bem mais rápido de digitar, e é o que a mensagem da lista já instrui a fazer."""
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")
    await _criar_vaga(db_session, "S2-50")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    assert "1. S2-49" in enviados[-1][1]
    assert "2. S2-50" in enviados[-1][1]

    resp = await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "2"))
    assert resp.status_code == 200
    assert "por quanto tempo" in enviados[-1][1].lower()

    resp_tempo = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1")
    )
    assert "reservada" in enviados[-1][1]

    reservas = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-50"})).json()
    assert len(reservas) == 1  # escolheu a opção 2 (S2-50), não a 1 (S2-49)


async def test_numero_fora_do_intervalo_pede_de_novo_sem_perder_a_lista(client_as_admin, db_session, monkeypatch):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    resp = await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "99"))
    assert resp.status_code == 200
    assert "número inválido" in enviados[-1][1].lower()

    from app.services.whatsapp_estado import obter_estado

    # a lista continua disponível — não precisa reiniciar a conversa por causa de um número errado
    assert await obter_estado("5511999998888") == {
        "step": "escolhendo_vaga",
        "vagas": ["S2-49"],
        "acao": "reservar",
    }

    resp_certo = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1")
    )
    assert "por quanto tempo" in enviados[-1][1].lower()


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
    assert "por quanto tempo" in enviados[-1][1].lower()

    resp_tempo = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1")
    )
    assert resp_tempo.status_code == 200
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
    # Nenhum dos dois sabe ainda que a vaga foi disputada — os dois recebem a pergunta de
    # duração; o conflito só é resolvido (com lock) quando cada um efetivamente confirma.
    assert "por quanto tempo" in enviados[-2][1].lower()
    assert "por quanto tempo" in enviados[-1][1].lower()

    resp1_tempo = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1")
    )
    resp2_tempo = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511988887777", "1")
    )
    assert resp1_tempo.status_code == 200
    assert resp2_tempo.status_code == 200
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
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1"))

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
    assert "por quanto tempo" in enviados[-1][1].lower()

    resp_tempo = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1")
    )
    assert resp_tempo.status_code == 200
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
    assert "por quanto tempo" in enviados[-1][1].lower()

    resp_tempo = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1")
    )
    assert resp_tempo.status_code == 200
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
    assert "por quanto tempo" in enviados[-1][1].lower()

    resp_tempo = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1")
    )
    assert resp_tempo.status_code == 200
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


async def _criar_reserva_prestes_a_vencer(db_session, telefone: str = "5511999998888", vaga_id: str = "S2-49") -> int:
    async with db_session() as db:
        vaga = await db.get(Vaga, vaga_id)
        vaga.status = StatusVaga.reservada
        reserva = Reserva(
            vaga_id=vaga_id,
            nome="Cliente Teste",
            telefone=telefone,
            inicio=datetime.utcnow() - timedelta(minutes=10),
            fim=datetime.utcnow() + timedelta(minutes=5),
            status="ativa",
            canal="whatsapp",
            lembrete_enviado=True,
        )
        db.add(reserva)
        await db.commit()
        await db.refresh(reserva)
        return reserva.id


async def test_confirmar_extensao_de_reserva_perto_do_vencimento(client_as_admin, db_session, monkeypatch):
    from app.routers import webhook_whatsapp
    from app.services.whatsapp_estado import definir_estado

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")
    reserva_id = await _criar_reserva_prestes_a_vencer(db_session)
    await definir_estado("5511999998888", {"step": "confirmando_reserva", "reserva_id": reserva_id})

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "sim"))
    assert resp.status_code == 200
    assert "estendida" in enviados[-1][1]

    async with db_session() as db:
        atualizada = await db.get(Reserva, reserva_id)
        assert atualizada.fim > datetime.utcnow() + timedelta(minutes=10)
        assert atualizada.lembrete_enviado is False


async def test_resposta_negativa_ao_lembrete_nao_altera_a_reserva(client_as_admin, db_session, monkeypatch):
    from app.routers import webhook_whatsapp
    from app.services.whatsapp_estado import definir_estado

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")
    reserva_id = await _criar_reserva_prestes_a_vencer(db_session)
    fim_original_resp = await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})
    fim_original = fim_original_resp.json()[0]["fim"]
    await definir_estado("5511999998888", {"step": "confirmando_reserva", "reserva_id": reserva_id})

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "não vou"))
    assert resp.status_code == 200
    assert "liberada automaticamente" in enviados[-1][1]

    depois_resp = await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})
    assert depois_resp.json()[0]["fim"] == fim_original


async def test_ocupar_vaga_livre_direto_pelo_codigo(client_as_admin, db_session, monkeypatch):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_veiculo(db_session, "11999998888", "ABC1234", "Fiat Argo")
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "/ocupar S2-49")
    )
    assert resp.status_code == 200
    assert "ocupada" in enviados[-1][1].lower()

    vaga = (await client_as_admin.get("/vagas/S2-49")).json()
    assert vaga["status"] == "ocupada"
    assert vaga["ocupante"]["placa"] == "ABC1234"


async def test_ocupar_sem_veiculo_cadastrado_pede_pra_completar_cadastro(client_as_admin, db_session, monkeypatch):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "/ocupar S2-49")
    )
    assert resp.status_code == 200
    assert "veículo cadastrado" in enviados[-1][1].lower()

    vaga = (await client_as_admin.get("/vagas/S2-49")).json()
    assert vaga["status"] == "livre"


async def test_ocupar_sem_argumento_confirma_chegada_de_reserva_ativa(client_as_admin, db_session, monkeypatch):
    """/ocupar sozinho, com uma reserva ativa em nome do cliente, confirma a chegada nela
    direto — nem precisa escolher a vaga, é a mesma coisa que "confirmar chegada" no app."""
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
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1"))
    assert "reservada" in enviados[-1][1].lower()

    resp = await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "/ocupar"))
    assert resp.status_code == 200
    assert "ocupada" in enviados[-1][1].lower()

    vaga = (await client_as_admin.get("/vagas/S2-49")).json()
    assert vaga["status"] == "ocupada"


async def test_cliente_nao_ocupa_reserva_de_outro_cliente_via_whatsapp(client_as_admin, db_session, monkeypatch):
    """Mesma proteção que já existe pelo app (services/sync.py: _cliente_do_operador)
    agora também vale pelo bot — antes, o sub sintético "whatsapp:<telefone>" nunca batia
    com nenhum Cliente.auth0_sub e a checagem tratava qualquer cliente pelo WhatsApp como
    staff sem restrição."""
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session, telefone="11911110000")
    await _criar_veiculo(db_session, "11911110000", "AAA1111", "Onix")
    await _criar_cliente(db_session, telefone="11922220000")
    await _criar_veiculo(db_session, "11922220000", "BBB2222", "Gol")
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    # Cliente A reserva.
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511911110000", "reservar"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511911110000", "1"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511911110000", "1"))
    assert "reservada" in enviados[-1][1].lower()

    # Cliente B tenta ocupar por cima, com o próprio veículo (placa diferente da reserva).
    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511922220000", "/ocupar S2-49")
    )
    assert resp.status_code == 200
    assert "reservada por outro cliente" in enviados[-1][1].lower()

    vaga = (await client_as_admin.get("/vagas/S2-49")).json()
    assert vaga["status"] == "reservada"


async def test_comando_barra_sai_do_fluxo_de_escolha_de_vaga_e_atende_o_comando(
    client_as_admin, db_session, monkeypatch
):
    """Antes: com um número fora do intervalo, qualquer coisa que o cliente mandasse
    depois (inclusive "/ajuda") era interpretada como parte do fluxo antigo — ele ficava
    sem saída, precisando esperar o estado expirar (5 min) pra conseguir fazer qualquer
    outra coisa. Agora um comando "/" a qualquer momento sai do fluxo e atende de verdade."""
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    resp_errado = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "99")
    )
    assert "número inválido" in enviados[-1][1].lower()
    assert "S2-49" in enviados[-1][1]  # lista atualizada, não só um aviso genérico

    resp_ajuda = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "/ajuda")
    )
    assert resp_ajuda.status_code == 200
    assert "Comandos" in enviados[-1][1]

    from app.services.whatsapp_estado import obter_estado

    assert await obter_estado("5511999998888") is None


async def test_comando_barra_sai_do_fluxo_de_escolha_de_tempo(client_as_admin, db_session, monkeypatch):
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")
    await _criar_vaga(db_session, "S2-50")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "1"))
    assert "por quanto tempo" in enviados[-1][1].lower()

    # Em vez de responder 1-4, manda outro comando — deve trocar de fluxo, não travar.
    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "/vagas")
    )
    assert resp.status_code == 200
    assert "S2-49" in enviados[-1][1] and "S2-50" in enviados[-1][1]

    vaga = (await client_as_admin.get("/vagas/S2-49")).json()
    assert vaga["status"] == "livre"  # nunca chegou a reservar, o fluxo foi abandonado


async def test_comando_barra_sai_do_fluxo_de_confirmar_extensao_de_reserva(
    client_as_admin, db_session, monkeypatch
):
    from app.routers import webhook_whatsapp
    from app.services.whatsapp_estado import definir_estado

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")
    reserva_id = await _criar_reserva_prestes_a_vencer(db_session)
    await definir_estado("5511999998888", {"step": "confirmando_reserva", "reserva_id": reserva_id})

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    resp = await client_as_admin.post(
        "/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "/ajuda")
    )
    assert resp.status_code == 200
    assert "Comandos" in enviados[-1][1]

    # a reserva não foi mexida (nem estendida, nem afetada) — só saiu do fluxo de pergunta
    reservas = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-49"})).json()
    assert reservas[0]["status"] == "ativa"


async def test_conflito_de_concorrencia_na_reserva_mostra_lista_atualizada(
    client_as_admin, db_session, monkeypatch
):
    """Dois clientes escolhem a mesma vaga (opção 1) quase ao mesmo tempo — um deles
    confirma primeiro, o outro esbarra no conflito só na hora de confirmar a duração
    (aplicar_reserva é onde a concorrência é resolvida de verdade). Antes disso, o
    segundo cliente via só um texto genérico "escolha outra", sem nenhuma lista — agora
    a mensagem já vem com o painel atualizado (a vaga que sumiu não aparece mais)."""
    from app.routers import webhook_whatsapp

    await _criar_cliente(db_session, telefone="11911110000")
    await _criar_cliente(db_session, telefone="11922220000")
    await _criar_vaga(db_session, "S2-49")
    await _criar_vaga(db_session, "S2-50")

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    # Os dois começam o fluxo e escolhem a opção 1 (S2-49) antes de qualquer um confirmar.
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511911110000", "reservar"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511922220000", "reservar"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511911110000", "1"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511922220000", "1"))

    # Cliente A confirma a duração primeiro — reserva S2-49 com sucesso.
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511911110000", "1"))
    assert "reservada" in enviados[-1][1].lower()

    # Cliente B confirma depois — ainda achava que a opção 1 era S2-49, mas ela já foi.
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511922220000", "1"))
    resposta_b = enviados[-1][1]
    assert "reservada por outra pessoa" in resposta_b.lower()
    assert "lista atualizada" in resposta_b.lower()
    assert "S2-50" in resposta_b
    assert "1. S2-49" not in resposta_b  # a que sumiu não aparece mais como opção

    # Cliente B consegue escolher a vaga restante imediatamente, sem reiniciar a conversa.
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511922220000", "1"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511922220000", "1"))
    assert "reservada" in enviados[-1][1].lower()

    reservas_50 = (await client_as_admin.get("/reservas", params={"vaga_id": "S2-50"})).json()
    assert len(reservas_50) == 1
    assert reservas_50[0]["telefone"] == "11922220000"


async def test_mensagem_de_reserva_confirmada_mostra_horario_de_brasilia_nao_utc(
    client_as_admin, db_session, monkeypatch
):
    """Bug real reportado: a mensagem de confirmação mostrava a hora UTC crua (3h à
    frente da hora de Brasília) em vez de converter — ex.: reserva feita "as 14h" (BRT)
    aparecia como "até 18h" numa reserva de 2h. Trava a hora "atual" pra testar a
    conversão de forma determinística."""
    from app.routers import webhook_whatsapp
    from app.services import whatsapp as whatsapp_service

    await _criar_cliente(db_session)
    await _criar_vaga(db_session, "S2-49")

    class _DatetimeFixo(datetime):
        @classmethod
        def utcnow(cls):
            return datetime(2026, 1, 15, 18, 0, 0)  # 18:00 UTC == 15:00 em Brasília

    monkeypatch.setattr(whatsapp_service, "datetime", _DatetimeFixo)

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(webhook_whatsapp, "enviar_mensagem", _fake_enviar)

    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "reservar"))
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "S2-49"))
    # Opção "4" = 2 horas => fim = 18:00 UTC + 2h = 20:00 UTC = 17:00 em Brasília.
    await client_as_admin.post("/webhook/whatsapp/segredo-correto", json=_payload("5511999998888", "4"))

    assert "até 17:00" in enviados[-1][1]
    assert "até 20:00" not in enviados[-1][1]
