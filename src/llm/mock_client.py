"""
Cliente LLM simulado (Mock) para entornos de CI/CD, desarrollo offline y tests unitarios.
Permite ejecutar el sistema sin necesidad de una API Key real ni consumo de cuota.
"""

from src.llm.base import BaseLLMClient
from src.core.logger import get_logger

logger = get_logger("llm.mock")


class MockLLMClient(BaseLLMClient):
    """Proveedor LLM simulado offline."""

    def __init__(self, prefix: str = "[Simulado]"):
        self.prefix = prefix
        logger.info("MockLLMClient inicializado (Modo Offline / Test)")

    def generate_response(self, prompt: str) -> str:
        """Genera una respuesta determinista basada en el contenido del prompt."""
        prompt_lower = prompt.lower()

        if "vacun" in prompt_lower:
            return (
                f"{self.prefix} Ofrecemos planes completos de vacunación para perros y gatos "
                "incluyendo rabia, polivalente y leucemia felina. Consulta nuestros horarios de atención."
            )
        elif "horario" in prompt_lower or "hora" in prompt_lower:
            return (
                f"{self.prefix} Nuestro horario habitual es de Lunes a Viernes de 9:00 a 20:00 "
                "y Sábados de 10:00 a 14:00. Disponemos además de servicio de urgencias 24h."
            )
        elif "urgencia" in prompt_lower or "emergencia" in prompt_lower:
            return (
                f"{self.prefix} Disponemos de atención de urgencias 24/7. "
                "Puedes acudir a nuestras instalaciones o llamar a nuestra línea de emergencia."
            )
        elif "precio" in prompt_lower or "costo" in prompt_lower:
            return (
                f"{self.prefix} Los precios varían según el servicio específico. "
                "Consulta nuestra lista de tarifas o visítanos para una valoración personalizada."
            )
        
        return (
            f"{self.prefix} He recibido tu consulta sobre '{prompt.strip().splitlines()[-1][:60]}...'. "
            "Para más detalles, consulta nuestra base de conocimientos o comunícate con nuestro equipo."
        )
