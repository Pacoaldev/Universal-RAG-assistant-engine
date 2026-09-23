# Changelog — Universal RAG assistant engine (OpenSpec)

All notable changes to the canonical OpenSpec specs.

## 2026-01-21 — review-repo-propose

- **Promoted specs:** `server-boot`, `mock-fallback`, `tdd-discipline`
- **Implementation:** lifespan-based deferred `UniversalAssistant()` init in
  `src/api/app.py`. Module-scope construction removed; routes read
  `request.app.state.assistant`. Last-resort try/except in lifespan builds a
  forced mock+local assistant via the existing factories (no second fallback
  path).
- **Tests:** 12/12 pass (3 new RED tests + 4 migrated existing tests + 5
  pre-existing untouched tests).
- **Lint:** ruff clean.
- **Diff budget:** ~118 net lines added (88 stat + 30 new conftest). Well under
  the 400-line review budget. No chained PRs, no `size:exception` needed.
- **Deviations:** D1 (`lifespan_context` wrap in conftest for httpx 0.27+);
  D2 (`app.state.assistant = None` sentinel at module level to satisfy
  import-time `is None` contract).
- **Archive path:** `openspec/changes/archive/2026-01-21-review-repo-propose/`

### Why this change

Module-scope `assistant = UniversalAssistant()` in `src/api/app.py` raised on
import whenever `GOOGLE_API_KEY` was missing, bypassing the existing
`src/llm/factory.py` mock fallback and crashing uvicorn before bind. The fix
moves construction into the FastAPI lifespan context manager so the server
boots and `/health` returns 200 even with no secrets. Mock fallback (already in
the factory) handles the rest.

### Out of scope (next candidates)

- **Candidate #2:** full error-handling hardening for `/api/chat`
  (`HTTPException(500, detail=f"...{str(e)}")` path).
- **Candidate #3:** CORS / authentication (`allow_origins=["*"]` +
  `allow_credentials=True`, no auth on `/api/chat`).
- **Candidate #4:** real embeddings, chunker, vector index, semantic reranking
  (current `UniversalAssistant.ask` is lexical substring scoring on
  `json.dumps(doc).lower()`).
- **Candidate #5:** `.dockerignore`, secrets handling for Firestore service
  account, `requirements.txt` vs `pyproject.toml` dedup.
- **CLI startup fix:** `src/cli/main.py` shares the same module-scope
  instantiation risk; separate scope.