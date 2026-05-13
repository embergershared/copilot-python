from fastapi.testclient import TestClient

from copilot_python_app.config import Settings
from copilot_python_app.main import create_app


def test_root_endpoint() -> None:
    app = create_app(Settings(name="example", environment="test", version="1.2.3"))
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"service": "example", "status": "ok"}


def test_health_endpoint() -> None:
    app = create_app(Settings(name="example", environment="test", version="1.2.3"))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "example",
        "environment": "test",
        "version": "1.2.3",
    }

