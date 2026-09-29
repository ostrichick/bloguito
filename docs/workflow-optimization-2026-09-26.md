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

## 2026-09-26 후속 설계: reviewed draft 빠른 수정 경로

### 문제

#465 후속 편집에서 사용자가 요청한 작업은 일정표와 시작시간 표의 통합, 근거가 확실한 문장의 자연스러운 단정형 수정, 중복 FAQ 삭제였다. 그러나 기존 `revise-draft` 경로는 모든 본문 변경을 동일하게 취급해 전체 WordPress inventory 동기화, 전체 bundle 의미 검토, 모든 공식 source 재수집을 요구했다. 검토 과정에서 이번 변경과 무관한 기존 제목·관련 글 문제까지 blocking issue가 되어 draft reviser와 SSH transport 코드 수정, 전체 회귀 테스트까지 작업 범위가 확대됐다.

빠른 경로의 목표는 검사를 생략하는 것이 아니라 **변하지 않았음을 구조적으로 증명한 범위를 다시 검사하지 않는 것**이다. 사용자가 작은 편집을 요청했을 때 시스템이 스스로 제목·공통 validator·SSH 계층까지 작업 범위를 확대하지 않아야 한다.

### v1 범위

첫 구현은 이미 독립 검토를 통과한 **WordPress draft**만 대상으로 한다. 공개 글은 현재 `update-existing` 전체 검토 경로를 유지하고, draft 빠른 경로의 운영 경험과 회귀 데이터가 쌓인 뒤 별도 단계로 검토한다.

빠른 경로 후보 명령은 `fast-revise-draft`로 둔다. 최종 CLI 이름은 구현 시 정할 수 있지만, 기존 `revise-draft`와 역할을 혼합해 자동으로 검증 수준을 낮추지 않는다.

### 빠른 경로 진입 조건

아래 조건을 모두 만족할 때만 fast path를 허용한다.

1. 대상이 현재 `draft`이고 로컬 `draft_posts.json`에 기존 reviewed `editorial_bundle`이 정확히 1건 존재한다.
2. 현재 WordPress 본문 SHA256이 호출자가 제시한 원본 SHA와 일치한다.
3. `brief` 전체, `temporal_source`, source URL/text/SHA/type, CTA actions, `official_navigation`, 제목, `related_posts`가 기존 reviewed bundle과 동일하다.
4. 새 원고에서 사용하는 모든 evidence `(source_id, quote)`가 기존 reviewed bundle에서 이미 사용된 evidence 집합의 부분집합이다. 새 공식 사실이나 새 인용을 fast path에서 도입하지 않는다.
5. 새 reader-visible 숫자·날짜·금액·지역·시간 토큰이 기존 reviewed 원고에 없던 값으로 추가되지 않는다. 기존 값을 표/문단 사이에서 이동하는 것은 허용한다.
6. 기존 독립 의미 검토와 정책 fingerprint가 여전히 유효하고 만료되지 않았다. 정책 파일이 바뀌었거나 기존 review가 stale이면 전체 검토로 승격한다.
7. 결정론 검사를 거친 뒤 모든 `reader_questions`가 계속 답변되고, 근거 없는 수치·금지문구·일정 바인딩 오류가 없다.

다음 변경은 v1 fast path에서 허용한다.

- 기존 사실을 유지한 표 합치기/나누기, 열 재배치, 행 재배치
- 이미 검토된 근거 범위 안에서 문장 표현을 자연스럽게 다듬기
- 같은 사실을 반복하는 문단·FAQ 삭제
- 소제목·caption·표 머리글의 의미 보존형 문구 수정
- 같은 reviewed evidence를 표와 문단 사이에서 재배치

다음 중 하나라도 있으면 **자동으로 고치거나 범위를 확대하지 않고** `FULL_REVIEW_REQUIRED`와 정확한 이유를 반환한다.

- 제목 변경
- brief/검색질문/적용 연도·지역·대상 변경
- source URL, source text/SHA, evidence quote 추가 또는 교체
- CTA 추가·삭제·목적지 변경
- `related_posts` 추가·교체
- 새로운 숫자·날짜·금액·공연장·지역·조건 추가
- 새 reader question 추가
- 판매상태·자격·신청 가능 여부처럼 의미상 위험도가 높은 새 주장
- 정책 fingerprint 변경 또는 기존 review 만료

이 경계가 중요하다. 예를 들어 #465의 표 병합·`130분입니다` 표현·중복 FAQ 삭제는 fast path 대상이지만, 독립 검토가 우연히 발견한 기존 제목 문제를 같은 작업에서 제목 수정으로 확대하면 fast path를 벗어난다. 그 제목 문제는 별도 개선 제안으로 남기거나 사용자가 범위를 넓혔을 때 전체 검토 작업으로 처리한다.

### delta 의미 검토

문장 표현이 실제로 바뀌는 작업에는 전체 글 의미 검토 대신 **변경 블록만** 검토한다. reviewer 입력은 다음으로 제한한다.

- 변경 전 블록
- 변경 후 블록
- 두 블록에 연결된 기존 evidence quote
- 사용자의 이번 수정 의도

