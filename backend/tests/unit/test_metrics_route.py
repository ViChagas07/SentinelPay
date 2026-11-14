import httpx
import pytest

from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit


async def _request(app: object, path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers)


async def test_metrics_requires_credential() -> None:
    app = create_app(Settings(app_env="local", metrics_token="metrics-secret"))
    app.state.metrics.record_http_request("GET", "/health", 200, 0.01)

    missing = await _request(app, "/metrics")
    wrong = await _request(app, "/metrics", headers={"Authorization": "Bearer nope"})

    assert missing.status_code == 401
    assert missing.json()["code"] == "metrics_unauthorized"
    assert missing.headers["www-authenticate"] == "Bearer"
    assert wrong.status_code == 401


async def test_metrics_accepts_bearer_and_header_token() -> None:
    app = create_app(Settings(app_env="local", metrics_token="metrics-secret"))
    app.state.metrics.record_http_request("GET", "/health", 200, 0.01)

    bearer = await _request(
        app,
        "/metrics",
        headers={"Authorization": "Bearer metrics-secret"},
    )
    header = await _request(
        app,
        "/metrics",
        headers={"X-Metrics-Token": "metrics-secret"},
    )

    assert bearer.status_code == 200
    assert bearer.headers["content-type"].startswith("text/plain")
    assert "paysentineliq_http_requests_total" in bearer.text
    assert 'route="/health"' in bearer.text
    assert header.status_code == 200


async def test_request_middleware_records_http_metrics() -> None:
    app = create_app(Settings(app_env="local", metrics_token="metrics-secret"))

    response = await _request(app, "/health")

    assert response.status_code == 200
    text = app.state.metrics.render().decode("utf-8")
    assert "paysentineliq_http_requests_total" in text
    assert 'route="/health"' in text
    assert 'status="200"' in text
    assert "paysentineliq_http_request_duration_seconds_count" in text


async def test_metrics_never_contains_pii_labels() -> None:
    app = create_app(Settings(app_env="local", metrics_token="metrics-secret"))
    app.state.metrics.record_analysis("boleto", "low")

    response = await _request(
        app,
        "/metrics",
        headers={"X-Metrics-Token": "metrics-secret"},
    )

    assert response.status_code == 200
    assert "@" not in response.text
    assert "user_id=" not in response.text
    assert "document_id=" not in response.text
