from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_liveness() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_ok(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "check_db_connection", lambda: True)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_not_ready(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "check_db_connection", lambda: False)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_readiness_checks_redis_when_async_backend_is_redis(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "async_backend", "redis")
    monkeypatch.setattr(main_module, "check_db_connection", lambda: True)
    monkeypatch.setattr(main_module, "check_redis_connection", lambda: False)
    response = client.get("/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["redis"] == "down"


def test_readiness_reports_redis_ok_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "async_backend", "redis")
    monkeypatch.setattr(main_module, "check_db_connection", lambda: True)
    monkeypatch.setattr(main_module, "check_redis_connection", lambda: True)
    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["redis"] == "ok"
