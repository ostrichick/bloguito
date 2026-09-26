# Bloguito 작업 흐름 최적화 — 2026-09-26

## 목적

사용자가 Bloguito 작업에서 Tailscale 연결 확인과 여러 검증 단계가 실제 작업보다 오래 걸리는 문제를 지적한 뒤, 프로젝트 전체 작업 흐름을 다시 점검해 확인한 10개 비효율을 한 번에 정리했다. 목표는 검증 수준을 낮추는 것이 아니라 **같은 실행 안에서 같은 사실을 여러 번 확인하는 중복을 제거**하는 것이다.

이 작업을 시작할 때 main 작업 트리에는 다른 게시물·관리자 UI·편집 정책 작업의 미커밋 변경이 이미 존재했다. 해당 변경은 되돌리거나 정리하지 않았고, 이 최적화와 직접 관련된 코드·지침만 추가·수정했다. 운영 WordPress 게시물, 서버 설정, cron, 공개 상태는 이 작업에서 변경하지 않는다.

## 적용한 10개 개선

| # | 기존 비효율 | 적용 결과 |
| --- | --- | --- |
| 1 | WSL/Tailscale 경로에서 WP 명령마다 `tailscale ping` 선행 | `update_existing_via_ssh.py`와 새 제한형 SSH transport는 **SSH를 먼저 시도**한다. SSH 연결 실패 코드 255 또는 실행 예외에서만 Tailscale을 한 번 진단한다. 원격 WP 명령 자체의 일반 오류는 Tailscale 장애로 오인하지 않는다. |
| 2 | `manual-review → check → publish` 과정에서 같은 AI 의미 검토 재호출 | `publish`는 이미 bundle에 결합된 의미 검토를 요구한다. Publisher의 잠금 안에서 최신 WP inventory와 `validate_bundle()`로 digest·policy·review 신선도를 검증하고, 같은 원고/정책에 대한 AI review를 다시 호출하지 않는다. review가 없거나 불일치·만료면 publish 전에 새 review가 필요하다. |
| 3 | 한 mutation의 시작과 종료에서 전체 WP inventory를 반복 다운로드 | mutation 시작의 최신 전체 inventory는 유지한다. 대상 글의 쓰기 직전/직후 `post get`도 유지한다. 성공 후에는 전체 목록을 즉시 다시 받는 대신 캐시를 **무효화**하고, 다음 독립 작업 또는 다음 자동화 후보가 실제로 inventory를 필요로 할 때 `ensure_inventory()`가 한 번 새로 동기화한다. |
| 4 | 사용자가 이미 현재 변경안 적용을 승인한 뒤에도 승인 전 비교 패키지를 다시 생성 | `AGENTS.md`와 `OPERATIONS.md`에서 `prepare_post_approval.py`를 **승인 전 비교가 실제로 필요한 단계**로 한정했다. 동일 변경안의 실제 적용 승인이 이미 있으면 정규 updater/reviser의 최신 inventory/source/CAS/백업/저장 후 검증을 바로 사용한다. |
| 5 | 로컬과 운영 서버에 편집 코드가 따로 있어 서버 버전 차이 때문에 재review | ChatGPT 수동 작업은 현재 로컬 checkout을 편집 코드의 정본으로 사용한다. 기존 공개 글은 `update_existing_via_ssh.py`, draft 생성·수정·승격 등은 새 `editorial_cli_via_ssh.py`가 로컬 정규 코드를 실행하면서 허용된 WP-CLI 명령만 SSH로 전달한다. 기존 서버에만 있던 reviewed draft manifest는 전환 시 한 번만 `sync_editorial_state_via_ssh.py`로 가져올 수 있으며 로컬 상태가 있으면 덮어쓰기를 거부한다. |
| 6 | 여러 동시 작업이 공통 policy/renderer를 바꿔 review digest가 중간에 무효화 | 공통 정책·renderer·validator 변경은 충돌 가능성이 있으면 전용 Git worktree에서 격리하고, 콘텐츠 적용과 공통 정책 변경을 동시에 진행하지 않는 규칙을 `AGENTS.md`/`OPERATIONS.md`에 추가했다. 로컬 정본 SSH 경로도 서버 checkout의 임의 변경 때문에 같은 원고를 재review하던 원인을 줄인다. |
| 7 | 작은 문구/데이터 변경에도 전체 Python suite 반복 | 변경 범위별 테스트 단계를 명시했다. 문서 변경은 문서 검사, 원고 변경은 bundle/글별 검사, 좁은 parser는 표적 테스트, renderer/validator/publisher/policy 같은 공통 코드는 표적 테스트 뒤 전체 suite를 **한 번** 실행한다. 이후 공통 코드가 바뀌지 않았다면 전체 suite를 반복하지 않는다. |
| 8 | 모든 글 수정에 360/390/desktop/200%/키보드 QA를 동일하게 반복 | CSS·renderer·표/목차 구조 변경은 전체 레이아웃/접근성 QA를 유지한다. HTML 구조가 같은 데이터·문구 수정은 대표 모바일 1개+데스크톱 1개, CTA 목적지만 바뀌면 실제 도착 화면+버튼 smoke test를 우선하도록 `EDITORIAL_SYSTEM.md`에 반영했다. 표 열/행 구조가 바뀌면 전체 표 접근성 검사를 계속 요구한다. |
| 9 | 같은 에이전트가 변경되지 않은 40KB 편집 규약을 후속 작업마다 처음부터 재독 | 같은 세션/작업에서 `EDITORIAL_SYSTEM.md`와 `editorial_policy.json`이 바뀌지 않았다면 이미 읽은 내용을 재사용한다. 새 worker는 최초 1회 읽고, 정책 파일이 실제로 바뀌었을 때만 다시 읽도록 공통 지침에 명시했다. |
| 10 | 같은 게시물의 작은 후속 수정마다 별도 MD를 만들어 기록 분산 | 같은 게시물·기능의 기존 작업 기록이 있으면 그 문서의 새 날짜/절에 후속 이력을 추가한다. 새 기능·독립 장애·배포·아키텍처 변경만 새 MD를 만든다. 이 문서는 이번 독립 워크플로 아키텍처 변경의 기준 기록이며 후속 최적화는 여기에 이어 기록한다. |

