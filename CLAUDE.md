# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Negotium (네고티움, formerly "Patch Machine") — an LLM-agent office-work / BPA console for non-IT Korean SMBs. The product is a closed daily loop: meeting minutes → auto work assignments → work status/weekly report → handover kits → hiring kits. There is **no database**: the `archive/` directory of Markdown/JSON/JSONL files is the single source of truth ("MD GitOps"). Sensitive work routes to a local vLLM model; general work routes to cloud providers. The **default cloud provider is Upstage Solar** (`solar-pro3`, OpenAI-compatible API at https://api.upstage.ai/v1); OpenAI/Anthropic/Gemini/Together are also supported.

Solar model selection is driven by the tier catalog in `adapters/llm/catalog.py` (`ModelProfile`, tiers `agent`/`reasoning`/`general`/`unknown`):
- `solar-pro3` — **office default**. Agent-specialized flagship (102B MoE, 128k ctx), tool calling with parallel calls, `reasoning_effort` `high|medium|low|minimal` (default `minimal`, so it returns content directly and fast).
- `solar-pro2` — previous flagship (31B, 65k ctx), reasoning tier, also tool-capable.
- `solar-open2` — open-weights agentic model for self-hosted vLLM serving (1M ctx). It **spends the token budget on hidden reasoning before content** and is much slower; it only accepts `reasoning_effort` `high|none` (not the hosted four-level scale). Give it a generous `max_tokens`.
- `solar-mini`, `syn-pro` — general tier, no `reasoning_effort`.

`hidden_reasoning` is deliberately a separate `ModelProfile` field from `tier`: `solar-pro3`/`solar-pro2` are reasoning/agent tier but return content directly, so deriving the token budget from the tier would regress the fast office default. Dated snapshots (`solar-pro2-251215`) inherit their base model's profile.

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

# Run everything (console + API on :8080 — one port, one origin)
negotium serve                     # serves frontend/dist at / when it exists
negotium serve --build-frontend    # npm install/build first (needs Node 20+)
# Other CLI: llm-gateway --port 8090 | reset-state --yes --actor <name> | skill list/run

# Frontend HMR only (optional; :5173 proxies /api and /health to :8080)
npm install --prefix frontend
npm run dev --prefix frontend
npm run build --prefix frontend    # tsc -b && vite build → served by :8080, no restart needed

