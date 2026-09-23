# Project Context — Universal RAG assistant engine

## Identity

- Name: `universal-rag-assistant-engine`
- Version: 1.0.0
- Author: Paco Alcaide (pacoaldev@gmail.com)
- License: MIT
- Python: >=3.10

## Purpose

Production-grade, modular RAG assistant engine. Multi-storage backends
(Firebase / Firestore implied), multi-LLM backends (Google Generative AI
implied). Designed to be domain-agnostic.

## Stack

- Runtime: Python 3.10+
- API: FastAPI + Uvicorn
- CLI: `assistant-cli` (entry `src.cli.main:main`), API server
  `assistant-api` (entry `src.api.app:start`)
- LLM: google-generativeai
- Storage: firebase-admin, google-cloud-firestore
- Validation/Config: pydantic, pydantic-settings
- UI/Logging: rich, python-dotenv

## Layout (top-level)

```text
src/
  cli/        # assistant-cli entry
  api/        # assistant-api entry (FastAPI)
  core/       # domain logic (likely RAG orchestrator)
  llm/        # LLM adapters
  storage/    # storage adapters (Firebase/Firestore)
tests/        # pytest suite
maskotas_knowledge_base.json   # single KB file (likely sample data)
Dockerfile, docker-compose.yml # container delivery
```

## Test runner

- Framework: pytest 8.0+
- Async: pytest-asyncio (auto mode)
- Command: `pytest` (addopts: `-v --tb=short`)
- testpaths: `["tests"]`
- Existing test files: `test_api`, `test_assistant`, `test_config`,
  `test_llm`, `test_storage`
- No `conftest.py` yet (gap)

## Gaps flagged for exploration phase

1. No `main.py`/`app.py` at root — entry points live under `src/`.
2. Single KB file (`maskotas_knowledge_base.json`) despite "universal"
   branding → suggests domain-agnostic claim is aspirational.
3. `pyproject.toml` and `requirements.txt` coexist — possible duplication
   (not yet inspected).
4. No `conftest.py` — pytest fixtures likely inline per file.
5. No `.github/`, no CI workflow files visible at top level.
6. No `CHANGELOG.md`, no `docs/`.
7. `README.md` badges reference actions that may not exist.

## Conventions

- Line length: 100 (ruff)
- Python target: 3.10
- Lint rules: E, F, I, W
- Module layout: src/ with subpackages, no top-level package

## Notes for downstream phases

- Strict TDD is active; every task in `sdd-tasks` must include a failing
  test that turns green.
- `delivery_strategy` defaults to `ask-on-risk`. When
  `sdd-tasks` forecasts >400 changed lines or `400-line budget risk: High`,
  orchestrator stops and asks before `sdd-apply`.
- Review budget: 400 lines per PR by default.