# Tasks: review-repo-propose

> Strict TDD is active. Tasks 1–2 are RED (failing tests). Task 3 is GREEN
> (implementation that turns them green). Task 4 migrates existing tests.
> Task 5 verifies and refactors.

## 1. Test infrastructure

- [x] 1.1 Add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]` in `pyproject.toml`.
- [x] 1.2 Create `tests/conftest.py` with:
  - autouse fixture that unsets `GOOGLE_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, and any other secrets in `os.environ` before each test.
  - `async_client` fixture using `httpx.AsyncClient(transport=httpx.ASGITransport(app=src.api.app.app))`. <!-- sdd-owner: implementation -->

## 2. Failing tests (red)

- [x] 2.1 In `tests/test_api.py`, add `test_import_does_not_raise_when_google_api_key_missing` — direct import of `src.api.app`, asserts no exception.
- [x] 2.2 In `tests/test_api.py`, add `test_health_responds_200_without_google_api_key` — drives lifespan via `async_client`, GETs `/health`, asserts status 200, body `status == "healthy"`, body `llm_provider == "mock"`.
- [x] 2.3 In `tests/test_api.py`, add `test_chat_returns_deterministic_answer_in_mock_mode` — POSTs to `/api/chat` with `{"query": "¿Cuáles son los horarios de atención?"}`, asserts status 200, `answer` starts with the configured `MockLLMClient` prefix, and contains `"horario"` (case-insensitive).

## 3. Implementation (green)

- [x] 3.1 Refactor `src/api/app.py`:
  - Remove module-scope `assistant = UniversalAssistant()`.
  - Add an `async def lifespan(app: FastAPI)` context manager that constructs `UniversalAssistant(...)` inside the `try` block and assigns to `app.state.assistant`. Catch exceptions, log, and assign `app.state.assistant = None` if construction still fails (defensive).
  - Wire `app = FastAPI(lifespan=lifespan, ...)`.
- [x] 3.2 Update route handlers (`/health`, `/api/chat`, `/api/knowledge`) to read `request.app.state.assistant` instead of the module-level `assistant`.
- [x] 3.3 Read `src/llm/factory.py` and confirm `MockLLMClient` is returned when `GeminiClient` raises `ValueError` on missing `GOOGLE_API_KEY`. If confirmed, no code change here. If not, add the missing fallback.

## 4. Migrate existing tests

- [x] 4.1 Migrate the 4 existing tests in `tests/test_api.py` from synchronous `TestClient(app)` (which currently relies on the buggy module-scope `assistant`) to the new `async_client` fixture. Assert equivalent behavior.

## 5. Verify & refactor

- [x] 5.1 Run `pytest -v` — all tests green, zero warnings escalated to errors.
- [x] 5.2 Run `ruff check src/ tests/` — no new lint errors.
- [x] 5.3 Smoke check: spawn a Python subprocess without `GOOGLE_API_KEY`, import `src.api.app`, assert no exception and `/health` reachable.

## Review Workload Forecast

- Estimated changed lines: ~130.
- 400-line budget risk: Low.
- Chained PRs recommended: No.
- Decision needed before apply: No.
- Delivery strategy: stays `ask-on-risk` (default); no risk threshold triggered.

## Notes

- All file paths are relative to repo root.
- Tests must be authored before implementation; the gatekeeper validates RED → GREEN ordering.
- Out-of-scope items (candidates #2–#5, CLI startup fix) remain untouched and are tracked elsewhere.

## Apply-phase deviations (recorded for review)

- D1: `client` fixture wraps `ASGITransport` with `app.router.lifespan_context(app)` to fire lifespan — httpx 0.27+ does not auto-invoke lifespan on ASGITransport. Same intent as design §3; different mechanism. No new dependency added.
- D2: `app.state.assistant = None` set after `FastAPI(...)` at module level to satisfy the spec test contract (`is None` at import time) before lifespan runs.