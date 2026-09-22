"""
Adaptador para Google Gemini API.
"""

from typing import Optional

import google.generativeai as genai

from src.core.config import settings
from src.core.logger import get_logger
from src.llm.base import BaseLLMClient

logger = get_logger("llm.gemini")


class GeminiClient(BaseLLMClient):
    """Cliente para la API de Google Gemini."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL

        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY no configurada. Configure la variable de entorno o "
                "use LLM_PROVIDER=mock para modo offline."
            )

        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(self.model_name)
        logger.info(f"GeminiClient configurado con modelo: {self.model_name}")

    def generate_response(self, prompt: str) -> str:
        """Genera respuesta usando Google Gemini con manejo seguro de errores."""
        try:
            response = self._model.generate_content(prompt)

            if response.candidates:
                # Extraer texto de las partes
                parts_text = []
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, "text"):
                                parts_text.append(part.text)
                if parts_text:
                    return "".join(parts_text).strip()

            if response.prompt_feedback and response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason
                logger.warning(f"Respuesta bloqueada por políticas de seguridad: {reason}")
                return f"La respuesta fue restringida por filtros de seguridad ({reason})."

            return "No se pudo generar una respuesta clara en este momento."

        except Exception as e:
            logger.error(f"Error en llamada a Gemini API: {e}")
            return f"Lo siento, ocurrió un problema al procesar tu consulta con la IA: {str(e)}"
