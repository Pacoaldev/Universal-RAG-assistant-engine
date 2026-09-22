"""
Pruebas para el motor RAG UniversalAssistant.
"""

from pathlib import Path
import json
from src.core.assistant import UniversalAssistant
from src.storage.local_json import LocalJSONKnowledgeStore
from src.llm.mock_client import MockLLMClient


def test_universal_assistant_flow(tmp_path: Path):
    """Verifica el flujo RAG completo con almacenamiento e IA inyectados."""
    test_file = tmp_path / "clinic_kb.json"
    data = {
        "services": [
            {"id": "s_dental", "nombre": "Limpieza Dental", "precio": "50€"}
        ]
    }
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    storage = LocalJSONKnowledgeStore(file_path=test_file)
    llm = MockLLMClient(prefix="[Bot]")

    assistant = UniversalAssistant(
        name="TestBot",
        organization="VetClinica",
        storage=storage,
        llm_client=llm
    )

    # Consulta válida con recuperación
    res = assistant.ask("¿Tienen servicio de limpieza dental y precio?")
    assert res.answer is not None
    assert res.sources_count >= 1
    assert res.processing_time_ms >= 0.0

    # Consulta vacía o inválida
    res_empty = assistant.ask("")
    assert "formula una pregunta" in res_empty.answer.lower()
