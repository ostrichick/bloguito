# 4.3 volatility 기반 freshness 전환 영향도 감사

**상태:** 영향도 확인 완료, 4.3 구현은 아직 시작하지 않음.

이 문서는 4.1 일반/행사 writer schema 분리와 4.2 post-specific exception registry 분리를 완료한 뒤, `content_type`·카테고리 중심의 freshness 판단을 volatility 중심으로 바꾸기 전에 현재 코드·테스트·데이터에 미치는 영향을 읽기 전용으로 조사한 결과다. WordPress, 운영 서버, 기존 게시물은 변경하지 않았다.

## 결론

4.3은 구현 가능하지만 **현재 바로 동작 전환까지 진행하면 안 된다.** 먼저 진행 중인 카테고리 개편을 정리한 뒤 그 최종 taxonomy를 기준으로 4.3 브랜치를 갱신해야 한다. 카테고리 개편 worktree는 현재 `editorial.py`, `temporal_validation.py`, `search_briefs.json`, 관련 회귀 테스트를 동시에 수정하고 있어 4.3 핵심 변경점과 직접 겹친다.

또한 현재 계획의 단일 `volatility` enum만으로는 게시물 수명과 source 재검증 강도를 모두 안전하게 표현하기 어렵다. 한 글 안에 상시 절차와 실시간 신청·예매 상태가 함께 존재할 수 있기 때문이다. 4.3 1차 구현에서는 기존 `content_type`과 30일 규칙을 fallback으로 유지하고, volatility는 **기존 안전 기준을 완화하지 않는 추가 메타데이터/강화 신호**로 도입해야 한다.

## 현재 freshness는 네 층으로 분리되어 있다

### 1. 주제 수명

`agent-publisher/agents/editorial.py::topic_reasons()`가 현재 핵심 게이트다.

- `content_type=evergreen`: `useful_until=null`, `evergreen_reason` 필수.
- `content_type=dated`: `useful_until`까지 최소 `min_remaining_days=30` 필요.
- `concert`, `welfare` evergreen은 #85 정확 예외를 제외하고 차단한다.
- 날짜형 단일-post 예외는 4.2 registry에서 정확한 ID·URL·기간을 다시 대조한다.

따라서 volatility를 추가하더라도 첫 릴리스에서 이 검사를 제거하면 안 된다.

### 2. 시간 근거의 의미 검증

`editorial.py::validate_bundle()`의 dated 분기와 `agents/temporal_validation.py`가 다음 서로 다른 계약을 담당한다.

- 일반 신청·판매 기간 `validate_availability()`
- 연도별 공식 기준 `validate_reference_period()`
- 월간 다중 행사 `validate_multi_event_schedule()`
- 기존 welfare 후속 일정 `validate_legacy_followup()`
- 기존 연금·건강·예방접종 기간 `validate_legacy_reference_period()`
- 공연 일정 listing-only 경로

이 계약들은 단순히 `dated`인지뿐 아니라 category, temporal mode, evidence, 실제 종료일을 함께 검사한다. volatility 한 필드로 대체하지 않고 기존 temporal mode를 우선 신호로 활용해야 한다.

### 3. source snapshot freshness

`validate_bundle()`은 현재 모든 source의 `fetched_at`을 전역 `source_max_age_hours=24`로 검사한다.

Standard 수정에서는 `agents/source_validation_cache.py::revision_source_recheck_plan()`이 다음 source만 network recheck한다.

- 신규 source
- URL/type/hash/title이 바뀐 source
- 24시간을 넘긴 source
- `source_requires_live_refresh()`가 현재 신청·판매·재고·좌석 상태 문구를 감지한 source

즉 live-state는 이미 category와 독립된 source-level 안전장치다. 4.3에서 이 regex 기반 보호를 제거하면 안 된다.

### 4. semantic review freshness

`review_max_age_hours=24`는 `validate_bundle`, `review_cache`, `fast_edit` lineage에서 공통으로 적용한다. 이는 글의 volatility와 다른 **검토 artifact의 신선도**이므로 4.3에서 변경하지 않는 것이 안전하다.

## 데이터 영향

### `search_briefs.json`

현재 검토된 brief는 13개다.

