# Solar 사용 후기 — Negotium

> Upstage Solar Agent Partner Stage 1 제출 문서입니다.
> 프로젝트: **Negotium** — 비 IT 한국 중소기업을 위한 LLM 에이전트 오피스워크/BPA 콘솔
> ([README](README.md) · [로드맵](docs/ROADMAP.md))

## 프로젝트 한 줄 설명

회의록→업무배정→주간보고→인수인계/채용이 하나의 닫힌 루프로 돌아가는 사내 설치형
오피스 자동화 콘솔입니다. DB 없이 Markdown 아카이브가 원본이고, `solar-pro3` 도구 호출
에이전트가 제품의 심장입니다. Upstage API를 **Chat Completions(에이전트 루프),
Document Parse(HWP/DOCX 파싱), Embeddings(시맨틱 검색)** 세 곳에서 사용합니다.

## 사용 후기

2주간 Negotium의 모든 AI 경로를 Solar 위에서 개발했습니다. 가장 큰 장점은 **OpenAI
호환성과 에이전트 특화의 조합**이었습니다. 별도 SDK 없이 base_url 교체만으로 기존
OpenAI 어댑터를 재사용했고, `solar-pro3`의 병렬 도구 호출은 조직 조회→문서 생성→메모리
검색을 한 턴에 엮는 에이전트 루프를 안정적으로 지탱했습니다. `reasoning_effort=minimal`
기본값은 "보고서 하나 만드는 데 30초 추론"이 아니라 즉답을 주기 때문에 오피스워크
제품의 기본 모델로 쓰기에 결정적이었습니다. 무엇보다 **Document Parse의 HWP/HWPX
지원**은 다른 어떤 글로벌 API도 제공하지 않는, 한국 시장용 제품을 만들 때의 실질적
차별점이었습니다 — 표가 살아있는 마크다운이 나오니 회의록 파이프라인에 바로 꽂혔습니다.
임베딩 API도 정규화 벡터(내적=코사인)라 순수 파이썬으로 검색 융합을 구현할 수 있었습니다.
같은 키 하나로 세 API가 모두 열리는 것도 운영상 큰 장점입니다. 아쉬운 점은 아래 기술
피드백에 가감없이 적었지만, 총평은 명확합니다: **한국어 오피스 도메인에서 에이전트
제품을 만든다면 Solar가 현재 가장 실용적인 선택**입니다.

## 잘 동작한 것

- **OpenAI-compatible**: `OpenAiProvider` 재사용 + base_url 교체로 어댑터 추가 비용 0.
  라이브 모델 목록(`/models`)도 그대로 동작.
- **`solar-pro3` 병렬 도구 호출**: 다중 턴 에이전트 루프(읽기 자동 실행/쓰기 승인 카드)가
  프로덕션 수준으로 안정적. 승인 재개 시 재추론 없이 호출 재생하는 설계도 문제없이 수용.
- **`reasoning_effort` 4단계**: 작업 라우트별로 minimal(채팅·문서)과 high(계획)를 나눠
  쓰는 운영이 가능. 숨은 추론 없이 content가 바로 오는 기본값이 오피스 UX에 적합.
- **Document Parse**: HWP v5 바이너리까지 처리하는 유일한 API. 동기 100페이지/50MB 한도는
  SMB 문서에 충분했고, `output_formats=["markdown"]`의 표 변환 품질이 좋았습니다.
- **Embeddings**: `embedding-passage`/`embedding-query` 분리, 4096차원 정규화 벡터,
  배치 100 — 문서화된 대로 동작했고 놀랄 일이 없었습니다.

## 아쉬웠던 점 · 개선 제안 (가감없이)

1. **function name 문자 제한의 에러 진단이 어렵습니다.** 도구 이름에 점(`.`)이 들어가면
   (`office_memory.search` 같은 MCP 관례) 요청 전체가 400으로 거부되는데, 에러 메시지가
   어느 필드의 어느 이름이 문제인지 짚어주지 않아 원인을 찾는 데 시간이 걸렸습니다.
   저희는 `[a-zA-Z0-9_-]` 변환 계층(`to_wire_name`/`tool_name_map`)을 만들어 해결했지만,
   **오류 응답에 위반 필드 경로를 포함**해 주시거나 문자 집합을 완화해 주시면 좋겠습니다.

2. **후속 턴 메시지 검증도 마찬가지입니다.** `tool_call_id`/`tool_calls`/`reasoning`
   필드를 정확히 보존하지 않으면 루프 2회차에서 400이 나는데, 몇 번째 메시지의 어떤
   필드가 문제인지 알 수 없어 컨텍스트 방화벽(메시지 정제 계층)과의 상호작용 디버깅이
   힘들었습니다. **검증 실패 지점을 가리키는 에러 상세**가 있으면 에이전트 개발 경험이
   크게 좋아질 것입니다.

3. **`solar-open2`와 호스티드 모델의 API 표면이 다릅니다.** `reasoning_effort`가
   호스티드는 4단계(`high|medium|low|minimal`), open2는 `high|none`뿐이고, open2는
   응답 전에 숨은 추론에 토큰을 크게 소모해 `max_tokens`를 보수적으로 주면 **빈 응답**이
   옵니다. 저희는 모델 프로필에 `hidden_reasoning` 필드를 따로 두고 토큰 예산을 분기해야
   했습니다. **모델별 권장 토큰 예산과 reasoning 동작 차이를 한 표로 문서화**해 주시면
   같은 시행착오를 줄일 수 있습니다. (vLLM 서빙 시 `--tool-call-parser solar_open2`
   플래그도 더 눈에 띄는 위치에 있으면 좋겠습니다.)

4. **`tool_choice="none"` 마지막 패스에서 채팅 템플릿 토큰이 본문으로 새어 나오는 경우가
   있습니다.** 도구를 더 부르고 싶은 모델이 `<|tool_call:begin|>...` 원문을 답변 텍스트로
   출력해, 사용자에게 노출되지 않도록 클라이언트에서 제거하는 처리를 추가해야 했습니다.
   서버 측에서 걸러지면 이상적입니다.

5. **작은 요청**: 임베딩 인덱싱처럼 대량 배치를 돌릴 때를 위한 배치 단위 부분 성공
   응답(일부 텍스트만 실패 시), Document Parse 결과에 페이지별 신뢰도 같은 메타데이터가
   있으면 파이프라인에서 재시도/검수 대상을 고르기 쉬워집니다.

## 재현 방법

```bash
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env   # NG_SOLAR_API_KEY 채우기
negotium serve --build-frontend
# http://localhost:8080 → 셋업 마법사(대화형, solar-pro3) → 회의록 붙여넣기 → 업무 자동 배정
```

Solar 연동 코드 위치: 에이전트 루프 `negotium/app/services/agent_loop_service.py`,
Document Parse `negotium/app/services/document_parse_service.py`,
Embeddings `negotium/app/services/archive_search_service.py`,
모델 티어 카탈로그 `negotium/adapters/llm/catalog.py`.
