"""
Configuración centralizada y tipada del sistema usando Pydantic Settings.
"""

from pathlib import Path
from typing import Optional, Dict
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Configuraciones del sistema con soporte para .env y defaults seguros."""
    
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Identidad y Dominio
    ASSISTANT_NAME: str = Field(default="Maskotas Bot", description="Nombre del asistente")
    ORGANIZATION_NAME: str = Field(default="Clínica Veterinaria Maskotas", description="Organización o dominio")
    SYSTEM_PROMPT_TEMPLATE: Optional[str] = None

    # Proveedor LLM
    LLM_PROVIDER: str = Field(default="gemini", description="Proveedor LLM: gemini | mock")
    GOOGLE_API_KEY: Optional[str] = Field(default=None, description="API Key de Google Gemini")
    GEMINI_MODEL: str = Field(default="models/gemini-1.5-flash", description="Modelo de Gemini a utilizar")

    # Almacenamiento RAG
    STORAGE_TYPE: str = Field(default="local", description="Tipo de almacenamiento: local | firestore")
    KNOWLEDGE_BASE_PATH: Path = Field(
        default=PROJECT_ROOT / "maskotas_knowledge_base.json",
        description="Ruta al archivo JSON local de la base de conocimientos"
    )
    
    # Firestore (solo si STORAGE_TYPE=firestore)
    FIREBASE_CREDENTIALS_PATH: Optional[Path] = Field(
        default=None,
        description="Ruta a las credenciales de servicio de Firebase"
    )
    FIRESTORE_COLLECTIONS: Dict[str, str] = Field(
        default_factory=lambda: {
            "general_info": "informacion_general_clinica",
            "services": "servicios_veterinaria"
        }
    )

    # API REST
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    @property
    def default_system_prompt(self) -> str:
        """Prompt de sistema predeterminado si no se especifica uno personalizado."""
        if self.SYSTEM_PROMPT_TEMPLATE:
            return self.SYSTEM_PROMPT_TEMPLATE
        return (
            f"Eres el asistente virtual de {self.ORGANIZATION_NAME}. "
            "Tu objetivo es proporcionar información precisa, empática y útil sobre nuestros servicios, "
            "horarios y consultas generales. "
            "Prioriza siempre la información verificada suministrada en la base de conocimientos. "
            "Si la información no está en el contexto, indícalo con amabilidad y honestidad. "
            "Sé profesional, claro y conciso."
        )


# Instancia única tipada
settings = Settings()
