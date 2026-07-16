# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Patch Machine — an LLM-agent based AI office-work / BPA system for non-IT companies. GitHub Issues and Discord messages flow through agents into patch proposals; office features (hiring, handover, document automation, work scheduling) run in the same console. There is **no database**: the `archive/` directory of Markdown/JSON/JSONL files is the single source of truth ("MD GitOps"). Sensitive work routes to a local vLLM model; general work routes to cloud providers (OpenAI/Anthropic/Gemini/Together).

## Commands

```bash
# Setup (Python 3.11, uv)
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"          # add ,local-ai for the vLLM/GPU stack (Linux only)
cp .env.example .env

# Lint / format / type-check (mypy is strict)
ruff check . && ruff format --check .
mypy negotium

# Tests (pytest, asyncio_mode=auto — async tests need no marker)
pytest -q
pytest tests/unit/test_graph.py -q                 # single file
pytest tests/unit/test_graph.py::test_name -q     # single test

# Run backend (FastAPI on :8080)
negotium serve
# Other CLI: llm-gateway --port 8090 | reindex | reset-state --yes --actor <name> | skill list/run | replay

# Frontend (React+Vite on :5173, proxies /api and /health to :8080)
npm install --prefix frontend
npm run dev --prefix frontend
npm run build --prefix frontend    # tsc -b && vite build

# Docker (no vLLM/CUDA in image; forces NG_VLLM_MODE=http)
docker compose -f docker/docker-compose.yml up --build
```

Pre-commit runs ruff (with `--fix`), ruff-format, and strict mypy.

## Architecture

Hexagonal (ports-and-adapters). Dependency direction: `domain` ← `application`/`agents` ← `adapters`/`archive` ← `app` (composition root).

- **`negotium/domain/`** — `entities.py` (IssueEvent, WorkSpec, PatchProposal, ReviewVerdict, RepoRef), `events.py`, and `ports.py`: `Protocol` interfaces (IssueSource, CodeRepository, LlmProvider, …) that every adapter implements.
- **`negotium/adapters/`** — implementations of the ports: `ingestion/` (GitHub webhook router, Discord bot, channel map), `llm/` (openai, anthropic, gemini, vllm HTTP, vllm embedded in-process, ollama, `fake_adapter.py` for tests, plus `gateway.py` which does local/cloud routing), `notifier/`, `vcs/`.
- **`negotium/application/`** — `event_bus.py` and `orchestrator.py`. Patch flow: GitHub/Discord event → EventBus → Orchestrator → AgentGraph → ArchiveWriter → `archive/YYYY/MM/*.md`.
- **`negotium/agents/`** — PM → Developer → Reviewer agent pipeline wired as a langgraph graph in `graph.py`; self-correction loop bounded by `NG_MAX_SELF_CORRECTION`.
- **`negotium/archive/`** — one file-backed store class per concern (access control, secrets, audit log, operations memory, volatile memory, uploads, …). These persist to `archive/` at the repo root (or `NG_ARCHIVE_DIR`); this is the persistence layer, not code to move to a DB.
- **`negotium/app/`** — FastAPI app (`main.py`), Typer CLI (`cli.py`), settings (`settings.py`, pydantic-settings with `NG_` env prefix), routers in `api/`, business services in `services/`, and `container.py` — the composition root where all adapters/stores/agents get wired together. New dependencies get wired here.
- **`negotium/llm_gateway/`** — optional standalone FastAPI process for external LLM calls only; the main backend delegates to it when `NG_LLM_GATEWAY_URL` is set.
- **`negotium/skills/<id>/SKILL.md`** — skill definitions (YAML front-matter + body), loaded by `app/services/skill_registry.py`. Single source of truth shared by the HTTP API, MCP hub, CLI, and work-schedule automation.
- **`negotium/context/`** — repo snapshot, tree-sitter AST indexer, BM25 Markdown retriever used to build agent context.
- **`frontend/`** — React 19 + TypeScript + Vite console; one page component per feature under `src/components/`, API client in `src/api.ts`. Auth is header-based: requests carry `X-NG-User`, and permissions come from the user's assigned position (position-centric access control, not per-user roles).

## Conventions

- mypy runs `--strict`; adapters that duck-type into untyped SDKs are exempted via explicit per-module overrides in `pyproject.toml` — add new boundary adapters there rather than loosening global settings.
- Tests use `FakeLlmProvider` and `respx` (httpx mocking); coverage intentionally omits the vllm/ollama adapters.
- `archive/` and `tests/fixtures/` are excluded from ruff and mypy — never lint or "fix" archive contents; they are runtime data.
- README and most product docs are written in Korean; `docs/architecture.md` has mermaid diagrams of the system, request flow, and LLM runtime modes.
