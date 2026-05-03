# Patch Machine

비 IT 기업이 사내 업무를 AI 기반으로 전환할 수 있도록 돕는
LLM 에이전트 기반 **AI 오피스워크 / BPA(Business Process Automation) 시스템**입니다.

회사의 업무, 문서, 인수인계, 채용, 진행상황을 AI가 정리하고 굴러가게 돕습니다.
민감한 사내 내용은 로컬 LLM으로, 일반 생성 업무는 GPT/Claude/Gemini API로 라우팅할 수 있습니다.
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

GPT, Claude, Gemini API는 각각 `PM_OPENAI_API_KEY`, `PM_ANTHROPIC_API_KEY`,
`PM_GEMINI_API_KEY`를 설정하면 프론트엔드의 LLM 채팅 탭에서 provider를 바꿔 호출할 수 있습니다.
채팅은 `archive/operations_memory.json`, `archive/current_status.md`, 최근 archive 로그를
컨텍스트로 사용합니다.

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
- **채용/면접**: 직무 요구사항, 면접 질문, 평가 루브릭, 온보딩 계획을 Markdown으로 생성.
- **인수인계**: archive 로그와 회사 메모리를 바탕으로 담당자 변경 문서를 생성.
- **업무 병목 파악**: 최근 업무 로그 상태를 묶어 관리자용 병목 요약 제공.
- **문서 자동화**: 회의록, 보고서, 업무 요청서, PPT 초안을 생성해 `archive/documents/`에 저장.

## Docker 실행

```bash
cp .env.example .env          # 값 채워 넣기
docker compose -f docker/docker-compose.yml up --build
```

Docker 이미지에는 vLLM/CUDA 스택이 포함되지 않습니다. 컨테이너에서 백엔드를 띄우면
`PM_VLLM_MODE=http`로 강제되고, 로컬 LLM은 사용하지 않은 채 GPT/Claude/Gemini API
라우트만 동작합니다. 사내 비공개 모델을 vLLM으로 직접 돌려야 한다면 위의
"로컬 GPU 머신에서 vLLM 임베드 실행" 절을 따라 호스트에서 실행하세요.

컨테이너가 올라오면 `http://localhost:5173`에서 React 프론트엔드를 확인할 수 있습니다.
FastAPI 백엔드는 `http://localhost:8080`에서 계속 제공됩니다.
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
