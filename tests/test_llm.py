"""
Pruebas para los clientes LLM.
"""

from src.llm.mock_client import MockLLMClient


def test_mock_llm_client():
    """Verifica el comportamiento del cliente mock offline."""
    client = MockLLMClient(prefix="[Test]")

    assert client.validate_input("Hola") is True
    assert client.validate_input("") is False
    assert client.validate_input("   ") is False
    assert client.validate_input("a" * 3000) is False

    response = client.generate_response("¿Tienen vacunas?")
    assert "[Test]" in response
    assert "vacunación" in response.lower()
