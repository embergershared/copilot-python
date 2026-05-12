from copilot_python_app.config import Settings
from copilot_python_app.health import get_health


def test_health_response_uses_settings() -> None:
    settings = Settings(name="example", environment="test", version="1.2.3")

    response = get_health(settings)

    assert response.model_dump() == {
        "status": "ok",
        "service": "example",
        "environment": "test",
        "version": "1.2.3",
    }

