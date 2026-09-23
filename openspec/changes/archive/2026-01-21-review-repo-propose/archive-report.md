# Archive Report — review-repo-propose

**Date:** 2026-01-21
**Archiver:** orchestrator (inline fallback; sdd-archive subagent failed on Free-Minions route)
**Verify verdict:** PASS

---

## 1. Summary

First OpenSpec archive for the `universal-rag-assistant-engine` project.
Implementation: FastAPI lifespan refactor in `src/api/app.py` that defers
`UniversalAssistant()` construction from module-scope to startup. Three new
specs promoted to canonical. 12/12 tests pass. Lint clean. Diff under budget.

---

## 2. Promoted Specs (canonical SHA-256)

| Domain | Path | SHA-256 |
|--------|------|---------|
| server-boot | `openspec/specs/server-boot/spec.md` | `c3b2fcb6bc929c9c66e97c0901cf05d4fccc6f35db8a68302a16dc4b4acffdda` |
| mock-fallback | `openspec/specs/mock-fallback/spec.md` | `4063c93d5bee4d1f189e22bfffbf6b234eb37dd4e5d84ff21e1ccb37578d2c5e` |
| tdd-discipline | `openspec/specs/tdd-discipline/spec.md` | `9814bbc074214b85d77a995f9474146e7e9737925c84b706f9a21c91855a373e` |

Original change copies preserved at
`openspec/changes/archive/2026-01-21-review-repo-propose/specs/*/spec.md`
for audit.

---

## 3. Task Truth (final state, captured pre-archive)

Source: `openspec/changes/archive/2026-01-21-review-repo-propose/tasks.md`

### 1. Test infrastructure
- [x] 1.1 Add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]` in `pyproject.toml`.
- [x] 1.2 Create `tests/conftest.py` with autouse `_isolate_google_api_key` + `client` AsyncClient fixture using `lifespan_context` + `ASGITransport`.

### 2. Failing tests (red)
- [x] 2.1 `test_import_does_not_raise_when_google_api_key_missing` — RED confirmed (AttributeError on `app.state.assistant`).
- [x] 2.2 `test_health_responds_200_without_google_api_key` — regression guard; in this environment the factory fallback already covers the missing-key path, so the test turned green alongside the other tests. Documented as such in `apply-progress.md`.
- [x] 2.3 `test_chat_returns_deterministic_answer_in_mock_mode` — same as 2.2.

### 3. Implementation (green)
- [x] 3.1 Refactor `src/api/app.py`: `lifespan` async context manager; module-scope construction removed; `app.state.assistant = None` sentinel at module level (deviation D2).
- [x] 3.2 Route handlers (`/health`, `/api/chat`, `/api/knowledge`) read `request.app.state.assistant`.
- [x] 3.3 `src/llm/factory.py` fallback verified to cover missing-key case; no code change.

### 4. Migrate existing tests
- [x] 4.1 All 4 existing tests in `tests/test_api.py` migrated to async `client` fixture.

### 5. Verify & refactor
- [x] 5.1 `pytest -v` — 12 passed.
- [x] 5.2 `ruff check src/ tests/` — All checks passed.
- [x] 5.3 Smoke: `python -c 'import src.api.app; ...'` — no ImportError, prints `None`.

---

## 4. Verification Findings

See: `openspec/changes/archive/2026-01-21-review-repo-propose/verify-report.md`
Verdict: **PASS**.

Headline numbers:
- 12/12 tests pass
- ruff: 0 violations
- diff stat: 4 files changed, 88 insertions(+), 29 deletions(-) + new `tests/conftest.py` (30 lines) = ~118 net lines (under 400 budget)
- 0 unauthorized files modified

---

## 5. Deviations Honored

Both deviations were captured in `apply-progress.md` and assessed in
`verify-report.md`. They are preserved in this archive.

- **D1** — `lifespan_context` wrap in `tests/conftest.py` because httpx 0.27+ no longer auto-fires FastAPI lifespan. Accepted as canonical pattern.
- **D2** — `app.state.assistant = None` sentinel at module level in `src/api/app.py` to satisfy the literal `is None` import-time contract. Non-intrusive; the actual construction still happens exclusively inside `lifespan`.

---

## 6. Rollback Notes

The move is reversible:

```bash
mv openspec/changes/archive/2026-01-21-review-repo-propose openspec/changes/review-repo-propose
```

The canonical specs already promoted remain in `openspec/specs/`; rolling back
the change directory does NOT un-promote them. To fully unwind:

```bash
rm -rf openspec/specs/server-boot openspec/specs/mock-fallback openspec/specs/tdd-discipline
mv openspec/changes/archive/2026-01-21-review-repo-propose openspec/changes/review-repo-propose
git checkout -- pyproject.toml src/api/app.py tests/test_api.py
rm tests/conftest.py
```

Code rollback touches: `pyproject.toml`, `src/api/app.py`, `tests/test_api.py`,
and removes `tests/conftest.py`. No data loss beyond the change artifacts
themselves.

---

## 7. End-of-cycle state

- `openspec/specs/` — 3 canonical specs (server-boot, mock-fallback, tdd-discipline).
- `openspec/changes/` — only `archive/` remains; no active changes.
- Next SDD change can start with `/gentle-sdd-status` (will recommend `sdd-new`).

---

## 8. Risks

- Subagent fallback was used for both `sdd-verify` and `sdd-archive` (Free-Minions / MinionsSub routes returned "assistant reported an error"). Future phases of other changes may need similar inline fallback unless those model routes recover.
- Pre-existing dirty `.gitignore` (not part of this change) remains in the working tree.
- Candidate #2 (chat error sanitization) is the natural next change and is unblocked now that #1 ships.