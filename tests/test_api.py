"""
Тесты для API endpoints.
"""
from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """Тест корневого endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "AI Customer Support Platform API"
    assert data["version"] == "0.1.0"
    assert data["status"] == "running"


def test_health_check(client: TestClient):
    """Тест health check endpoint."""
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "version" in data
    assert "checks" in data
    assert data["version"] == "0.1.0"


def test_liveness_probe(client: TestClient):
    """Тест liveness probe."""
    response = client.get("/health/liveness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


def test_readiness_probe(client: TestClient):
    """Тест readiness probe."""
    response = client.get("/health/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


def test_supported_platforms(client: TestClient):
    """Тест получения поддерживаемых платформ."""
    response = client.get("/api/v1/integration/platforms")
    assert response.status_code == 200
    platforms = response.json()
    assert isinstance(platforms, list)
    assert "wildberries" in platforms
    assert "telegram" in platforms
    assert "yandex-alice" in platforms


def test_chat_endpoint_missing_data(client: TestClient):
    """Тест chat endpoint с отсутствующими данными."""
    response = client.post("/api/v1/conversation/chat", json={})
    assert response.status_code == 422  # Validation error


def test_webhook_url_generation(client: TestClient):
    """Тест генерации URL для webhook."""
    platform = "telegram"
    response = client.get(f"/api/v1/integration/webhook-url/{platform}")
    assert response.status_code == 200
    data = response.json()
    assert "webhook_url" in data
    assert "platform" in data
    assert data["platform"] == platform
    assert "instructions" in data
