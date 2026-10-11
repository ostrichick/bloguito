# Bloguito 반복 작업 개선 구현 기록 — 2026-10-11

이 문서는 `docs/bloguito-workflow-improvement-plan-2026-10-11.md`의 실행 결과를 **로컬 구현 / 테스트 / 운영 배포**로 분리해 기록한다. 계획의 원인 분석은 당시 정적 코드 검사이며 이 기록의 구현 결과와 구별한다. 본문은 새 릴리스가 운영 환경에 설치되었다는 뜻이 아니다.

## 실행 결과와 계약

| ID | 로컬 구현 결과 | 주 검증 경계 | 운영 적용 |
| --- | --- | --- | --- |
| S1 | 스케줄러·수동 growth writer 공유 잠금, 중복 실행 실패 상태 | 병렬 실행, 프로세스 예외/종료, 알림 중복 | 미배포 |
| S2 | 이미지 생성 시점 WordPress snapshot을 image-only CAS에 고정 | 사전 검사 후 동시 변경, thumbnail 변경/응답 유실 시 import fence | 미배포 |
| S3 | 신규 `prepare-draft`의 durable creating/created/complete journal, 작성 즉시 post ID 기록, 모호한 요청 재생성 차단 | lost SSH response, 메타 실패 후 동일 ID 재개, 외부 글 변조 | 미배포 |
| T2 | 카탈로그의 임시 원격 PHP 실행별 이름·finally cleanup, tracked 백로그 CAS, 원자 개별 기록+세대 일치 검증 | 동시 sync, 파일 교체/읽기 오류, 사용자 편집 경합 | 미배포 |
| T3 | 새 draft의 permalink/Rank Math 메타를 내용 SHA·title/status/slug/발췌문 CAS와 함께 guarded transaction/readback | 성공 재실행과 메타 불일치/응답 유실; PHP 문법 검사 | 미배포 |
| T4 | 공식 법령 조항 및 PDF 페이지 범위 선택 수집, 별도 원문 SHA/버전·텍스트 SHA 유지 및 캐시 경계 | 60k 초과 원문, 범위 밖 인용 차단, cache/reviewer stale | 미배포 |
| T1 | 다른 검색 질문의 공유 공식 URL 중복 예외를 사람 승인·정확한 brief/비교대상 SHA receipt에 결합 | 실제 같은 질문은 하드 블록; 자동 scheduler 예외 없음 | 미배포 |
| F1 | 동일 action+release+route+transport만 묶는 `summarize_workflow_metrics.py --cohorts` | 5개 미만 표본의 비교 부적합 표시 | 미배포 |
| Q2 | `report_growth_queue.py` 읽기 전용 JSON 보고서 | missing/mismatched growth provenance에서는 조치 대상 숨김 | 미배포 |
| Q3 | 결과에 `drafts_created` 병기, 역사적 `published` 키 유지, 사용자 로그 draft 명칭 | 기존 파서 호환, 상태 검사 | 미배포 |
| R2 | 위임 이미지 선택 approval kind 분리 및 WP MU 검사 동기화; null-thumbnail combined edit; 명시적 lossless PNG staging | 브라우저·이미지 생성 호출의 자체 증명은 하지 않음 | 미배포 |
| R1 | 이미지 시작 상태 지문 계산을 부작용 없는 별도 내부 모듈로 이동, 기존 공개 import 유지 | 기존 image/followthrough 테스트 | 미배포 |
| F2 | **부분 구현:** 이미지 업로드 직전 동일 상태의 글/썸네일 조회를 2 WP reads → 1로 병합. 기존 SSH 경로는 이미 1회라 SSH 감소 없음; edit-post의 별개 CAS 경계는 유지 | 읽기 실패/응답 유실/동시 편집 실패 주입, 호출 횟수 fixture. 운영 속도 개선 실측 없음 | 미배포 |
| Q1 | **하네스 구현:** 기존 CDP 탭에서 390/1280 렌더·TOC·표/카드·CTA·계산기 관측 및 PNG/SHA 증거, 독립 검증 후 task-state 결합. 정적 렌더는 WordPress QA로 인정하지 않음 | 13개 synthetic fixture, 실제 인증 미리보기 브라우저 실행/네이티브 200% 확대는 미검증 | 미배포 |

