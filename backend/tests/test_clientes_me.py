import pytest

ROLE_CLAIM = "https://estacionamento.dom/role"
_OUTRA_PESSOA = {"sub": "google-oauth2|outra-pessoa-teste", ROLE_CLAIM: "operador"}
_ADMIN = {"sub": "auth0|admin-teste", ROLE_CLAIM: "admin"}


def _autenticar_como(usuario: dict) -> None:
    """Troca a identidade autenticada no meio do teste (mesma app, mesma conexão).

    client_as_admin e client_as_operador não podem ser usados juntos num mesmo teste —
    os dois sobrescrevem a mesma chave global (app.dependency_overrides[get_current_user]),
    então o que vale na hora da requisição é sempre o último fixture cujo setup rodou, não
    qual client foi chamado. Pra simular duas identidades diferentes agindo em sequência,
    trocamos essa entrada manualmente dentro do teste, usando um único client.
    """
    from app.main import app
    from app.security.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: usuario


@pytest.fixture(autouse=True)
def _sem_redis(monkeypatch):
    from redis import RedisError

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))


@pytest.fixture(autouse=True)
def _mock_whatsapp(monkeypatch):
    from app.routers import clientes as clientes_router

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    monkeypatch.setattr(clientes_router, "enviar_mensagem", _fake_enviar)
    return enviados


async def test_get_me_sem_cadastro_retorna_404(client_as_operador):
    resp = await client_as_operador.get("/clientes/me")
    assert resp.status_code == 404


async def test_criar_meu_cadastro(client_as_operador, _mock_whatsapp):
    resp = await client_as_operador.post(
        "/clientes/me", json={"nome": "Fulano", "telefone": "11999998888", "email": "fulano@dompagamentos.com"}
    )
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["nome"] == "Fulano"
    assert corpo["telefone"] == "11999998888"
    assert corpo["veiculos"] == []
    assert len(_mock_whatsapp) == 1
    assert "Bem-vindo" in _mock_whatsapp[0][1]

    resp2 = await client_as_operador.get("/clientes/me")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == corpo["id"]


async def test_criar_meu_cadastro_duas_vezes_conflita(client_as_operador):
    await client_as_operador.post("/clientes/me", json={"nome": "Fulano", "telefone": "11999998888"})
    resp = await client_as_operador.post("/clientes/me", json={"nome": "Fulano", "telefone": "11988887777"})
    assert resp.status_code == 409


async def test_adota_cadastro_criado_pelo_admin_por_telefone(client_as_admin):
    _autenticar_como(_ADMIN)
    resp_admin = await client_as_admin.post(
        "/admin/clientes",
        json={"nome": "Pré-cadastro Admin", "telefone": "11977776666", "tipo_cliente": "mensalista"},
    )
    assert resp_admin.status_code == 201

    # Outra pessoa loga pela primeira vez com o mesmo telefone pré-cadastrado pelo admin.
    _autenticar_como(_OUTRA_PESSOA)
    resp = await client_as_admin.post(
        "/clientes/me", json={"nome": "Nome Real", "telefone": "11977776666", "email": "x@dompagamentos.com"}
    )
    assert resp.status_code == 201
    assert resp.json()["nome"] == "Nome Real"

    _autenticar_como(_ADMIN)
    listagem = await client_as_admin.get("/admin/clientes")
    assert len(listagem.json()) == 1  # não duplicou


async def test_telefone_de_outro_cadastro_conflita(client_as_admin):
    _autenticar_como(_ADMIN)
    resp1 = await client_as_admin.post("/clientes/me", json={"nome": "Admin", "telefone": "11911112222"})
    assert resp1.status_code == 201

    _autenticar_como(_OUTRA_PESSOA)
    resp2 = await client_as_admin.post("/clientes/me", json={"nome": "Outra Pessoa", "telefone": "11911112222"})
    assert resp2.status_code == 409


async def test_atualizar_meu_cadastro(client_as_operador):
    await client_as_operador.post("/clientes/me", json={"nome": "Fulano", "telefone": "11999998888"})
    resp = await client_as_operador.patch("/clientes/me", json={"email": "novo@dompagamentos.com"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "novo@dompagamentos.com"


async def test_adicionar_e_remover_veiculo(client_as_operador):
    await client_as_operador.post("/clientes/me", json={"nome": "Fulano", "telefone": "11999998888"})
    resp = await client_as_operador.post(
        "/clientes/me/veiculos", json={"placa": "abc1234", "veiculo": "Fiat Argo"}
    )
    assert resp.status_code == 201
    assert resp.json()["placa"] == "ABC1234"
    veiculo_id = resp.json()["id"]

    meu = await client_as_operador.get("/clientes/me")
    assert len(meu.json()["veiculos"]) == 1

    resp_dup = await client_as_operador.post(
        "/clientes/me/veiculos", json={"placa": "abc1234", "veiculo": "Outro"}
    )
    assert resp_dup.status_code == 409

    resp_del = await client_as_operador.delete(f"/clientes/me/veiculos/{veiculo_id}")
    assert resp_del.status_code == 204

    meu2 = await client_as_operador.get("/clientes/me")
    assert len(meu2.json()["veiculos"]) == 0


async def test_placa_e_opcional_e_dois_veiculos_sem_placa_nao_conflitam(client_as_operador):
    await client_as_operador.post("/clientes/me", json={"nome": "Fulano", "telefone": "11999998888"})

    resp1 = await client_as_operador.post("/clientes/me/veiculos", json={"veiculo": "Bike"})
    assert resp1.status_code == 201
    assert resp1.json()["placa"] is None

    resp2 = await client_as_operador.post("/clientes/me/veiculos", json={"veiculo": "Patinete"})
    assert resp2.status_code == 201
    assert resp2.json()["placa"] is None

    meu = await client_as_operador.get("/clientes/me")
    assert len(meu.json()["veiculos"]) == 2


async def test_nao_remove_veiculo_de_outro_cadastro(client_as_admin):
    _autenticar_como(_ADMIN)
    await client_as_admin.post("/clientes/me", json={"nome": "Admin", "telefone": "11933334444"})
    resp = await client_as_admin.post("/clientes/me/veiculos", json={"placa": "zzz9999", "veiculo": "Onix"})
    veiculo_id = resp.json()["id"]

    _autenticar_como(_OUTRA_PESSOA)
    await client_as_admin.post("/clientes/me", json={"nome": "Operador", "telefone": "11955556666"})
    resp_del = await client_as_admin.delete(f"/clientes/me/veiculos/{veiculo_id}")
    assert resp_del.status_code == 404
