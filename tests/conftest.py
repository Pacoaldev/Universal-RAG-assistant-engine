"""Shared pytest fixtures for HTTP integration tests."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app


@pytest.fixture(autouse=True)
def _isolate_google_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Borra GOOGLE_API_KEY del entorno en cada test (spec §server-boot
    test-isolation scenario). No-op si ya estaba ausente."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """AsyncClient que dispara el lifespan de FastAPI vía ASGITransport.

    httpx 0.27+ NO invoca lifespan automáticamente; lo abrimos explícitamente
    con `app.router.lifespan_context(app)` para materializar
    `app.state.assistant` antes de la primera request.
    """
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac
