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

콘텐츠 수정 중 transport 코드를 즉석에서 변경하지 않는다. Bloguito 서버의 수동 편집 transport는 설정에서 한 방식으로 정한다. 현재 환경처럼 일반 22번 SSH보다 Tailscale SSH가 실제로 안정적이면 `BLOGUITO_SSH_MODE=tailscale` 또는 동등한 프로젝트 설정을 정본으로 두고 처음부터 그 경로를 사용한다.

fast mutation의 연결 정책은 다음처럼 단순하게 둔다.

1. 설정된 transport로 대상 `post get` 시도.
2. exit 255이면 Tailscale 사용 환경에 한해 `tailscale ping -c 1`로 한 번 진단.
3. 같은 mutation을 최대 한 번만 재시도.
4. 두 번째 실패에서는 `transport_unavailable`로 종료하고 WordPress 변경을 시도하지 않는다.

콘텐츠 작업 도중 일반 SSH↔Tailscale 전환 기능을 새로 구현하거나 companion/browser 재연결을 반복하지 않는다. transport 개선은 별도 인프라 작업으로 분리한다.

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