# Docker (no vLLM/CUDA in image; forces NG_VLLM_MODE=http)
docker compose -f docker/docker-compose.yml up --build
```

Pre-commit runs ruff (with `--fix`), ruff-format, and strict mypy.

## Architecture

- **`negotium/domain/`** — `LlmRoute`, and `ports.py` with the `LlmProvider`/`LlmMessage`/`LlmResponse` protocol every LLM adapter implements (incl. multimodal ContentPart helpers).
- **`negotium/adapters/llm/`** — providers (openai, anthropic, gemini, vllm HTTP, vllm embedded in-process, ollama, `fake_adapter.py` for tests), `gateway.py` (local/cloud routing + secret-pattern force-local), `catalog.py` (provider metadata + live model listing). **Solar reuses `OpenAiProvider`** with a different base_url — no dedicated adapter.
- **Archive search**: `archive/search_index.py` is a chunk-level BM25 engine (CJK char-bigram tokens, incremental mtime-diff index under `archive/search_index/`, shared corpus rules in `archive/_corpus.py`); `PermanentMemoryStore.search()` delegates to it (legacy substring scan is the corruption fallback), so chat inject, the `office_memory.search` tool, and `/api/memory/permanent/search` all use it. Opt-in semantic layer: `services/archive_search_service.py` embeds chunks via Upstage `/v1/embeddings` (`embedding-passage`/`embedding-query`, RRF fusion) — every chunk passes `sanitize_context(destination="frontier_llm")` before egress and blocked chunks are never sent; toggle lives in `AutomationConfig.search`, refresh runs as the `search_index` automation job.
- **`negotium/archive/`** — one file-backed store class per concern (access control, secrets, audit log, operations/permanent/volatile memory, work schedule, process plans, HR evaluations, MCP audit/sessions, …). Shared locked-file persistence helpers live in `archive/_store.py` — use them instead of hand-rolling portalocker+json. Stores persist to `archive/` at the repo root (or `NG_ARCHIVE_DIR`).
- **`negotium/app/console_site.py`** — serves the built React console (`frontend/dist`, override with `NG_FRONTEND_DIST`) from the backend process, so UI and API share one port. `/assets` is a `StaticFiles` mount; the SPA shell comes from the app's 404 handler, **only** for GET/HEAD requests that matched no route (`scope["endpoint"] is None`) outside `/api` and `/assets` — so 405s, slash redirects, and endpoint-raised 404 bodies keep working. The legacy contributor site lives under `/contribute`, not `/`.
- **`negotium/app/`** — FastAPI app (`main.py`), Typer CLI (`cli.py`), settings (`settings.py`, pydantic-settings with `NG_` env prefix), business services in `services/` (LLM/chat, documents, memory, MCP hub, skills, context firewall), and `container.py` — the composition root wiring stores + LLM gateway. Attachments: `services/office_doc_parser.py` extracts docx/hwpx (stdlib zip+XML) and binary hwp (olefile) locally; `services/document_parse_service.py` calls Upstage Document Parse (same Solar key) **only on the cloud route** with a `<upload>.parsed.md` sidecar cache — the route is threaded into `_resolve_document_attachments` so local-route files never leave the machine. Automation: a minute-tick scheduler loop in `main.py` (sleep-first, guarded by env != "test" and `NG_AUTOMATION_ENABLED`) calls `services/automation_service.run_due_jobs` — weekly-report generation and work reminders, config/state in `archive/automation.py`, in-app notifications in `archive/notifications.py`, outbound via a Slack-style `{"text": ...}` webhook. Jobs default to disabled; state keys are marked at attempt start (one attempt per slot).
- **`negotium/app/api/`** — the frontend REST API split by domain: `auth.py`, `setup.py`, `uploads.py`, `documents.py` (documents + /hr), `integrations.py` (MCP hub), `llm.py`, `work.py` (work-schedule/process-plans/status/progress/handover + **/reports/weekly**), `agent.py` (office agent plans, ai-jobs, skills), `admin.py`, `memory.py`. Each exposes `create_<domain>_router(container)`; `__init__.py` aggregates them under `/api`. Cross-domain helpers live in `api/_shared.py` — notably `_complete_office_task` (single LLM entry point, task-routed, empty-response fallback) and the step engine `_generate_process_steps` + `_enqueue_process_steps` (turns any markdown into ordered, dependency-chained WorkScheduleItems; used by meeting minutes, handover, and process design).
- **`negotium/llm_gateway/`** — optional standalone FastAPI process for external LLM calls only; the main backend delegates to it when `NG_LLM_GATEWAY_URL` is set.
- **`negotium/skills/<id>/SKILL.md`** — office skill definitions (YAML front-matter + body), loaded by `services/skill_registry.py`; shared by the HTTP API, MCP hub, and CLI.
- **`frontend/`** — React 19 + TypeScript + Vite console; every page is lazy-loaded (see App.tsx page map), API client split by domain under `src/api/` with an index barrel. Auth is token-based: `POST /api/auth/login` (PBKDF2 credentials in `archive/auth.json`) returns a session token, sent as `X-NG-User: Bearer <token>` (12h sliding TTL, renewed on activity). Effective permissions resolve position → department policy → role; `/auth/me` reports the same set enforcement uses. Login is rate-limited (5 fails / 5 min per user id and per IP).

## Core office loops (what must keep working)

1. 회의록→업무배정: `POST /api/documents/generate` with `document_type=meeting_minutes, generate_tasks=true, participants=...` → minutes doc + work-schedule items (integration test `test_meeting_minutes_action_items_become_work_schedule`).
2. 주간보고: `POST /api/reports/weekly` gathers schedule + bottleneck summaries + recent logs → manager report (`test_weekly_report_collects_schedule_and_writes_document`).
3. 인수인계: `POST /api/handover/brief` (auto-gathers outgoing owner's activity, optionally creates follow-up tasks).
4. 채용/면접: `POST /api/hr/{role-requirements,interview-kit,onboarding-plan}`.
All four funnel through `_complete_office_task` with the 6 `LlmTaskName` routes (`memory_summary, agent_planning, document_generation, hiring, handover, chat`) so per-task provider/model overrides apply uniformly.

## Agent tool loop

`NG_LLM_AGENT_TOOLS=true` 일 때, 도구 지원 모델(`catalog.model_supports_tools`)에 한해 채팅/설치 마법사가 `services/agent_loop_service.run_agent_loop`를 통해 다중 턴 도구 호출을 수행한다.

- 도구는 `services/mcp_hub_service`에 등록 (`list_tool_descriptors` + `_dispatch_tool` + `TOOL_POLICIES`). 읽기 도구는 자동 실행, 쓰기 도구는 승인 카드를 띄운다 (`is_read_tool`).
- **MCP 도구명은 점을 쓰지만 OpenAI/Solar function name은 `[a-zA-Z0-9_-]`만 허용한다.** `to_wire_name`으로 변환하고 `tool_name_map`으로 되돌린다 — 안 하면 전체 요청이 400난다.
- 승인은 내용 해시(`approval_id_for`)로 검증하고, 재개 시 **재추론 없이 승인된 호출을 그대로 실행**한다 (`_execute_approved_calls`). 모델이 인자를 미세하게 바꿔 다시 제안하면 사용자가 두 번 승인해야 하기 때문.
- `ui.open_surface`는 `services/ui_surface_service.UI_SURFACES`의 화면을 채팅 안에 인라인 렌더한다. 프론트 매핑은 `frontend/src/components/chat/surfaceRegistry.tsx`.
- 도구 결과는 신뢰불가 입력으로 취급한다: 배너 부착 + `guard_tool_arguments`를 결과에도 적용. 민감 시트는 클라우드 라우트에서 셀 값을 가린다.
- 컨텍스트 방화벽(`sanitize_llm_messages`/`sanitize_llm_response`)은 `tool_call_id`/`tool_calls`/`reasoning`을 반드시 보존해야 한다. 빠뜨리면 루프 2회차에서 400.

## Adding an LLM provider

Follow the `solar`/`together` pattern (OpenAI-compatible providers reuse `OpenAiProvider`). Touchpoints: `app/settings.py` (fields + provider Literal), `app/container.py` `_build_llm`, `adapters/llm/catalog.py` (ProviderName, PROVIDERS, requires_api_key set, `_openai_compatible_models` branch), **`archive/llm_runtime.py` `KNOWN_PROVIDERS`** (forgetting this silently downgrades routes to vllm), `archive/secret_store.py` `list_masked`, `app/api/_shared.py` (`_settings_api_key`, `_default_base_url`, `_resolve_runtime_model`, `_complete_with_provider`, `_firewall_destination`), `llm_gateway/app.py`, `app/schemas/core.py`, `services/context_firewall_service.py` FRONTIER_DESTINATIONS, frontend `api.ts` LlmProviderName + hardcoded provider lists in AdminSettingsPage/LlmTaskRoutingPanel/InitialOfficeSetupWizard, `.env.example`.

## Conventions

- mypy runs `--strict`; adapters that duck-type into untyped SDKs are exempted via explicit per-module overrides in `pyproject.toml` — add new boundary adapters there rather than loosening global settings.
- Tests use `FakeLlmProvider` (ScriptedResponse) and monkeypatched `httpx.AsyncClient`; coverage intentionally omits the vllm/ollama adapters.
- `archive/` is runtime data (user PII) — gitignored, never commit or lint it. `tests/fixtures/` is also excluded from ruff/mypy.
- Env vars use the `NG_` prefix. `NG_LLM_PROVIDER`/`NG_LLM_DEFAULT_ROUTE`/`NG_LLM_GATEWAY_URL`/`NG_LOCAL_LLM_BASE_URL` work via validation aliases in `LlmSettings`.
- README and most product docs are written in Korean.
- Generated documents honor a leading `<!-- negotium:format=markdown|html|csv|json|text -->` directive (legacy `patchmachine:` still parsed).
