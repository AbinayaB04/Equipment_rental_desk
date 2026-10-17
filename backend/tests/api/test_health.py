from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

ALLOWED_ORIGIN = "http://localhost:5173"


def make_client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="",
        cors_origins=(ALLOWED_ORIGIN,),
        log_level="INFO",
    )
    return TestClient(create_app(settings))


def test_health_returns_ok():
    response = make_client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_allows_a_configured_origin():
    response = make_client().get("/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_health_does_not_allow_an_unlisted_origin():
    response = make_client().get("/health", headers={"Origin": "http://evil.example"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