| 구분 | 개수 |
| --- | ---: |
| evergreen | 10 |
| dated | 3 |
| life-health | 6 |
| tax | 4 |
| welfare | 2 |
| concert | 1 |

dated 3개는 콘서트 1개, welfare 2개다. evergreen 10개 안에는 순수 상시 절차뿐 아니라 매년 반복되는 제도와 현행 정책성 혜택도 섞여 있다. 따라서 `evergreen → timeless-procedure` 일괄 변환은 잘못된 결과를 만든다.

2026-10-02 기준 `reviewed_at/review_until` 창이 아직 유효한 brief는 `senior-implant-insurance-guide`, `long-term-care-grade-guide`, `national-pension-silver-loan` 3개뿐이다. migration reporter는 만료된 brief에 volatility 후보를 제안할 수는 있어도 `approved`/`review_until`을 갱신하거나 다시 활성화해서는 안 된다.

대표적인 모호성은 다음과 같다.

- 여권·주민등록·우편물 같은 상시 민원 절차: `timeless-procedure` 후보가 명확하다.
- 근로장려금·자동차세 연납처럼 매년 특정 시기가 반복되는 글: `annual-policy`와 `seasonal` 구분이 필요하다.
- 임플란트 건강보험·기후동행 관련 현행 제도·세금포인트처럼 종료일은 없지만 정책 개정 가능성이 있는 글: 현재 5개 enum에는 정확한 표현이 없다.
- 콘서트·지역 월간 행사처럼 특정 일정에 묶인 글: `one-off`가 자연스럽지만 예매 상태 주장은 별도로 `live` freshness가 필요할 수 있다.

따라서 기존 초기 설계에서 검토했던 **`policy-current`를 enum에 다시 포함하는 것이 적절하다.** 권장 post-level 값은 `timeless-procedure`, `policy-current`, `annual-policy`, `seasonal`, `one-off`, `live`다. 다만 `live`는 아래 source-level 신호와 함께 사용한다.

### `POST_CATALOG.md`

현재 카탈로그에는 공개 57편, 임시글 4편이 있고 공개글 자동 분류는 에버그린 37편, 시즌형 20편으로 표시된다. 그러나 이것은 4.3 migration truth로 사용할 수 없다.

`scripts/sync_post_catalog.py::determine_type_and_category()`는 제목에 `추석`, `9월`, `콘서트`, `예매`, `독감`이 있는지만 보고 시즌형을 정한다. 실제로 2026년 10월 지역 행사 글 여러 편이 카탈로그에서는 에버그린으로 표시된다. 따라서 카탈로그 유형은 migration candidate의 보조 신호로만 사용하고 자동 확정 근거로 사용하지 않는다.

## 진행 중 카테고리 개편과의 충돌

`C:\Dev\Worktrees\Bloguito\category-reorg-20261002`는 현재 다음 4.3 핵심 파일을 수정 중이다.

- `agent-publisher/agents/editorial.py`
- `agent-publisher/agents/temporal_validation.py`
- `agent-publisher/data/search_briefs.json`
- 다수 temporal/category 회귀 테스트

개편안은 `events` 카테고리를 새로 기간형으로 취급하고, 기존 `life-health`를 `health`, `transport`, `life-admin` 등으로 이동하며, 행사 temporal validator도 `category_key == events`를 요구하도록 바꾸고 있다.

따라서 4.3은 **카테고리 개편 완료 → 4.3 브랜치 rebase/merge → 새 taxonomy 기준 영향 테스트** 순서로 진행한다. 동시에 두 작업에서 `editorial.py`/`temporal_validation.py`를 수정하지 않는다.

## 단일 post-level volatility만으로 부족한 이유

예를 들어 “정부 서비스 신청 방법”은 대부분 상시 절차이지만 본문에 “현재 신청 가능”이라는 상태를 넣는 순간 해당 source는 실시간 검증이 필요하다. 반대로 콘서트 글도 날짜·장소 자체는 one-off 일정 근거지만 “현재 예매 가능”은 live claim이다.

따라서 4.3은 다음 두 레벨을 구분하는 것이 안전하다.