검토 항목은 `meaning_preserved`, `evidence_still_supports`, `conditions_preserved`, `no_new_claims`, `reader_task_preserved`로 제한한다. reviewer에게 제목·다른 섹션·관련 글처럼 변경 범위 밖의 품질 개선을 찾도록 요청하지 않는다. 범위 밖에서 발견한 사항이 있더라도 mutation을 막는 issue로 승격하지 않는다.

새 bundle에는 전체 review를 위조하지 않고 별도 `fast_edit_review` 기록을 남긴다. 최소 필드는 다음과 같다.

```json
{
  "mode": "delta",
  "base_review_digest": "...",
  "base_policy_digest": "...",
  "delta_digest": "...",
  "checks": {
    "meaning_preserved": true,
    "evidence_still_supports": true,
    "conditions_preserved": true,
    "no_new_claims": true,
    "reader_task_preserved": true
  },
  "issues": [],
  "checked_at": "..."
}
```

향후 `promote-draft`가 composite review를 인정할지는 별도 구현 결정이다. v1에서는 fast-edited draft를 실제 공개하려는 시점에 기존 공개 전 검증 정책에 따라 full review를 요구해도 된다. fast path의 우선 목표는 반복 편집 중의 불필요한 전체 검토를 제거하는 것이다.

### 결정론 검사 분리

현재 `validate_bundle()`은 duplicate topic, related-post 실재 여부처럼 **전체 inventory가 필요한 검사**와 문단 근거·수치·표 구조·일정 바인딩처럼 **원고 자체만으로 확인 가능한 검사**를 한 함수에서 수행한다. fast path에서는 `validate_fast_edit(old_bundle, new_bundle)` 또는 동등한 scope-aware 검사를 둔다.

fast validator는 다음을 계속 검사한다.

- evidence quote가 source snapshot 안에 실제 존재하는지
- 숫자·날짜·금액 근거
- 표 header/cell 구조와 schedule binding
- reader question coverage
- 금지 문구·raw HTML/URL
- action/navigation/related/title이 baseline과 불변인지
- 새 factual token이 생기지 않았는지

반면 아래 검사는 baseline과 동일함이 증명되면 반복하지 않는다.

- 전체 WordPress 중복 주제 검색
- unchanged related post의 현재 존재 여부
- unchanged CTA 목적지 전체 재검증
- 변경하지 않은 문단의 의미 재검토

### source 재검증

v1은 source 자체가 바뀌지 않는 편집만 허용한다. source snapshot이 정책의 `source_max_age_hours` 안에 있고 기존 review도 유효하면 **모든 공식 URL을 다시 받지 않는다**.

문구가 바뀐 블록의 evidence source가 최신성 경계에 가까운 경우에는 해당 source ID만 선택적으로 재조회할 수 있도록 `fetch_sources_subset()` 같은 좁은 인터페이스를 추가한다. source가 바뀌었거나 SHA가 달라지면 fast path는 즉시 중단하고 full review로 승격한다. 전체 source set을 fast path 안에서 자동 교체하지 않는다.

### WordPress 원격 왕복 축소

fast path는 brief·중복·related link 구성이 변하지 않으므로 전체 WordPress inventory 약 1MB를 다시 받을 필요가 없다. 원격 호출은 대상 글 하나로 제한한다.

1. `wp post get <ID>`로 `post_status, post_title, post_name, post_content, post_excerpt`만 읽는다.
2. 상태·제목·slug·현재 content SHA를 baseline과 비교한다.
3. 원본 대상 글 JSON과 local draft index를 백업한다.
4. `post_content`와 필요할 때 `post_excerpt`만 갱신한다.
5. 같은 필드만 다시 읽어 저장 결과를 검증한다.

전체 inventory가 필요한 조건이 생기면 fast path에서 inventory를 받기 시작하지 않고 full path로 승격한다.

### SSH/Tailscale 처리

콘텐츠 수정 중 transport 코드를 즉석에서 변경하지 않는다. Bloguito 서버의 일반 수동 편집 transport는 Direct SSH를 기본으로 고정한다. Tailscale은 Direct SSH로 처리할 수 없는 비상·복구·사설 관리 작업에서만 일회성으로 명시 선택하며, `BLOGUITO_SSH_MODE=tailscale` 같은 지속 설정을 일반 콘텐츠 작업의 정본으로 두지 않는다.

fast mutation의 연결 정책은 다음처럼 단순하게 둔다.

1. Direct SSH로 대상 `post get`을 시도한다.
2. 실패해도 공개 REST/웹 조회로 목적을 달성할 수 있으면 그 경로를 사용하고 Tailscale로 전환하지 않는다.
3. 서버 내부 명령이 반드시 필요한 작업에서만 Tailscale을 명시적으로 선택하고, 실패 시 `tailscale ping -c 1`로 한 번 진단한다.
4. 같은 mutation은 멱등성이 확인된 경우에만 최대 한 번 재시도한다.
5. 두 번째 실패에서는 `transport_unavailable`로 종료하고 WordPress 변경을 시도하지 않는다.

콘텐츠 작업 도중 일반 SSH↔Tailscale 전환 기능을 새로 구현하거나 companion/browser 재연결을 반복하지 않는다. transport 개선은 별도 인프라 작업으로 분리한다.

#### 2026-09-27 후속 변경

