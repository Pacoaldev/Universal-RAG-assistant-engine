"""
Pruebas para el almacén de conocimientos local.
"""

import json
from pathlib import Path

from src.storage.local_json import LocalJSONKnowledgeStore


def test_local_json_store(tmp_path: Path):
    """Verifica carga, búsqueda y guardado en LocalJSONKnowledgeStore."""
    test_file = tmp_path / "test_knowledge.json"
    data = {
        "services": [
            {
                "id": "s1",
                "nombre": "Vacunación Canina",
                "descripcion": "Protección contra rabia y parvovirus",
            },
            {
                "id": "s2",
                "nombre": "Cirugía General",
                "descripcion": "Quirófano equipado para esterilizaciones",
            },
        ],
        "info": [{"tema": "horarios", "detalle": "Lunes a Viernes de 9:00 a 20:00"}],
    }
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    store = LocalJSONKnowledgeStore(file_path=test_file)

    # Buscar vacunación
    results = store.search("vacuna")
    assert "services" in results
    assert len(results["services"]) >= 1
    assert results["services"][0]["id"] == "s1"

    # Buscar horarios
    info_results = store.search("horarios de atención")
    assert "info" in info_results
    assert len(info_results["info"]) >= 1

    # Búsqueda sin resultados
    empty_results = store.search("término inexistente xyz123")
    assert len(empty_results) == 0


def test_local_json_save_data(tmp_path: Path):
    """Verifica la persistencia de nuevos datos."""
    test_file = tmp_path / "saved_knowledge.json"
    store = LocalJSONKnowledgeStore(file_path=test_file)

    new_data = {"faq": [{"pregunta": "¿Aceptan tarjetas?", "respuesta": "Sí, todas las tarjetas."}]}
    success = store.save_data(new_data)
    assert success is True
    assert store.get_all() == new_data


def test_firestore_store_scoring():
    """Verifica el cálculo de scoring léxico en FirestoreKnowledgeStore."""
    from src.storage.firestore_store import FirestoreKnowledgeStore

    store = FirestoreKnowledgeStore()
    doc = {"nombre": "Vacunación Canina", "descripcion": "Protección contra rabia"}

    score_match = store._score_document(doc, ["vacunacion", "rabia"])
    score_no_match = store._score_document(doc, ["cirugia", "dental"])

    assert score_match > 0
    assert score_no_match == 0

