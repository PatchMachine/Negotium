# Patch Machine

비 IT 기업이 사내 업무를 AI 기반으로 전환할 수 있도록 돕는
LLM 에이전트 기반 **AI 오피스워크 / BPA(Business Process Automation) 시스템**입니다.

회사의 업무, 문서, 인수인계, 채용, 진행상황을 AI가 정리하고 굴러가게 돕습니다.
민감한 사내 내용은 로컬 LLM으로, 일반 생성 업무는 GPT/Claude/Gemini/Together API로 라우팅할 수 있습니다.
모든 추론 과정과 결정 근거는 Markdown 파일로 저장되어(**MD GitOps**) 누구나 메모장으로 읽고 수정할 수 있습니다.

## 핵심 가치

- **AI 오피스워크**: 회의록, 보고서, 업무 요청서, 인수인계, 면접 키트를 한 콘솔에서 생성.
- **BPA 지향**: 반복 업무와 병목을 기록하고 회사 운영 흐름을 자동화.
- **관심사 분리**: Event Ingestion / Context / Agents / Verification / Knowledge / Serving 6계층.
- **Ports-and-Adapters**: GitHub -> Slack, OpenAI -> Ollama 등 어댑터만 바꾸면 됨.
- **GitOps**: 별도 DB 없이 `archive/*.md`가 단일 진실 원본.
- **Privacy by Default**: 사내 핵심 로직은 로컬 LLM 라우트로 강제.

## 아키텍처 (요약)

```
GitHub Issue  --+
Discord Msg   --+--> EventBus --> Orchestrator --> archive/YYYY/MM/*.md
Office Form   --+                         |
                                          v
              Company Memory + Archive + LLM Gateway
                                          |
                                          v
              채용/면접 · 인수인계 · 문서 자동화 · 업무 병목 요약
```

## 빠른 시작

```bash
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env          # 값 채워 넣기
patch-machine serve
```

백엔드 API와 기존 서버 렌더링 페이지는 FastAPI 서버에서 제공됩니다.
개발 모드에서는 API 키 암호화용 개발 키가 자동 적용됩니다. 운영 배포에서는 반드시 `.env`에
충분히 긴 `PM_SECRET_KEY`를 직접 설정하세요.

- 외부 참여 안내: `http://localhost:8080/`
- 참여 방법: `http://localhost:8080/join`
- 운영 메모리 설정: `http://localhost:8080/operations`
- 운영 메모리 API: `http://localhost:8080/api/operations-memory`
- API 문서: `http://localhost:8080/docs`
- 상태 확인: `http://localhost:8080/health`

운영 메모리는 처음에는 비어 있으며 UI에서 저장하면 `archive/operations_memory.json`에 기록됩니다.
회사 이름, 오피스 프로젝트, 진행 중 계획은 에이전트 프롬프트에 함께 전달되어 패치 판단 컨텍스트로 쓰입니다.

## 프론트엔드 로컬 실행

```bash
npm install --prefix frontend
npm run dev --prefix frontend
```

React 프론트엔드는 `http://localhost:5173`에서 열립니다. 개발 서버는 `/api`와 `/health` 요청을
`http://localhost:8080`의 FastAPI 백엔드로 프록시합니다.
프론트엔드에는 운영 메모리, LLM 채팅, 업무 현황, 채용/면접, 문서 자동화, 인수인계,
GitHub/Discord 현황 탭이 포함됩니다.

## LLM 채팅

기본 로컬 모델은 vLLM Python 엔진의 `Qwen/Qwen3-4B`입니다.
vLLM은 별도 프로세스/컨테이너 없이 FastAPI 백엔드 안에 임베드되어 GPU에서 직접 로드됩니다.

```bash
PM_LLM_DEFAULT_ROUTE=local
PM_LLM_PROVIDER=vllm
PM_VLLM_MODE=embedded             # FastAPI 내부에서 vllm.LLM로 직접 로드
PM_VLLM_MODEL=Qwen/Qwen3-4B
PM_VLLM_DTYPE=bfloat16
PM_VLLM_MAX_MODEL_LEN=8192
PM_VLLM_GPU_MEMORY_UTILIZATION=0.9
```

외부에 OpenAI 호환 vLLM 서버를 별도로 띄우고 싶다면 `PM_VLLM_MODE=http`로 두고
`PM_VLLM_BASE_URL`을 가리키면 됩니다.

GPT, Claude, Gemini, Together API는 각각 `PM_OPENAI_API_KEY`, `PM_ANTHROPIC_API_KEY`,
`PM_GEMINI_API_KEY`, `PM_TOGETHER_API_KEY`를 설정하면 프론트엔드의 LLM 채팅 탭에서 provider를 바꿔 호출할 수 있습니다.
Together는 OpenAI-compatible 엔드포인트를 사용하며 기본값은 `PM_TOGETHER_BASE_URL=https://api.together.ai/v1`,
기본 모델은 `PM_TOGETHER_MODEL=openai/gpt-oss-20b`입니다.
API 설정 화면은 OpenAI, Anthropic, Gemini, Together의 모델 목록 API를 호출해 최신 모델을 불러옵니다.
아직 키를 저장하지 않은 상태에서도 입력 중인 키로 “모델 목록 확인”을 눌러 live 목록을 확인할 수 있습니다.
채팅은 `archive/operations_memory.json`, `archive/work_memory.json`, `archive/current_status.md`,
최근 archive 로그를 컨텍스트로 사용합니다.