사용자 요청에 따라 `agents/remote_transport_config.py`의 일반 해석 규칙을 Direct SSH 우선으로 강화했다. 지속 환경설정에 `BLOGUITO_SSH_MODE=tailscale`과 Tailscale용 host/user/WSL 값이 남아 있어도 CLI에서 transport를 명시하지 않은 일반 호출은 `direct` + `bloguito` 별칭을 사용한다. Tailscale 설정값은 `--ssh-mode tailscale`처럼 예외 경로를 명시적으로 선택했을 때만 재사용한다.

2026-09-28 후속 보안 작업에서 운영 서버의 SSH 방화벽도 Direct 우선 정책에 맞췄다. `bloguito-ssh-private-only.service`는 전용 `BLOGUITO_SSH` 체인에서 승인된 운영자 IPv4 `/32`와 `tailscale0`만 허용하고 나머지 신규 TCP/22를 DROP한다. `ssh bloguito`는 Windows에서 `wordpress-blog` / `ubuntu` 실제 로그인까지 성공했으며 Tailscale 경로도 비상 접속으로 유지된다. 공인 IP가 바뀌면 Tailscale으로 접속해 서버의 비공개 source CIDR을 갱신한다. OCI Security List/NSG source 범위는 서버 Instance Principal에 조회 권한이 없어 콘솔 확인이 별도로 남아 있다.

### 향후 작업에서의 테스트 정책

fast path **기능 자체를 처음 구현할 때**는 공통 검증 코드가 바뀌므로 다음을 수행한다.

- fast edit classifier 단위 테스트
- delta review scope 테스트
- schedule/table 재배치 회귀 테스트
- CAS/backup/save verification 테스트
- 단일 대상 SSH transport 테스트
- 표적 테스트 통과 후 전체 `agent-publisher/tests` 1회

기능이 안정화된 뒤 **개별 콘텐츠 수정**에서는 전체 suite를 다시 실행하지 않는다.

- candidate fast-edit classification
- fast deterministic check
- 필요한 경우 delta semantic review 1회
- 대상 글 CAS + 저장 후 검증
- 표 구조가 바뀐 경우 해당 표 렌더/접근성 smoke test
- CTA가 바뀌지 않았다면 CTA 도착 URL 재검사는 생략

### 기대되는 #465 같은 작업 흐름

```text
현재 draft + manifest 확인
        ↓
사용자 요청 범위만 candidate에 반영
        ↓
fast classifier
  brief/source/title/CTA/related 불변 확인
        ↓
changed blocks만 delta review
        ↓
fast deterministic check
        ↓
대상 post get + SHA CAS
        ↓
backup → update → post get 검증
```

이 흐름에서는 공통 validator를 작업 도중 수정하지 않고, 전체 inventory를 받지 않고, 전체 source set을 재수집하지 않고, 전체 article semantic review를 하지 않으며, 전체 Python suite도 실행하지 않는다. fast classifier가 거부하면 그 시점에서 멈추고 full review가 필요한 이유만 보고한다.

### 구현 순서

1. `fast_edit.py`에 baseline/new bundle diff classifier와 fast deterministic validator를 추가한다.
2. 기존 reviewer adapter에 changed-block 전용 delta review 입력/결과 스키마를 추가한다.
3. `fast-revise-draft` updater를 대상 단일 `post get` 기반 CAS/backup/save 경로로 구현한다.
4. `editorial_cli.py`와 제한형 SSH adapter에 해당 action만 추가한다.
5. Tailscale transport 선택을 작업 중 추론이 아니라 프로젝트 설정으로 고정한다.
6. 표적 테스트 후 전체 suite 1회, 실제 reviewed test draft에서 dry-run/classification을 검증한다.
7. 운영 경험이 충분히 쌓인 뒤 public post용 fast path를 별도로 검토한다.

## 2026-09-26 후속 구현: 1~7단계 효율화

사용자 요청에 따라 위 설계를 실제 코드로 확장했다. 이번 변경은 운영 WordPress 글을 수정하거나 공개하는 작업이 아니라 로컬 편집·검증 경로 자체의 개선이다.

1. `agents/workflow_metrics.py`를 추가해 CLI 전체 `total_ms`, inventory/source/semantic-review 단계 시간, WordPress/source 요청 횟수를 Git 제외 runtime JSONL에 기록한다.
2. `fast-revise-draft`를 구현했다. 기존 reviewed draft의 brief/source/CTA/title/related/navigation 불변, 기존 evidence 부분집합, 새 수치·시간·지역형 token과 새 고위험 상태 주장 부재를 먼저 검사한다. 통과 시 변경 블록만 delta semantic review하고 대상 글 `get → update → get`으로 저장한다. fast-edited bundle에는 기존 full review와 별도의 `fast_edit_review`를 함께 보존하므로 기존 `promote-draft`는 full review digest가 다시 맞기 전에는 그대로 공개를 차단한다.
3. `validate_bundle()`을 scope-aware하게 만들어 `validate_content`, `validate_sources`, `validate_site_context`, `validate_review_binding`을 독립 호출할 수 있게 했다. 기본 호출은 네 scope를 모두 사용해 기존 full validation 계약을 유지한다.
4. 전체 `fetch_sources()`는 최대 4개 URL을 제한 병렬 조회하고 선언 순서와 `s0...` ID를 보존한다. `fetch_sources_subset()`은 선택한 source ID만 재조회하며 기존 actions/citation metadata를 유지한다.
5. `agents/remote_transport_config.py`로 `BLOGUITO_SSH_MODE/HOST/USER/WSL_DISTRO` 기본 transport 설정을 중앙화했다. 기존 CLI 옵션은 override로 유지한다.
6. `agents/wordpress_mutation.py`에 `get_post`, `update_post`, `verify_cas`, `backup_json`, `verify_saved_fields`를 추출해 public updater, draft reviser, fast-edit가 같은 mutation primitive를 사용한다.
7. WordPress inventory를 schema v2의 `ID/post_title/post_status/content_sha256/content_urls`로 경량화했다. 신규 글 중복은 URL signature로 판정하고, 기존 글 수정에서 동일 URL 후보만 읽기 전용 단건 `post get`으로 hydrate해 기존 source-footer 예외 판정을 유지한다. SSH transport는 inventory로 관측한 후보 ID를 읽을 수만 있고 update 대상 ID에는 추가하지 않는다.

