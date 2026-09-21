# Bloguito — 생활정보 24

대한민국 생활정보 블로그를 위한 WordPress + Python 에디토리얼 자동화 저장소다. `agent-publisher/main.py`가 후보 탐색, 원문 수집, 근거를 붙인 원고 생성·검토, 썸네일 제작, WordPress **임시글(draft) 등록**을 연결한다. 공개 전환은 사람의 개별 확인과 별도 명시적 명령이 필요하다. 수익·검색 유입·모든 콘텐츠의 사실 정확도는 보장되지 않는다.

## 어디부터 읽어야 하나

| 작업 | 문서 |
| --- | --- |
| 지침·안전 기준 | [AGENTS.md](AGENTS.md) |
| 주제 선정·원고·검토·등록·공개 규약 | [docs/EDITORIAL_SYSTEM.md](docs/EDITORIAL_SYSTEM.md) 및 실제 임계값인 [`editorial_policy.json`](agent-publisher/editorial_policy.json) |
| 로컬 실행, 운영·백업·배포 체크리스트 | [docs/OPERATIONS.md](docs/OPERATIONS.md) |
| 문서 전체 목차와 날짜별 작업 증거 | [docs/INDEX.md](docs/INDEX.md) |
| 다른 AI로 인계 | [PROJECT_HANDOVER.md](PROJECT_HANDOVER.md) |
| 콘텐츠 구조/수요 검증 구상 | [콘텐츠 전략 제안](docs/CONTENT_STRATEGY_2026-09-20.md) — **미구현 제안**, 자동 실행 정책 아님 |

초기 [구현 계획](implementation_plan.md)·[완료 기록](walkthrough.md)과 오래된 인계서는 **역사 자료**다. 당시 백업 명령, 모델 우선순위, '자동 발행' 및 광고·SEO 관련 주장을 현행 지침으로 사용하지 않는다. 본 README 역시 운영 서버의 최신 상태를 증명하지 않는다.

## 구성 요소

| 위치 | 기능 |
| --- | --- |
| `agent-publisher/main.py` | Radar → Curator → Editorial Writer → Designer → Publisher 자동 임시글 생성 |
| `agent-publisher/editorial_cli.py` | 공식 출처 수집, 검토·검사, 임시글 생성/갱신, 사람 확인 후 공개 전환 |
| `agent-publisher/agents/` | 주제 후보·원문·검증·썸네일·WP 처리. `copywriter.py`는 레거시이며 활성 파이프라인은 `editorial_writer.py` 사용 |
| `agent-publisher/whatsapp-bridge/` | WhatsApp 명령 처리. Git에 있는 코드와 운영 서비스의 버전·환경값은 구분 |
| `wordpress/` | WordPress·MariaDB Compose와 자체 MU 플러그인. 기존 사이트에서 `setup.sh` 재실행 금지 |
| `scripts/` | 백업 동기화, 감사 및 제한된 운영 작업 도구 |
| `docs/` | 정본 편집·운영 규약, 제안, 날짜별 검증·배포·콘텐츠 근거 |

WordPress 사이트: [lifeinfo24.org](https://lifeinfo24.org). 관리자에서 **글 → 모든 글**의 글 ID 열은 [2026-09-21 운영 적용·WP 후크 검사 기록](docs/admin-post-id-column-2026-09-21.md) 참고(당시 로그인 브라우저 UI 검사는 미실시).

## 로컬 준비

Python 3.12, Git Bash, 프로젝트 작업에 필요한 Docker/Node를 준비한다. 비밀정보는 `.env.example`을 참고해 **추적되지 않는 환경별 파일**에만 넣는다. `agent-publisher/data/`의 운영 상태와 로그인·DB·SSH 자격증명은 Git에 올리지 않는다.

```powershell
# 프로젝트 루트 / Windows PowerShell
py -3.12 -m venv agent-publisher/.venv
./agent-publisher/.venv/Scripts/python.exe -m pip install -r agent-publisher/requirements.txt
$env:PYTHONPATH=(Resolve-Path './agent-publisher').Path
$env:PYTHONIOENCODING='utf-8'
./agent-publisher/.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests -q
```

운영 Linux의 `run_daily.sh`는 `agent-publisher/venv` 경로를 사용할 수 있으므로 Windows `.venv`와 혼동하지 않는다. 자동화·복구·Compose를 **실행하기 전** [운영 가이드](docs/OPERATIONS.md)의 사전 조건을 확인한다. `docker compose config`는 `--quiet`만 사용해 DB 비밀번호가 출력되지 않게 한다.

## 운영과 검증의 경계

- 글 공개, 기존 글 수정, DB 복구, WordPress/WhatsApp 서비스 재시작·배포는 테스트나 문서 정리와 별개의 작업이다. 기본은 draft, 출처/원고/검토가 불일치하면 보류한다.
- `backup_daily.sh`의 v3 코드에는 플러그인·테마까지 포함한 구성요소 검사가 있으나, **독립 환경에서 전체 사이트의 실제 복원과 비밀정보 암호화는 마지막 기록에서 미검증**이다. [백업 기록](docs/backup-recovery-2026-09-20.md)과 실제 서버 상태를 재확인한다.
- 2026-09-20과 21일의 콘텐츠 목록·테스트 개수·배포 증거는 [문서 목차](docs/INDEX.md)의 해당 날짜별 문서를 참고한다. 예를 들어 9월 20일의 '임시글 11편'은 9월 21일 상태를 뜻하지 않는다.
- 설정이나 코드 변경 시 기존 미커밋 작업을 보존하고 적절한 테스트를 거친 뒤 의도한 파일만 커밋·푸시한다. 운영 적용 여부는 결과에서 별도로 밝힌다.