**독립 원본 보존:** 작업 전 `main`의 `docs/POST_CATALOG.md`, `docs/clarity-integration-2026-09-29.md`, `docs/INDEX.md` 미커밋 변경과 계획서 untracked 파일을 덮어쓰지 않고 별도 Git worktree에서 구현했다. 신규 공개 포스트·임시글·대표이미지·예약 cron에 대한 WordPress mutation은 이 구현 검증 단계에서 수행하지 않았다.

## 확인된 한계

- 신규 draft의 `wp post create`와 로컬 journal은 동일 데이터베이스 transaction을 공유하지 않는다. 따라서 응답/ID 자체가 유실되면 **확실한 단일 post ID가 확인되지 않는 한 자동 복구가 아니라 차단**한다. 제목이나 본문이 같다는 이유로 기존 글을 임의 채택하거나 두 번째 `post create`를 보내지 않는다. 서버 측 생성 토큰을 완전히 원자적이라 주장하려면 독립 WordPress DB·hook/cache 장애 검증이 먼저 필요하다.
- Rank Math 메타의 guarded 원격 WordPress PHP는 syntax-only 검증을 수행했다. 실제 isolated WordPress DB의 transaction rollback, WP hook/object-cache 동작을 추가 검증하기 전 운영에 적용됐다고 주장하지 않는다.
- `image_gen`·CoS `save_image` 실제 호스트 호출의 독립된 서명 영수증은 현재 로컬 manifest의 문자열로 대체할 수 없다. 원본 파일 SHA·선택 주체·후속 업로드 기록을 검증하되 호스트 도구 호출 그 자체의 암호학적 확인을 주장하지 않는다.
- 기존 실행 성공 중앙값(신규 약 46.6초, 수정 45.7초, 이미지 60.8초)은 서로 다른 코드 버전과 작업 난도 표본이어서 이 릴리스의 절감률로 전용하지 않는다. 실제 운영 적용 후 동일 코드 버전·유형의 추가 표본에서 비교한다.
- 범용 브라우저 QA는 실제 접속된 CDP 세션·URL·post ID·저장된 content SHA가 필요한 도구이며, synthetic 테스트 스크린샷만으로 운영 WordPress 테마나 인증 미리보기의 레이아웃을 확인했다고 볼 수 없다. 기존 200% 접근성 확대는 절반 viewport 근사 검증일 뿐이다.
- F2는 실제 SSH latency 개선이 아니라 동일 Python 프로세스 내 WordPress 읽기 횟수만 2→1로 줄인 좁은 최적화다. 쓰기 직전 CAS와 쓰기 직후 readback을 유지한다.

## 운영 릴리스 승인 전 게이트

1. 모든 Git commit을 한 검증된 통합 브랜치에 합치고 `git diff --check`, 필요한 전체 Python/PHP 테스트와 release manifest consistency를 통과시킨다.
2. `build_editorial_release.py`로 clean HEAD에서 immutable manifest/archive를 만든 뒤 `install_editorial_release.py`를 disposable app에 적용·rollback 실험한다. WordPress MU plugin은 이 Python release에 포함되지 않으므로 독립 업데이트/기존 해시 복원 검증이 필요하다.
3. **운영 WordPress의 기존 본문/메타·공개 상태를 임의로 수정해 smoke test하지 않는다.** 별도 disposable WordPress/DB 검증과 백업·운영 비밀값/cron 보존 검사 후 배포한다. 실패 시 기존 release/hash를 되돌리고 이미 생성된 post ID는 중복 생성하지 않는다.
4. 배포 후 실제 cron 한 번의 결과, WordPress 저장·메타/이미지 readback, 통계 코호트의 충분한 관측치를 분리해 기록한다. 단순 코드 unit 통과를 운영 성공으로 승격하지 않는다.

## Q1·F2 최종 통합 검증 (2026-10-11, 운영 미배포)

