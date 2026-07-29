# Negotium Architecture

Negotium is an AI office-work / BPA system: a React console + FastAPI backend with
local/cloud LLM routing over a Markdown-first archive (no database).

## 1. System Overview

```mermaid
flowchart TB
  User["Users: owner, manager, staff, viewer"] --> Frontend["React Console (frontend/dist, served at /)"]
  Frontend -->|"REST API (X-NG-User: Bearer token), same origin"| FastAPI["FastAPI Backend: negotium serve — localhost:8080"]

  FastAPI --> Documents["Documents API (회의록/보고서/HR)"]
  FastAPI --> Work["Work API (배정/현황/주간보고/인수인계)"]
  FastAPI --> Memory["Memory API (운영/영구/휘발성)"]
  FastAPI --> Admin["Admin API (키/권한/감사)"]
  FastAPI --> McpHub["MCP Hub (skills/hf/public_reference/agent)"]

  Documents --> OfficeTask["_complete_office_task (task routing)"]
  Work --> OfficeTask
  OfficeTask --> LlmGateway["LLM Gateway"]

  LlmGateway --> Solar["Upstage Solar (default)"]
  LlmGateway --> OpenAI["OpenAI GPT"]
  LlmGateway --> Claude["Anthropic Claude"]
  LlmGateway --> Gemini["Google Gemini"]
  LlmGateway --> LocalVllm["Embedded vLLM (sensitive route)"]
  LlmGateway --> FakeLLM["Fake LLM for Tests"]

  Documents --> Archive["archive/ (MD GitOps)"]
  Work --> Archive
  Memory --> Archive
  Admin --> Archive
```

## 2. Core Office Loop

```mermaid
flowchart LR
  Notes["회의 메모"] --> Minutes["회의록 생성\nPOST /api/documents/generate"]
  Minutes -->|"generate_tasks=true"| Steps["step engine\n_generate_process_steps"]
  Steps --> Schedule["업무 배정\narchive/work_schedule.json"]
  Schedule --> Status["업무 현황·병목 요약\nGET /api/work-items"]
  Status --> Weekly["주간보고\nPOST /api/reports/weekly"]
  Schedule --> Handover["인수인계 킷\nPOST /api/handover/brief"]
  Handover -->|"후속 업무"| Schedule
  Org["부서/직급 컨텍스트"] --> Hiring["채용/면접 키트\nPOST /api/hr/*"]
```

## 3. LLM Task Routing

All office completions funnel through `_complete_office_task`, routed per task
(`memory_summary, agent_planning, document_generation, hiring, handover, chat`)
via `archive/llm_runtime.json` — each task can pin a provider/model, and the
route degrades gracefully (empty-response fallback keeps demos alive).

```mermaid
flowchart TB
  Task["Office task (document_generation, hiring, ...)"] --> Runtime["LlmRuntimeStore task_routes"]
  Runtime -->|"api"| Cloud["Solar / GPT / Claude / Gemini / Together"]
  Runtime -->|"local"| Vllm["Embedded vLLM (Qwen3-4B)"]
  Cloud --> Guard["Context firewall + secret force-local"]
  Vllm --> Guard
```

## 4. Archive and Persistence

```mermaid
flowchart LR
  Archive["archive/"] --> Memory["operations_memory.json / work_memory.json"]
  Archive --> Schedule["work_schedule.json"]
  Archive --> Runtime["llm_runtime.json"]
  Archive --> Secrets["secrets/api_keys.enc.json"]
  Archive --> ACL["access_control.json / auth.json"]
  Archive --> Docs["documents/ hr/ handover/ work_architecture/"]
  Archive --> Audit["audit_log.jsonl"]
  Archive --> Volatile["volatile_memory/ + compressed context"]

  Memory --> Context["LLM Context"]
  Schedule --> Context
  Docs --> Context
```

All stores share the locked-file helpers in `negotium/archive/_store.py`
(portalocker + UTF-8 JSON/JSONL).

## 5. Access Control

```mermaid
flowchart TB
  Login["POST /api/auth/login (PBKDF2 검증, 5회 실패 시 429)"] --> Token["세션 토큰 (12h 슬라이딩 TTL)"]
  Token --> Request["X-NG-User: Bearer &lt;token&gt;"]
  Request --> AuthStore["AuthStore.resolve_token (archive/auth.json)"]
  AuthStore -->|"만료/위조"| Unauthorized["401"]
  AuthStore --> ACL["AccessControlStore"]
  ACL --> User["UserRecord"]
  User --> Position["PositionRecord permissions"]
  Position --> Check{"Required permission?"}
  Check -->|"allowed"| Handler["API handler"]
  Check -->|"denied"| Forbidden["403"]
```

비밀번호는 PBKDF2-SHA256(20만 회) 해시로, 세션 토큰은 SHA-256 해시로만
`archive/auth.json`에 저장됩니다. 유효 권한은 직급(position) → 부서 정책 → 역할(role)
순으로 해석되며, `/auth/me`가 반환하는 권한 목록도 동일한 규칙을 따릅니다.

Default roles: `owner` (all via `*`), `manager` (memory/LLM/documents/uploads/work),
`staff` (LLM chat/uploads/work read), `viewer` (work read only). Day-to-day access
is position-centric: a user's assigned position carries the permission list.

## 6. Deployment Shape

```mermaid
flowchart TB
  subgraph HostGpu["Host GPU Mode (sensitive local LLM)"]
    HostBackend["uv run negotium serve"] --> EmbeddedVllm["Embedded vLLM"]
    HostFrontend["npm run dev --prefix frontend"] --> HostBackend
  end

  subgraph DockerMode["Docker Compose Mode (cloud providers)"]
    DockerFrontend["frontend container"] --> DockerBackend["negotium container"]
    DockerBackend --> CloudProviders["Solar (default), GPT, Claude, Gemini, external vLLM HTTP"]
  end
```

Recommended local GPU mode:

```bash
NG_LLM_PROVIDER=vllm \
NG_LLM_DEFAULT_ROUTE=local \
NG_VLLM_MODE=embedded \
NG_VLLM_PRELOAD_ON_STARTUP=true \
uv run negotium serve
```

Docker mode is for the frontend and non-GPU backend operation; it does not load
the embedded local GPU model.
