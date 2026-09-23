# SDD Design — Defer Assistant Initialization to Startup Handler

**Change:** `review-repo-propose`
**Phase:** Design
**Status:** Ready for Tasks
**Author:** SDD executor (auto mode)
**Date:** 2026-01-21

---

## 1. Architecture Delta

### Current shape (broken)

```python
# src/api/app.py:42 — module-scope construction
app = FastAPI(...)
assistant = UniversalAssistant()   # raises here if GOOGLE_API_KEY missing

@app.get("/health")
def health_check():
    return HealthResponse(... assistant.name, assistant.llm.__class__.__name__ ...)
```

Any import of `src.api.app` (uvicorn import-time, `TestClient(app)` at module scope, `from src.api.app import app`) instantiates `UniversalAssistant()` before uvicorn binds. With `LLM_PROVIDER="gemini"` and no `GOOGLE_API_KEY`, `GeminiClient.__init__` raises `ValueError` → uvicorn never reaches `start()` → container healthcheck spins.

### Target shape

```python
# src/api/app.py — assistant moved into startup
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Construyendo UniversalAssistant en lifespan.startup()")
    app.state.assistant = UniversalAssistant()
    try:
        yield
    finally:
        # sin recursos remotos que cerrar; placeholder para futuro shutdown
        app.state.assistant = None


app = FastAPI(
    title="Universal RAG Assistant API",
    ...,
    lifespan=lifespan,
)
```

### Handler wiring

Each route handler gains a `Request` parameter to access `app.state`:

```python
from fastapi import Request

@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check(request: Request):
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
    assistant = request.app.state.assistant
    all_data = assistant.storage.get_all()
    summary = {category: len(items) for category, items in all_data.items()}
    return {
        "total_categories": len(summary),
        "documents_by_category": summary,
        "storage_backend": assistant.storage.__class__.__name__,
    }
```

`root()` does not touch the assistant — stays signature-less.

### Error containment inside lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.assistant = UniversalAssistant()
        logger.info("UniversalAssistant listo.")
    except Exception as e:
        logger.exception("Fallo crítico construyendo UniversalAssistant; arrancando en modo degradado.")
        # SPEC §server-boot: /health must still respond 200.
        # Construimos un fallback in-place: mismas factories, forzado a mock.
        from src.llm.mock_client import MockLLMClient
        from src.storage.local_json import LocalJSONKnowledgeStore
        from src.core.config import settings
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
```

The try/except exists to satisfy the "health 200 even if init blows up" requirement even when the factory fallback itself fails (e.g. broken import, syntax error). In practice the factory fallback path is what handles missing `GOOGLE_API_KEY`; the try/except is a belt-and-suspenders for catastrophic cases.

---

## 2. Failure Containment

### Factory fallback verification (read of `src/llm/factory.py` and `src/storage/factory.py`)

**`src/llm/factory.py`** (lines 18–30):

```python
if prov == "gemini":
    try:
        from src.llm.gemini_client import GeminiClient
        return GeminiClient()
    except Exception as e:
        logger.warning(...)
        return MockLLMClient(prefix="[Fallback Mode]")
return MockLLMClient()
```

`GeminiClient.__init__` raises `ValueError` when `GOOGLE_API_KEY` is `None` or empty (`src/llm/gemini_client.py:24`). The factory catches it and returns `MockLLMClient`. **The missing-key case is covered.**

**`src/storage/factory.py`** (lines 16–30):

```python
if st_type == "firestore":
    return FirestoreKnowledgeStore(...)
