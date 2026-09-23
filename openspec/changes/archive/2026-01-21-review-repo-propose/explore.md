# SDD Explore — Universal RAG Assistant Engine

Scope: surface real gaps, not invented refactors.
Method: read every file under `src/`, all 5 tests, infra, KB sample, README.
No code proposed. No tech recommendations.

## RAG pipeline shape (actual, not advertised)

`src/core/assistant.py::UniversalAssistant.ask()`:

1. `self.llm.validate_input(query)` — delegates validation to LLM adapter.
2. `self.storage.search(query)` — `LocalJSONKnowledgeStore` tokenizes query,
   scores each document by `re.findall(r'\b<token>\b', json.dumps(doc).lower())`,
   returns top-K per category. `FirestoreKnowledgeStore` does a substring
   match on each doc dump.
3. `_format_context` → joins doc dumps into a string.
4. Prompt assembly + `self.llm.generate_response(prompt)`.

There is no `chunker`, no `embedder`, no vector index, no similarity ranking
beyond substring frequency. The label "RAG" in README and pyproject
description is aspirational, not implemented. `mock_client.py` answers
from a hardcoded if/elif chain — it does not consume retrieved context.

## Candidates (ranked by severity, evidence, why it matters)

### 1. Module-level `assistant = UniversalAssistant()` in `api/app.py` crashes server on startup when creds are missing or LLM init fails
- **Severity:** high
- **Files:** `src/api/app.py:42`, `src/llm/factory.py:24-33`, `src/llm/gemini_client.py:23-28`, `src/core/config.py:30`
- **Why it matters:** `app = FastAPI(...)` is followed by `assistant = UniversalAssistant()`. With `LLM_PROVIDER=gemini` and no `GOOGLE_API_KEY`, `GeminiClient.__init__` raises `ValueError`. The server cannot import → uvicorn fails → Docker HEALTHCHECK returns "unhealthy" forever; `/health` never responds. The factory has a fallback to `MockLLMClient`, but the API never uses the factory — it instantiates `UniversalAssistant()` directly. A typo in `.env`, a missing key in CI, or `STORAGE_TYPE=firestore` without ADC all kill the process before FastAPI can bind.
- **Evidence:** `src/api/app.py:42` instantiates `UniversalAssistant()` at import time. `src/llm/factory.py:23-30` is the only place the fallback exists; `assistant.py:48-49` calls it, but `app.py` bypasses it.

### 2. `/api/chat` leaks raw exception strings to clients; LLM errors are returned as normal answers instead of raising
- **Severity:** high (security + UX)
- **Files:** `src/api/app.py:82-92`, `src/llm/gemini_client.py:55-58`, `src/llm/factory.py:29-33`
- **Why it matters:** `chat_endpoint` catches `Exception` and returns
  `detail=f"Error interno al procesar la consulta: {str(e)}"`. Anything raised by
  the stack — file paths, library internals, partial API responses — is echoed
  to the HTTP client. `GeminiClient.generate_response` returns
  `f"Lo siento, ocurrió un problema ... : {str(e)}"` as a plain answer, so the
  caller never sees the failure mode. `assistant.ask` cannot tell success from
  provider failure; metrics (`processing_time_ms`) record a "successful"
  response for an outage.
- **Evidence:** `src/api/app.py:86-91` (`raise HTTPException(... detail=f"...{str(e)}")`), `src/llm/gemini_client.py:56-58`.

### 3. CORS `allow_origins=["*"]` with `allow_credentials=True` and zero authentication on `/api/chat`
- **Severity:** high
- **Files:** `src/api/app.py:28-34`
- **Why it matters:** The combination is a known security antipattern
  (Starlette rejects it in newer versions; in supported versions browsers can
  send credentialed cross-origin requests to the API). The README makes no
  mention of auth, rate limiting, or API keys. Any deployment exposing `:8000`
  to the public internet is unauthenticated and quotable.
