"""Pruebas para los endpoints de la API FastAPI."""

import importlib


def test_import_does_not_raise_when_google_api_key_missing(monkeypatch):
    """SPEC §server-boot: importar src.api.app no debe ejecutar construcción."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    import src.api.app as app_module
    importlib.reload(app_module)
    assert app_module.app.state.assistant is None  # aún no se construyó
    assert hasattr(app_module.app, "router")


async def test_health_responds_200_without_google_api_key(client):
    """SPEC §server-boot: server boots and /health returns 200 with no key."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["llm_provider"] == "MockLLMClient"


async def test_chat_returns_deterministic_answer_in_mock_mode(client):
    """SPEC §mock-fallback: determinista, sin GOOGLE_API_KEY, prefijo + keyword."""
    response = await client.post(
        "/api/chat", json={"query": "¿Cuáles son los horarios de atención?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("[Fallback Mode]")
    assert "horario" in data["answer"].lower()


async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data


async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "assistant_name" in data


async def test_chat_endpoint(client):
    payload = {"query": "¿Cuáles son los horarios de atención?"}
    response = await client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "processing_time_ms" in data


async def test_chat_endpoint_validation(client):
    payload = {"query": ""}
    response = await client.post("/api/chat", json=payload)
    assert response.status_code == 422