단계별 표적 검증을 각각 완료한 뒤 공통 변경이 모두 끝난 상태에서 전체 Python suite를 실행했다. 첫 전체 실행은 `publisher.reformat_draft()`의 새 `hydrate_post` 로컬 import 누락 1개 원인으로 2개 테스트가 실패했고, import를 수정한 뒤 최종 재실행은 **486 tests, OK (skipped=1)**였다. 변경 Python 파일 `py_compile`과 `git diff --check`도 통과했다. 테스트 출력의 `simulated transfer interruption`은 기존 백업 실패 주입 테스트의 의도된 로그다. 현재 main 작업 트리에는 이 작업 이전부터 다른 게시물·관리자 UI·보안·복구 작업의 미커밋 변경이 함께 있어, 관련 없는 변경을 커밋에 섞지 않기 위해 이 후속 구현에서는 자동 commit/push를 수행하지 않았다.

### 2026-09-26 fast-edit 최종 보강

실제 #465 reviewed manifest를 mutation 없이 dry-run한 결과를 바탕으로 fast path의 경계를 한 번 더 좁혔다.

- delta semantic review는 문단과 표 행뿐 아니라 **섹션 제목, 표 caption/headers, FAQ 질문**의 변경도 별도 scope로 전달한다. 표를 합치거나 머리글을 바꿨는데 reviewer가 구조 문자열을 보지 못하는 사각지대를 제거했다.
- `fast-revise-draft`는 `--edit-intent`를 필수로 받아 이번 사용자 요청 범위를 delta reviewer에게 전달한다. reviewer는 변경 블록과 기존 evidence, edit intent만 보고 범위 밖의 제목/관련 글 개선점을 blocking issue로 만들지 않는다.
- 대상 WordPress 조회는 `post_status,post_title,post_name,post_content,post_excerpt` 다섯 필드만 `post get`으로 읽고 `get → update → get` 3회 왕복을 유지한다. 전체 inventory는 fast path에서 받지 않는다.
- SSH exit 255는 읽기 명령과 `fast-revise-draft`의 멱등 update만 진단 후 **1회** 재시도한다. `post create`는 응답 유실 뒤 중복 draft가 생길 수 있으므로 자동 재시도하지 않는다.
- 새 사실 token의 지역/공연장 감지는 공식 source snapshot에 실제 등장하는 후보와 주요 광역 지역명을 중심으로 제한했다. 이전 정규식은 `정리`의 `리`, `당시`의 `시` 같은 일반 한국어를 행정구역 suffix로 오인할 수 있었다.
- 실제 #465 bundle dry-run에서 `한눈에 보기 → 정리` 소제목 변경은 `candidate`, 제목 변경은 `FULL_REVIEW_REQUIRED(title_changed)`로 분리되는 것을 확인했다. WordPress에는 이 검증 과정에서 쓰기를 수행하지 않았다.

최종 보강 후 `test_fast_edit.py` 13건, `test_editorial_cli_via_ssh_transport.py` 13건이 통과했고, 변경 Python 파일 `py_compile`, `git diff --check`, 전체 `agent-publisher/tests` **501 tests, OK (skipped=1)**를 확인했다. 전체 suite는 마지막 classifier 수정 뒤 최종 상태에서 1회 재실행했다.

## 2026-09-26 글쓰기·수정 프로세스 재점검

사용자 요청: 블로그의 글쓰기·수정 절차를 간단히 설명하고 쉽게 최적화할 부분을 확인한다. 이번 작업은 현행 문서와 로컬 구현을 확인한 읽기 중심 점검이다. 운영 SSH·WordPress 변경·공개·서버 배포는 수행하지 않았다. 기존 `main.py` 수정 및 미추적 작업 파일은 보존했다.

### 사용자에게 설명할 기본 흐름

1. 요청을 새 글, 기존 글의 사실/근거 변경, 검토된 임시글의 표현 정리로 구분하고 대상과 공개 상태를 확인한다.
2. 새 글과 사실 변경은 중복·공식 근거·정보 유효기간을 확인한 뒤 근거가 연결된 구조화 원고를 작성한다.
3. 독립 의미 검토와 CLI 규칙 검사를 수행한다. 유효한 동일 원고·정책의 의미 검토는 등록 단계에서 다시 호출하지 않는다.
4. 새 글은 임시글로 등록한다. 기존 글 수정은 승인 범위 안에서 원본 일치 확인·백업·저장 후 재조회로 검증한다. 공개 전환은 글별 명시적 요청에 따라 별도 경로로 수행한다.
5. 변경 범위에 맞춘 화면 확인을 수행하고 결과·보류 이유·미검증 범위를 기존 관련 MD에 기록한다.

