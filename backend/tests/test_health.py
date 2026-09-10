from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_vagas_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/vagas")
    assert response.status_code == 403  # HTTPBearer sem credenciais