- F2 안전한 중복 읽기 최소화: 통합 `1e596b3`, `test_f2_read_snapshots.py` 6건 단독 PASS. 직접 Python 호출의 동일 snapshot WP roundtrip 2→1은 mock 계측값이며 SSH 왕복/지연 절감의 실측 근거는 아니다.
- Q1 실제 CDP 세션용 하네스: 통합 `aa250c5`, `test_browser_qa.py` 13건 synthetic/offline PASS. 운영 WordPress의 인증 preview에 접속해 PASS를 기록한 것은 아니다.
- 릴리스 inventory 불일치와 독립 테스트 import 경로는 통합 후 `501c7d2`에서 보정했다. 정규 `run_validation.py --route repository --run` 결과: **Python 1,296건, failures 0, errors 0, skipped 2, exit 0**. Windows 환경의 `cron shell requires Linux` 및 `symlinks unavailable`이 건너뜀 원인이다.
- 독립 PHP 테스트: 운영 컨테이너 **`/tmp` 임시 격리 디렉터리**에 현재 로컬 PHP fixture 19개만 전송하고 `wordpress/tests/run.php`를 실행했다. 전체 파일 문법 검사 및 독립 contract runner **exit 0**; 임시 디렉터리 정리 확인. 실제 WP DB나 게시물 쓰기 테스트는 하지 않았다.
- clean HEAD의 `build_editorial_release.py --archive` 산출물은 87개 런타임·정책 파일의 digest와 installer manifest 검증에 통과했다. 이 빌더는 `run_daily.sh`, `scripts/`, `wordpress/mu-plugins/`를 패키징하지 않는다. 공유 lock의 실행 코드는 포함되는 `main.py`에 있지만 cron 셸 로깅 개선은 별도 배포 대상이다. MU의 `manual_agent_delegated` 허용은 반드시 분리된 검증·백업·롤백 절차로 적용해야 한다.
- 현재 운영 `editorial-release.json`의 revision은 `9b8145c0680e1d27d9e252d7f0cfaf2c3191a8d5`, inventory digest는 `3104dbc8c9ea1e9c3d3da173826b7e10772b064220a410f491bd489b40ca8cdb`로 확인했다. 운영 `run_daily.sh` SHA-256 `850c5c510eef74db72dcacf05f91ed2f406be0d1222d403f0512b0449c760e42`, 운영 MU SHA-256 `a77b668fd1c12c137a54ed0a14e63c3056e060f0bb43848ed5e2823b602f867f`. 로컬 MU SHA-256은 `d10d4b3bff10378f965b7e9db8d6d912c3ee99fdeb833136e0774939639794fa`로 **서로 다르다**.
- 운영 `backups/editorial-20261010T031614Z/manifest.json`과 백업 파일의 존재는 읽기 전용으로 확인했다. **복구 시뮬레이션·실제 WordPress DB 통합·cron 동작·인증 미리보기·성능 개선률 검증은 아직 하지 않았다.** 현재 단계에서 운영 릴리스, WordPress draft 수정 또는 공개 발행을 실행하지 않는다.

## 14항목 후속 구현·운영 안전 재판정 (2026-10-11)

**판정 축:** 다음 `완료`는 *로컬 기능 구현 및 관련 회귀* 기준이다. `부분`은 코드 범위 또는 계획의 실제 증거가 더 필요하다는 의미다. 전 항목 **운영 신규 릴리스 미배포**이며, 코드 완료가 WordPress 실운영 검증을 뜻하지 않는다.