작업 시작 설명은 “이번 작업은 [새 글/내용 변경/표현 정리]이며, [근거 확인 범위] → [검토 범위] → [임시글 저장/승인된 글 수정] → 결과 확인 순서로 진행합니다” 수준으로 짧게 한다. 작업 종료에는 대상 글·변경 내용·공개 상태·검증 범위를 전달한다.

### 확인한 최적화와 제약

- 이미 로컬 구현됨: 동일 검토 재사용, 대상 한 글만 조회하는 `fast-revise-draft`, 변경 블록 의미 검토, 공식 출처 최대 4개 동시 조회, 경량 inventory, 단계별 시간/호출 수 기록. 실제 운영 성능이나 서버 자동화 적용 여부는 이번 점검으로 검증하지 않았다.
- 즉시 적용 가능한 운영 개선: 시작 시 수정 범위를 분류하고, 같은 글의 표현 정리 요청을 한 후보 원고에 모아 한 번 검토·저장한다. 제목/숫자/날짜/출처/CTA 변경은 전체 검토 경로로 구분한다. 검토와 check에는 같은 실행에서 얻은 inventory를 재사용할 수 있으나 실제 등록·일반 갱신의 최신 inventory와 저장 직전 원본 검사는 유지한다.
- 지침에 이미 있음: 같은 실행 안의 정책 재독해, 동일 변경안 승인 후 비교 패키지 재생성, 불필요한 Tailscale 선행 진단, 작은 콘텐츠 수정의 전체 코드 테스트 반복을 생략한다. 화면 구조 변경은 전체 접근성 QA를 유지한다.
- 새로 확인한 제약: fast 수정 저장은 기존 full review를 보존하지만 plan은 바뀐다. 다음 fast 수정의 baseline 검증은 이 full review와 현재 plan의 결합을 요구하므로 재검토를 요구한다. 테스트용 `sample()`과 고정 `NOW`로 소제목을 두 번 바꾸는 무변경 검증을 실행했고, 첫 번째는 `candidate`, 두 번째는 `FULL_REVIEW_REQUIRED` 및 `base_review_not_current`, `review_not_bound_to_current_content`를 반환했다. API·SSH·WordPress 쓰기는 실행하지 않았다.
- 간단한 대응은 표현 수정을 한 번에 묶는 것이다. 연속 fast 수정을 허용하는 누적 검토 연결 구현은 별도 코드 변경·회귀 검증이 필요한 후속 개선이며 이번에는 구현하지 않았다. 공개 글의 빠른 수정도 현재 기능으로 주장하지 않는다.
- 기존 workflow metrics는 존재하지만 실행 출처와 대표성이 확인되지 않아 운영 소요 시간·절감률의 근거로 쓰지 않았다. 실제 새 글/내용 변경/표현 정리 작업의 단계별 측정을 먼저 비교하는 것이 후속 성능 개선의 기준이다.

검증: 현행 편집/운영 문서·정책과 CLI/writer/fast-edit/metrics 소스를 확인했고 연속 fast 수정 제약을 로컬 샘플로 재현했다. 이번 문서 추가 외 코드·정책 변경은 없으며 전체 Python suite는 반복하지 않았다.

### 후속: 세 가지 최적화 실행 규칙 적용

사용자가 위 세 가지 최적화의 적용을 요청했다. 기존 코드가 경로별 검토·저장을 이미 지원하므로 새 자동 분류기나 연속 fast 수정 기능을 추가하지 않고, `AGENTS.md`의 기본 행동 규칙과 `OPERATIONS.md`의 구체적인 경로 선택·묶음 처리·재사용 조건에 반영했다. 시작 시 짧은 진행 설명, 같은 글의 승인된 수정 묶음, 저장 전 추가 요청 합치기, 저장 후 원본 재확인, 검토/목록/정책 재사용 조건, fast 경로 거부 시 전체 검토 전환과 종료 보고를 명시했다.

편집 규범 `EDITORIAL_SYSTEM.md`와 `editorial_policy.json`, 실행 코드는 변경하지 않아 이번 문서 반영 때문에 기존 review fingerprint를 바꾸지 않는다. 실제 글·운영 서버 변경은 없다. 문서 diff와 정본 연결을 확인하며 전체 Python suite는 문서 변경에 불필요하므로 실행하지 않는다. 의도한 문서 세 개만 Git에 반영하고 다른 미커밋 작업은 보존한다.

## 2026-09-28 신규 draft 원클릭 Fast 경로

사용자 피드백에서 Antigravity 대비 Chat On Steroids 신규 글 작성 시간이 과도하게 길어진 핵심 원인이 개별 안전장치 자체보다 `manual-review → check → 대표 이미지 생성/검수 → publish → catalog sync`를 에이전트가 여러 차례 도구 왕복으로 실행하는 구조임을 확인했다. 기존 9/26 최적화로 source 병렬 수집, 경량 inventory, 동일 review 재사용, fast-edit는 이미 구현돼 있었으므로 이번 변경은 **일반 신규 draft의 후반부 오케스트레이션만 합치는 것**에 한정했다.

