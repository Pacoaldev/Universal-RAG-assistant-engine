# Server Boot Without Secrets — Specification

## Purpose

The FastAPI server MUST bind its listening port and answer `GET /health`
with HTTP 200 even when required external secrets (`GOOGLE_API_KEY`,
Firestore credentials) are absent, empty, or invalid. Missing or invalid
secrets MUST be detected and contained at startup, never at module import
time, so that container healthchecks and developer startup flows succeed.

## Requirements

### Requirement: Deferred Assistant Initialization

The system MUST instantiate `UniversalAssistant` inside the FastAPI
lifespan startup handler, NOT at module-import time. Module-scope
construction of any object that may raise on missing credentials is
forbidden.

#### Scenario: assistant is constructed after lifespan startup

- GIVEN `LLM_PROVIDER="gemini"` and `GOOGLE_API_KEY` is unset
- WHEN uvicorn imports `src.api.app`
- THEN the module import succeeds without raising
- AND `app.state.assistant` is `None` until the lifespan handler runs
- AND after the lifespan startup completes, `app.state.assistant` is a
  fully constructed `UniversalAssistant` instance

#### Scenario: existing factory fallback is preserved

- GIVEN `LLM_PROVIDER="gemini"` and `GOOGLE_API_KEY` is unset
- WHEN the lifespan handler constructs the assistant
- THEN `src.llm.factory.get_llm_client` is the only path that selects
  the LLM implementation
- AND `GeminiClient` construction failure MUST cause `MockLLMClient` to
  be selected, exactly as today
- AND no second fallback path is introduced in `src.api.app`

### Requirement: Health Endpoint Always 200 in Degraded Mode

The `GET /health` endpoint MUST respond with HTTP 200 and a body
matching `HealthResponse` regardless of whether LLM and storage backends
were initialized in degraded mode.

#### Scenario: health responds 200 with no Google API key

- GIVEN no `GOOGLE_API_KEY` is present in the process environment
- AND `LLM_PROVIDER="gemini"`
- WHEN uvicorn boots the app and a client calls `GET /health`
- THEN the response status code is `200`
- AND the body contains `status: "healthy"`
- AND the body contains a non-empty `assistant_name`
- AND the body contains `llm_provider` reflecting the effective
  backend (`GeminiClient` if key present, `MockLLMClient` otherwise)

#### Scenario: health responds 200 with missing Firestore credentials

- GIVEN Firestore credentials are absent or unreachable
- AND `STORAGE_TYPE="firestore"`
- WHEN a client calls `GET /health`
- THEN the response status code is `200`
- AND the body still reports `status: "healthy"`
- AND the response body may indicate a degraded storage backend, but
  MUST NOT raise an HTTP 5xx

#### Scenario: health route never raises HTTPException

- GIVEN any combination of missing or invalid LLM and storage secrets
- WHEN a client calls `GET /health`
- THEN the route handler MUST NOT call `raise HTTPException(...)`
- AND the route handler MUST NOT leak exception tracebacks into the
  response body

### Requirement: Chat Endpoint Degrades Gracefully on Provider Failure

When the configured LLM provider cannot be used, `POST /api/chat` MUST
return a structured response that signals the failure mode to the
client without leaking stack traces. A raw `HTTP 500` with
`detail=f"...{str(e)}"` is NOT acceptable in this change.

#### Scenario: chat returns structured failure when key is invalid

- GIVEN `GOOGLE_API_KEY` is present but rejected by the upstream API
  (401/403 from the provider)
- WHEN a client POSTs `{"query": "..."}` to `/api/chat`
- THEN the response status code is `503`
- AND the response body contains a structured error with a stable
  `code` field (e.g. `"code": "llm_unavailable"`)
- AND the response body MUST NOT contain a Python stack trace or
  internal library message

#### Scenario: chat works in mock fallback when key is missing

- GIVEN no `GOOGLE_API_KEY` is present
- AND `LLM_PROVIDER="gemini"`
- WHEN a client POSTs `{"query": "¿Cuáles son los horarios de atención?"}`
  to `/api/chat`
- THEN the response status code is `200`
- AND the response body is a valid `AssistantResponse`
- AND the `answer` field is produced by `MockLLMClient`

### Requirement: Public HTTP Contract Preserved

The change MUST NOT alter the externally visible HTTP contract of
`/`, `/health`, `/api/chat`, or `/api/knowledge`. Existing clients and
OpenAPI consumers MUST NOT need to change.

#### Scenario: OpenAPI schema remains stable

- GIVEN the change is merged
- WHEN a client fetches `/openapi.json`
- THEN the schema for `/health` still defines `HealthResponse`
- AND the schema for `/api/chat` still accepts `ChatRequest` and
  returns `AssistantResponse`
- AND no path is added, removed, or renamed

#### Scenario: /health remains unauthenticated

- GIVEN the change is merged
- WHEN a request without any auth headers is made to `GET /health`
- THEN the server responds 200
- AND no auth middleware or dependency blocks the request

## Out of scope

- **Candidate #2** — full error-handling hardening for `/api/chat`
  (removing the raw `detail=f"...{str(e)}"` path in all failure
  modes, structured logging, retry classification, sanitized
  upstream-error mapping). This change only covers the "no API key"
  branch.
- **Candidate #3** — CORS hardening, authentication, rate limiting
  on `/api/chat`. The current `allow_origins=["*"]` + `allow_credentials=True`
  combination stays untouched.
- **Candidate #4** — real embeddings, chunker, vector index, semantic
  reranking. Retrieval remains the existing lexical token-frequency
  scorer in `src/storage/local_json.py`.
- **Candidate #5** — `.dockerignore`, secrets handling for Firestore
  service-account JSON, dependency consolidation. No infrastructure
  files change in this proposal.
- **CLI startup fix** — `src/cli/main.py` has the same module-scope
  instantiation risk and is explicitly out of scope.
- **Health check depth** — `/health` does NOT probe Firestore, Gemini
  network reachability, or vector store connectivity. Degraded mode
  is always "healthy" in this change.
- **Configuration changes** — no new env vars. `Settings` is unchanged.