- **Evidence:** `src/api/app.py:29-34` (middleware init); `app.py:79-93` (`/api/chat` has no auth dependency); no auth middleware in `requirements.txt` or `pyproject.toml`.

### 4. "RAG" branding with no embeddings, no chunker, no vector index — and `mock_client.py` ignores retrieved context
- **Severity:** high (semantic / architecture)
- **Files:** `README.md:1-50` (claims), `pyproject.toml:description` (claim), `src/core/assistant.py:90-115` (pipeline), `src/storage/local_json.py:43-77` (retrieval), `src/llm/mock_client.py:21-49` (mock), `src/storage/firestore_store.py:55-73` (firestore retrieval).
- **Why it matters:** Retrieval is pure lexical: tokenize query → count occurrences of each token in `json.dumps(doc).lower()`. There is no semantic similarity, no embeddings, no chunk splitter (each top-level dict under any category is treated as one document, including its full `faqs` list). Mock LLM answers from a hardcoded `if/elif` on keywords ("vacun", "horario", "urgencia", "precio") and never reads the retrieved context — `test_llm.py` passes because of this hardcoding, masking the fact that `assistant.ask` does not actually wire context → LLM in offline mode. Anyone reading "RAG" and pointing this at a domain other than veterinary Spanish keywords will get nonsense.
- **Evidence:** `src/storage/local_json.py:55-67` (scoring), `src/storage/firestore_store.py:64-72` (substring match on doc dump), `src/llm/mock_client.py:21-49` (no `prompt` inspection beyond keyword match), `tests/test_llm.py:14-16` only asserts prefix and the word "vacunación" — never asserts that retrieved docs reached the answer.

### 5. `requirements.txt` duplicates runtime deps from `pyproject.toml`, drifts from dev deps, and there is no `.dockerignore` + no secrets handling for the Firestore service account
- **Severity:** medium
- **Files:** `requirements.txt:1-12`, `pyproject.toml:18-37`, `.github/workflows/ci.yml:23-25`, `Dockerfile:21-23`, `docker-compose.yml:11-15`, `.gitignore:1-9`
- **Why it matters:**
  - `requirements.txt` lists the 9 runtime deps plus `pytest`, `pytest-asyncio`, `httpx`. CI installs from `requirements.txt` and then `pip install ruff` separately (`ci.yml:25`) because `ruff`/`mypy` are only in `pyproject[dev]`. A new contributor who runs `pip install -r requirements.txt` never gets `ruff` or `mypy`. `requirements-dev.txt` is missing.
  - All version specifiers are `>=` lower bounds — no upper bound, no lock file. `pip install -r requirements.txt` and `pip install -e .` can yield different graphs.
  - `Dockerfile:22` does `COPY . .` with no `.dockerignore`. `.git/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `logs/`, and a local `.env` (if present) all enter the build context. A `.env` accidentally created on the host (not committed, gitignored) would be baked into the image and the `GOOGLE_API_KEY` would leak to anyone with `docker history`.
  - `docker-compose.yml` does not mount or `secrets:` the Firebase service-account JSON. `STORAGE_TYPE=firestore` in compose has no path to the credential file; users either bake it into the image (leak) or fail at runtime.

## Other gaps worth surfacing (lower priority, not in top 5)

- **No `conftest.py`** (`tests/`). Fixtures are recreated per-file (`tmp_path` in `test_storage.py`, inline setup in `test_assistant.py`).
- **Coverage gaps in tests:** `src/core/logger.py` (0 tests), `src/cli/main.py` (0 tests), `src/llm/factory.py` (0 tests), `src/storage/factory.py` (0 tests), `src/llm/gemini_client.py` (0 tests — no `genai` mock), `src/storage/firestore_store.py` (0 tests). KB failure modes (missing file, malformed JSON, encoding errors) are untested.
- **Hardcoded veterinary defaults in `Settings`:** `ASSISTANT_NAME="Maskotas Bot"`, `ORGANIZATION_NAME="Clínica Veterinaria Maskotas"`, `FIRESTORE_COLLECTIONS={"general_info": "informacion_general_clinica", "services": "servicios_veterinaria"}` (`src/core/config.py:25-52`). A "Universal" project that defaults to a veterinary clinic name contradicts its own README universal-domain example (`productos`/`politicas`).
- **`LocalJSONKnowledgeStore` caches `_data` in memory forever after `__init__`.** No reload on file change. Multi-worker deployments diverge on writes; hot-reload requires restart.
- **No schema validation on the KB file.** A typo in a category name silently produces empty results. The README universal example (`productos`, `politicas`) does not match the default Firestore collection names — adapting to a new domain silently leaves the Firestore store pointing at nonexistent veterinary collections.
- **Logger singleton in `core/logger.py`** uses module-level `_initialized` bool and returns `logging.getLogger("assistant")` from `setup_logging` but the function is only called the first time. Tests that patch `LOG_LEVEL` won't see effect because `setup_logging` early-returns on `_initialized=True`. No way to reset.
- **`src/cli/main.py:43-44`** instantiates `UniversalAssistant()` itself if no assistant is passed, inheriting the same startup-crash risk as `api/app.py`. The `except Exception as e` (line 103) prints and continues — infinite spin loop on init failure.
- **`validate_input` lives on `BaseLLMClient`** (`src/llm/base.py:22-30`) but `UniversalAssistant.ask` calls `self.llm.validate_input(query)`. Validation semantics are tied to the LLM implementation, not the domain. Two LLM adapters can validate differently.
- **README inaccuracies:**
  - Line 112: `# O directamente: python chatbot.py` — file `chatbot.py` does not exist anywhere in the repo. The README points users at a nonexistent entry point.
  - Line 169 references `LICENSE`; the actual file is `LICENSE.md` (verified by `find`). Cosmetic but inconsistent.
