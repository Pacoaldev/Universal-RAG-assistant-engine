"""
Factoría para instanciar almacenes de conocimiento según configuración.
"""

from typing import Optional

from src.core.config import settings
from src.core.logger import get_logger
from src.storage.base import BaseKnowledgeStore
from src.storage.firestore_store import FirestoreKnowledgeStore
from src.storage.local_json import LocalJSONKnowledgeStore

logger = get_logger("storage.factory")


def get_knowledge_store(storage_type: Optional[str] = None) -> BaseKnowledgeStore:
    """
    Retorna la instancia configurada del almacén de conocimientos.

    Args:
        storage_type: 'local' o 'firestore'. Si es None, usa settings.STORAGE_TYPE.
    """
    st_type = (storage_type or settings.STORAGE_TYPE).lower()

    if st_type == "firestore":
        logger.info("Instanciando FirestoreKnowledgeStore")
        return FirestoreKnowledgeStore(
            credentials_path=settings.FIREBASE_CREDENTIALS_PATH,
            collections=settings.FIRESTORE_COLLECTIONS,
        )

    logger.info(f"Instanciando LocalJSONKnowledgeStore ({settings.KNOWLEDGE_BASE_PATH})")
    return LocalJSONKnowledgeStore(file_path=settings.KNOWLEDGE_BASE_PATH)
