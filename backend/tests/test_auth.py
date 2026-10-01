"""Optional deployment access control must protect operational endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

import app.main as main_module


@pytest.fixture()
def protected_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OCEANAID_API_KEY", "test-shared-key")
    monkeypatch.delenv("AQUASENSE_API_KEY", raising=False)
    with TestClient(main_module.app) as client:
        yield client


def test_operational_http_endpoint_requires_configured_key(protected_client: TestClient) -> None:
    denied = protected_client.get("/v1/surveys")
    assert denied.status_code == 401

    allowed = protected_client.get(
        "/v1/surveys",
        headers={"X-API-Key": "test-shared-key"},
    )
    assert allowed.status_code == 200
    assert protected_client.get("/v1/surveys?api_key=test-shared-key").status_code == 200


def test_service_metadata_remains_available_without_key(protected_client: TestClient) -> None:
    assert protected_client.get("/").status_code == 200


def test_cors_preflight_does_not_require_api_key(protected_client: TestClient) -> None:
    response = protected_client.options(
        "/v1/surveys",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_websocket_requires_configured_key(protected_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as denied:
        with protected_client.websocket_connect("/v1/surveys/survey-auth/stream"):
            pass
    assert denied.value.code == 1008

    with protected_client.websocket_connect(
        "/v1/surveys/survey-auth/stream?api_key=test-shared-key"
    ) as websocket:
        assert websocket.receive_json()["event"] == "stream.ready"
