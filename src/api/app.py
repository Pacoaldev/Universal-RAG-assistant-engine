"""
Servidor REST FastAPI para el asistente RAG universal.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.core.assistant import AssistantResponse, UniversalAssistant
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("api.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa UniversalAssistant en startup; limpia en shutdown.

    El try/except garantiza que /health responda 200 incluso ante un fallo
    catastrófico de construcción. La rama except reusa las mismas factories
    forzando mock+local — no introduce un segundo fallback path.
    """
    try:
        app.state.assistant = UniversalAssistant()
        logger.info("UniversalAssistant listo.")
    except Exception:
        logger.exception(
            "Fallo crítico construyendo UniversalAssistant; arrancando en modo degradado."
        )
        from src.llm.factory import get_llm_client
        from src.storage.factory import get_knowledge_store

        app.state.assistant = UniversalAssistant(
            name=settings.ASSISTANT_NAME,
            organization=settings.ORGANIZATION_NAME,
            llm_client=get_llm_client("mock"),
            storage=get_knowledge_store("local"),
        )
    try:
        yield
    finally:
        app.state.assistant = None


app = FastAPI(
    title="Universal RAG Assistant API",
    description=(
        "API REST modular y de producción para consultas "
        "de asistencia virtual impulsadas por RAG."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Estado inicial: el assistant se materializa dentro de lifespan.startup().
# Garantiza que app.state.assistant sea accesible desde el primer import.
app.state.assistant = None

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
def health_check(request: Request):
    """Estado de salud y configuración del sistema."""
    assistant = request.app.state.assistant
    return HealthResponse(
        status="healthy",
        assistant_name=assistant.name,
        organization=assistant.organization,
        storage_type=assistant.storage.__class__.__name__,
        llm_provider=assistant.llm.__class__.__name__,
    )


@app.post("/api/chat", response_model=AssistantResponse, tags=["Chat"])
def chat_endpoint(request: Request, body: ChatRequest):
    """
    Envía una consulta al asistente RAG y obtiene una respuesta contextualizada.
    """
    assistant = request.app.state.assistant
    try:
        return assistant.ask(body.query)
    except Exception as e:
        logger.error(f"Error procesando endpoint /api/chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al procesar la consulta: {str(e)}",
        )


@app.get("/api/knowledge", tags=["Knowledge"])
def get_knowledge_summary(request: Request):
    """Obtiene un resumen de la base de conocimientos activa."""
    assistant = request.app.state.assistant
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