외부 LLM 호출만 별도 프로세스로 분리하려면 경량 게이트웨이를 실행합니다.

```bash
patch-machine llm-gateway --port 8090
PM_LLM_GATEWAY_URL=http://localhost:8090 patch-machine serve
```

게이트웨이는 GPT/Claude/Gemini/Together/vLLM HTTP 호출, 공급자별 모델 목록 조회, API 키 저장소 조회만 담당합니다.
GitHub/Discord 이벤트 처리나 로컬 vLLM 임베드 프리로드 없이 독립적으로 실행됩니다.

### 로컬 GPU 머신에서 vLLM 임베드 실행

NVIDIA GPU + 최신 드라이버가 있는 호스트에서 곧바로 백엔드를 실행합니다.

```bash
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install -e ".[dev,local-ai]"
# flash-attn은 CUDA 빌드가 까다로워 build isolation 없이 별도 설치합니다.
uv pip install --no-build-isolation "flash-attn>=2.6"
cp .env.example .env              # PM_VLLM_MODE=embedded 등 확인
patch-machine serve
```

첫 요청에서 모델 가중치 로딩 + CUDA 그래프 캡처가 일어나기 때문에 수십 초~수 분이 걸릴 수 있습니다.
이후 요청은 동일 프로세스 안에서 즉시 처리됩니다.

## AI 오피스 BPA 기능

- **회사 메모리 엔진**: 조직 구조, 부서, 역할, 핵심 업무 흐름, 사용 도구, 민감정보 정책 저장.
- **인사관리(조직도/직급/직원 배정)**: `인사관리` 화면에서 부서를 상위 부서(`parent_id`)와 연결한 계층형 조직도로 설계하고, 권한 역할과 분리된 직급(`PositionRecord`)을 정의해 직원에게 부서·직급을 배정합니다. 인사평가는 같은 화면의 하위 탭으로 분리되어 제공됩니다.
- **권한과 조직의 분리**: 기능 접근 권한은 `권한 관리` 화면의 권한 역할(`RoleRecord`)로, 조직 직급/부서는 `인사관리`에서 별도로 다룹니다. `회사 운영 설정`은 매니저 등급 이상(`memory:write`)만 접근할 수 있습니다.
- **영구 메모리 원천**: 패치 로그, 감사 로그, 생성 문서, 승격된 메모리, LLM-사용자 대화 JSONL을 검색 가능한 원천 기록으로 유지.
- **휘발성 작업 메모리**: 영구 메모리와 현재 대화를 LLM이 요약한 전역/사용자/세션별 작업 기억을 `archive/volatile_memory/`에 저장.
- **컨텍스트 압축**: 긴 영구 원천 기록을 원문 삭제 없이 source refs를 가진 압축 컨텍스트 캐시로 변환.
- **메모리 스키마/삭제 승인**: 회사별 영구메모리 타입과 필드를 `archive/memory/schema.json`에서 관리하고, 민감 기록 삭제는 요청/승인/tombstone 흐름으로 처리.
- **에이전트 실행 허가**: 작업 스케줄과 영구 메모리를 근거로 작업 계획을 만들고, 계획 전용/승인 작업/정책 기반 자동 실행 모드를 구분.
- **업무 아키텍처**: 회사 진행 업무를 단계, 역할, 의존성, 리스크, 산출물 중심의 계획 문서로 생성.
- **작업 스케줄링**: 작업자별 업무, 상태, 우선순위, 시작일/마감일을 `archive/work_schedule.json`에 저장.
- **채용/면접**: 직무 요구사항, 면접 질문, 평가 루브릭, 온보딩 계획을 Markdown으로 생성.
- **인수인계**: archive 로그와 회사 메모리를 바탕으로 담당자 변경 문서를 생성.
- **업무 병목 파악**: 최근 업무 로그 상태를 묶어 관리자용 병목 요약 제공.
- **문서 자동화**: 회의록, 보고서, 업무 요청서, PPT 초안을 생성해 `archive/documents/`에 저장.

운영 메모리는 장기적으로 유지되는 회사 정보이고, 현재 작업 메모리는 지금 진행 중인 업무 상태입니다.
AI 업무 아키텍처 생성 결과는 `archive/work_architecture/`에 Markdown으로 남고, 관련 작업 스케줄은
`archive/work_schedule.json`에서 CRUD로 관리됩니다.

## 관리 로그와 초기화

관리자 변경, API 키 변경, 계정 요청 승인/거절, 업로드, 문서 생성, 운영 메모리/LLM 런타임 변경은
`archive/audit_log.jsonl`에 append-only JSONL로 기록됩니다. 관리자 화면은
`/api/admin/audit-log`를 통해 최근 감사 로그를 조회할 수 있습니다.

