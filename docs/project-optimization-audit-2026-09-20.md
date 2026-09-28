# Bloguito 코드·중복 파일·운영 최적화 감사 (2026-09-20)

## 범위와 변경 원칙

- 프로젝트: `C:\Projects\Bloguito`.
- Git `main`, 기준 커밋 `ddd86c7`; 점검 시작 시 작업 폴더 깨끗함. `git ls-files`에 포함된 124개 파일, 주요 Python 진입점·발행 검증·백업·테스트·Docker/CI·WordPress 연계 지침을 확인함.
- Linux 서버의 크론탭은 읽기 전용으로 확인: 04:00 통합 백업, 08:00 자동 초안 생성 명령. 실제 크론 실행 성공률·가장 최신 원격 백업의 구성/복원까지 확인했다는 뜻은 아님.
- 공개 홈페이지, 개인정보처리방침 및 게시물 URL `?p=304`의 HTTP 응답과 HTML 스크립트 개수를 읽기 전용으로 조사. 세 페이지 모두 HTTP 200, Google Analytics 외부 스크립트 1개와 `gtag config` 1개를 확인. GA4 수집·전송과 동의 작동까지 검증한 것은 아님.
- WordPress DB·공개/임시 게시물·플러그인·크론·DNS·서버 배포·백업 파일을 수정하거나 삭제하지 않음. 사용자 요청에 따라 확인된 코드 버그 2개와 회귀 테스트만 로컬에서 수정함. Git 커밋/푸시는 수행하지 않음.

## 파일 구조 / 중복 판단

| 항목 | 증거 | 분류 / 처리 |
|---|---|---|
| `agent-publisher/.venv/` | 약 4,338개 파일, 102.86MB; `.gitignore`에 포함 | 설치 의존성 환경. Git 정리 대상 아님. 환경 재생성 절차를 확인한 뒤에만 재구성. |
| `.clinerules`, `.continuerules`, `GEMINI.md` | 3개 SHA256 동일 | 내용 중복이지만 Cline/Continue/Gemini 소비자가 다를 수 있음. 직접 삭제 금지; 도구별 짧은 참조 파일 + 공통 `AGENTS.md`/`docs/EDITORIAL_SYSTEM.md` 통합 검토. |
| `agents/copywriter.py` vs `agents/editorial_writer.py` | `main.py`는 후자를 `CopywriterAgent`로 별칭 import. 전자는 여러 기존 테스트에서 직접 import | 기능상 레거시 중복. 테스트 마이그레이션·실제 배포 참조 검증 전 제거 금지. |
| `editorial.render_legacy` vs `render` | `publisher.reformat_draft`가 구형 본문 비교에 사용 | 의도적인 호환 구현. 삭제 대상 아님. |
| `agent-publisher/analyze.py`, `check_sitemap.py`, `infolspot_analysis.json` | 타 사이트 `infolspot.com` 하드코딩, 메인 파이프라인의 직접 호출 없음 | 오래된 연구/진단 파일 후보. 콘텐츠 근거·회귀 참조 확인 후 `archive/research/` 이동 검토; 데이터 삭제 금지. |
| `scripts/archive/`, `agent-publisher/archive/` | 과거 수동 정정·실험 스크립트 | 아카이브라는 용도가 명확하므로 유지; 실행 가능 문서에서 오래된 절차를 현행으로 소개하지 않도록 정리. |
| `backups/` 로컬 폴더 | 9월 12~16일자 DB-only gzip 5개, 약 1.13MB | 삭제 금지. 이 로컬 폴더에는 통합 스냅샷이 보이지 않음. 원격에 최신 통합 백업이 없다는 증거는 아님. |

## 긴급도 높은 로직·운영 리스크