`editorial_cli.py prepare-draft`를 추가했다. 구조화 bundle의 content/source 결정론 preflight는 WordPress inventory 없이 로컬에서 실행한다. preflight가 통과하면 현재 review가 없을 때 `EditorialWriterAgent(writing_enabled=False)` 의미 검토와 `DesignerAgent` 대표 이미지 생성·비전 검수를 최대 2개 worker thread에서 병렬 실행한다. bundle에 현행 content/policy에 결합된 current review가 있으면 reviewer를 다시 호출하지 않는다. 두 작업 뒤 content/source/review binding을 로컬에서 다시 확인하고 bundle과 HTML preview를 저장한다.

실제 WordPress 쓰기는 기존 `PublisherAgent.publish()`를 그대로 사용한다. Publisher가 잠금 안에서 lightweight inventory를 한 번 새로 받아 site 중복·관련 글·review binding을 포함한 full validation을 수행하므로, Fast 경로가 별도의 사전 inventory와 `check`를 반복하지 않아도 저장 직전 안전 검사는 유지된다. `--image-path`가 없으면 현행 v2 대표 이미지 정책으로 자동 생성하고, 이미 검수한 로컬 jpg/jpeg/png/webp가 있으면 그 경로를 그대로 사용할 수 있다. `scripts/editorial_cli_via_ssh.py` allowlist도 `prepare-draft`의 draft create, Rank Math 3개 메타, 생성된 post ID에 한정된 featured-image import만 허용하도록 확장했다.

SSH adapter에서 `prepare-draft`가 성공하면 `scripts/sync_post_catalog.py`를 별도 Direct SSH 읽기 경로로 자동 실행한다. 동기화는 한 번 실패하면 1회만 재시도한다. 두 번 모두 실패해도 이미 생성된 WordPress draft를 다시 만들지 않도록 전체 명령을 재실행하라는 오류로 처리하지 않고, `sync_post_catalog.py`만 별도로 재실행하라는 경고를 출력한다. 이는 post create 응답 이후의 비멱등 재시도로 중복 draft가 생기는 것을 막기 위한 경계다.

운영 경로는 세 수준으로 정리했다. 일반 신규 draft는 Fast `prepare-draft`, 기존 draft/public 글 수정은 현행 updater/reviser를 사용하는 Standard 경로, 정책 예외·출처 충돌·공통 코드/정책 변경처럼 단계별 원인 진단이 필요한 작업은 기존 `manual-review/review → check → publish`를 분리하는 Strict 경로다. Fast는 검증을 생략하는 모드가 아니라 동일 안전 검사를 한 프로세스 안에서 재사용·병렬화하는 모드다.

검증은 `test_prepare_draft_fast_path.py`, `test_editorial_cli_via_ssh_transport.py`, 기존 `test_publish_flow_efficiency.py`, `test_post_catalog.py`, 대표 이미지 safety/routing, workflow metrics를 묶어 66건 통과한 뒤 전체 `agent-publisher/tests`를 한 번 실행했다. 최종 결과는 **601 tests, OK**였고 변경 Python 파일 `py_compile`과 `git diff --check`도 통과했다. 테스트의 `simulated transfer interruption`, 이미지 API unavailable 폴백, catalog sync 실패 경고는 각각 기존 실패 주입/폴백 및 새 재시도 경계를 검증하는 의도된 출력이다. 이번 최적화 검증에서는 실제 WordPress draft를 만들거나 운영 글을 변경하지 않았다. 실제 신규 글 한 편의 wall-clock 절감률은 다음 실사용 `workflow-metrics.jsonl`에서 `semantic_review`, `cover_generation`, `inventory_sync`, `total_ms`를 비교해 확인한다.

## 2026-09-29 P0 기존 글 수정 지연 개선

대전 행사 draft #641 후속 작업에서 대표이미지 교체와 제한된 내용 수정이 전체 source/review/revision 경로로 여러 번 확대되어 wall-clock이 비정상적으로 길어진 사례를 기준으로 P0를 구현했다. 목표는 안전장치를 제거하는 것이 아니라 **작은 변경이 기본적으로 작은 경로를 타고, 변경되지 않은 검증은 코드가 재사용하도록 만드는 것**이다.

