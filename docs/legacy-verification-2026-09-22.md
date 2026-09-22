# 구형 공개 글 현대화 6단계 독립 검증 — 2026-09-22

## 검증 범위와 판정 기준

- 검증 대상: 사용자에게 제시된 여섯 단계 **① 전수 진단 → ② 글별 우선순위 → ③ 공통 서식 → ④ 글 하나 파일럿 및 글별 승인 → ⑤ 나머지 순차 개선 및 글별 승인 → ⑥ 지속 품질 감사**. 이전 계획의 배포·편집·스케줄 승인 여부를 추측하지 않으며 준비·로컬 테스트·실제 운영 적용을 따로 기록한다.
- 프로젝트 루트 `AGENTS.md`, `docs/EDITORIAL_SYSTEM.md`, `agent-publisher/editorial_policy.json`, `docs/OPERATIONS.md`와 현재 코드/작업 기록을 확인했다. 로컬 Git HEAD 관측값 `6c38256`; 현재 작업 트리에 다른 담당자의 추적/미추적 수정이 존재한다. 이 검증은 Git 변경·서버·WordPress 쓰기 없이 수행했다.
- 특히 공개 REST의 `content.rendered` SHA256은 실제 WordPress 원본 `post_content`의 교체 전 해시가 아니다. 원본 해시나 사람 검토 증거를 확보하지 않은 게시물은 공개 변경 완료로 판정하지 않는다.
- 아래 `확인`은 로컬 코드 또는 산출물 존재·실제 명령의 결과를 뜻한다. 다른 담당자의 공식 근거 판단을 별도 외부 원문으로 다시 교차검증한 것은 아니며 해당 사실의 결론까지 독립 인증하지 않는다.

## 단계별 누락 점검