1. **백업이 WordPress 전체 복원을 보장하지 않음 — 높은 우선순위.** `agent-publisher/backup_daily.sh`는 MariaDB 덤프, `wp-content/uploads`, 에이전트/Compose 설정과 JSON을 보관한다. `wp-content/plugins`, `themes`, `mu-plugins`, 설치된 Site Kit 등 WordPress 파일 전체와 Nginx/인증서 운영 설정은 현행 패키지에 포함된다는 근거가 없음. Docker Compose의 `wp_data` 이름 있는 볼륨을 새 호스트에서 재현할 때 누락될 수 있음. 먼저 테스트 환경에서 백업 범위를 확대하고 복원해야 함.
2. **설정 복원 불완전 — 높은 우선순위.** `restore_backup.sh`는 `configs.tar.gz`를 풀지만 `configs_staging/agent-publisher/data/*.json`만 실제 복사함. 백업한 `agent-publisher/.env`, `config.py`, `wordpress/.env`, Compose 파일 등은 복원하지 않음. 성공 메시지의 'Full blog restoration'은 실제 실행 범위보다 큼. 비밀번호·설정 파일을 무작정 운영 환경에 덮어쓰지 말고 명시적 매핑/사전 확인/스테이징 검증을 설계할 것.
3. **배포 재현성 — 높은 우선순위.** `wordpress/docker-compose.yml`이 `wordpress:latest`를 사용하여 재설치/재배포 때 예상치 못한 버전 변경 가능. 검증된 구체적 버전 또는 digest 고정 후 업데이트 절차를 별도로 만들 것. `wordpress/setup.sh`는 기본 글 강제 삭제·고유주소 변경을 포함하는 초기화 도구로, 기존 사이트에서 재실행 금지.
4. **오프사이트 백업 무결성 및 SSH — 높은 우선순위.** `scripts/sync_backups.py`는 고정 IP와 개인 PC 키 파일 경로를 포함하며 `StrictHostKeyChecking=no` 사용. 같은 파일명이 존재하면 크기/체크섬 검증 없이 건너뜀. 전송 중 실패한 파일의 잔해를 최신으로 오인할 수 있음. 환경 설정/SSH alias, 임시 파일로 다운로드 뒤 원자적 이동, 원격 해시·아카이브 무결성 검사와 테스트 권장.
5. **Site Kit/정책 정합성 — 확인 필요.** 과거 `docs/sitekit-and-editorial-handoff-2026-09-20.md`에는 캐시된 홈페이지에 GA 태그가 없다는 시점 기록이 있음. 이번 재조회에서는 홈페이지·개인정보처리방침·#304 페이지에 각각 외부 GA 스크립트 1개/gtag config 1개가 확인되어 해당 과거 관찰을 현재 사실로 사용하면 안 됨. 단, 네트워크 이벤트 1회만 발생하는지, GA4 수집이 정상인지, 동의 동작과 정책 안내가 일치하는지는 미검증. 실서비스 개인정보 방침은 자동 생성 원고처럼 광고·행정 절차를 혼합하지 말고 확인된 실제 처리 내용을 기준으로 관리할 것.
6. **검사/테스트의 증명 범위.** `test_backup_restore.py`는 합성 아카이브와 체크섬·파일 줄바꿈 테스트 중심으로, MariaDB·WordPress 플러그인/테마의 실제 복구를 시연하지 않음. 검증 완료 문구를 전체 복구 성공으로 해석 금지.
7. **중복 글 판정의 보수성과 한계.** `search_intent.duplicate_posts`는 필수 제목 토큰 전부 포함 또는 동일 공식 URL 문자열 포함으로 막음. 공통 안내 페이지 하나를 공유하는 다른 질문까지 중복 판단할 수 있으며, 반대로 다른 URL로 게시한 의미상 중복은 못 잡을 수 있음. 검색 의도·제도·대상·지역별 식별자로 보완한 테스트가 필요.
8. **운영 명칭 및 관측.** `main.py`의 `stats['published']`는 실제로 강제로 draft 생성된 개수를 센다. 알림 본문은 '신규 임시글'로 바로잡았지만 변수명과 일부 로그는 여전히 발행으로 표시하므로 운영 대시보드에서 오독 위험. `quota_tracker.py`는 API 제공자의 실제 잔여량이 아닌 프로세스 내 성공 호출 횟수의 로컬 추정임. 주석에는 UTC/PDT 표현 혼재.

## 이번에 적용한 로컬 수정 (운영 미배포)

- `agents/publisher.py`: 임시글에 `source-links` 마커 문자열만 존재한다는 이유로 재서식을 허용하던 우회 조건 삭제. `render_legacy()` 원문, 현재 renderer 본문 또는 자동 추천 카드 차이만 허용. 사용자 편집 임의 본문은 원본 보존을 위해 차단.
- `agents/curator.py`: 새 뉴스 원문을 수집할 때 `last_article_image_url` 초기화. 이전 기사 이미지가 다음 기사 썸네일로 전달되는 상태 누출 차단.
- `tests/test_editorial_system.py`, `tests/test_ticket_validation.py`: 각각 수정 전 오류 재현, 수정 후 통과하는 회귀 테스트 추가.
- 테스트 명령: `PYTHONPATH=agent-publisher agent-publisher/.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests -q` (PowerShell에서는 `PYTHONPATH` 환경변수 지정 후 실행). 결과 **139 tests / OK**. `git diff --check` 통과. 외부 서비스 종단간 통합 테스트 또는 서버 배포 검증을 의미하지 않음.

## 추천 작업 순서

1. **백업/복구 재설계:** 현재 스냅샷을 삭제하지 말고 WordPress 플러그인·테마·MU 플러그인·필요 설정 범위를 정의. 스테이징 환경에서 복구하고 로그인/글/첨부파일/사이트맵/플러그인 상태까지 대조. 그 뒤 백업 로직 배포.
2. **로컬 수정 2건 운영 반영:** 코드 리뷰 → 커밋 → 배포 전 스냅샷 → 서버 코드 해시 비교 → 서버 테스트 → 워드프레스 초안 상태 변경 없이 정상 운영 점검. 현재는 미실시.
3. **배포 버전 관리:** `wordpress:latest` 지양. CI의 합성 백업 테스트와 별도로 배포 사전 검증을 구축.
4. **레거시 파일 정리:** `copywriter.py` 의존 테스트 교체 후 제거 또는 레거시 전용 위치로 이동, `infolspot` 조사 파일 아카이브, 3종 에이전트 규칙 파일은 소비 도구의 실제 참조 방식 확인 후 공통화.
5. **콘텐츠·통계 관리:** Search Console/GA4 실수집과 동의·정책을 별도 점검. 검색어 측정 없이 자동 생성 후보를 인기 검색어로 표기하지 말 것.

**현재 상태:** Git에 수정된 4개 파일과 이 감사 문서만 미커밋. WordPress·서버·DNS·원본 백업·기존 게시물은 변경하지 않음.