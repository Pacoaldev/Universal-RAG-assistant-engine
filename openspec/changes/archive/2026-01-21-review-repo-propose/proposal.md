# SDD Proposal: Defer Assistant Initialization to Startup Handler

**Candidate:** #1 (API server crashes on import when `GOOGLE_API_KEY` is missing)  
**Change name:** `review-repo-propose`  
**Phase:** Proposal  
**Status:** Ready for Spec

---

## 1. Why

### Problem Statement

`src/api/app.py:42` instantiates `UniversalAssistant()` at module import time:

```python
app = FastAPI(...)
assistant = UniversalAssistant()  # ← crashes here, before uvicorn binds
```

When `LLM_PROVIDER="gemini"` and `GOOGLE_API_KEY` is absent, `GeminiClient.__init__` raises `ValueError`. The uvicorn process fails to import the `app` module entirely—no port bind, no `/health` endpoint, container marked unhealthy. The factory in `src/llm/factory.py:23–30` contains the correct fallback logic (`MockLLMClient`), but `app.py` bypasses it by calling `UniversalAssistant()` directly instead of going through the factory.

### Evidence

- **File:** `src/api/app.py:42`  
  Code: `assistant = UniversalAssistant()` at module scope.

- **File:** `src/core/assistant.py:48–49`  
  `UniversalAssistant.__init__` calls `get_llm_client()` unconditionally.

- **File:** `src/llm/factory.py:23–30`  
  `get_llm_client()` catches exceptions and falls back to `MockLLMClient`, but only at call time.

- **File:** `src/llm/gemini_client.py` (not shown, but inferred from explore)  
  `GeminiClient.__init__` raises if `GOOGLE_API_KEY` is None or invalid.

### Why It Matters

- **Deployment impact:** Any missing env var (typo in `.env`, absent in CI/container) kills the process before health check can pass. HEALTHCHECK loop spins forever.
- **Blocks downstream fixes:** Auth, observability, and error handling changes cannot be tested/deployed until `/health` is reliable.
- **Factory is unused:** The fallback logic in `factory.py` is dead code in the API path; CLI likely has the same issue.

---

## 2. What Changes

### Scope

- Defer `UniversalAssistant()` instantiation from module-import time to FastAPI startup (via lifespan context manager).
- Move `assistant = UniversalAssistant()` from module scope to startup handler.
- Make `assistant` available to route handlers via FastAPI's `app.state` (or request context).
- Ensure `/health` responds 200 even if LLM/storage init fails or times out.
- No changes to `UniversalAssistant` contract; preserve all public methods and signatures.
- No changes to `factory.py` fallback logic; rely on existing mock init.

### Surfaces

| Surface | Change | Rationale |
|---------|--------|-----------|
| `src/api/app.py` | Add lifespan handler; move assistant init to startup | Defer init to first request |
| `src/api/app.py` (routes) | Route handlers read `request.app.state.assistant` | Access deferred instance |
| `tests/test_api.py` | Add test: boot without `GOOGLE_API_KEY`, `/health` → 200 | Verify startup resilience |
| (New test fixture?) | Async test client with env isolation | Run server in mock mode |

### No Changes

- `src/core/assistant.py` (interface unchanged)
- `src/llm/factory.py` (logic unchanged; fallback still works)
- `src/core/config.py` (Settings unchanged)
- `src/cli/main.py` (out of scope; separate issue)

---

## 3. Goals (Pass Criteria)

**Binary pass:** All four must be true.

1. **Server starts without `GOOGLE_API_KEY` set**  
   - `uvicorn` binds to port 8000 and does not crash during import or startup.
   - No exceptions in module load.

2. **`GET /health` returns 200 with valid response**  
   - Requests to `/health` succeed even if LLM provider init was deferred.
   - Response contains `status: "healthy"`.

3. **`/api/chat` returns deterministic mock answer when no API key is set**  
   - POST `{"query": "vacunación"}` returns a response containing "vacunación".
   - No exception leak to client; response is 200 with valid `AssistantResponse` JSON.

4. **Pytest-asyncio test passes in CI**  
   - Test boots server without `GOOGLE_API_KEY`, calls `/health` and `/api/chat`, asserts deterministic answers.
   - Test runs in auto async mode; no manual event loop management.

### Non-Goals (explicit exclusions)