| 단계 | 지금 확인한 실제 산출물 | 아직 완료했다고 볼 수 없는 부분 |
| --- | --- | --- |
| 1. 전수 진단 | `docs/legacy-post-modernization-audit-2026-09-22.md`, `docs/legacy-post-modernization-worklog-2026-09-22.md`, `scripts/audit_legacy_posts.py` 및 공개 REST 스냅샷. 문서상 공개 30편, 신규형 5편·구형 25편, 잘못된 요약 박스 닫는 태그 별도 조사 24편. REST 전수의 사실·브라우저·링크 상태를 계속 `unverified`로 둔 것이 올바른 구분이다. | 공개 API는 임시·예약·비공개 글을 포괄하지 않으며 30편의 모든 문단·표와 공식 자료를 독립 교차 검증한 증거가 없다. 모바일/200% 확대 실측도 없다. `missing_toc_candidate` 25편을 곧바로 25편의 필수 수정으로 해석하지 않는다. |
| 2. 우선순위와 내용 연구 | 검증 중 다른 담당자가 `docs/legacy-content-priority-2026-09-22.md`를 새로 완성했다. 30개 ID 모두 P0~P3와 사유·후속 조치가 있으며, #137·#101은 P0, #55·#79·#103 등은 P1. `tmp/legacy_audit_20260922/content-worker1/`에 #55/#79/#103의 brief, bundle, 인용 매트릭스가 있다. | 세 원고의 보관된 `check-{55,79,103}.json` 모두 `needs_review`이며 독립 의미 검토/정식 WordPress 수정용 전체 상태 인벤토리가 없다. #55에는 `duplicate_topic` 추가. #103의 목포 개별 기관명·주소·전화 목록은 공식 검색 결과에서 아직 확보하지 못했다. #101의 출처 제목/도착지 불일치는 콘텐츠 담당 문서에 기록됐으며 이 검증에서는 외부 원문을 재열람하지 않았다. |
| 3. 공통 서식 | `wordpress/mu-plugins/bloguito-legacy-callout-spacing.php`, `wordpress/mu-plugins/bloguito-legacy-toc.php`, `wordpress/tests/legacy-toc-contract-test.php`가 로컬에 존재한다. `docs/legacy-layout-rollout-2026-09-22.md`는 긴 구형 글 19편만 목차 추가, 짧은 6편·신규형 5편 출력 보존, #85의 표 두 개를 내용 보존한 별도 사본으로 준비했다고 기록한다. | 두 MU 플러그인의 실제 운영 설치·CSS 적용·WordPress 테마/필터 결합·사람의 360/390px·200%·보조기술 QA는 여기서 확인하지 않았다. CSS는 잘못된 저장 HTML 태그를 직접 교정하지 않는다. #85 표는 사전 변경안이며 본문 미적용. 기존 글의 구조 전환이 서버에 완료됐다고 볼 수 없다. |
| 4. #137 파일럿 | `docs/pilot-post-137-preparation-2026-09-22.md`, `tmp/legacy_audit_20260922/pilot137/bundle.unreviewed.json`·인용 매트릭스·미검토 HTML 미리보기가 있다. 국세청 근거에서 2027년 후속 신청기한과 2026년 지급 예외를 작성했다. 현재 코드로 `validate_bundle(..., require_review=False)`를 직접 재검사하면 `ready`, 사유 `[]`: 기존 문서의 시간 유효성 차단 두 건은 이후 다른 담당자가 추가한 `legacy_followup` 경로로 해결됐다. | **실제 `editorial_cli.py check`는 종료 코드 2**, 사유 `review_not_bound_to_current_content`, `review_stale`, `semantic_review_failed`. 독립 모델 의미 검토 6항목을 통과하지 않았고 실제 WordPress 원본 해시·원본 백업·전체 상태 인벤토리·게시물별 승인·모바일 UI·`update-existing` 적용/사후 재조회도 없다. 파일럿 완료/게시 완료라고 표기하면 안 된다. |
| 5. 나머지 글 순차 개선 | 30편 대기열과 세 편의 보강 원고·#85 표 사본 등 **검토 가능한 준비물**이 있다. `agent-publisher/agents/editorial_updater.py`에는 기존 공개 글의 원본 해시 검사와 정상 수정 경로가 있다. | #137이 독립 검토·승인·적용을 통과하지 않았으므로 다른 게시물들의 연속 공개 수정 완료 근거가 없다. #55/#79/#103도 검사 보류 상태이며 한 편씩 근거 재확인·원본 백업·글별 승인 후 정상 경로로 진행해야 한다. |
| 6. 지속 품질 관리 | `scripts/audit_legacy_posts.py`가 단일 읽기 전용 엔트리포인트이고 `docs/legacy-audit-automation-2026-09-22.md`, `agent-publisher/tests/test_legacy_post_audit.py`가 있다. 페이지 헤더/총수/중복 검증, 변경 감지, 출처·링크·서식 후보, 안전한 `unverified` 상태, 선택적 사람 검증 레지스터/기한을 확인했다. 타깃 감사 테스트는 이 작업 직전 9건 통과 기록이 있고, 아래 전체 테스트에도 포함된다. | **스케줄러는 활성화하지 않았다.** 실제 사람의 검증 레지스터가 없어 30편의 `review_due`가 미확인이고, 이메일/알림 담당·실패 복구·장기 운영·경쟁 수정 감지도 미검증이다. 수집 결과는 자동 사실검증이나 자동 편집·게시를 뜻하지 않는다. |

## 넓은 로컬 검사: 명령과 실제 결과

프로젝트 루트에서 `docs/OPERATIONS.md:17-39`를 출발점으로 실행했다. 비밀 구성값을 출력하지 않았고, 실제 WordPress·서버·복원·배포 명령은 실행하지 않았다. Python에서는 `PYTHONPATH=./agent-publisher`, `PYTHONIOENCODING=utf-8`, `PYTHONDONTWRITEBYTECODE=1`를 설정하고 기존 `agent-publisher/.venv/Scripts/python.exe`를 사용했다. 전체 테스트는 fixture의 임시 썸네일/모의 백업 출력을 생성할 수 있으나 라이브 WordPress 수정 검사는 아니다.