- **CI badge in README** references `actions/workflows/ci.yml` — the file exists at `.github/workflows/ci.yml`. Badge works.
- **`maskotas_knowledge_base.json`** has a key `informacion_general_clinica` (plural), matching `Settings.FIRESTORE_COLLECTIONS` defaults — but the file also contains entries with `tema: "dirección"` whose `respuesta` mentions "Calle Ficticia, 123, Manises" while another entry says "Madrid" (line `dirección` answer mentions Madrid inside `contacto` answer, then Manises inside `dirección` answer — `maskotas_knowledge_base.json` has a minor data inconsistency: `contacto` says "Calle Ficticia, 123, Madrid" but `dirección` says "Calle Ficticia, 123, Manises"). Cosmetic; not a code bug.

## Files inspected

- `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`, `.dockerignore` (absent)
- `Dockerfile`, `docker-compose.yml`
- `README.md`, `LICENSE.md`
- `maskotas_knowledge_base.json`
- `src/api/app.py`, `src/api/__init__.py`
- `src/cli/main.py`, `src/cli/__init__.py`
- `src/core/assistant.py`, `src/core/config.py`, `src/core/logger.py`, `src/core/__init__.py`
- `src/llm/base.py`, `src/llm/factory.py`, `src/llm/gemini_client.py`, `src/llm/mock_client.py`, `src/llm/__init__.py`
- `src/storage/base.py`, `src/storage/factory.py`, `src/storage/firestore_store.py`, `src/storage/local_json.py`, `src/storage/__init__.py`
- `tests/test_api.py`, `tests/test_assistant.py`, `tests/test_config.py`, `tests/test_llm.py`, `tests/test_storage.py`, `tests/__init__.py` (empty)
- `.github/workflows/ci.yml`

## Next-recommended proposal

Candidate **#1 (API startup crash)** is the first to propose. It is the smallest
diff to fix, blocks real deployments (any missing env var kills the container),
and unblocks downstream concerns (auth, observability) because once `/health`
actually responds reliably the rest of the hardening can be measured.
