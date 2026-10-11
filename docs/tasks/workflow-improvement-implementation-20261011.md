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
