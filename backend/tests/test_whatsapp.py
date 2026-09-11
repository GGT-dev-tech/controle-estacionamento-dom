import pytest

from app.services.whatsapp import processar_comando, processar_mensagem


@pytest.fixture(autouse=True)
def _sem_redis(monkeypatch):
    from redis import RedisError

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))


async def _criar_vaga(client, vaga_id):
    resp = await client.post("/vagas", json={"id": vaga_id, "numero": vaga_id.split("-")[1], "andar": "S2"})
    assert resp.status_code == 201


async def test_comando_ajuda(client_as_admin, db_session):
    async with db_session() as session:
        resposta = await processar_comando("11999998888", "/ajuda", session)
    assert "Comandos" in resposta


async def test_comando_vagas_lista(client_as_admin, db_session):
    await _criar_vaga(client_as_admin, "S2-49")
    async with db_session() as session:
        resposta = await processar_comando("11999998888", "/vagas", session)
    assert "S2-49" in resposta


async def test_fluxo_reservar_e_cancelar_via_whatsapp(client_as_admin, db_session, monkeypatch):
    # /reservar agora pergunta a duração antes de confirmar — precisa de um Redis de
    # verdade (fake em memória) pra lembrar o passo entre as duas mensagens; o resto do
    # arquivo usa o fixture _sem_redis (fail-open) porque não depende de estado.
    import fakeredis.aioredis

    from app.services import whatsapp_estado

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(whatsapp_estado, "get_redis", lambda: fake)

    await _criar_vaga(client_as_admin, "S2-50")
    telefone = "11999998888"

    async with db_session() as session:
        resposta = await processar_comando(telefone, "/reservar S2-50", session)
    assert "por quanto tempo" in resposta.lower()

    async with db_session() as session:
        resposta = await processar_mensagem(telefone, "1", session)
    assert "reservada" in resposta.lower()

    vaga = (await client_as_admin.get("/vagas/S2-50")).json()
    assert vaga["status"] == "reservada"

    async with db_session() as session:
        resposta_cancelar = await processar_comando(telefone, "/cancelar S2-50", session)
    assert "cancelada" in resposta_cancelar.lower()

    vaga_livre = (await client_as_admin.get("/vagas/S2-50")).json()
    assert vaga_livre["status"] == "livre"


async def test_comando_reservar_vaga_inexistente(client_as_admin, db_session):
    async with db_session() as session:
        resposta = await processar_comando("11999998888", "/reservar S2-999", session)
    assert "não encontrada" in resposta.lower()


async def test_comando_status_placa(client_as_admin, db_session):
    await _criar_vaga(client_as_admin, "S2-51")
    await client_as_admin.post(
        "/movimentacoes/entrada",
        json={"vaga_id": "S2-51", "nome": "Ana", "placa": "AAA1111", "veiculo": "Onix", "tipo_cliente": "rotativo"},
    )
    async with db_session() as session:
        resposta = await processar_comando("11999998888", "/status AAA1111", session)
    assert "S2-51" in resposta


async def test_comando_desconhecido(client_as_admin, db_session):
    async with db_session() as session:
        resposta = await processar_comando("11999998888", "/oi", session)
    assert "não reconhecido" in resposta.lower()
