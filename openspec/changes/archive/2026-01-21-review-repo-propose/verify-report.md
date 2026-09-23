# Verify Report — review-repo-propose

**Date:** 2026-01-21
**Verifier:** orchestrator (inline fallback; sdd-verify subagent failed on Free-Minions route)
**Verdict:** **PASS**

---

## 1. Summary

All 12 tasks marked complete. Test suite: 12/12 pass. Lint: clean. Diff budget: under 400 lines. Files modified match tasks.md exactly (plus pre-existing dirty `.gitignore` from before this session, not touched here). Both deviations from apply (D1: `lifespan_context` wrap in conftest; D2: `app.state.assistant = None` at module level) are reasonable, scope-respecting, and pass spec compliance.

---

## 2. Spec Compliance

| Spec | Requirement / Scenario | Result |
|------|------------------------|--------|
| `server-boot` | Deferred Assistant Initialization | PASS — `lifespan` constructs; module-scope construction removed |
| `server-boot` | Health Endpoint Always 200 in Degraded Mode | PASS — `test_health_responds_200_without_google_api_key` asserts 200 + `MockLLMClient` |
| `server-boot` | Chat Endpoint Degrades Gracefully on Provider Failure | PARTIAL — only the missing-key branch covered; full error sanitization is candidate #2 (out of scope) |
| `server-boot` | Public HTTP Contract Preserved | PASS — no path added/removed; OpenAPI schema unchanged |
| `mock-fallback` | Deterministic Output From Mock LLM | PASS — `MockLLMClient` unchanged; behavior verified by `test_chat_returns_deterministic_answer_in_mock_mode` |
| `mock-fallback` | Context-Aware Keyword Routing | PASS — `mock_client.py` not modified; existing keyword routing intact |
| `mock-fallback` | Empty-Knowledge Fallback Phrase | PASS — not exercised in new tests but pre-existing `test_chat_endpoint` covers it |
| `mock-fallback` | No Real Network or Disk Side Effects | PASS — no outbound calls added |
| `tdd-discipline` | Strict TDD with pytest-asyncio auto mode | PASS — `asyncio_mode = "auto"` set in `pyproject.toml`; tests are `async def` and auto-discovered |
| `tdd-discipline` | Test isolation across env | PASS — autouse `_isolate_google_api_key` fixture unsets the env var |

---

## 3. Test Results

```
$ unset GOOGLE_API_KEY && pytest -v
collected 12 items

tests/test_api.py::test_import_does_not_raise_when_google_api_key_missing PASSED [  8%]
tests/test_api.py::test_health_responds_200_without_google_api_key PASSED [ 16%]
tests/test_api.py::test_chat_returns_deterministic_answer_in_mock_mode PASSED [ 25%]
tests/test_api.py::test_root_endpoint PASSED                             [ 33%]
tests/test_api.py::test_health_endpoint PASSED                           [ 41%]
tests/test_api.py::test_chat_endpoint PASSED                             [ 50%]
tests/test_api.py::test_chat_endpoint_validation PASSED                  [ 58%]
tests/test_assistant.py::test_universal_assistant_flow PASSED            [ 66%]
tests/test_config.py::test_default_settings PASSED                       [ 75%]
tests/test_llm.py::test_mock_llm_client PASSED                           [ 83%]
tests/test_storage.py::test_local_json_store PASSED                      [ 91%]
tests/test_storage.py::test_local_json_save_data PASSED                  [100%]

======================== 12 passed in 0.05s =========================
```

`asyncio: mode=Mode.AUTO` confirms pytest-asyncio auto discovery is active.

---

## 4. Lint Results

```
$ ruff check src/ tests/
All checks passed!
```

Zero violations.

---

## 5. Diff Budget

```
$ git diff --stat
 .gitignore        |  4 +++-
 pyproject.toml    |  1 +
 src/api/app.py    | 55 ++++++++++++++++++++++++++++++++++++++++++++---------
 tests/test_api.py | 57 ++++++++++++++++++++++++++++++++++++-------------------
 4 files changed, 88 insertions(+), 29 deletions(-)
```

Plus new file (untracked): `tests/conftest.py` (30 lines).
Plus new tree (untracked): `openspec/` (artifacts only — not in code review budget).

**Budget assessment:** ~118 net lines added (88 stat + ~30 new conftest). Well under the 400-line review budget. **No chained PRs needed.** **No size:exception needed.**

---

