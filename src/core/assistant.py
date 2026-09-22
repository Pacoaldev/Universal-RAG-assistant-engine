"""
Motor principal del asistente RAG universal.
Desacoplado de frameworks específicos con inyección de dependencias completa.
"""

import json
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logger import get_logger
from src.llm.base import BaseLLMClient
from src.llm.factory import get_llm_client
from src.storage.base import BaseKnowledgeStore
from src.storage.factory import get_knowledge_store

logger = get_logger("core.assistant")


class AssistantResponse(BaseModel):
    """Modelo estructurado de respuesta del asistente."""

    answer: str
    sources_count: int = 0
    sources: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    processing_time_ms: float = 0.0
    model_used: str = "unknown"


class UniversalAssistant:
    """Orquestador RAG universal para cualquier dominio de conocimiento."""

    def __init__(
        self,
        name: Optional[str] = None,
        organization: Optional[str] = None,
        system_prompt: Optional[str] = None,
        storage: Optional[BaseKnowledgeStore] = None,
        llm_client: Optional[BaseLLMClient] = None,
    ):
        self.name = name or settings.ASSISTANT_NAME
        self.organization = organization or settings.ORGANIZATION_NAME
        self.system_prompt = system_prompt or settings.default_system_prompt
        self.storage = storage or get_knowledge_store()
        self.llm = llm_client or get_llm_client()

        logger.info(
            f"Asistente '{self.name}' inicializado para '{self.organization}' "
            f"(Storage: {self.storage.__class__.__name__}, LLM: {self.llm.__class__.__name__})"
        )

    def _retrieve_context(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """Recupera información relevante del almacén."""
        return self.storage.search(query)

    def _format_context(self, results: Dict[str, List[Dict[str, Any]]]) -> str:
        """Formatea los resultados recuperados en un bloque de contexto legible para el LLM."""
        if not results or not any(results.values()):
            return ""

        lines = [f"\n--- INFORMACIÓN RELEVANTE DE {self.organization.upper()} ---"]
        for category, docs in results.items():
            if not docs:
                continue
            cat_title = category.replace("_", " ").title()
            lines.append(f"\n[{cat_title}]:")
            for doc in docs:
                lines.append(f"- {json.dumps(doc, ensure_ascii=False)}")

        lines.append("--- FIN DE INFORMACIÓN RELEVANTE ---\n")
        return "\n".join(lines)

    def ask(self, query: str) -> AssistantResponse:
        """
        Procesa una consulta del usuario mediante RAG y genera una respuesta informada.
        """
        start_time = time.perf_counter()

        # Validación
        if not self.llm.validate_input(query):
            logger.warning(f"Consulta rechazada por validación: '{query}'")
            return AssistantResponse(
                answer="Por favor, formula una pregunta clara y concisa.", processing_time_ms=0.0
            )

        logger.info(f"Procesando consulta: '{query}'")

        # 1. Recuperación de contexto
        search_results = self._retrieve_context(query)
        context_str = self._format_context(search_results)
        total_sources = sum(len(docs) for docs in search_results.values())

        # 2. Construcción de Prompt
        prompt = (
            f"{self.system_prompt}\n\n"
            f"{context_str}\n"
            f"Pregunta del usuario: {query}\n\n"
            f"Respuesta de {self.name}:"
        )

        # 3. Generación LLM
        answer = self.llm.generate_response(prompt)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"Consulta respondida en {elapsed_ms:.2f}ms con {total_sources} fuentes encontradas"
        )

        return AssistantResponse(
            answer=answer,
            sources_count=total_sources,
            sources=search_results,
            processing_time_ms=round(elapsed_ms, 2),
            model_used=self.llm.__class__.__name__,
        )
