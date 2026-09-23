# Strict TDD Discipline — Specification

## Purpose

Every code change under the `review-repo-propose` change MUST be
authored test-first. A failing test MUST be added (or updated) before
any production code under `src/` is modified. The test MUST turn green
with the production change. This guarantees `pytest` is the source of
truth for behavior, not documentation.

## Requirements

### Requirement: Test-First Workflow

For every requirement defined in `server-boot/spec.md` and
`mock-fallback/spec.md`, the implementer MUST add or update a pytest
test that fails on `main` and passes after the implementation lands.
Implementation work that ships without a covering test MUST be
reverted.

#### Scenario: failing test exists before implementation

- GIVEN a new requirement is added to `specs/<domain>/spec.md`
- WHEN the `sdd-apply` phase begins
- THEN a pytest test in `tests/` exercises that requirement
- AND running `pytest` against the un-applied implementation exits
  non-zero with the new test listed as failed
- AND running `pytest` after the implementation lands exits zero
  with the new test passing

#### Scenario: test file location

- GIVEN a new behavior is added in `src/api/app.py`
- WHEN tests are authored
- THEN they live in `tests/test_api.py` (HTTP behavior) or a new
  module under `tests/` colocated by concern
- AND no test file is created under `src/`

### Requirement: Pytest Async Mode Auto

Async tests MUST run under `pytest-asyncio` with `asyncio_mode =
"auto"` configured in `pyproject.toml`. No test function MAY decorate
itself with `@pytest.mark.asyncio` unless that decoration is required
because auto mode is disabled.

#### Scenario: async test runs without explicit marker

- GIVEN `pyproject.toml` declares `[tool.pytest.ini_options] asyncio_mode = "auto"`
- WHEN a new async test `async def test_health_under_degraded_mode()`
  is added to `tests/test_api.py`
- THEN `pytest` discovers and executes it without an explicit
  `@pytest.mark.asyncio` decorator
- AND the test result is reported in the standard pytest summary

#### Scenario: FastAPI lifespan is exercised via AsyncClient

- GIVEN the lifespan handler is now the source of truth for assistant
  construction
- WHEN tests need to validate startup behavior
- THEN they use `httpx.AsyncClient` with
  `ASGITransport(app=app)` (or `lifespan="on"` for `TestClient`)
- AND they do NOT import `app` at module scope and rely on module
  load to construct the assistant

### Requirement: Test Command and Configuration

The canonical test command is `pytest` with the addopts and config
already declared in `pyproject.toml`:

- `-v` (verbose)
- `--tb=short`
- `testpaths = ["tests"]`
- `asyncio_mode = "auto"`

No new test runner, no new config file, no new plugin MUST be
introduced for this change.

#### Scenario: running pytest is sufficient

- GIVEN a clean checkout with the change applied
- WHEN the developer runs `pytest` from the repo root
- THEN all collected tests run
- AND the exit code is `0` on success, non-zero on any failure
- AND no additional `pip install` step is required to run the suite

#### Scenario: pytest-asyncio is already installed

- GIVEN the project's runtime dependencies
- WHEN `pytest` is invoked
- THEN the `pytest-asyncio` plugin is auto-loaded
- AND a warning about an unregistered async marker does NOT appear

### Requirement: Test Coverage of Degraded Startup

Tests MUST cover the "server boots without secrets" scenarios
explicitly. They MUST NOT rely on mocking the LLM factory to fake the
fix; they MUST run against the real lifespan handler with the env var
unset.

#### Scenario: health under no GOOGLE_API key

- GIVEN `GOOGLE_API_KEY` is unset in the test process environment
- AND the lifespan handler has run
- WHEN the test client GETs `/health`
- THEN the response is 200 with `status: "healthy"`

#### Scenario: chat under no GOOGLE_API key

- GIVEN `GOOGLE_API_KEY` is unset in the test process environment
- AND the lifespan handler has run
- WHEN the test client POSTs a valid query to `/api/chat`
- THEN the response is 200
- AND the response `answer` is non-empty and deterministic

#### Scenario: test isolation from host environment

- GIVEN the developer's shell has `GOOGLE_API_KEY` set
- WHEN the new test runs
- THEN the test MUST NOT depend on that value
- AND the test MUST work the same way on a machine without the
  variable
- AND the test MUST clean up any environment mutation it performs
  (use `monkeypatch.setenv(..., None)` or fixture teardown)

## Out of scope

- **Candidate #2** — testing the new error-shape responses for
  `/api/chat` is only required for the single "invalid API key"
  branch covered by `server-boot/spec.md`. The broader error-mapping
  matrix belongs to candidate #2.
- **Candidate #3** — auth/rate-limit tests are not required; no
  auth surface is touched in this change.
- **Candidate #4** — vector index, chunker, embedding tests are not
  required; no RAG semantics change.
- **Candidate #5** — `requirements-dev.txt`, lockfile, or `.dockerignore`
  tests are not required; no infrastructure changes here.
- **Coverage threshold enforcement** — `pytest --cov` or any
  coverage gate is not introduced in this change.
- **Mutation testing, property-based testing, contract testing** —
  out of scope; stick to plain pytest.