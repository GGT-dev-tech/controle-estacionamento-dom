from fastapi.testclient import TestClient

from app.main import app


def test_vagas_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/vagas")
    assert response.status_code == 403  # HTTPBearer sem credenciais


async def test_health_ok_quando_dependencias_disponiveis(client_as_admin, monkeypatch):
    from app.services import redis_cache

    class _RedisFalso:
        async def ping(self) -> bool:
            return True

    monkeypatch.setattr(redis_cache, "get_redis", lambda: _RedisFalso())

    resp = await client_as_admin.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok", "redis": "ok"}


async def test_health_degradado_quando_redis_indisponivel(client_as_admin, monkeypatch):
    from redis import RedisError

    from app.services import redis_cache

    monkeypatch.setattr(redis_cache, "get_redis", lambda: (_ for _ in ()).throw(RedisError()))

    resp = await client_as_admin.get("/health")
    assert resp.status_code == 503
    dados = resp.json()
    assert dados["status"] == "degradado"
    assert dados["database"] == "ok"
    assert dados["redis"] == "erro"