## 유지한 안전 경계

다음 검사는 비용이 있어도 역할이 서로 달라 제거하지 않았다.

- 실제 쓰기 작업 시작 시 최신 정상 상태 전체 WordPress inventory 1회
- 기존 글 수정의 쓰기 직전 대상 `post get`과 예상 본문 SHA 비교(CAS)
- 기존 공개 글/draft updater의 적용 직전 공식 source 재조회와 저장된 source SHA 비교
- 원본 전체 백업
- 저장 직후 대상 `post get`과 상태·제목·slug·본문/발췌문 검증
- `draft → publish`의 명시적 사용자 승인과 공개 직전 공식 source 재검증
- 원고·정책·source·review digest 또는 신선도가 실제로 달라진 경우 새 의미 검토

따라서 “빠르게 만들기 위해 검사를 건너뛴다”는 변경은 포함하지 않는다.

## 새 로컬 정본 원격 실행 경로

`scripts/editorial_cli_via_ssh.py`는 일반 SSH 셸이 아니다. 현재 action과 대상 ID에서 정규 편집 코드가 필요로 하는 WP-CLI 명령만 허용한다. 다른 게시물 ID, 임의 `wp option`, 임의 update 필드 등은 transport 단계에서 거부한다. 신규 draft는 `post_status=draft`만 허용하며 생성된 ID를 읽은 뒤 그 ID에 대한 저장 검증·SEO meta·permalink 명령만 추가로 허용한다.

기존 공개 글의 `update-existing`은 HTML/제목/발췌문 허용 범위가 별도로 좁게 구현된 기존 `scripts/update_existing_via_ssh.py`를 계속 사용한다.

운영 예약 자동화(cron)의 `main.py`는 운영 서버에서 실행되는 별도 경로다. 이번 “로컬 정본 + 원격 WP transport” 전환은 **ChatGPT 수동 작업 경로**에 적용하며, 서버 cron 자체의 배포 구조를 없앤 것은 아니다.

## 검증

변경 중 표적 테스트를 먼저 실행했다.

- 원격 transport, inventory lifecycle, publish review 재사용, updater/draft reviser/action destination/publisher 안전 경로: 42건 통과
- 공통 editorial, draft category, legacy draft 예외, #225 정책: 43건 통과
- 원격 transport와 공통 editorial 재검증: 56건 통과
- 범용 editorial SSH transport, 기존 public updater transport, publish/inventory 경로: 23건 통과
- 최종 Tailscale 진단 범위 축소 후 remote transport 집중 테스트: 12건 통과
- 수정 Python 파일 `py_compile`: 통과
- `git diff --check`: 통과(Windows LF/CRLF 변환 예정 경고만 존재)
- 기존 main 작업트리에서 최종 전체 `python -m unittest discover -s agent-publisher/tests -q`: **453 tests, OK (skipped=1)**, 종료 0. 이 작업트리에는 다른 동시 작업의 아직 미커밋된 편집 정책·테스트 수정도 함께 존재하므로, 이 결과를 이번 커밋만의 독립 회귀 결과로 표현하지 않는다. 출력의 `simulated transfer interruption`은 백업 전송 실패를 의도적으로 주입하는 기존 테스트의 로그이며 전체 suite 실패가 아니다.
- 최신 `origin/main`(`0775323`) 위에 이번 커밋만 cherry-pick한 clean 통합 worktree에서는 전체 suite가 **421 tests, 1 failure, 1 skipped**였다. 유일한 실패는 기존 `test_legacy_85_welfare_navigation...test_exact_85_timeline_exception_full_bundle_ready_without_review`이며 `reader_middle_dot_disallowed` 때문에 발생했다. 같은 테스트를 **이번 커밋이 없는 `origin/main` 원본에서 단독 실행해도 동일하게 실패**했으므로 이번 최적화가 만든 회귀가 아니다. 이번 커밋의 transport/publish/inventory/updater 표적 테스트 **43건은 clean 통합 worktree에서도 모두 통과**했다.

위 표적 실행들은 일부 테스트가 서로 겹치므로 숫자를 합산해 고유 테스트 수처럼 표현하지 않는다. 전체 suite 재실행은 첫 작업트리 검증과 원격 main 통합 검증이라는 서로 다른 상태를 확인하기 위해 각각 한 번 수행했으며, 동일 상태에서 반복 실행하지 않았다.

## 운영 반영 경계

이 작업은 로컬 프로젝트 코드와 공통 지침을 최적화한다. 운영 WordPress 콘텐츠나 공개 상태를 변경하는 작업이 아니므로 게시물 쓰기와 공개 승격은 수행하지 않는다. `sync_editorial_state_via_ssh.py`도 기존 서버 draft 상태를 실제 로컬 정본으로 가져와야 하는 첫 draft 작업 시 한 번 실행하는 전환 도구이며, 이번 코드 검증 자체를 위해 운영 상태를 임의로 복사하지 않는다.