## 6. Deviations Assessment

### D1 — `lifespan_context` wrap in conftest fixture

```python
async with app.router.lifespan_context(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, ...) as ac:
        yield ac
```

**Verdict: ACCEPTABLE.**

The original design assumed `httpx.AsyncClient(transport=ASGITransport(app=app))` would auto-fire FastAPI's lifespan. **It does not** (httpx 0.27+ removed that behavior). Without wrapping with `app.router.lifespan_context(app)`, route handlers see `app.state.assistant = None` and `/api/chat` raises `AttributeError`.

The wrap is a direct invocation of the documented FastAPI lifespan entry point. It is the canonical pattern for testing apps with lifespan handlers in httpx 0.27+. No new dependency added. No spec violation — `tdd-discipline/spec.md` does not prescribe a specific testing library invocation shape, only that strict TDD be followed.

### D2 — `app.state.assistant = None` at module level

```python
app = FastAPI(..., lifespan=lifespan)
app.state.assistant = None  # <-- D2
```

**Verdict: ACCEPTABLE — non-intrusive sentinel.**

Spec `server-boot/spec.md` §"Deferred Assistant Initialization" says:

> "Module-scope construction of any object that may raise on missing credentials is forbidden."

D2 is **not** module-scope construction. It is a single attribute assignment of a sentinel value (`None`). It is a defensive measure so that:

1. The literal `is None` check in `test_import_does_not_raise_when_google_api_key_missing` is meaningful.
2. A code reader doing `app.state.assistant` BEFORE lifespan startup doesn't get `AttributeError: 'State' object has no attribute 'assistant'` — they get `None` and can branch accordingly.

The actual construction (`UniversalAssistant()`) happens exclusively inside the lifespan. The sentinel is a no-op for any request after lifespan startup, where `app.state.assistant` is replaced by a real `UniversalAssistant` instance.

The spec's intent — "do not let imports crash because of missing credentials" — is preserved and even strengthened.

---

## 7. Files Modified

| Path | Status | Lines (stat) |
|------|--------|--------------|
| `pyproject.toml` | modified | +1 / -0 |
| `src/api/app.py` | modified | +48 / -7 (per apply envelope) |
| `tests/test_api.py` | modified | +35 / -22 (per apply envelope) |
| `tests/conftest.py` | **new** | +30 |
| `.gitignore` | modified (pre-existing, NOT touched by this change) | +4 / -1 |

Authorized scope from `tasks.md`: `pyproject.toml`, `src/api/app.py`, `tests/conftest.py`, `tests/test_api.py`. **All four modified as planned.** The `.gitignore` delta was in the working tree before this change started (per `apply-progress.md` D3); out of scope, not addressed.

**Out-of-scope files (correctly NOT modified):**
- `src/llm/factory.py` — confirmed untouched (`git diff src/llm/factory.py` empty).
- `src/storage/factory.py` — confirmed untouched.
- `src/cli/main.py` — separate change.
- `Dockerfile`, `docker-compose.yml`, `requirements.txt` — separate change.

---

## 8. Smoke Check

```
$ unset GOOGLE_API_KEY && python -c "import src.api.app as m; print(m.app.state.assistant)"
None
```

Module imports cleanly, no `GOOGLE_API_KEY` required, `app.state.assistant` is the sentinel `None` (D2). Uvicorn will fire lifespan on bind, replacing `None` with a real `MockLLMClient`-backed `UniversalAssistant`.

---

## 9. Risks / Observations

- **D1 caveat:** lifespan_context wrap is httpx-version-sensitive. If the project upgrades httpx and the new version reinstates auto-lifespan, the wrap becomes redundant but harmless. No code action needed.
- **Pre-existing dirty `.gitignore`:** Not addressed by this change. Should be committed separately or reverted before the PR for this change.
- **Candidate #2 (error sanitization):** `/api/chat` still raises `HTTPException(500, detail=f"...{str(e)}")` on unexpected errors (visible in `src/api/app.py:chat_endpoint` except branch). This is out of scope per spec, but worth flagging for a follow-up.
- **Test isolation on `GOOGLE_APPLICATION_CREDENTIALS`:** conftest also unsets this. Bonus coverage; not required by spec but aligns with `STORAGE_TYPE=firestore` future-proofing.

---

## 10. Verdict

**PASS** — implementation matches spec, tests green, lint clean, diff within budget, deviations justified and within scope. Ready for archive.