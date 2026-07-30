# Negotium (네고티움)

**비 IT 한국 중소기업을 위한 LLM 에이전트 오피스워크 / BPA 콘솔.**
회의록 → 업무 배정 → 주간보고 → 인수인계/채용까지, 회사의 반복 오피스워크가
하나의 닫힌 루프로 굴러갑니다. DB 없이 `archive/`의 Markdown/JSON이 단일 진실
원본이며(**MD GitOps**), 기본 클라우드 LLM은 **Upstage Solar** (`solar-pro3`)입니다.

> Upstage **Solar Agent Partner Stage 1** 프로젝트입니다.
> Solar 사용 경험과 기술 피드백: [SOLAR_REVIEW.md](SOLAR_REVIEW.md) ·
> 개발 현황과 향후 계획: [docs/ROADMAP.md](docs/ROADMAP.md)

## 왜 만들었나

한국 중소기업의 오피스워크는 여전히 한글 문서, 엑셀, 구두 지시로 돌아갑니다.
IT 팀이 없는 회사가 SaaS를 도입하려면 데이터를 남의 DB에 맡겨야 하고,
AI를 쓰려면 민감한 사내 문서를 통째로 외부에 보내야 합니다. Negotium은 반대로 설계했습니다:

- **모든 데이터는 내 서버의 파일로** — DB 없이 `archive/*.md`가 원본. 메모장으로도 읽힙니다.
- **AI는 라우팅으로 통제** — 민감 작업은 로컬 vLLM, 일반 작업은 클라우드(Solar 기본).
  외부로 나가는 모든 컨텍스트는 **반출 제어(컨텍스트 방화벽)** 를 통과합니다.
- **업무가 스스로 굴러가게** — 회의록이 업무가 되고, 업무 기록이 보고서·인수인계가 되는
  닫힌 루프 + 스케줄러가 주간보고·리마인더를 알아서 돌립니다.

## 핵심 기능

| 영역 | 내용 |
| --- | --- |
| **코어 루프 4종** | 회의록→업무배정(담당자·순서·의존성 자동), 업무현황→주간보고, 인수인계 킷(+후속 업무 배정), 채용/면접 킷 |
| **AI 어시스턴트** | `solar-pro3` 도구 호출 에이전트 — 조직 조회·문서 생성·메모리 검색·엑셀 읽기를 스스로 수행, 쓰기 작업은 승인 카드로 통제 |
| **문서 첨부** | **HWP·HWPX·DOCX**·PDF·이미지·엑셀 — 클라우드 라우트는 Upstage Document Parse로 표/서식까지 변환(파일별 캐시로 재과금 없음), 로컬 라우트는 내장 파서 |
| **아카이브 검색** | 청크 BM25 + 한국어 문자 2-gram("합의했지"로 "합의" 문서 검색) + 옵트인 Upstage 임베딩 시맨틱 검색 |
| **자동화** | 주간보고 자동 생성, 마감/정체 업무 리마인더, 인앱 알림함(🔔) + 슬랙 호환 웹훅 |
| **보안** | 세션 토큰 인증(PBKDF2)·로그인 스로틀링·직급 기반 접근 제어·감사 로그·컨텍스트 방화벽·archive 자동 git 백업 |

## Upstage Solar 활용 (3종)

Negotium은 Upstage API를 세 곳에서 사용합니다 — 모두 같은 `NG_SOLAR_API_KEY` 하나로 동작합니다.

1. **Chat Completions — 에이전트 루프의 심장.** `solar-pro3`의 병렬 도구 호출로
   AI 어시스턴트·셋업 마법사가 조직 설계, 문서 생성, 메모리 검색을 수행합니다.
   `reasoning_effort=minimal` 기본값 덕에 오피스 작업 응답이 빠릅니다.
2. **Document Parse (`/v1/document-digitization`)** — 한국 기업 문서의 실제 형식인
   HWP/HWPX/DOCX를 표·서식이 살아있는 마크다운으로 변환해 회의록·문서 생성에 반영합니다.
3. **Embeddings (`/v1/embeddings`)** — `embedding-passage`/`embedding-query`로 아카이브
   청크를 색인해 키워드 검색과 RRF 융합. **방화벽을 통과한 청크만 전송**됩니다
   (주민등록번호가 든 청크는 아예 나가지 않고 감사 기록만 남음).

### 모델 티어

모델 선택 화면은 모델을 **에이전트형 / 추론형 / 일반형** 으로 구분해 보여주고,
선택한 모델로 제한되는 기능을 함께 안내합니다.

| 모델 | 티어 | 컨텍스트 | 도구 호출 | reasoning_effort |
| --- | --- | --- | --- | --- |
| `solar-pro3` | 에이전트형 (기본값) | 128k | 지원 (병렬 호출) | `high\|medium\|low\|minimal` |
| `solar-pro2` | 추론형 | 65k | 지원 | `high\|medium\|low\|minimal` |
| `solar-open2` | 에이전트형 (자체 호스팅) | 1M | 지원 | `high\|none` |
| `solar-mini` | 일반형 | 32k | 지원 | 미지원 |

