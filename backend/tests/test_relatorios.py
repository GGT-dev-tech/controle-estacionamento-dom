import pytest


@pytest.fixture(autouse=True)
def _sem_redis(monkeypatch):
    from redis import RedisError

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))


async def test_relatorio_diario_requer_admin(client_as_operador):
    resp = await client_as_operador.get("/relatorios/diario")
    assert resp.status_code == 403


async def test_relatorio_diario_conta_vagas(client_as_admin):
    await client_as_admin.post("/vagas", json={"id": "S2-60", "numero": "60", "andar": "S2"})
    await client_as_admin.post("/vagas", json={"id": "S2-61", "numero": "61", "andar": "S2"})
    await client_as_admin.post(
        "/movimentacoes/entrada",
        json={"vaga_id": "S2-60", "nome": "Ana", "placa": "AAA1111", "veiculo": "Onix", "tipo_cliente": "rotativo"},
    )

    resp = await client_as_admin.get("/relatorios/diario")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["total_vagas"] == 2
    assert dados["ocupadas"] == 1
    assert dados["livres"] == 1
    assert dados["entradas_hoje"] == 1


async def test_enviar_relatorio_diario_requer_cron_secret(client_as_admin, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "cron_secret", "segredo-cron")
    monkeypatch.setattr(settings, "relatorio_destinatarios", "admin@dompagamentos.com.br")

    resp_sem_header = await client_as_admin.post("/relatorios/diario/enviar")
    assert resp_sem_header.status_code == 404

    resp_ok = await client_as_admin.post("/relatorios/diario/enviar", headers={"X-Cron-Secret": "segredo-cron"})
    assert resp_ok.status_code == 200
    # Sem RESEND_API_KEY configurado nos testes, o envio falha graciosamente (sem exceção).
    assert resp_ok.json()["enviado"] is False


async def test_historico_retorna_serie_diaria(client_as_admin):
    await client_as_admin.post("/vagas", json={"id": "S2-62", "numero": "62", "andar": "S2"})
    await client_as_admin.post(
        "/movimentacoes/entrada",
        json={"vaga_id": "S2-62", "nome": "Bia", "placa": "BBB2222", "veiculo": "HB20", "tipo_cliente": "visitante"},
    )

    resp = await client_as_admin.get("/relatorios/historico?dias=3")
    assert resp.status_code == 200
    dias = resp.json()
    assert len(dias) == 3
    assert dias[-1]["entradas"] == 1


async def test_exportar_movimentacoes_csv(client_as_admin):
    await client_as_admin.post("/vagas", json={"id": "S2-63", "numero": "63", "andar": "S2"})
    await client_as_admin.post(
        "/movimentacoes/entrada",
        json={"vaga_id": "S2-63", "nome": "Caio", "placa": "CCC3333", "veiculo": "Kwid", "tipo_cliente": "rotativo"},
    )

    resp = await client_as_admin.get("/relatorios/movimentacoes/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    assert "CCC3333" in resp.text


async def test_exportar_relatorio_diario_pdf(client_as_admin):
    resp = await client_as_admin.get("/relatorios/diario/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