- Error leakage from `/api/chat` (candidate #2).
- CORS/auth hardening (candidate #3).
- Real embeddings/chunking RAG (candidate #4).
- CLI startup fix (separate change).
- Health check detail logic (e.g., fail if storage is unreachable); health always returns 200 in this change.

---

## 4. Impact

### Callers

| Caller | Impact |
|--------|--------|
| Uvicorn process | **High:** Import no longer crashes; startup explicit. Server boots in degraded mode if creds missing. |
| Route handlers (`chat_endpoint`, `health_check`, `get_knowledge_summary`) | **Medium:** Read `app.state.assistant` instead of module global. Transparent; same interface. |
| CI/Docker entrypoint | **High:** No change to command, but behavior changes: server boots now and retries/logs instead of crashing. |
| Tests | **High:** Must use async client; test fixtures must manage app lifecycle. |

### Public API

- **HTTP contract:** No change. Routes, request/response models, status codes unchanged.
- **Python API:** `UniversalAssistant` class interface unchanged. Instantiation still deferred but from caller perspective identical.

### Config

- No new env vars required.
- Existing `GOOGLE_API_KEY`, `LLM_PROVIDER`, `STORAGE_TYPE` behavior unchanged.
- `.env` no longer required to run; missing key triggers fallback as designed.

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Factory init side effects on startup** | Medium | Factory may log warnings, create temp files, or make network calls during init. This was deferred; now happens at startup instead of at import. Could delay boot. | Review factory logs during test; cap startup timeout; fallback is synchronous so no deadlock. |
| **State race condition if `/health` is called during init** | Low | Lifespan startup is atomic before any route is served. FastAPI queues requests until startup completes. No race. |
| **Lifespan vs lazy property trade-off** | Low | Lifespan (chosen) is explicit, testable, modern. Lazy property would be simpler but less clear when init happens and harder to test failure modes. |
| **Assistant is None between shutdown and next start (reload)** | Low | Uvicorn reload during dev will re-run lifespan handler. App state is cleared. Acceptable for dev; production uses single-process mode. |
| **Tests that import `app` directly see uninitialized state** | Medium | Existing `test_api.py` must use async test client, not direct `app` import. Verify all tests use `TestClient` or `AsyncClient`. |

---

## 6. Alternatives Considered

### A. Lazy Property (Rejected — less testable)

```python
@property
def assistant(self):
    if not hasattr(self, '_assistant'):
        self._assistant = UniversalAssistant()
    return self._assistant
```

**Pros:** Minimal diff; defers to first use.  
**Cons:** Init happens in request handler (async context unclear); harder to test failure; no explicit startup semantics; thread-unsafe without lock.

### B. Environment-var Preload in .env (Rejected — masks issue)

```bash
# Always set GOOGLE_API_KEY in .env, even if empty
GOOGLE_API_KEY=""
```

**Pros:** No code change; triggers fallback at init.  
**Cons:** Masks the real problem (missing creds in CI); does not help Docker/K8s where .env is not provided; requires all deployments to carry dummy file.

### C. Dependency Override at Test Time (Rejected — incomplete)

```python
from fastapi.testclient import TestClient
app.dependency_overrides[...] = lambda: MockAssistant()
```

**Pros:** Leaves production code unchanged; clear test setup.  
**Cons:** Does not fix production crash; still crashes on import if no key; only helps tests.

### D. **Lifespan Context Manager (Chosen)**

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.assistant = UniversalAssistant()
    yield
    # shutdown (if needed)

app = FastAPI(lifespan=lifespan)
```

**Pros:** Modern FastAPI pattern (0.93+); explicit startup/shutdown; async-friendly; testable via `AsyncClient`; routes access via `request.app.state`.  
**Cons:** Requires FastAPI 0.93+; routes must be updated to use `request.app.state`; slightly more code.

---

## 7. Open Questions

1. **Is `pyproject.toml` pinned to FastAPI 0.93+?**  
   Lifespan handler requires 0.93+. If older version in use, must update or fall back to `@app.on_event("startup")` pattern.

2. **Should `/health` validate connectivity (Firestore, LLM)?**  
   Out of scope for this change. Health always returns 200. Separate change can add optional health checks.

3. **Do we need graceful shutdown in the lifespan handler?**  
   Unlikely for LLM clients (stateless). Storage (Firestore) may have open connections. Covered in yield block if needed later.

4. **Are there other module-scope instantiations that will crash?**  
   Explore flagged `src/cli/main.py:43–44` has the same issue. Out of scope; separate fix.

5. **Should `assistant` be immutable after startup?**  
   Current design allows routes to read `app.state.assistant`. No guard against mutation. Acceptable; `UniversalAssistant` is not designed for re-init.

---

## Affected Files

- `src/api/app.py` (main change: defer init)
- `tests/test_api.py` (new test + async client setup)
- Possibly `pyproject.toml` (verify FastAPI version)

## Test Entry Point

New test in `tests/test_api.py`:

```python
async def test_server_starts_without_api_key():
    """
    Server boots without GOOGLE_API_KEY; /health returns 200; 
    /api/chat returns mock response.
    """
```

---

**Next Phase:** `spec` (design API details, lifespan handler pseudocode, test pseudocode).
