"""
Interfaz abstracta para almacenes de conocimiento.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseKnowledgeStore(ABC):
    """Contrato base para cualquier backend de almacenamiento de información."""

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        Busca documentos relevantes para la consulta dada.

        Args:
            query: Texto de consulta del usuario.
            limit: Límite máximo de resultados por categoría.

        Returns:
            Diccionario agrupado por categorías de documentos coincidentes.
        """
        pass

    @abstractmethod
    def get_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Retorna todos los documentos indexados en el almacén."""
        pass

    @abstractmethod
    def save_data(self, data: Dict[str, List[Dict[str, Any]]]) -> bool:
        """Guarda o actualiza documentos en el almacén."""
        pass
