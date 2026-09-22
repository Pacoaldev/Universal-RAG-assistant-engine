"""
Servidor REST FastAPI para el asistente RAG universal.
"""

import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.core.assistant import AssistantResponse, UniversalAssistant
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("api.app")

app = FastAPI(
    title="Universal RAG Assistant API",
    description=(
        "API REST modular y de producción para consultas "
        "de asistencia virtual impulsadas por RAG."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instancia del asistente
assistant = UniversalAssistant()


class ChatRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        json_schema_extra={
            "example": "¿Cuáles son los horarios de atención y qué servicios de vacunación ofrecen?"
        },
    )


class HealthResponse(BaseModel):
    status: str
    assistant_name: str
    organization: str
    storage_type: str
    llm_provider: str


@app.get("/", tags=["Root"])
def root():
    """Ruta raíz de bienvenida."""
    return {
        "message": f"Bienvenido a la API de {settings.ASSISTANT_NAME}",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Estado de salud y configuración del sistema."""
    return HealthResponse(
        status="healthy",
        assistant_name=assistant.name,
        organization=assistant.organization,
        storage_type=assistant.storage.__class__.__name__,
        llm_provider=assistant.llm.__class__.__name__,
    )


@app.post("/api/chat", response_model=AssistantResponse, tags=["Chat"])
def chat_endpoint(request: ChatRequest):
    """
    Envía una consulta al asistente RAG y obtiene una respuesta contextualizada.
    """
    try:
        response = assistant.ask(request.query)
        return response
    except Exception as e:
        logger.error(f"Error procesando endpoint /api/chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al procesar la consulta: {str(e)}",
        )


@app.get("/api/knowledge", tags=["Knowledge"])
def get_knowledge_summary():
    """Obtiene un resumen de la base de conocimientos activa."""
    all_data = assistant.storage.get_all()
    summary = {category: len(items) for category, items in all_data.items()}
    return {
        "total_categories": len(summary),
        "documents_by_category": summary,
        "storage_backend": assistant.storage.__class__.__name__,
    }


def start():
    """Punto de entrada para ejecutar el servidor uvicorn."""
    uvicorn.run("src.api.app:app", host=settings.API_HOST, port=settings.API_PORT, reload=False)


if __name__ == "__main__":
    start()