| 검사 | 실제 결과 | 해석·주의 |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests -q` | **첫 실행** `Ran 236 tests in 14.284s`, `FAILED (failures=2, skipped=1)`, 실제 unittest 종료 1. | `test_article_layout.py::test_at_a_glance_table_precedes_actions_and_navigation` 및 `::test_only_procedures_receive_step_numbers` 두 건이 단일 절차에 `STEP 1`을 기대했으나 렌더러가 단일 배지를 의도적으로 생략해 불일치. 기존 `docs/callout-spacing-audit-2026-09-22.md:19-20`에도 같은 이전 불일치 기록. 본 검증 담당자는 파일을 수정하지 않았다. |
| 다른 담당자의 `test_article_layout.py` 수정 이후 **동일 전체 명령 재실행** | `Ran 236 tests in 14.349s`, unittest 종료 **0**, 실패 0, 건너뜀 1. | 현재 파일의 테스트는 단일 STEP 생략을 명시적으로 기대한다. 출력의 `FAILED bloguito_backup_... simulated transfer interruption`는 테스트 fixture의 의도된 전송 실패 시뮬레이션 로그이고 unittest의 최종 `FAILED` 판정이 아니다. 전체 테스트 성공은 현재 로컬 환경·그 시점의 트리 기준이며 운영 서버 검증은 아니다. |
| Python 소스 전체 비작성 `compile(..., 'exec')` 점검 | `agent-publisher/`와 `scripts/`의 85개 중 **84개 통과, 1개 실패**. | `scripts/archive/attach_remaining_thumbs.py:9`의 `unexpected indent`. 줄 8의 `tasks = [tasks[1]]` 다음 들여쓴 딕셔너리 조각에서 발생하며 2026-09-12 보관된 일회성 WordPress 작업 스크립트다. **실행하지 않고 수정 범위 밖이므로 그대로 두었다.** |
| 보관된 `scripts/archive/` 제외, 활성 Python 비작성 컴파일 | **69개 통과, 오류 0**, 종료 0. | `compile(source_bytes, path, 'exec')`로 검사해 `.pyc`를 의도적으로 생성하지 않았다. 런타임 외부 API/운영 결과의 검증은 아니다. |
| `bash -n agent-publisher/backup_daily.sh agent-publisher/restore_backup.sh` (Git Bash) | 종료 0. | 문법만 확인, 백업/복원 실행 안 함. |
| `node --check` (WhatsApp bridge `index.js`, `command_policy.js`, `command_policy.test.js`) | 세 파일 모두 종료 0. | 문법 검사만 해당. |
| `node --test agent-publisher/whatsapp-bridge/command_policy.test.js` | **3개 통과, 실패 0**, 종료 0. | 명령 정책의 로컬 단위 테스트만 해당. 실제 WhatsApp 메시지·게시 명령 발송하지 않음. |
| `docker compose -f wordpress/docker-compose.yml config --quiet` | `MYSQL_ROOT_PASSWORD`와 `MYSQL_PASSWORD`를 로컬 명령의 정적 `ci-placeholder`로 지정해 종료 0. | Compose 구성 파싱만, 서버·컨테이너·DB를 시작/교체하지 않았고 설정 원문·비밀값 출력하지 않음. |
| `git diff --check` | 종료 0. | 기존 변경 사항의 추적 파일 공백 검사. 작업트리의 여러 CRLF↔LF 경고는 출력됐으나 오류는 없음; 미추적 파일까지 검사한 결과는 아니다. Git add/commit/push 안 함. |
| `php -l` (로컬 PHP) | **미실행: 현재 PATH 및 일반 설치 위치에 PHP 실행 파일 없음.** | 다른 담당자의 `docs/legacy-layout-rollout-2026-09-22.md:45-50`에는 운영 측 PHP 표준입력 `php -l`, 23개 합성 검사, 실제 30편 포함 207개 계약 검사 통과가 기록돼 있으나 **이번 검증 담당자가 독립 실행하지는 않았다.** 서버를 호출하거나 PHP를 설치하지 않음. |

`#137`의 현재 CLI 상태도 별도로 재점검했다: `validate_bundle(..., require_review=False)` → `ready`, 이유 없음, 종료 0. 같은 준비 원고의 `editorial_cli.py check bundle.unreviewed.json --inventory public-only-inventory-excluding-137.json` → `needs_review`, 위 세 독립 검토 사유, 종료 **2**. 준비물 인벤토리는 공개 목록 29편만 담으므로 운영 갱신의 전체 상태 중복 검사 자료가 아니다. 콘텐츠 후보 #55/#79/#103의 보관된 `check-*.json`은 모두 `needs_review`; #55는 별도 `duplicate_topic`까지 보고한다.

