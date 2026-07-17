# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Negotium (네고티움, formerly "Patch Machine") — an LLM-agent office-work / BPA console for non-IT Korean SMBs. The product is a closed daily loop: meeting minutes → auto work assignments → work status/weekly report → handover kits → hiring kits. There is **no database**: the `archive/` directory of Markdown/JSON/JSONL files is the single source of truth ("MD GitOps"). Sensitive work routes to a local vLLM model; general work routes to cloud providers. The **default cloud provider is Upstage Solar** (`solar-open2`, OpenAI-compatible API at https://api.upstage.ai/v1); OpenAI/Anthropic/Gemini/Together are also supported.

The former developer-tool surface (coding-agent patch pipeline, GitHub/Discord ingestion, patchops) was removed in the office pivot — do not reintroduce it. Historical archives may still contain `YYYY/MM` patch logs; reading them stays supported.

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
pytest tests/integration/test_app_smoke.py -q      # end-to-end office flows (FakeLLM)
pytest tests/unit/test_llm_gateway.py::test_name -q

# Run backend (FastAPI on :8080)
negotium serve
# Other CLI: llm-gateway --port 8090 | reset-state --yes --actor <name> | skill list/run

# Frontend (React+Vite on :5173, proxies /api and /health to :8080; needs Node 20+)
npm install --prefix frontend
npm run dev --prefix frontend
npm run build --prefix frontend    # tsc -b && vite build

# Docker (no vLLM/CUDA in image; forces NG_VLLM_MODE=http)
docker compose -f docker/docker-compose.yml up --build
```

Pre-commit runs ruff (with `--fix`), ruff-format, and strict mypy.

## Architecture

- **`negotium/domain/`** — `LlmRoute`, and `ports.py` with the `LlmProvider`/`LlmMessage`/`LlmResponse` protocol every LLM adapter implements (incl. multimodal ContentPart helpers).
- **`negotium/adapters/llm/`** — providers (openai, anthropic, gemini, vllm HTTP, vllm embedded in-process, ollama, `fake_adapter.py` for tests), `gateway.py` (local/cloud routing + secret-pattern force-local), `catalog.py` (provider metadata + live model listing). **Solar reuses `OpenAiProvider`** with a different base_url — no dedicated adapter.
- **`negotium/archive/`** — one file-backed store class per concern (access control, secrets, audit log, operations/permanent/volatile memory, work schedule, process plans, HR evaluations, MCP audit/sessions, …). Shared locked-file persistence helpers live in `archive/_store.py` — use them instead of hand-rolling portalocker+json. Stores persist to `archive/` at the repo root (or `NG_ARCHIVE_DIR`).
- **`negotium/app/`** — FastAPI app (`main.py`), Typer CLI (`cli.py`), settings (`settings.py`, pydantic-settings with `NG_` env prefix), business services in `services/` (LLM/chat, documents, memory, MCP hub, skills, context firewall), and `container.py` — the composition root wiring stores + LLM gateway.
- **`negotium/app/api/`** — the frontend REST API split by domain: `auth.py`, `setup.py`, `uploads.py`, `documents.py` (documents + /hr), `integrations.py` (MCP hub), `llm.py`, `work.py` (work-schedule/process-plans/status/progress/handover + **/reports/weekly**), `agent.py` (office agent plans, ai-jobs, skills), `admin.py`, `memory.py`. Each exposes `create_<domain>_router(container)`; `__init__.py` aggregates them under `/api`. Cross-domain helpers live in `api/_shared.py` — notably `_complete_office_task` (single LLM entry point, task-routed, empty-response fallback) and the step engine `_generate_process_steps` + `_enqueue_process_steps` (turns any markdown into ordered, dependency-chained WorkScheduleItems; used by meeting minutes, handover, and process design).
- **`negotium/llm_gateway/`** — optional standalone FastAPI process for external LLM calls only; the main backend delegates to it when `NG_LLM_GATEWAY_URL` is set.
- **`negotium/skills/<id>/SKILL.md`** — office skill definitions (YAML front-matter + body), loaded by `services/skill_registry.py`; shared by the HTTP API, MCP hub, and CLI.
- **`frontend/`** — React 19 + TypeScript + Vite console; every page is lazy-loaded (see App.tsx page map), API client split by domain under `src/api/` with an index barrel. Auth is header-based: requests carry `X-NG-User`; permissions come from the user's assigned position.

## Core office loops (what must keep working)

1. 회의록→업무배정: `POST /api/documents/generate` with `document_type=meeting_minutes, generate_tasks=true, participants=...` → minutes doc + work-schedule items (integration test `test_meeting_minutes_action_items_become_work_schedule`).
2. 주간보고: `POST /api/reports/weekly` gathers schedule + bottleneck summaries + recent logs → manager report (`test_weekly_report_collects_schedule_and_writes_document`).
3. 인수인계: `POST /api/handover/brief` (auto-gathers outgoing owner's activity, optionally creates follow-up tasks).
4. 채용/면접: `POST /api/hr/{role-requirements,interview-kit,onboarding-plan}`.
All four funnel through `_complete_office_task` with the 6 `LlmTaskName` routes (`memory_summary, agent_planning, document_generation, hiring, handover, chat`) so per-task provider/model overrides apply uniformly.

## Adding an LLM provider

Follow the `solar`/`together` pattern (OpenAI-compatible providers reuse `OpenAiProvider`). Touchpoints: `app/settings.py` (fields + provider Literal), `app/container.py` `_build_llm`, `adapters/llm/catalog.py` (ProviderName, PROVIDERS, requires_api_key set, `_openai_compatible_models` branch), **`archive/llm_runtime.py` `KNOWN_PROVIDERS`** (forgetting this silently downgrades routes to vllm), `archive/secret_store.py` `list_masked`, `app/api/_shared.py` (`_settings_api_key`, `_default_base_url`, `_resolve_runtime_model`, `_complete_with_provider`, `_firewall_destination`), `llm_gateway/app.py`, `app/schemas/core.py`, `services/context_firewall_service.py` FRONTIER_DESTINATIONS, frontend `api.ts` LlmProviderName + hardcoded provider lists in AdminSettingsPage/LlmTaskRoutingPanel/InitialOfficeSetupWizard, `.env.example`.

## Conventions

- mypy runs `--strict`; adapters that duck-type into untyped SDKs are exempted via explicit per-module overrides in `pyproject.toml` — add new boundary adapters there rather than loosening global settings.
- Tests use `FakeLlmProvider` (ScriptedResponse) and monkeypatched `httpx.AsyncClient`; coverage intentionally omits the vllm/ollama adapters.
- `archive/` is runtime data (user PII) — gitignored, never commit or lint it. `tests/fixtures/` is also excluded from ruff/mypy.
- Env vars use the `NG_` prefix. `NG_LLM_PROVIDER`/`NG_LLM_DEFAULT_ROUTE`/`NG_LLM_GATEWAY_URL`/`NG_LOCAL_LLM_BASE_URL` work via validation aliases in `LlmSettings`.
- README and most product docs are written in Korean.
- Generated documents honor a leading `<!-- negotium:format=markdown|html|csv|json|text -->` directive (legacy `patchmachine:` still parsed).