- `edit-draft`를 기존 reviewed draft 수정의 기본 상위 진입점으로 추가했다. 저장된 reviewed bundle과 후보 bundle을 먼저 로컬에서 비교하고, 기존 `fast_edit.validate_fast_edit()`가 허용하면 `fast-revise-draft`의 target-only CAS/delta-review 경로를 사용한다. 새 사실·숫자·날짜·출처·CTA·제목·정책 변화나 검토 만료가 있으면 기존 `revise-draft` Standard 경로로 자동 전환한다.
- `replace-featured-image`를 추가했다. 본문 bundle이나 전체 inventory를 열지 않고 현재 본문 SHA와 `_thumbnail_id`를 모두 CAS로 확인한 뒤 이미 검수한 1200×675 이미지만 import한다. 저장 후 status/title/slug/content/excerpt와 Rank Math 3개 메타가 그대로인지, 새 attachment URL·MIME·ALT·`_thumbnail_id`가 정상인지 확인한다. 기존 attachment는 자동 삭제하지 않는다.
- `validation_reuse.py`가 content/source/policy/review fingerprint를 계산해 Fast 후보에서 source/policy/full-review/delta-review 재사용 상태를 명시한다. `workflow-metrics.jsonl`에는 Fast/Standard/image-only route와 validation reuse/skip 카운터가 추가된다.
- `task_state.py`가 `agent-publisher/data/editorial_runs/task-state/post-<ID>.json`에 작업 단계를 원자적으로 기록한다. WordPress 저장 뒤 화면 검증이 남으면 `saved_pending_qa`로 남아 세션 압축·연결 중단 후 `pending` 단계부터 이어갈 수 있다. 상태 파일에는 원고나 source 원문을 복제하지 않고 ID, SHA, route, 완료 단계와 산출물 경로만 기록한다.
- Fast 편집의 changed-block 의미 검토 결과는 baseline review digest, policy digest, delta digest, edit intent에 묶어 task-state에 보존한다. 중단 뒤 live 본문이 아직 작업 시작 SHA이면 같은 delta review를 재사용하고, 이미 저장 예정 SHA이면 mutation을 재실행하지 않고 QA 단계로 복귀한다. 둘과 다른 SHA는 `resume_state_conflict`로 차단한다.
- Windows CLI 진입점은 stdout/stderr를 UTF-8 `errors=replace`로 재구성하고 자식 Python 기본 인코딩도 UTF-8로 고정한다. 진단용 한글·기호 출력 실패가 성공한 편집 작업을 `UnicodeEncodeError`로 뒤집는 문제를 차단한다.

대표이미지 import는 비멱등 media mutation이므로 SSH 255에서 자동 재시도하지 않는다. 반대로 `edit-draft`의 동일 post update는 CAS가 전제된 멱등적 동일값 쓰기이므로 기존 fast-edit와 같은 1회 재시도 범위를 사용할 수 있다. P0 구현 자체에서는 실제 WordPress 글이나 대표이미지를 변경하지 않는다.

## 2026-09-29 P1 검증 재사용·Standard 지연 개선

P0 이후 남은 실제 병목을 `workflow-metrics.jsonl`로 다시 확인했다. 정상 source fetch는 대체로 약 0.5~2.5초였지만 semantic review는 보통 10~20초에서 길게는 70~150초까지 변동했고, `revise-draft` 성공 실행의 target read가 약 10~13초, inventory sync가 약 3~10초를 차지했다. 따라서 P1은 장기 source cache보다 **연속 Fast 검토 연결, semantic review 재사용/timeout, Standard read-only 단계 병렬화**를 우선했다.

- `fast_edit.py`에 full-review anchor와 digest-bound `fast_edit_chain`을 추가했다. 각 delta는 original full review/policy, 정확한 이전 content digest, 정확한 결과 content digest, delta digest, edit-intent digest에 결합된다. 모든 검토가 current이고 source/policy/factual scope가 그대로일 때 최대 5개 delta까지 연속 Fast 수정할 수 있고, chain 단절·만료·한도 초과에서는 Standard로 fail closed한다. 이전 full review의 digest를 새 원고에 직접 덮어써서 current인 것처럼 가장하지 않는다.
- `review_cache.py`를 추가해 semantic review를 정확한 review body, 현재 policy fingerprint, 실제 reviewer 구현 파일 digest에 content-addressed 방식으로 저장한다. review 기한이 유효하고 세 fingerprint가 모두 같을 때만 모델 호출을 생략한다. malformed/stale/policy·code mismatch cache는 단순 miss로 처리한다.
- reviewer HTTP 요청은 기본 45초 timeout을 사용하고 preferred model과 capacity fallback 한 개까지만 시도한다. 429/503/timeout은 즉시 fallback하고 500/502/504는 같은 모델에서 1회만 짧게 재시도한다. semantic/schema/auth 오류는 fallback으로 우회하지 않는다. 진단 문구도 Windows console encoding 때문에 작업 자체가 실패하지 않도록 ASCII-safe 경고를 사용한다.
- `source_validation_cache.py`를 추가했다. 최근 동일 URL/SHA를 검증한 source는 기본 15분, 최대 30분의 짧은 receipt를 재사용하고 누락·만료된 ID만 기존 `fetch_sources_subset()`으로 다시 받는다. extractor 구현 digest가 바뀌면 receipt를 무효화하고, 미래 timestamp도 거부한다. 현재 예매·판매·신청·재고·매진 같은 상태 source는 receipt를 항상 우회해 live refresh한다. 새 SHA는 기존처럼 즉시 전체 revision을 차단한다.
- Standard `revise-draft`의 inventory sync, 초기 target read, source recheck를 `ThreadPoolExecutor`와 독립 `contextvars` context로 병렬화했다. 세 snapshot을 서로 대조한 후 full validation을 수행하며, mutation 직전 fresh target CAS와 저장 후 target readback은 제거하지 않았다. P1의 목적은 안전 read를 없애는 것이 아니라 독립 read의 wall-clock을 겹치는 것이다.
- task-state를 v2로 올려 `task-state/post-<ID>/current.json`과 `archive/` 구조를 사용한다. raw edit intent 대신 SHA256, artifact path+SHA, Standard preflight checkpoint와 sanitized error type/code를 저장한다. transient timeout/SSH 255/일시적 5xx는 integrity block과 구분해 같은 fingerprint의 `--resume` 후보로 남기며, v1 state는 읽기 호환한다.
- workflow metrics는 실사용 `workflow-metrics.jsonl`과 unit-test `workflow-metrics-test.jsonl`을 기본 분리하고 `run_context`를 기록한다. review cache hit/miss/store, source receipt hit/refetch, model timeout/retry/fallback 카운터도 같은 실행 context에 기록한다.

