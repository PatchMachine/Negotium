# Patch Machine

비 IT 기업이 **GitHub Issues + Discord** 만으로 IT 기업처럼 운영할 수 있도록 돕는,
LLM 에이전트 기반 **자동 SI/SE 시스템**입니다.

버그 리포트가 들어오면 PM → Developer → Reviewer 에이전트가 협력해
코드 컨텍스트를 학습하고 **패치 Diff**를 제안합니다. 모든 추론 과정과 결정 근거는
Markdown 파일로 저장되어(**MD GitOps**) 누구나 메모장으로 읽고 수정할 수 있습니다.

## 핵심 가치

- **관심사 분리**: Event Ingestion / Context / Agents / Verification / Knowledge / Serving 6계층.
- **Ports-and-Adapters**: GitHub -> Slack, OpenAI -> Ollama 등 어댑터만 바꾸면 됨.
- **GitOps**: 별도 DB 없이 `archive/*.md`가 단일 진실 원본.
- **Privacy by Default**: 사내 핵심 로직은 로컬 LLM 라우트로 강제.

## 아키텍처 (요약)

```
GitHub Issue  --+
                +--> EventBus --> Orchestrator
Discord Msg  --+                       |
                                       v
                 Context (AST + MD Retriever)
                                       |
                                       v
                 PM -> Developer -> Reviewer (self-correction)
                                       |
                                       v
                 archive/YYYY/MM/*.md  +  GitHub/Discord 코멘트
```

## 빠른 시작

```bash
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env          # 값 채워 넣기
patch-machine serve
```

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