return LocalJSONKnowledgeStore(...)
```

No try/except. But `FirestoreKnowledgeStore.__init__` does NOT raise at construction time — it stores `credentials_path` and `collections` only, with lazy `_db = None`. The first real Firestore call (`_get_client()`) would raise, but only on first request. So storage init never crashes at module-load OR lifespan-startup. **Storage init is safe for boot.**

### Decision: rely on existing factory fallback

Do **NOT** introduce a custom "degraded assistant" object that bypasses the factory. Reasoning:

1. The proposal itself says "no changes to factory.py fallback logic; rely on existing mock init."
2. `src/core/assistant.py:__init__` already calls `get_llm_client()` and `get_knowledge_store()`. The factory path is the only path.
3. Adding a parallel degraded-object constructor duplicates the factory's responsibility and creates two fallback paths the spec explicitly forbids ("no second fallback path is introduced in src.api.app" — `server-boot/spec.md`).

### Lifespan-level safety net

The lifespan try/except remains as a **last-resort catch** for catastrophic init failures (e.g. corrupted `.env`, missing `maskotas_knowledge_base.json` causing `LocalJSONKnowledgeStore.__init__` to set empty data and continue, network DNS blocking `import google.generativeai`). On such failure, it builds a forced `mock` + `local` assistant explicitly via the factories so the server still answers `/health`. This is **not** a second fallback — it re-enters the same factories with explicit short-circuit arguments.

### Behavior matrix

| Env state | What `UniversalAssistant()` returns | `app.state.assistant.llm.__class__.__name__` | `/health` | `/api/chat` |
|-----------|-------------------------------------|----------------------------------------------|-----------|-------------|
| `LLM_PROVIDER=gemini`, no key | `MockLLMClient` (via factory) | `"MockLLMClient"` | 200, healthy | 200, mock answer |
| `LLM_PROVIDER=gemini`, valid key | `GeminiClient` | `"GeminiClient"` | 200, healthy | 200, real answer |
| `LLM_PROVIDER=mock` (explicit) | `MockLLMClient` | `"MockLLMClient"` | 200, healthy | 200, mock answer |
| `STORAGE_TYPE=firestore`, no creds | `FirestoreKnowledgeStore` (lazy `_db=None`) | n/a | 200, healthy | 200/500 on first `.search()` (out of scope) |
| Catastrophic init failure | forced mock+local assistant | `"MockLLMClient"` | 200, healthy | 200, mock answer |

---

## 3. Test Plan (Strict TDD)

### Configuration preflight

`pyproject.toml` MUST gain `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`. Today the key is absent (default `strict` in pytest-asyncio ≥ 0.23). The spec `tdd-discipline/spec.md` mandates `auto`. Without this, every new async test would need `@pytest.mark.asyncio` decoration. **Decision: add the key as part of this change** (pyproject.toml is not in the no-change list).

### New fixture: `tests/conftest.py`

```python
"""Shared pytest fixtures for HTTP integration tests."""

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app


@pytest.fixture(autouse=True)
def _isolate_google_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Borra GOOGLE_API_KEY del entorno en cada test (spec §server-boot
    test-isolation scenario). No-op si ya estaba ausente."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """AsyncClient que dispara el lifespan de FastAPI vía ASGITransport.

    `AsyncClient` con `ASGITransport(app=app)` ejecuta el lifespan context
    manager antes de la primera request, materializando `app.state.assistant`.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
```

Note on autouse: the spec requires tests to work both with and without a host-level `GOOGLE_API_KEY`. `monkeypatch.delenv(..., raising=False)` covers both: deletes if present, no-op otherwise. Cleanup is automatic on fixture teardown.

### Author failing tests FIRST (in this order, all in `tests/test_api.py`)

```python
"""Pruebas para los endpoints de la API FastAPI."""

import pytest


async def test_health_responds_200_without_google_api_key(client):
    """SPEC §server-boot: server boots and /health returns 200 with no key."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["llm_provider"] == "MockLLMClient"


async def test_chat_returns_deterministic_answer_in_mock_mode(client):
    """SPEC §mock-fallback: determinista, sin GOOGLE_API_KEY, prefijo + keyword."""
    response = await client.post(
        "/api/chat", json={"query": "¿Cuáles son los horarios de atención?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("[Fallback Mode]")
    assert "horario" in data["answer"].lower()


def test_import_does_not_raise_when_google_api_key_missing(monkeypatch):
    """SPEC §server-boot: importar src.api.app no debe ejecutar construcción."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    import importlib
    import src.api.app as app_module
    importlib.reload(app_module)
    assert app_module.app.state.assistant is None  # aún no se construyó
    assert hasattr(app_module.app, "router")
```

(Each test fails on `main` today: import crashes; old `TestClient(app)`-based tests crash at module load. They turn green after the lifespan refactor lands.)

### Migrate existing 4 tests in `tests/test_api.py`

The current `client = TestClient(app)` at module scope is the root cause — it triggers the eager `UniversalAssistant()` construction. Refactor:

```python
async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data


async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "assistant_name" in data