| 항목 | 로컬 구현 판정 | 원 계획 기준 잔여 증거/한계 |
| --- | --- | --- |
| S1 실행 잠금 | 완료 | Linux cron-vs-direct 동시 실행 검증 미완료; 운영 cron 미변경 |
| S2 이미지 CAS | 완료 | 운영 WordPress 이미지 경합/비멱등 import 실행 미검증 |
| S3 Draft journal | 완료 | 같은 post ID 재개·모호한 응답 재시도 차단 fixture PASS; 실제 DB crash 경계 미검증 |
| T1 검색 의도 | 완료 | synthetic/검토 승인 계약 PASS, 실제 #928/#139/#926 인적 의미 검토 별도 |
| T2 카탈로그 | 완료 | atomic per-file + digest generation detection. 전체 쌍을 하나의 DB transaction으로 주장하지 않음 |
| T3 SEO CAS | 완료 | 독립 PHP 모형 DB 13 시나리오 PASS; 실제 MariaDB row lock/cache/rollback 미검증 |
| T4 원문 부분추출 | 완료 | exact source/raw SHA 계약 테스트 PASS, 운영 대형 공식 자료 roundtrip 별도 |
| F1 성능 계측 | 부분 | cohort 계측/표시는 구현; 동질 운영 표본·median/P90 비교 미확보 |
| F2 조회 효율 | 부분 | 기존 이미지 승인 pre/post 각 2 WP reads→1 fresh snapshot, 총 논리 조회 4→2(단위 mock); preimport 2→1. SSH/live latency 변화 미측정 |
| Q1 브라우저 QA | 부분 | 하네스 구현, CDP 9222에서 Lenovo 대상만 확인; Bloguito 탭 및 정확한 post SHA 부재로 390/1280 운영 Preview 미검증 |
| Q2 성장 후보 보고 | 완료 | 읽기 전용 근거·보류 이유 보고서 구현, 성장 인과·측정 수요 추정 없음 |
| Q3 상태 인계 | 부분 | `task-status --post-id` 읽기 전용 상태별 다음 행동 구현, 실제 WP readback은 독립 필요 |
| R1 공통 구조 | 부분 | 순수 이미지 baseline과 공통 edit resume/image phase 계약 분리; 대형 editor/transport의 잔여 구조 분리는 안전성 검증 후 단계적으로 진행 |
| R2 이미지 정합성 | 부분 | 승인 주체/PNG/null 썸네일과 `selection_actor` 영수증 일치 검증 구현; host image_gen 서명 증거 및 MU 운영 적용 미확보 |

**이번 후속 구현 통합:** F2 기존 이미지 보존 승인에서 원본 글·썸네일을 매 시점 하나의 신선한 WordPress snapshot으로 가져오고, 쓰기 전/후 경계 자체는 유지했다. Q3 read-only operational status는 결과 모호함을 `blocked_before_write`로 추정하지 않으며 내용 SHA와 별도 live readback을 요구한다. R2는 staging actor 불일치·누락을 실패 처리한다. signed release inventory에 `agent-publisher/run_daily.sh`(실행모드·rollback 보존)와 `wordpress/mu-plugins/bloguito-post-row-actions.php`(별도 설치, 자동 갱신 아님)를 추가했다. 서버의 기존 MU 파일 SHA가 다르면 Python 설치 시작 전 실패한다. `--preflight-only`는 **원격 운영 호스트에서 읽기 전용 진단**에 사용한다.

**검증:** 최종 통합 코드 Python repository route `1,308 tests, 0 failures, 0 errors, 4 skipped, exit 0`(Windows Linux-only cron 1, Windows symlink 관련 2, 로컬 PHP 실행 불가 1). 격리 PHP 컨테이너에서 신규 draft guarded metadata 스크립트의 모형 DB 13/13 PASS, MU PHP syntax/contract runner PASS. S3 journal recovery 6 PASS, 백업 archive 내부 gzip 손상 실패 주입 포함 synthetic backup restore 12 PASS. 이는 실제 WordPress/MariaDB 데이터베이스 통합이나 사이트 전체 복원 성공이 아니다. 자세한 사유는 `docs/bloguito-db-validation-2026-10-11.md`.

**운영 적용 차단 사유:** 현재 운영 runtime revision `9b8145c…`, 운영 MU SHA `a77b668f…`, 새 소스 MU SHA `d10d4b3b…`로 불일치한다. 노트북은 Docker/WSL/MariaDB가 없고 운영 서버는 RAM 952 MiB(available 약 461 MiB)로 프로덕션 자원 경합 없이 독립 MariaDB를 추가하기 어렵다. 실제 Linux cron 경쟁 테스트, 독립 DB 원자성/캐시 검증, 실백업 복원 훈련, WordPress MU 분리 설치/롤백 확인, 실제 CDP 인증 Preview QA가 미완료이므로 신규 runtime/MU/cron 운영 배포를 실행하지 않았다. 특정 글 공개·게시물 수정·비멱등 media import **0건**.
