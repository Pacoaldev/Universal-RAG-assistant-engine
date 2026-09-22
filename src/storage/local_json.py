"""
Almacén de conocimientos local basado en archivo JSON y búsqueda por relevancia.
Permite ejecutar el proyecto sin depender de Firestore ni de una cuenta de Google Cloud.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from src.storage.base import BaseKnowledgeStore
from src.core.logger import get_logger

logger = get_logger("storage.local_json")


class LocalJSONKnowledgeStore(BaseKnowledgeStore):
    """Implementación local en memoria con persistencia en JSON."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self.load()

    def load(self) -> None:
        """Carga los datos desde el archivo JSON si existe."""
        if not self.file_path.exists():
            logger.warning(f"Archivo de base de conocimientos no encontrado: {self.file_path}")
            self._data = {}
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            logger.info(f"Base de conocimientos cargada ({sum(len(v) for v in self._data.values())} documentos)")
        except Exception as e:
            logger.error(f"Error al leer {self.file_path}: {e}")
            self._data = {}

    def _score_document(self, doc: Dict[str, Any], query_tokens: List[str]) -> float:
        """Calcula una puntuación de coincidencia léxica para un documento."""
        doc_str = json.dumps(doc, ensure_ascii=False).lower()
        score = 0.0
        
        for token in query_tokens:
            if not token:
                continue
            # Coincidencia exacta de token
            count = len(re.findall(r"\b" + re.escape(token) + r"\b", doc_str))
            if count > 0:
                score += count * 2.0
            elif token in doc_str:
                score += 1.0

        return score

    def search(self, query: str, limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """Busca documentos relevantes ordenados por puntuación de coincidencia."""
        if not query or not query.strip():
            return {}

        query_clean = query.lower().strip()
        tokens = [t for t in re.findall(r"\w+", query_clean) if len(t) > 2]
        if not tokens:
            tokens = [query_clean]

        results: Dict[str, List[Dict[str, Any]]] = {}

        for category, items in self._data.items():
            scored_items = []
            for item in items:
                score = self._score_document(item, tokens)
                if score > 0:
                    scored_items.append((score, item))

            # Ordenar por mayor puntuación
            scored_items.sort(key=lambda x: x[0], reverse=True)
            if scored_items:
                results[category] = [item for _, item in scored_items[:limit]]

        return results

    def get_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Retorna todos los documentos."""
        return self._data

    def save_data(self, data: Dict[str, List[Dict[str, Any]]]) -> bool:
        """Guarda los datos en memoria y en el archivo JSON."""
        try:
            self._data = data
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Base de conocimientos guardada en {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"Error al guardar datos en {self.file_path}: {e}")
            return False