## 바로 해결해야 하는 게이트와 변경 경계

1. #137: 정상 사전검사 통과 뒤 독립 의미 검토 6항목, 모든 숫자·날짜·문단·표·FAQ와 최신 공식 원문 재조회/해시, 전체 WordPress 상태 인벤토리 및 **원본 저장 본문** 해시 확인, 원본 백업, 글별 사람 승인, 모바일·접근성 점검을 마친 뒤에만 전용 `update-existing` 사용. 이번 검증은 이 작업을 진행하지 않았다.
2. #55/#79/#103과 #101: 콘텐츠 우선순위 문서의 공식 출처·직접 답변 결손을 각각 재검토한다. #103은 실제 목포 병원 목록을 확보하기 전 구체 기관명을 창작하면 안 되며, #101의 출처 불일치는 별도 원문 교차검증 후 수정한다. 후보 세 편의 기존 검사 보류 상태를 우회하지 않는다.
3. 공통 서식: MU CSS/목차의 운영 설치 여부 및 #85 표 후보를 **별도 승인·배포 절차**로 확인한다. 필터와 테마 충돌, 360/390px·200%·키보드·보조기술·실제 CSS 여백을 검증하고, 원본 HTML 교정과 CSS 가리기 효과를 구별한다.
4. 지속 감사: 유효한 사람 검증 레지스터·검토 주기·담당자·오류 시 알림/실패 복구 및 동시 업데이트 한계를 정한 뒤 스케줄을 별도 승인한다. 스크립트가 자동으로 게시물 수정이나 사실 검증을 완료했다고 표현하지 않는다.
5. 보관 Python 파일의 문법 오류는 발견 기록만 남긴다. 실제 실행 대상이 아닌 파일을 현재 범위에서 실행·수정하거나 위험한 과거 WordPress 편집 명령을 재활성화하지 않는다.

**검증자의 변경 범위:** 이 `docs/legacy-verification-2026-09-22.md` 신규 문서 하나. 기존 코드·스크립트·테스트·문서, Git, 스케줄러, 운영 서버 및 WordPress 게시물·설정은 변경하지 않았다. 다른 담당자가 동시 수정한 `test_article_layout.py`와 다른 작업 파일의 변경은 본 검증 작업에 귀속하지 않는다.

## 독립 검증 문서 작성 이후 갱신 — 12:51 KST

위 17·38·42행의 #137 의미 검토 보류는 **문서 최초 검사 시점**의 정확한 기록이다. 그 뒤 정확한 홈택스 조회 URL을 격리 Edge에서 실제 탐색해 HTML 조회 화면과 로그인 필요 안내를 확인했고(`docs/legacy-browser-qa-2026-09-22.md`), 그 브라우저 관찰과 미검증 경계를 #137 원고의 행동 링크 메타데이터에 연결했다. 다시 실행한 `editorial_cli.py review`는 6개 의미 검토 항목 모두 참·이슈 0건, `editorial_cli.py check bundle.reviewed.json`은 `ready`·종료 코드 0으로 통과했다. 증거는 `docs/pilot-post-137-preparation-2026-09-22.md`의 후속 기록과 Git 제외 `tmp/legacy_audit_20260922/pilot137/bundle.reviewed.json`, `bundle.reviewed.html`이다. **공개 WordPress 게시글을 수정하거나 실제 배포를 검증한 것은 아니다.** 전체 상태 인벤토리, DB 원본 해시, 원본 백업, 글별 사람 승인과 수정 후 모바일/접근성 검사는 여전히 필요하다.
