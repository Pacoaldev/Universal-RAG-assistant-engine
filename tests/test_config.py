"""
Pruebas para el módulo de configuración.
"""

from src.core.config import Settings


def test_default_settings():
    """Verifica que las configuraciones por defecto sean seguras y no fallen."""
    custom_settings = Settings(
        ASSISTANT_NAME="Test Bot",
        ORGANIZATION_NAME="Test Corp",
        STORAGE_TYPE="local",
        LLM_PROVIDER="mock"
    )

    assert custom_settings.ASSISTANT_NAME == "Test Bot"
    assert custom_settings.ORGANIZATION_NAME == "Test Corp"
    assert custom_settings.STORAGE_TYPE == "local"
    assert custom_settings.LLM_PROVIDER == "mock"
    assert "Test Corp" in custom_settings.default_system_prompt