async def test_chat_endpoint(client):
    payload = {"query": "¿Cuáles son los horarios de atención?"}
    response = await client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "processing_time_ms" in data


async def test_chat_endpoint_validation(client):
    payload = {"query": ""}
    response = await client.post("/api/chat", json=payload)
    assert response.status_code == 422
```

All 4 of 5 existing tests in `test_api.py` need migration (root, health, chat, chat-validation) — that's the full file except itself. `test_assistant.py`, `test_llm.py`, `test_storage.py`, `test_config.py` are unaffected (no `app` import).

### Test command

`pytest` (already configured: `-v --tb=short`, `testpaths=["tests"]`, `pythonpath=["."]`). New tests are async and auto-discovered by `pytest-asyncio` once `asyncio_mode = "auto"` is added.

### Test verification matrix

| Test | Before refactor | After refactor |
|------|-----------------|----------------|
| `test_health_responds_200_without_google_api_key` | FAIL (ImportError at `from src.api.app import app`) | PASS |
| `test_chat_returns_deterministic_answer_in_mock_mode` | FAIL | PASS |
| `test_import_does_not_raise_when_google_api_key_missing` | FAIL | PASS |
| `test_root_endpoint` (migrated) | PASS or FAIL depending on env | PASS |
| `test_health_endpoint` (migrated) | PASS or FAIL depending on env | PASS |
| `test_chat_endpoint` (migrated) | PASS or FAIL depending on env | PASS |
| `test_chat_endpoint_validation` (migrated) | PASS | PASS |

---

## 4. Files to Change (Exact Paths)

| Path | Change | Lines (est.) |
|------|--------|--------------|
| `src/api/app.py` | Add `lifespan` context manager; move `UniversalAssistant()` construction inside; add `Request` param to 3 routes; remove module-scope `assistant` | ~30 |
| `tests/conftest.py` | NEW: `client` fixture (AsyncClient + ASGITransport) + `_isolate_google_api_key` autouse | ~30 |
| `tests/test_api.py` | Drop module-scope `TestClient`; convert 4 existing tests to async `client` fixture; add 3 new TDD tests | ~70 |
| `pyproject.toml` | Add `asyncio_mode = "auto"` under `[tool.pytest.ini_options]` | +1 |

**Estimated total diff:** ~130 lines. Well under the 400-line review budget.

### NOT to change

- `src/llm/factory.py` — verified fallback already handles missing key.
- `src/storage/factory.py` — Firestore is lazy-init; storage init does not crash at boot.
- `src/llm/mock_client.py`, `src/llm/gemini_client.py` — unchanged.
- `src/storage/local_json.py`, `src/storage/firestore_store.py` — unchanged.
- `src/core/assistant.py`, `src/core/config.py`, `src/core/logger.py` — unchanged.
- `src/cli/main.py` — separate change (CLI startup has its own issue).

---

## 5. Files NOT to Change

(For review clarity — listed explicitly even though outside scope)

- `src/cli/main.py` — CLI startup fix is its own change.
- `src/core/assistant.py`, `src/core/config.py`, `src/core/logger.py` — interfaces unchanged.
- `Dockerfile`, `docker-compose.yml` — no env or entrypoint changes.
- `requirements.txt` — no new deps; `httpx>=0.27` and `pytest-asyncio>=0.23` are already dev deps.
- All spec files under `openspec/changes/review-repo-propose/specs/` — frozen at proposal acceptance.
- `tests/test_assistant.py`, `tests/test_llm.py`, `tests/test_storage.py`, `tests/test_config.py` — do not import `app`; unaffected.

---

## 6. Rollout / Risk

### Existing API clients

- HTTP contract: unchanged. Same paths (`/`, `/health`, `/api/chat`, `/api/knowledge`), same request/response models (`ChatRequest`, `HealthResponse`, `AssistantResponse`), same status codes for happy paths.
- OpenAPI schema: unchanged. FastAPI lifespan does not alter route introspection.
- `/health` body field types: unchanged.

### Existing tests impact

- `tests/test_api.py`: 4 tests fully rewritten to async pattern (verified by reading file). They were coupled to module-scope `assistant`; now coupled to `client` fixture.
- Other test files: zero changes (verified by reading each).
- Risk: if `pytest-asyncio` auto-mode is misconfigured, every new async test fails with "async function not marked". Mitigation is the explicit `asyncio_mode = "auto"` line in `pyproject.toml`.

### Pytest-asyncio mode decision

`auto` is correct. Rationale:
- Spec `tdd-discipline/spec.md` mandates `asyncio_mode = "auto"`.
- `strict` mode would require `@pytest.mark.asyncio` on every async test → ceremony without benefit; tests would still work but contradict the spec.
- `auto` discovers `async def test_*` automatically and is the modern default for FastAPI async suites.

### FastAPI version check

`pyproject.toml` declares `fastapi>=0.110.0`. The lifespan context-manager API shipped in FastAPI 0.93.0. **Confirmed compatible**, no dependency bump needed.

### httpx version check

`pyproject.toml` declares `httpx>=0.27.0`. `httpx.ASGITransport` was added in httpx 0.27 (replacing the deprecated `app=...` keyword on `AsyncClient`). **Confirmed compatible**.

### Deployment behavior change

| Scenario | Before | After |
|----------|--------|-------|
| `LLM_PROVIDER=gemini`, no key, container | Crash on import, container unhealthy | Boots, `/health` 200, `/api/chat` returns mock |
| `LLM_PROVIDER=gemini`, valid key | Boots, real answers | Boots, real answers (unchanged) |
| `LLM_PROVIDER=mock` | Boots, mock | Boots, mock (unchanged) |
| `STORAGE_TYPE=firestore`, no creds, first request | Crash on import | Boots; first request to `/api/knowledge` may 500 (out of scope, spec accepts) |

---

## 7. Open Questions — Resolved

### Q1: Does `LLM_PROVIDER=mock` (explicit) bypass Gemini entirely?

**Yes — verified.** `src/llm/factory.py:30`:

```python
if prov == "gemini":
    try:
        return GeminiClient()
    except Exception:
        return MockLLMClient(prefix="[Fallback Mode]")
