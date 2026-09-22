"""
Factoría para instanciar clientes LLM según configuración.
"""

from typing import Optional

from src.core.config import settings
from src.core.logger import get_logger
from src.llm.base import BaseLLMClient
from src.llm.mock_client import MockLLMClient

logger = get_logger("llm.factory")


def get_llm_client(provider: Optional[str] = None) -> BaseLLMClient:
    """
    Retorna el cliente LLM configurado.

    Args:
        provider: 'gemini' o 'mock'. Si es None, usa settings.LLM_PROVIDER.
    """
    prov = (provider or settings.LLM_PROVIDER).lower()

    if prov == "gemini":
        try:
            from src.llm.gemini_client import GeminiClient

            return GeminiClient()
        except Exception as e:
            logger.warning(
                f"No se pudo inicializar GeminiClient ({e}). Fallback automático a MockLLMClient."
            )
            return MockLLMClient(prefix="[Fallback Mode]")

    return MockLLMClient()