### 초기화 CLI 명세

초기화는 Patch Machine 백엔드가 설치된 호스트에서 실행합니다. 개발 환경에서는 저장소 루트에서
가상환경을 활성화한 뒤 실행하고, Docker 환경에서는 `patch-machine` 이미지/컨테이너 안에서 실행합니다.

```bash
# 로컬 개발 환경
cd /path/to/PatchMachine_Core_Engine
source .venv/bin/activate
patch-machine reset-state --yes --actor admin

# uv로 실행하는 경우
uv run patch-machine reset-state --yes --actor admin
```

Docker Compose로 띄운 경우에는 archive 볼륨을 공유하는 백엔드 컨테이너에서 실행합니다.

```bash
docker compose -f docker/docker-compose.yml run --rm patch-machine \
  patch-machine reset-state --yes --actor admin
```

옵션은 다음과 같습니다.

- `--yes`: 필수 확인 플래그입니다. 없으면 파괴적 초기화를 거부합니다.
- `--actor <name>`: 감사 로그에 남길 실행자 이름입니다. 예: `admin`, `ops`, `local-owner`.
- `--include-workspaces / --no-include-workspaces`: `.pm_workspaces/` 작업 디렉터리까지 비울지 결정합니다. 기본값은 포함입니다.

예를 들어 내부 메모리와 계정/API 키만 초기화하고 작업 디렉터리는 남기려면 다음처럼 실행합니다.

```bash
patch-machine reset-state --yes --actor admin --no-include-workspaces
```

이 명령은 `archive/`의 운영 메모리, 권한, 인증 세션, API 키 저장소, 업로드, 생성 문서,
`archive/conversations/`, `archive/volatile_memory/`, `archive/memory/`, `archive/agent_execution/`와
`.pm_workspaces/` 작업 디렉터리를 비웁니다. `.env`, 소스 코드, 외부 공급자 모델 캐시나 API 서버는
건드리지 않습니다. 초기화 작업 자체는 새 `archive/audit_log.jsonl`에 `system.reset`으로 기록됩니다.

### 메모리 저장 위치

- `archive/YYYY/MM/*.md`: 패치/처리 로그 영구 메모리
- `archive/audit_log.jsonl`: 감사 로그 영구 메모리
- `archive/conversations/*.jsonl`: 사용자/LLM 대화 영구 메모리
- `archive/documents/`, `archive/hr/`, `archive/handover/`, `archive/work_architecture/`: 생성 산출물 영구 메모리
- `archive/memory/promoted/*.md`: 관리자가 휘발성 요약을 영구 원천으로 승격한 기록
- `archive/memory/schema.json`, `archive/memory/schema_proposals.json`: 동적 영구메모리 스키마와 승인 대기 제안
- `archive/memory/deletion_requests.json`, `archive/memory/tombstones.jsonl`: 삭제 승인 요청과 tombstone 이력
- `archive/volatile_memory/`: 전역/사용자/세션별 휘발성 메모리와 압축 컨텍스트
- `archive/agent_execution/`: 에이전트 작업 계획과 실행 요청 로그

## Docker 실행

```bash
cp .env.example .env          # 값 채워 넣기
docker compose -f docker/docker-compose.yml up --build
```

Docker 이미지에는 vLLM/CUDA 스택이 포함되지 않습니다. 컨테이너에서 백엔드를 띄우면
`PM_VLLM_MODE=http`로 강제되고, 로컬 LLM은 사용하지 않은 채 GPT/Claude/Gemini/Together API
라우트만 동작합니다. 사내 비공개 모델을 vLLM으로 직접 돌려야 한다면 위의
"로컬 GPU 머신에서 vLLM 임베드 실행" 절을 따라 호스트에서 실행하세요.

컨테이너가 올라오면 `http://localhost:5173`에서 React 프론트엔드를 확인할 수 있습니다.
FastAPI 백엔드는 `http://localhost:8080`에서 계속 제공됩니다.
LLM 게이트웨이는 `http://localhost:8090`에서 별도로 뜨며, 메인 백엔드는 `PM_LLM_GATEWAY_URL`로
게이트웨이에 LLM 호출을 위임합니다.
`archive/`, `config/`, 작업 디렉터리는 compose 설정에 따라 호스트와 연결됩니다.

## Discord 채널 매핑

`config/channel_map.yml` 예시:

```yaml
guilds:
  "123456789":
    channels:
      bugs-payments:
        channel_id: "987654321"
        repo: "acme/payments"
```

## 개발

```bash
ruff check . && ruff format --check .
mypy patch_machine
pytest -q
```

## 로드맵

- Phase 1 (현재): GitHub + Discord 이벤트 -> 패치 제안 코멘트.
- Phase 2: Docker 샌드박스 + 자동 PR.
- Phase 3: 기술 자산화(면접/코테 자동 생성).
- Phase 4: vLLM/Ollama 로컬 AI 라우팅 + 배포 패키징.

## 라이선스

MIT