`solar-open2`는 오픈 웨이트 모델로 vLLM 서빙 시
`--tool-call-parser solar_open2 --enable-auto-tool-choice`가 필요하며, 응답 전에
숨은 추론에 토큰을 크게 쓰므로 `max_tokens`를 넉넉히 주어야 합니다.

## 빠른 시작 (3분)

```bash
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
# .env에서 NG_SOLAR_API_KEY만 채우면 됩니다 (console.upstage.ai에서 발급)
negotium serve --build-frontend          # 콘솔 빌드 + 서버 (Node 20+ 필요)
```

브라우저에서 `http://localhost:8080` 하나만 열면 콘솔과 API가 함께 제공됩니다.
첫 화면의 **초기 셋업 마법사**가 관리자 생성 → LLM 연결 → 회사 프로필 → 조직 설계 →
구성원 로그인 발급까지 안내합니다. Solar 키가 있으면 마법사가 대화형(에이전트)으로,
없으면 폼 기반으로 동작하며 — **키가 없어도 모든 화면은 열리고 AI 생성만 안내 문구로 대체**됩니다.

- 콘솔: `http://localhost:8080/` · API 문서: `/docs` · 상태: `/health`

Docker로 실행하려면 (vLLM/CUDA 미포함, 클라우드 라우트 전용):

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
```

## 아키텍처 (요약)

```
회의 메모 · 업로드 문서(HWP/DOCX/PDF/XLSX)
        │
        ▼
FastAPI 콘솔 API ──▶ 회사 메모리(운영/영구/휘발성) + 아카이브 검색(BM25+임베딩)
        │                 │
        │           컨텍스트 방화벽 (반출 제어·PII 마스킹)
        ▼                 ▼
solar-pro3 에이전트 루프 ──▶ 회의록→업무배정 / 주간보고 / 인수인계 / 채용킷
        │
        ▼
archive/*.md · *.json  (MD GitOps — DB 없음, 자동 git 백업)
```

- **Ports-and-Adapters**: LLM 어댑터만 바꾸면 Solar ↔ GPT/Claude/Gemini/Together ↔ 로컬 vLLM 전환.
  Solar는 OpenAI-compatible이라 별도 SDK 없이 동작합니다.
- **로컬 vLLM**: GPU 호스트에서는 `NG_VLLM_MODE=embedded`로 FastAPI 프로세스 안에 직접 로드
  (`uv pip install -e ".[dev,local-ai]"`), 외부 서버는 `NG_VLLM_MODE=http`.
- **6개 작업 라우트**(회의록/계획/문서/채용/인수인계/채팅)별로 provider·모델을 관리자 화면에서 지정.
- 외부 LLM 호출만 분리하려면 `negotium llm-gateway --port 8090` + `NG_LLM_GATEWAY_URL`.

## 보안·프라이버시

- **인증**: PBKDF2 비밀번호 + 12시간 슬라이딩 세션 토큰, 로그인 시도 제한(5회/5분), 계정 신청·승인 흐름.
- **접근 제어**: 직급(position) 중심 권한 — 직원에게 배정된 직급의 권한 목록으로 기능 접근을 판단.
- **컨텍스트 방화벽**: 외부 LLM·임베딩으로 나가는 모든 컨텍스트에서 비밀키·주민등록번호·카드번호
  등을 마스킹하고, 민감 등급에 따라 로컬 강제/차단. 모든 결정이 감사 로그에 남습니다.
- **아카이브 git 백업**: `archive/`를 중첩 git 저장소로 자동 커밋(기본 30분) — 문서 이력 추적과
  실수 복구. `secrets/`·인증 상태는 이력에서 제외되며, 옵트인 원격 push를 지원합니다.
- 관리자 변경·문서 생성·키 변경 등 모든 관리 행위는 `archive/audit_log.jsonl`에 append-only 기록.

## 개발

```bash
ruff check . && ruff format --check .
mypy negotium                     # --strict
pytest -q                         # 353 tests
npm run dev --prefix frontend     # 프론트 HMR (선택, :5173 → :8080 프록시)
```

운영 상세(초기화 CLI, 메모리 저장 위치, Patch Machine 마이그레이션)는
[docs/operations.md](docs/operations.md), 전체 아키텍처는 [docs/architecture.md](docs/architecture.md)를 보세요.

## 로드맵

완료된 기능과 향후 개발 계획은 **[docs/ROADMAP.md](docs/ROADMAP.md)** 에 정리되어 있습니다. 요약:

- **완료**: 코어 루프 4종, Solar 에이전트 루프, HWP/DOCX 파싱(Document Parse),
  자동화 스케줄러(주간보고·리마인더·웹훅), 아카이브 검색(BM25+임베딩), 보안 하드닝, git 백업.
- **다음**: 업종별 온보딩 템플릿·데모 데이터, 결재(승인) 흐름, 이메일/그룹웨어 인제스트,
  HWP·Excel·PPT 실파일 출력, 생성 문서 품질 피드백 루프.

## 라이선스

MIT
