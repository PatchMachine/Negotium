# 운영 가이드

README에서 분리한 운영 상세 문서입니다: 상태 초기화 CLI, 메모리 저장 위치, Patch Machine 마이그레이션.

## 초기화 CLI (`negotium reset-state`)

초기화는 Negotium 백엔드가 설치된 호스트에서 실행합니다. 개발 환경에서는 저장소 루트에서
가상환경을 활성화한 뒤 실행하고, Docker 환경에서는 `negotium` 이미지/컨테이너 안에서 실행합니다.

```bash
# 로컬 개발 환경
source .venv/bin/activate
negotium reset-state --yes --actor admin

# uv로 실행하는 경우
uv run negotium reset-state --yes --actor admin

# Docker Compose
docker compose -f docker/docker-compose.yml run --rm negotium \
  negotium reset-state --yes --actor admin
```

옵션:

- `--yes`: 필수 확인 플래그입니다. 없으면 파괴적 초기화를 거부합니다.
- `--actor <name>`: 감사 로그에 남길 실행자 이름입니다. 예: `admin`, `ops`.
- `--include-workspaces / --no-include-workspaces`: `.ng_workspaces/` 작업 디렉터리까지 비울지 결정합니다. 기본 포함.

이 명령은 `archive/`의 운영 메모리, 권한, 인증 세션, API 키 저장소, 업로드, 생성 문서,
대화 기록, 휘발성 메모리, 에이전트 실행 로그와 작업 디렉터리를 비웁니다.
**아카이브 백업용 중첩 git 저장소(`archive/.git`)와 그 이력도 함께 삭제됩니다.**
`.env`, 소스 코드, 외부 API 서버는 건드리지 않으며, 초기화 자체는 새
`archive/audit_log.jsonl`에 `system.reset`으로 기록됩니다.

## 메모리 저장 위치

- `archive/YYYY/MM/*.md`: 과거 처리 로그 영구 메모리 (읽기 호환)
- `archive/audit_log.jsonl`: 감사 로그
- `archive/conversations/*.jsonl`: 사용자/LLM 대화 기록
- `archive/documents/`, `archive/hr/`, `archive/handover/`, `archive/work_architecture/`: 생성 산출물
- `archive/uploads/`: 업로드 원본 (+ Document Parse 결과 사이드카 `.parsed.md`)
- `archive/memory/promoted/*.md`: 승격된 영구 메모리
- `archive/memory/schema*.json`, `deletion_requests.json`, `tombstones.jsonl`: 스키마와 삭제 승인 이력
- `archive/volatile_memory/`: 휘발성 메모리·압축 컨텍스트 (파생 캐시)
- `archive/search_index/`: 검색 색인 (파생 캐시, 재생성 가능)
- `archive/secrets/`: 암호화된 API 키와 로컬 마스터 키 (백업 git에서 제외)
- `archive/automation.json`, `notifications.json`: 자동화 설정·상태와 인앱 알림

## Patch Machine에서 마이그레이션

Negotium 리브랜딩은 breaking change입니다. 기존 Patch Machine 설치를 이어 쓰려면:

1. **환경 변수**: `.env`의 모든 `PM_` 접두사를 `NG_`로 바꿉니다 (`sed -i 's/^PM_/NG_/' .env`).
2. **CLI**: `patch-machine serve` → `negotium serve`. 재설치: `uv pip install -e ".[dev]"`.
3. **인증**: API를 직접 호출하는 스크립트는 `POST /api/auth/login`으로 세션 토큰을
   발급받아 `X-NG-User: Bearer <토큰>` 헤더로 보내야 합니다 (사용자 이름만 넣는 방식은 401).
4. **작업 디렉터리**: `mv .pm_workspaces .ng_workspaces` (또는 새로 클론 후 초기 세팅).
5. **archive/**: 그대로 사용 가능하며, 관리자 설정 → 자동화에서 git 백업을 켜면 이력 관리가 시작됩니다.
