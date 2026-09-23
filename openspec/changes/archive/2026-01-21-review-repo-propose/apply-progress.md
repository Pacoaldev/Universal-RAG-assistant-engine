# Apply Progress — review-repo-propose

**Phase:** apply
**Mode:** strict TDD (RED → GREEN → REFACTOR)
**Executor:** sdd-apply (auto)
**Status:** success

## TDD Cycle Evidence

### RED (failing tests first)

- **pytest command:** `pytest -v`
- **Result:** `1 failed, 11 passed in 0.09s`
- **Failed test:** `tests/test_api.py::test_import_does_not_raise_when_google_api_key_missing`
- **Failure reason:** `AttributeError: 'State' object has no attribute 'assistant'` — module-scope `assistant = UniversalAssistant()` populated the route via a global, not `app.state.assistant`. Importing the module left `app.state` empty (no `assistant` attribute).
- **Note on the other two new tests:** `test_health_responds_200_without_google_api_key` and `test_chat_returns_deterministic_answer_in_mock_mode` PASSED in this environment even before the refactor. Reason: `google.generativeai` is not installed locally, so the existing factory's `try/except` already returns `MockLLMClient(prefix="[Fallback Mode]")`. The environment never triggered the original crash. These two tests still serve as regression guards: they assert the new contract (prefix + keyword) and would catch any future regression in the mock-fallback path.

### GREEN (implementation)

- **Changes:**
  - `src/api/app.py` — added `@asynccontextmanager async def lifespan(app)`, removed module-scope `assistant = UniversalAssistant()`, added `app.state.assistant = None` after `FastAPI(...)` for import-time contract, updated `health_check`, `chat_endpoint`, `get_knowledge_summary` to read `request.app.state.assistant`.
  - `pyproject.toml` — added `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`.
  - `tests/conftest.py` (NEW) — autouse `_isolate_google_api_key` (deletes `GOOGLE_API_KEY` + `GOOGLE_APPLICATION_CREDENTIALS`) + `client` async fixture that wraps `ASGITransport` with `app.router.lifespan_context(app)` to force lifespan execution (httpx 0.27+ does not auto-invoke lifespan).
  - `tests/test_api.py` — removed module-scope `TestClient`; migrated 4 existing tests to async + added 3 new RED tests.
- **pytest command:** `pytest -v`
- **Result:** `12 passed in 0.05s`

### REFACTOR

- **ruff command:** `ruff check src/ tests/`
- **Initial violations:** `tests/conftest.py:3:8 F401 os imported but unused`, `tests/conftest.py:31:21 W292 no newline`, `tests/test_api.py:63:39 W292 no newline`.
- **Fixes:** dropped `import os` (unused), appended trailing newlines.
- **Final ruff result:** `All checks passed!`
- **Final pytest command:** `pytest -v`
- **Final pytest result:** `12 passed in 0.05s`

## Smoke check (task 5.3)

Subprocess without `GOOGLE_API_KEY`:

```
$ python -c 'import src.api.app as m; print(m.app.state.assistant, bool(m.app.router))'
None True
```

Import succeeds. `app.state.assistant` is `None` (no eager construction). `app.router` exists.

## Files changed (git diff --stat)

```
pyproject.toml    |  1 +
src/api/app.py    | 55 ++++++++++++++++++++++++++++++++++++++++++++---------
tests/test_api.py | 57 ++++++++++++++++++++++++++++++++++++-------------------
4 files changed, 88 insertions(+), 29 deletions(-)
```

Plus new untracked file: `tests/conftest.py` (1102 bytes).

## Deviation from design

### D1 — Lifespan invocation in fixture

The design's literal `client` fixture code was:

```python
transport = ASGITransport(app=app)
async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
    yield ac
```

This does NOT invoke the lifespan context manager in httpx 0.27+ — verified locally (route handlers saw `assistant = None`). To make lifespan run, the fixture wraps the AsyncClient with `app.router.lifespan_context(app)`:

```python
async with app.router.lifespan_context(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
```

`lifespan_context` is the FastAPI/Starlette internal that fires the registered lifespan ASGI callable as a context manager. This is the canonical mechanism for invoking lifespan without adding `asgi-lifespan` as a new dependency (which the spec forbids: "no new test runner, no new plugin"). Same intent as the design; different mechanism.

### D2 — `app.state.assistant = None` at module level

The design's spec test asserts `app.state.assistant is None` at import time. The design's lifespan code only sets `app.state.assistant` inside the `try` block, which means at import time `app.state.assistant` does not exist (AttributeError). To make the contract `is None` literally true, `app.state.assistant = None` is initialized at module level, right after `app = FastAPI(...)`. The lifespan then upgrades it to the real instance (or rebuilds it on the catastrophic-failure path).

## Out-of-scope confirmation

- `src/llm/factory.py` — NOT modified (verified fallback path already handles missing `GOOGLE_API_KEY`).
- `src/storage/factory.py` — NOT modified (Firestore is lazy-init).
- `src/llm/mock_client.py`, `src/llm/gemini_client.py` — NOT modified.
- `src/storage/*.py`, `src/core/*.py`, `src/cli/main.py` — NOT modified.
- `Dockerfile`, `docker-compose.yml`, `requirements.txt` — NOT modified.

## TDD discipline notes

- RED authored before any production change to `src/api/app.py`.
- Tests turned green only after the lifespan refactor landed.
- No test was skipped (`@pytest.mark.skip` not used).
- Refactor pass did not change behavior; only removed an unused import and added trailing newlines.

## Risk register (post-apply)

| Risk | Status |
|------|--------|
| httpx 0.27+ ASGITransport does not auto-invoke lifespan | Mitigated via `app.router.lifespan_context(app)` in the `client` fixture |
| Local env: `google.generativeai` missing | Mitigated by factory fallback to `MockLLMClient` — confirmed by `test_chat_returns_deterministic_answer_in_mock_mode` |
| Spec test contract `is None` at import time | Mitigated by module-level `app.state.assistant = None` |

## Next recommended

`sdd-verify` — verify the implementation against specs and design.