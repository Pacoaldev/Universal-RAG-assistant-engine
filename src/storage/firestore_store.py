"""
Almacén de conocimientos basado en Google Cloud Firestore.
Implementa inicialización bajo demanda (lazy-init) para evitar fallos de importación.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.logger import get_logger
from src.storage.base import BaseKnowledgeStore

logger = get_logger("storage.firestore")


class FirestoreKnowledgeStore(BaseKnowledgeStore):
    """Adaptador para Google Cloud Firestore."""

    def __init__(
        self, credentials_path: Optional[Path] = None, collections: Optional[Dict[str, str]] = None
    ):
        self.credentials_path = credentials_path
        self.collections = collections or {
            "general_info": "informacion_general_clinica",
            "services": "servicios_veterinaria",
        }
        self._db = None

    def _get_client(self):
        """Inicializa el cliente de Firestore solo cuando sea necesario."""
        if self._db is not None:
            return self._db

        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                if self.credentials_path and Path(self.credentials_path).exists():
                    cred = credentials.Certificate(str(self.credentials_path))
                    firebase_admin.initialize_app(cred)
                else:
                    # Intento con Application Default Credentials (ADC)
                    firebase_admin.initialize_app()

            self._db = firestore.client()
            logger.info("Conexión con Firestore establecida correctamente")
            return self._db
        except Exception as e:
            logger.error(f"Error al inicializar Firestore: {e}")
            raise RuntimeError(f"No se pudo conectar con Firestore: {e}")

    def _score_document(self, doc: Dict[str, Any], query_tokens: List[str]) -> float:
        """Calcula una puntuación de coincidencia léxica para un documento."""
        doc_str = json.dumps(doc, ensure_ascii=False).lower()
        score = 0.0

        for token in query_tokens:
            if not token:
                continue
            count = len(re.findall(r"\b" + re.escape(token) + r"\b", doc_str))
            if count > 0:
                score += count * 2.0
            elif token in doc_str:
                score += 1.0

        return score

    def search(self, query: str, limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """Busca documentos en Firestore ordenados por relevancia léxica."""
        if not query or not query.strip():
            return {}

        query_clean = query.lower().strip()
        tokens = [t for t in re.findall(r"\w+", query_clean) if len(t) > 2]
        if not tokens:
            tokens = [query_clean]

        db = self._get_client()
        results = {}

        for key, collection_name in self.collections.items():
            scored_items = []
            try:
                docs = db.collection(collection_name).stream()
                for doc in docs:
                    data = doc.to_dict()
                    score = self._score_document(data, tokens)
                    if score > 0:
                        scored_items.append((score, data))

                scored_items.sort(key=lambda x: x[0], reverse=True)
                if scored_items:
                    results[key] = [item for _, item in scored_items[:limit]]
            except Exception as e:
                logger.error(f"Error al consultar la colección {collection_name}: {e}")

        return results

    def get_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Obtiene todos los documentos de las colecciones configuradas."""
        db = self._get_client()
        data = {}
        for key, collection_name in self.collections.items():
            data[key] = [doc.to_dict() for doc in db.collection(collection_name).stream()]
        return data

    def save_data(self, data: Dict[str, List[Dict[str, Any]]]) -> bool:
        """Sube documentos a Firestore."""
        db = self._get_client()
        try:
            for key, items in data.items():
                col_name = self.collections.get(key, key)
                for item in items:
                    doc_id = item.get("id") or item.get("tema")
                    if doc_id:
                        db.collection(col_name).document(str(doc_id)).set(item)
                    else:
                        db.collection(col_name).add(item)
            return True
        except Exception as e:
            logger.error(f"Error al guardar datos en Firestore: {e}")
            return False