1. `brief.volatility`: 글 전체의 기본 lifecycle/정책 변경 성격.
2. `requires_live_state` 또는 `sources[].volatility=live` 같은 별도 명시적 live 신호: 특정 source가 현재 상태를 증명할 때의 재조회 강도.

기존 `source_requires_live_refresh()` regex는 계속 fallback으로 유지한다. 명시적 `live`가 있으면 regex가 상태 문구를 놓쳐도 항상 network recheck하고, regex가 live를 감지하면 메타데이터가 없어도 계속 강제 recheck한다.

`fetch_sources_subset()`은 기존 snapshot core 필드 이외의 reviewed metadata를 보존하므로 향후 source-level volatility 필드를 넣어도 selective re-fetch 과정에서 유지할 수 있다.

## 권장 4.3 구현 순서

### 4.3A — metadata-only 릴리스

동작을 바꾸지 않는다.

- `brief.volatility`를 optional로 허용한다.
- 허용 enum을 코드에서 검증한다.
- 기존 `content_type`, `useful_until`, category gate, 30일 기준은 그대로 둔다.
- 신규 brief에는 volatility를 명시하도록 writer/topic 준비 경로를 보강한다.
- 기존 brief·게시물에는 값을 자동 저장하지 않는다.
- read-only migration reporter를 추가해 `candidate`, `confidence`, `signals`, `conflicts`, `requires_review`를 출력한다.
- 초기 policy fingerprint에는 현재 bundle에 실제 명시된 volatility 규칙만 좁게 결합한다. 이 단계에서 `GENERAL_POST_STANDARD.md` 전체를 불필요하게 다시 고쳐 모든 일반 글 review를 일괄 무효화하지 않는다.

이 단계에서 volatility 추가는 `brief_changed`이므로 기존 `change_classifier`가 자동으로 Standard 수정으로 올린다. 별도 Fast 우회 코드는 만들 필요가 없다.

### 4.3B — 안전 기준 강화만 적용

기존 규칙을 완화하지 않고 volatility가 더 강한 검사를 요구할 때만 사용한다.

- `live`: 저장 직전 network recheck 강제. 기존 live regex와 OR 조건.
- `annual-policy`: `dated` + 공식 reference period/useful_until 요구.
- `seasonal`: `dated` + 공식 시즌 종료/useful_until 요구.
- `one-off`: `dated` + 실제 종료일/useful_until 요구.
- `timeless-procedure`: 기존 evergreen 조건을 만족해야 하며 live/annual temporal mode가 있으면 거부.
- `policy-current`: useful_until 강제 없이 허용하되 일반 source 24시간 freshness와 review freshness를 계속 적용하고, 현행 정책 근거 연도/개정일 검토를 유지한다.

이 단계에서도 `concert`, `events`, 기존 welfare/legacy category 예외를 제거하지 않는다. category 기반 gate와 volatility가 모두 통과해야 한다.

### 4.3C — fallback 제거 검토

최소 한 릴리스 동안 신규 brief와 수정된 기존 글의 migration 결과를 쌓은 뒤에만 진행한다.

- category 전용 lifetime gate를 volatility로 대체 가능한지 비교한다.
- `content_type`을 파생값으로 만들지, compatibility 필드로 계속 보관할지 결정한다.
- `radar.py`/`curator.py`의 evergreen 직행 분기를 volatility 기반으로 바꾸기 전에 뉴스 의존 없는 상시 절차 경로가 유지되는지 확인한다.
- WordPress `expires_at`에 연결된 `useful_until`을 제거하거나 재해석하지 않는다.

## migration candidate 규칙

자동 저장이 아니라 후보 보고서만 만든다.

### 높은 신뢰도 후보

- `multi_event_schedule=true` 또는 Event Post Standard 월간 행사는 `one-off`/`seasonal` 후보로 표시하되 자동 확정하지 않음
- concert의 특정 공연/투어 일정 → `one-off`; 단 판매 상태 source는 별도 live 검사
- `reference_period.kind=annual_rule`, legacy `annual_pension`, `annual_health_ceiling` → `annual-policy`
- `flu_season`, `national_flu_season` → `seasonal`
- evergreen reason이 특정 마감과 무관한 상시 민원 절차라고 명시되고 연도/시즌 temporal mode가 없는 경우 → `timeless-procedure` 후보