P1에서도 실제 WordPress 글을 검증 목적으로 수정하지 않는다. 구현 검증은 mock/temp 상태와 회귀 테스트로 수행하고, 실운영 첫 적용은 사용자가 실제 특정 글 수정을 요청했을 때 P0/P1 경로의 metrics와 task-state를 관찰하는 방식으로 한다.

## 2026-09-29 P2 통합 수정·원격 왕복 축소

P2 기준선은 실사용 `workflow-metrics.jsonl`의 최근 성공 Standard `revise-draft`였다. 해당 실행은 약 21.5초, WordPress 왕복 5회였고 target read가 약 10.6초를 차지했다. P2는 이 CAS/readback 안전 검사를 삭제하지 않고 **서버 안에서 하나의 제한된 guarded mutation으로 원자화**해 네트워크 왕복만 줄이는 방향으로 구현했다.

- `wordpress_mutation.py`에 고정 PHP 프로그램과 엄격한 JSON stdin schema를 사용하는 `guarded_update_post()`를 추가했다. 클라이언트가 허용한 post ID, expected status/title/slug/excerpt/content SHA, 변경 필드만 전달하며 서버가 CAS → `wp_update_post()` → fresh readback → 전체 desired state 검증을 한 WP-CLI process에서 수행한다. Fast draft는 target `get → guarded mutation` 2회, Standard draft는 보통 inventory + initial target get + guarded mutation 약 3회로 줄어든다.
- SSH transport는 guarded eval의 **정확한 고정 script 문자열과 payload schema**만 허용한다. Fast/Standard, draft/public별 허용 status와 update field를 분리하고, raw `post update`에 Fast 재시도 권한을 주지 않는다. guarded mutation만 SSH 255에서 1회 replay할 수 있으며 서버는 이미 desired state가 정확히 적용돼 있으면 `already_applied`로 종료한다. title/status/slug/excerpt/content 중 하나라도 제3자 변경과 충돌하면 recovery로 오인하지 않는다. media import는 계속 non-idempotent라 자동 재시도하지 않는다.
- `edit-post`를 reviewed 기존 글의 통합 상위 진입점으로 추가했다. draft/public reviewed index 중 정확히 한 곳에서 target을 찾고, Fast classifier를 content scope에 적용한 뒤 status별 narrow mutator를 선택한다. 기존 `edit-draft`, `update-existing`, `replace-featured-image`는 호환·진단용으로 남긴다.
- public Fast는 `published_posts.json`에 reviewed editorial bundle이 있고, 그 bundle을 렌더한 SHA가 caller가 제시한 현재 공개 본문 SHA와 정확히 같을 때만 허용한다. 표현·구조 정리만 changed-block delta review로 처리하고 사람이 작성한 public excerpt는 보존한다. Standard public 저장 성공 뒤에는 기존 reviewed public manifest도 새 bundle로 원자 갱신해 다음 Fast 기준점이 stale하지 않게 한다. reviewed manifest가 없는 legacy public post를 임의로 Fast 대상에 편입하지 않는다.
- 본문+대표이미지 요청은 content와 image를 두 phase로 분리한다. content 저장·local manifest 갱신을 먼저 끝낸 뒤 새 content SHA와 기존 thumbnail ID를 CAS로 image-only mutation한다. 본문 저장 직후 중단돼 local manifest가 이전 상태인 좁은 crash window는 baseline/desired fingerprint가 정확히 일치할 때만 manifest를 재조정한다. 이미지 import 직후에는 attachment ID와 image/ALT/content SHA를 task-state checkpoint로 기록하고, 재개 시 같은 attachment의 thumbnail/ALT/MIME/URL/본문·SEO 보존을 검증만 하므로 중복 import를 만들지 않는다.
- task-state는 v3로 확장해 `content_saved`, `image_saved`, image outcome checkpoint, QA 요구 scope를 기록한다. QA scope는 reader-visible content 변화, CTA destination, table/layout topology, featured image, public-page 여부에서 결정하며, featured-image QA는 저장된 attachment ID와 실제 관측 `_thumbnail_id`가 같아야 완료할 수 있다. v1/v2 state는 읽기 호환한다.
- public Standard도 draft Standard와 같은 read-only 병렬화 패턴을 사용하고 guarded mutation을 통해 저장한다. Rank Math 업데이트는 기존 reviewed 3개 key/value allowlist를 유지하며 Fast public은 SEO를 변경하지 않는다.

P2 구현 검증에서는 실제 WordPress 글을 테스트 목적으로 수정하지 않았다. mock/temp 기반으로 guarded CAS/replay, draft/public Fast/Standard, public manifest binding, content+image resume, image outcome reconciliation, scope-aware QA와 SSH allowlist를 검증한다. 실운영 절감률은 다음 자연스러운 reviewed 글 수정에서 `workflow-metrics.jsonl`의 `wp_roundtrips`, `wp_guarded_mutations`, `total_ms`를 P2 기준선과 비교해 확인한다.
