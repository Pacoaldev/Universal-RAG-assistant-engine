"""Módulo de almacenamiento y recuperación de conocimientos (Knowledge Stores)."""

from src.storage.base import BaseKnowledgeStore
from src.storage.factory import get_knowledge_store

__all__ = ["BaseKnowledgeStore", "get_knowledge_store"]