### 사람 확인이 필요한 후보

- “매년 반복”되는 신청 제도: `annual-policy`와 `seasonal` 중 선택 필요
- 종료일이 없지만 법·고시·요금·급여 기준이 바뀔 수 있는 상시 제도: `policy-current`
- 상시 절차와 현재 접수/판매 상태가 한 글에 섞인 경우: post 기본값과 live source scope를 별도 결정
- 카탈로그가 에버그린이라고만 표시한 기존 글

migration report의 최소 출력은 `{id, existing_content_type, suggested_volatility, confidence, signals, conflicts, requires_review, source}`로 한다. 신호 우선순위는 **명시적 temporal contract → 정확한 reviewed exception/procedure → brief lifecycle 문구 → 제목/category heuristic** 순서이며 마지막 단계는 낮은 신뢰도로만 사용한다.

## 구현 시 직접 영향을 받는 파일

### 반드시 검토/수정

- `agents/editorial.py`: `topic_reasons`, dated validation branch, policy fingerprint 대상 필드
- `agents/temporal_validation.py`: reference/event/legacy temporal 계약과 volatility compatibility
- `agents/source_validation_cache.py`: explicit live가 regex를 보강하도록 recheck planner 확장
- `data/search_briefs.json`: 신규/검토 완료 brief의 volatility 값
- 관련 `test_editorial_system`, reference-period, multi-event, schedule-listing, legacy temporal 테스트

### 1차 릴리스에서는 유지

- `review_max_age_hours=24`
- `source_max_age_hours=24`
- `source_requires_live_refresh()` regex
- 기존 `content_type` 필드
- 기존 category fail-closed gate
- `useful_until → WordPress expires_at` 연결
- `review_max_age_hours=24` 및 review cache/Fast lineage 계약

### fallback 제거 단계에서 검토

- `agents/radar.py`: evergreen brief는 뉴스 RSS 없이 direct 처리
- `agents/curator.py`: editorial_direct는 evergreen만 통과
- `scripts/sync_post_catalog.py`: 제목 keyword 기반 자동 유형 표시

## 필수 테스트 게이트

4.3A 이전/이후 기존 fixture 결과가 동일해야 한다.

1. volatility 없는 모든 기존 bundle 결과가 완전히 동일하다.
2. unknown volatility는 fail closed 한다.
3. volatility 필드만 추가하면 기존 reviewed bundle을 자동 승인하지 않고 Standard 재검토로 이동한다.
4. `live`는 source text regex에 상태 문구가 없어도 network recheck한다.
5. regex가 live 상태를 감지하면 metadata가 누락돼도 계속 network recheck한다.
6. annual/seasonal/one-off가 `useful_until`·공식 기간 없이 evergreen으로 우회할 수 없다.
7. `policy-current`가 “현재 신청 가능” 같은 live 주장을 자동으로 허용하지 않는다.
8. Event Post Standard와 concert listing-only가 기존 시간 검증을 그대로 통과한다.
9. legacy #85와 4.2 exception registry의 적용 범위가 넓어지지 않는다.
10. migration report는 값을 제안만 하고 `search_briefs.json`, WordPress, reviewed manifest를 수정하지 않는다.
11. 만료된 brief에 후보값을 계산해도 `approved`나 `review_until`을 연장하지 않는다.

## Go / No-Go 기준

현재는 **4.3 코드 구현 No-Go, 설계 준비 Go**다. 이유는 기능 설계 자체의 불가능이 아니라 진행 중인 category reorganization과 핵심 파일 충돌이 있기 때문이다.

4.3A 구현을 시작해도 되는 조건은 다음과 같다.

- category reorganization의 최종 taxonomy와 legacy compatibility가 main에 정리됨.
- 위 6개 volatility 값 또는 동등한 두 레벨 모델이 확정됨.
- migration reporter의 입력 source를 `search_briefs`/reviewed bundle 중심으로 정하고 POST_CATALOG 유형은 참고값으로만 사용함.
- 4.1/4.2 전체 회귀 baseline이 유지됨.

이 조건이 충족되면 먼저 4.3A metadata-only를 구현하고 결과를 검토한 뒤 4.3B 강화 규칙으로 넘어간다.
