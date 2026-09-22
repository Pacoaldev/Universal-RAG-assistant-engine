"""
Pruebas para los endpoints de la API FastAPI.
"""

from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_root_endpoint():
    """Verifica que el endpoint raíz responda correctamente."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data


def test_health_endpoint():
    """Verifica el estado de salud del servicio."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "assistant_name" in data


def test_chat_endpoint():
    """Verifica el endpoint /api/chat con una consulta válida."""
    payload = {"query": "¿Cuáles son los horarios de atención?"}
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "processing_time_ms" in data


def test_chat_endpoint_validation():
    """Verifica que peticiones con query vacía sean rechazadas."""
    payload = {"query": ""}
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 422  # Unprocessable Entity
