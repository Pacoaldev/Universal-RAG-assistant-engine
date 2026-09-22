"""
Interfaz abstracta para clientes LLM.
"""

from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """Contrato base para clientes de modelos de lenguaje."""

    @abstractmethod
    def generate_response(self, prompt: str) -> str:
        """
        Genera una respuesta basada en el prompt recibido.
        
        Args:
            prompt: Texto completo de entrada con contexto.
            
        Returns:
            Texto de respuesta generado por el modelo.
        """
        pass

    def validate_input(self, text: str, max_length: int = 2000) -> bool:
        """
        Valida que el input no esté vacío y no sobrepase el límite razonable.
        
        Args:
            text: Texto de entrada.
            max_length: Longitud máxima permitida.
        """
        if not text or not text.strip():
            return False
        return len(text.strip()) <= max_length