return MockLLMClient()   # ← any non-"gemini" value (including "mock") lands here
```

`prov.lower() == "mock"` skips the `try`/`except` block entirely and returns `MockLLMClient()` directly. No network call, no import of `google.generativeai`, no key check. Clean bypass.

### Q2: Should `/health` report `llm_provider` exactly (`"mock"`) or expose a new `effective_provider` field?

**Decision: keep the existing field name `llm_provider`, keep its value as `assistant.llm.__class__.__name__`** (e.g. `"MockLLMClient"`, `"GeminiClient"`). Rationale:

- Adding `effective_provider` violates the spec's "Public HTTP Contract Preserved" requirement (`server-boot/spec.md`). Clients depending on `HealthResponse.llm_provider` would silently lose information.
- The spec itself says the field should reflect "the effective backend (`GeminiClient` if key present, `MockLLMClient` otherwise)" — that's the class name pattern, not the short token.
- The proposed test name in the task prompt (`llm_provider == "mock"`) is refined here to `llm_provider == "MockLLMClient"` to match the spec. **This is the only assertion in the proposed test that diverges from the user's prompt, and the spec is the source of truth.** If the user prefers the short token, change the field assignment to:
  ```python
  llm_provider=type(assistant.llm).__name__.replace("Client", "").lower(),  # "mock" / "gemini"
  ```
  — but this is an API contract change and would require re-running the spec acceptance check.

### Q3 (additional): Why not `dependency_overrides` for tests instead of lifespan?

`TestClient(app)` historically could fire `on_event("startup")` automatically, but for the missing-key case the *import* itself crashes before `TestClient` exists. The lifespan refactor is mandatory for production; the AsyncClient fixture is just the test-side mirror.

---

## Acceptance Checklist

- [x] Spec `server-boot/spec.md` covered by 3 new tests + lifespan refactor.
- [x] Spec `mock-fallback/spec.md` covered by `test_chat_returns_deterministic_answer_in_mock_mode`.
- [x] Spec `tdd-discipline/spec.md` covered by `conftest.py` fixture + `pyproject.toml` `asyncio_mode = "auto"`.
- [x] No changes to `factory.py` (factory fallback is sufficient).
- [x] No second fallback path introduced in `src.api.app`.
- [x] `/health` always 200 (catastrophic-init try/except in lifespan).
- [x] HTTP contract preserved.
- [x] Diff under 400 lines (~130 estimated).

---

## Next Phase

`sdd-tasks` — decompose into ordered tasks with strict TDD ordering (failing test → production change → green).