# 4.3 volatility 기반 freshness 전환 영향도 감사

**상태:** 카테고리 8분류 개편과 1~4.2 통합 완료. 4.3A metadata-only와 4.3B 안전 강화까지 구현 완료. 기존 category/content-type fallback 제거는 아직 하지 않음.

이 문서는 4.1 일반/행사 writer schema 분리와 4.2 post-specific exception registry 분리를 완료한 뒤, `content_type`·카테고리 중심의 freshness 판단을 volatility 중심으로 바꾸기 전에 현재 코드·테스트·데이터에 미치는 영향을 읽기 전용으로 조사한 결과다. WordPress, 운영 서버, 기존 게시물은 변경하지 않았다.

## 결론

카테고리 8분류 개편은 `5ea14ea`로 `main`에 통합됐고 정책 최적화 1~4.2와 충돌도 해소했다. 그 기반에서 **4.3A와 4.3B를 구현했다.** 다만 기존 category/content-type 규칙은 아직 제거하지 않고 additive gate로 유지한다.

단일 `volatility` enum 대신 lifecycle과 live-state를 분리했다. lifecycle은 `timeless-procedure`, `policy-current`, `annual-policy`, `seasonal`, `one-off` 5종이고, 현재 상태 재검증은 별도 `requires_live_state` boolean으로 관리한다. 기존 `content_type`과 30일 규칙은 fallback으로 유지한다.

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
| life-admin | 3 |
| welfare | 3 |
| tax | 4 |
| concert | 1 |
| transport | 1 |
| health | 1 |

dated 3개는 콘서트 1개, welfare 2개다. evergreen 10개 안에는 순수 상시 절차뿐 아니라 매년 반복되는 제도와 현행 정책성 혜택도 섞여 있다. 따라서 `evergreen → timeless-procedure` 일괄 변환은 잘못된 결과를 만든다.

2026-10-02 기준 `reviewed_at/review_until` 창이 아직 유효한 brief는 `senior-implant-insurance-guide`, `long-term-care-grade-guide`, `national-pension-silver-loan` 3개뿐이다. migration reporter는 만료된 brief에 volatility 후보를 제안할 수는 있어도 `approved`/`review_until`을 갱신하거나 다시 활성화해서는 안 된다.

대표적인 모호성은 다음과 같다.

- 여권·주민등록·우편물 같은 상시 민원 절차: `timeless-procedure` 후보가 명확하다.
- 근로장려금·자동차세 연납처럼 매년 특정 시기가 반복되는 글: `annual-policy`와 `seasonal` 구분이 필요하다.
- 임플란트 건강보험·기후동행 관련 현행 제도·세금포인트처럼 종료일은 없지만 정책 개정 가능성이 있는 글: 현재 5개 enum에는 정확한 표현이 없다.
- 콘서트·지역 월간 행사처럼 특정 일정에 묶인 글: `one-off`가 자연스럽지만 예매 상태 주장은 별도로 `live` freshness가 필요할 수 있다.

따라서 기존 초기 설계에서 검토했던 **`policy-current`를 enum에 다시 포함했다.** post-level lifecycle 값은 `timeless-procedure`, `policy-current`, `annual-policy`, `seasonal`, `one-off`이며 `live`는 enum이 아니라 별도 boolean 신호로 분리했다.

### `POST_CATALOG.md`

현재 카탈로그에는 공개 57편, 임시글 4편이 있고 공개글 자동 분류는 에버그린 37편, 시즌형 20편으로 표시된다. 그러나 이것은 4.3 migration truth로 사용할 수 없다.

`scripts/sync_post_catalog.py::determine_type_and_category()`는 제목에 `추석`, `9월`, `콘서트`, `예매`, `독감`이 있는지만 보고 시즌형을 정한다. 실제로 2026년 10월 지역 행사 글 여러 편이 카탈로그에서는 에버그린으로 표시된다. 따라서 카탈로그 유형은 migration candidate의 보조 신호로만 사용하고 자동 확정 근거로 사용하지 않는다.

## 카테고리 개편 통합 결과

8개 현행 taxonomy는 `events`, `concert`, `welfare`, `tax`, `health`, `transport`, `life-admin`, `finance`다. 과거 `life-health`는 reviewed bundle 읽기 호환에만 남긴다.

4.3은 이 taxonomy 위에서 동작하지만 **volatility를 category의 다른 이름으로 만들지 않는다.** 예를 들어 `health` 안에도 `timeless-procedure`, `policy-current`, `annual-policy`, `seasonal`이 모두 존재할 수 있다. `events`는 현재 시간 검증 경계를 유지하고, volatility 도입만으로 행사 표준의 `multi_event_schedule` 계약을 우회하지 않는다.

## 단일 post-level volatility만으로 부족한 이유

예를 들어 “정부 서비스 신청 방법”은 대부분 상시 절차이지만 본문에 “현재 신청 가능”이라는 상태를 넣는 순간 해당 source는 실시간 검증이 필요하다. 반대로 콘서트 글도 날짜·장소 자체는 one-off 일정 근거지만 “현재 예매 가능”은 live claim이다.

따라서 4.3은 다음 두 레벨을 구분하는 것이 안전하다.

1. `brief.volatility`: 글 전체의 기본 lifecycle/정책 변경 성격.
2. `brief.requires_live_state`: 현재 상태를 증명할 때의 재조회 강도. 첫 릴리스에서는 source-level schema를 추가하지 않는다.

기존 `source_requires_live_refresh()` regex는 계속 fallback으로 유지한다. `requires_live_state=true`이면 regex가 상태 문구를 놓쳐도 항상 network recheck하고, regex가 live를 감지하면 metadata가 없어도 계속 강제 recheck한다.

`fetch_sources_subset()`은 기존 snapshot core 필드 이외의 reviewed metadata를 보존하므로 향후 source-level volatility 필드를 넣어도 selective re-fetch 과정에서 유지할 수 있다.

## 확정 4.3 실행 순서

### 4.3A — metadata-only 릴리스 — 완료

기존 metadata가 없는 bundle 동작은 바꾸지 않는다.

- `brief.volatility`를 optional로 허용한다: `timeless-procedure`, `policy-current`, `annual-policy`, `seasonal`, `one-off`.
- 현재 상태 확인은 post lifecycle과 분리해 `brief.requires_live_state: bool`을 optional로 둔다. 향후 필요한 경우 source-level `volatility=live`를 추가할 수 있지만 A에서는 저장 schema를 넓히지 않는다.
- unknown volatility 또는 boolean이 아닌 `requires_live_state`는 fail closed 한다.
- 기존 `content_type`, `useful_until`, category gate, 30일 기준은 그대로 둔다.
- 신규 reviewed brief에는 volatility와 필요 시 `requires_live_state`를 명시하도록 topic 준비 경로를 보강한다.
- 기존 brief·게시물에는 값을 자동 저장하지 않는다.
- read-only migration reporter를 추가해 `candidate`, `requires_live_state`, `confidence`, `signals`, `conflicts`, `requires_review`를 출력한다.
- 초기 policy fingerprint에는 현재 bundle에 실제 명시된 volatility 규칙만 좁게 결합한다. 이 단계에서 `GENERAL_POST_STANDARD.md` 전체를 불필요하게 다시 고쳐 모든 일반 글 review를 일괄 무효화하지 않는다.

이 단계에서 volatility 추가는 `brief_changed`이므로 기존 `change_classifier`가 자동으로 Standard 수정으로 올린다. 별도 Fast 우회 코드는 만들 필요가 없다.

### 4.3B — 안전 기준 강화만 적용 — 완료

기존 규칙을 완화하지 않고 volatility가 더 강한 검사를 요구할 때만 사용한다.

- `requires_live_state=true`: 저장 직전 관련 official source network recheck 강제. 기존 live regex와 OR 조건이며 receipt cache로 생략할 수 없다.
- `annual-policy`: `dated` + 공식 reference period/useful_until 요구.
- `seasonal`: `dated` + 공식 시즌 종료/useful_until 요구.
- `one-off`: `dated` + 실제 종료일/useful_until 요구.
- `timeless-procedure`: 기존 evergreen 조건을 만족해야 하며 live/annual temporal mode가 있으면 거부.
- `policy-current`: useful_until 강제 없이 허용하되 일반 source 24시간 freshness와 review freshness를 계속 적용하고, 현행 정책 근거 연도/개정일 검토를 유지한다. 현재 신청·판매 가능을 주장하려면 별도 `requires_live_state=true`가 필요하다.

이 단계에서도 `concert`, `events`, 기존 welfare/legacy category 예외를 제거하지 않는다. category 기반 gate와 volatility가 모두 통과해야 한다.

### 4.3C — fallback 제거 검토

최소 한 릴리스 동안 신규 brief와 수정된 기존 글의 migration 결과를 쌓은 뒤에만 진행한다.

- category 전용 lifetime gate를 volatility로 대체 가능한지 비교한다.
- `content_type`을 파생값으로 만들지, compatibility 필드로 계속 보관할지 결정한다.
- `radar.py`/`curator.py`의 evergreen 직행 분기를 volatility 기반으로 바꾸기 전에 뉴스 의존 없는 상시 절차 경로가 유지되는지 확인한다.
- WordPress `expires_at`에 연결된 `useful_until`을 제거하거나 재해석하지 않는다.

### 4.3D — discovery 경로 전환

4.3C와 분리한다. `radar.py`와 `curator.py`의 기존 `content_type=evergreen` 분기는 RSS 없이 공식 source로 바로 가는 비용·안전 최적화이므로 lifecycle enum만 보고 즉시 대체하지 않는다. `timeless-procedure`와 `policy-current`의 직접 source 경로, `annual-policy`/`seasonal`의 최신 공고 탐색 필요성을 각각 fixture로 만든 뒤 전환한다.

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

migration report의 최소 출력은 `{id, existing_content_type, suggested_volatility, suggested_requires_live_state, confidence, signals, conflicts, requires_review, source}`로 한다. 신호 우선순위는 **명시적 temporal contract → 정확한 reviewed exception/procedure → brief lifecycle 문구 → 제목/category heuristic** 순서이며 마지막 단계는 낮은 신뢰도로만 사용한다.

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

4.3A 이전/이후 기존 fixture 결과가 동일해야 한다. 현재 통합 baseline은 **801 tests PASS, 1 skipped**다.

1. volatility 없는 모든 기존 bundle 결과가 완전히 동일하다.
2. unknown volatility는 fail closed 한다.
3. volatility 필드만 추가하면 기존 reviewed bundle을 자동 승인하지 않고 Standard 재검토로 이동한다.
4. `requires_live_state=true`는 source text regex에 상태 문구가 없어도 network recheck한다.
5. regex가 live 상태를 감지하면 metadata가 누락돼도 계속 network recheck한다.
6. annual/seasonal/one-off가 `useful_until`·공식 기간 없이 evergreen으로 우회할 수 없다.
7. `policy-current`만으로 “현재 신청 가능” 같은 live 주장을 자동으로 허용하지 않는다.
8. Event Post Standard와 concert listing-only가 기존 시간 검증을 그대로 통과한다.
9. legacy #85와 4.2 exception registry의 적용 범위가 넓어지지 않는다.
10. migration report는 값을 제안만 하고 `search_briefs.json`, WordPress, reviewed manifest를 수정하지 않는다.
11. 만료된 brief에 후보값을 계산해도 `approved`나 `review_until`을 연장하지 않는다.

## Go / No-Go 기준

현재 구현 결과는 다음과 같다.

- **4.3A: 완료.** optional lifecycle/live metadata, fail-closed validation, explicit bundle fingerprint binding, read-only migration reporter를 구현했다.
- **4.3B: 완료.** 기존 gate를 제거하지 않고 annual/timeless 추가 계약과 save-time live source network recheck를 구현했다.
- **4.3C: 부분 진행.** 실제 운영 표본으로 live-state 재조회가 확인된 뒤, `welfare + evergreen` blanket gate 중 사람이 명시적으로 `policy-current`와 `requires_live_state`를 확정한 brief에 한해서만 legacy category fallback을 제거한다. `dated` temporal 검증과 metadata가 없는 welfare fallback은 유지한다.
- **4.3D: NO-GO.** 4.3C의 제한적 전환 결과를 먼저 관찰하고 discovery 전환은 별도 변경으로 진행한다.

2026-10-02 migration report는 13개 brief 중 현재 review window가 살아 있는 3개를 그대로 식별했고, 9개를 사람 검토가 필요한 후보로 남겼다. 기존 `search_briefs.json`, `approved`, `review_until`, reviewed manifest, WordPress 상태는 자동 변경하지 않았다. 4.3C/D는 explicit metadata를 실제 신규/수정 bundle에 적용한 뒤 한 릴리스 이상 관찰하고 진행한다.

후속 수동 검토에서는 review window가 현재 유효한 3건을 `topic_reasons()`까지 대조했다. `senior-implant-insurance-guide`는 `policy-current` + `requires_live_state=false`, `national-pension-silver-loan`은 분기별 금리 확인 때문에 `policy-current` + `requires_live_state=true`로 확정했다. 이후 `long-term-care-grade-guide`를 다시 검토한 결과, 원래 `life-health + evergreen`으로 작성된 상시 장기요양보험 제도 안내가 2026-10-02 카테고리 개편에서 `welfare`로 이동하면서 blanket `welfare + evergreen` 차단과 충돌한 사례임을 확인했다. 장기요양은 종료일을 임의로 만들 dated 주제가 아니라 현행 법·급여 기준이 개정될 수 있는 상시 제도이므로 `policy-current + requires_live_state=true`를 명시하고, 이 explicit 계약에 한해서 legacy category gate를 대체하도록 4.3C를 좁게 진행한다. 만료된 10건의 `approved`/`review_until`은 변경하지 않는다.

이 수동 확정은 **로컬 repository의 reviewed brief 데이터만** 변경한다. `scripts/install_editorial_release.py`는 운영 서버에 기존 `data/search_briefs.json`이 있으면 그 파일을 덮어쓰지 않으므로 코드 릴리스만으로 이 2건의 metadata가 운영에 적용되지는 않는다. 따라서 실제 4.3C/D 관찰기간은 별도의 reviewed data 적용 및 릴리스가 이루어진 뒤부터 계산해야 하며, 로컬 커밋 시점을 관찰 시작으로 간주하지 않는다.

### 4.3C/D 실행 readiness 체크리스트

현재 판정은 **제한적 GO**다. `policy-current`로 사람이 확정한 welfare evergreen만 category blanket fallback을 대체할 수 있고, 그 밖의 `content_type`/dated temporal fallback 제거와 `radar.py`·`curator.py` discovery 전환은 계속 NO-GO다.

1. 운영의 reviewed `search_briefs.json`에 사람이 확정한 explicit volatility metadata가 실제 적용되어야 한다. 코드 저장소의 로컬 값만으로는 관찰을 시작한 것으로 보지 않는다.
2. 그 metadata를 사용하는 실제 릴리스를 최소 한 번 운영하고, 신규 또는 수정 bundle에서 legacy gate와 volatility gate의 결과를 함께 기록한다.
3. legacy gate가 HOLD인데 volatility만 PASS하는 사례는 원인을 분리한다. 장기요양처럼 category 재분류 때문에 blanket gate만 잘못 막는 경우에는 explicit reviewed lifecycle로 그 gate만 대체할 수 있다. 실버론처럼 실제 temporal 의미가 미해결인 경우에는 기존 dated 검증을 그대로 유지한다.
4. `requires_live_state=true`인 실제 케이스에서 저장 직전 network recheck와 receipt bypass가 동작했는지 확인한다. 테스트 fixture만으로 이 조건을 충족했다고 보지 않는다.
5. `long-term-care-grade-guide`는 `evergreen + policy-current + requires_live_state=true`가 맞는 것으로 재판정했다. `useful_until`을 만들거나 다른 카테고리로 위장하지 않고, explicit metadata가 모두 존재하는 경우에만 welfare evergreen blanket gate를 대체한다.
6. 4.3C 검토 시 `useful_until → WordPress expires_at`, 30일 최소 lifetime, category fail-closed, legacy exception 범위가 기존보다 약해지지 않았음을 비교한다.
7. 4.3D 전에는 discovery fixture를 최소 `timeless-procedure`, `policy-current`, `annual-policy`, `seasonal`별로 만든다. 상시 절차·현행 정책은 공식 source 직행 여부를, annual/seasonal은 최신 공고 탐색 필요성을 각각 검증한다.
8. 4.3C와 4.3D는 같은 변경으로 묶지 않는다. fallback 제거 결과를 먼저 관찰한 뒤 discovery 전환을 별도 변경·회귀검증으로 진행한다.

현재 `radar.py`는 `content_type == 'evergreen'`인 brief만 RSS 없이 `editorial_direct`로 보내고, `curator.py` 역시 `editorial_direct`를 evergreen에 한해 허용한다. 이는 아직 의도적인 legacy fallback이며 이번 단계에서는 수정하지 않는다.

## 운영 릴리스와 관찰 시작 상태 — 2026-10-02

2026-10-02 15:21 KST까지 다음 운영 적용을 완료했다.

- Git `main`/`origin/main`을 `7dcefc32a6bca6bc8aa6d22b76a9d992243239a9`로 맞춘 뒤, 운영 `/home/ubuntu/agent-publisher`에 현재 agents 패키지, `editorial_cli.py`, `editorial_policy.json`, critical-fact/policy-exception registry와 4개 활성 정책 문서를 release installer 경로로 배포했다.
- installer는 운영 `config.py`, `main.py`, 기존 `data/search_briefs.json`을 통째로 교체하지 않았다. 배포 전 파일별 롤백 manifest는 `/home/ubuntu/agent-publisher/backups/editorial-20261002T061701Z/manifest.json`이다.
- 배포 직후 `agents/volatility.py`, `agents/critical_facts.py`, `agents/event_post_standard.py`, `editorial_policy.json`, `data/critical_facts/registry.json`의 운영 SHA가 release 파일과 일치했고 `validate_critical_fact_registry()`가 `True`를 반환했다. `main.py --help`도 현행 8개 category를 정상 노출했다.
- 코드 배포 전후 기존 운영 `search_briefs.json` SHA는 `cc2973ff683875c822812c4fca1e1b7d8121c39cc99830281eb863de00e57c37`로 동일했다. 운영에는 과거 10개 brief만 있었고 수동 확정한 3개 신규 reviewed brief는 아직 없었다.
- 관찰 대상으로 확정한 `senior-implant-insurance-guide`와 `national-pension-silver-loan` 두 reviewed row만 운영 데이터에 추가했다. 기존 10개 row는 byte-level 원본 백업과 구조 비교로 보존했고 `approved`, `reviewed_at`, `review_until`, `useful_until` 값을 변경하지 않았다. `long-term-care-grade-guide`는 `dated_category_cannot_bypass_time_check` legacy 충돌 때문에 추가하지 않았다.
- 운영 data backup은 `/home/ubuntu/agent-publisher/backups/volatility-briefs-20261002T062027Z`이며, 적용 후 `search_briefs.json`은 12개 row, SHA `277d6fe726a9ed58ac0505c8bf7dcb631e4744d1a02c09efea2e16e6508d88be`다.
- readback에서 두 대상 모두 `topic_reasons(..., 2026-10-02) == []`, migration 제안과 explicit metadata가 일치했다. 정적 source text를 넣은 smoke에서도 implant brief는 live refresh를 강제하지 않고, silver-loan brief는 `requires_live_state=true` 때문에 source 문구와 무관하게 live refresh를 강제했다.

운영 cron은 `0 8 * * * /home/ubuntu/agent-publisher/run_daily.sh`로 확인됐다. 이번 코드/data 적용은 2026-10-02 15:21 KST에 끝났으므로 그날 08:00 정규 실행은 관찰 표본이 아니다. 이 시점에는 테스트·readback만으로 최소 한 릴리스 관찰 조건을 충족했다고 간주하지 않았고 4.3C/4.3D를 계속 NO-GO로 유지했다. 이후 같은 날 17:06 KST 수동 운영 `prepare-draft`에서 explicit live-state의 실제 save-time recheck를 별도로 관찰했으며, 다음 정규 실행은 추가 운영 표본으로 본다.

### 첫 explicit live-state 운영 표본 — 2026-10-02 16:27 KST

`national-pension-silver-loan`을 `volatility=policy-current`, `requires_live_state=true`인 실제 신규 draft 후보로 준비해 운영 `prepare-draft` 경로를 실행했다. 관찰용 bundle은 국민연금공단의 실버론 지원내용, 신청방법, 상환, 이자 모의계산 4개 공식 페이지를 2026-10-02 16:19 KST에 새로 조회했다. 현재 공식 원문은 2026년 4분기 대부이자율 `연 3.21%`, 연체이자율 `연 6.42%`를 표시하고 있었고, 이자율이 매 분기 변경된다는 문구도 함께 확인됐다.

- explicit volatility metadata 자체는 유효했고 `topic_reasons() == []`, `temporal_contract_reasons() == []`였다.
- migration 결과는 기존 검토값과 일치했지만 `policy_current_keeps_legacy_dated_contract` 충돌 신호를 그대로 유지했다. 이는 `policy-current`가 기존 `content_type=dated` 계약을 면제하지 않는다는 의도된 상태다.
- 원고의 evidence, 숫자 근거, 문장부호, 공식 링크 형식 오류를 제거한 뒤 deterministic preflight에서 남은 사유는 정확히 `temporal_source_not_bound`, `availability_not_verified` 두 개뿐이었다.
- 16:27 KST에 실제 `scripts/editorial_cli_via_ssh.py ... prepare-draft` 경로로 재실행해도 같은 두 사유로 `SystemExit` HOLD가 발생했다. local/remote WordPress write 전에 중단됐고 receipt도 생성되지 않았다.
- 직후 WordPress draft 목록은 기존 `#837`, `#592` 두 건뿐으로 확인되어 이 관찰 시도에서 새 draft가 만들어지지 않았음을 검증했다.

이 표본은 readiness 체크리스트의 **legacy gate HOLD / volatility metadata PASS 불일치 사례**에 해당한다. 따라서 4.3C fallback 제거는 계속 **NO-GO**다. 또한 저장 단계까지 도달하지 못했으므로 `requires_live_state=true`가 save-time에 모든 reviewed source의 receipt를 우회하고 network recheck를 강제하는 운영 조건은 아직 충족되지 않았다. 이 한 사례를 통과시키기 위해 별도의 범용 quarterly-policy 예외나 temporal bypass를 즉시 추가하지 않고, 기존 dated lifetime/temporal 의미를 별도 재검토 대상으로 남긴다.

### explicit seasonal live-state 저장 성공 표본 — 2026-10-02 17:06 KST

사용자가 선택한 `energy-voucher-deadline-2026`을 `content_type=dated`, `volatility=seasonal`, `requires_live_state=true`, `useful_until=2026-12-31`로 준비했다. reviewed window는 `2026-10-02`부터 `2026-10-31`까지이며 deterministic preflight와 semantic review가 모두 `ready`였다. 공식 source 3개는 에너지바우처 지원안내, 신청안내, parser가 직접 읽을 수 있는 공식 영상 상세 페이지이며, 전체 신청기간 `2026-06-15 ~ 2026-12-31`과 별개로 `2026-10-01 ~ 2026-10-02` 신청·재신청 일시중단을 원고에 명시했다.

- `scripts/editorial_cli_via_ssh.py ... prepare-draft`의 17:05:54~17:06:57 KST 실제 운영 run이 `status=ok`로 끝났다.
- 성공 run의 workflow metrics는 `source_fetch_requests=3`, `source_receipt_refetch=3`, `source_recheck=415.69ms`, `wp_roundtrips=1`이었다. `source_receipt_hit`은 없었다.
- `requires_live_state=true`이면 `source_requires_live_refresh()`가 모든 reviewed source에 `True`를 반환하고, `verify_explicit_live_sources()`가 세 source ID를 모두 `force_refresh_ids`로 넘긴다. 이 경로에서는 `_load_reusable_receipt()`보다 `force_refresh_ids`가 우선하므로 receipt hit로 network fetch를 생략할 수 없다. 실제 성공 run에서도 세 source가 모두 refetch됐고 receipt 3개가 `2026-10-02T17:06:02+09:00`에 새로 기록됐으며 각 observed SHA가 reviewed SHA와 일치했다. 다만 성공 run 직전에 이 세 URL의 유효한 receipt가 이미 존재했다는 별도 로그는 없으므로, 운영 표본 자체가 증명하는 것은 **save-time 3/3 강제 refetch**이고 receipt 선점 상태의 A/B 비교는 코드 경로 검증에 의존한다.
- 대표 이미지는 생성 API를 호출하지 않고 로컬 reviewed JPEG를 `--image-path`로 전달했다. WordPress attachment `#842`의 SHA256은 `energy-cover-couple.jpg`와 일치했고, 성공 run metrics에도 `cover_generation` timing이 없다. 사용자가 ChatGPT/CoS에서 명시적으로 포스트 작성을 지시한 경로에서는 Gemini 이미지를 사용하지 않는 운영 기준을 유지했다.
- WordPress에는 `#841` `2026 에너지바우처 신청기간: 10월 2일 일시중단, 12월 31일 마감`이 `draft`로 저장됐다. 기존 `#837`, `#592` draft는 유지됐고 과거 에너지바우처 `#90`은 계속 `trash`다. 이후 같은 bundle의 재실행은 `duplicate_topic`에서 WordPress write 전에 차단돼 두 번째 draft를 만들지 않았다.
- draft manifest의 `expires_at`은 `2026-12-31`로 저장돼 `brief.useful_until`과 일치했고 category는 `정부 복지·지원금`(ID 3)으로 유지됐다. 30일 최소 lifetime, dated/seasonal temporal gate, category fail-closed, 기존 exception 범위를 완화하지 않았다.

이 표본으로 readiness 체크리스트 4번의 핵심인 **실제 `requires_live_state=true` save-time network recheck**는 운영에서 충족됐다. receipt 재사용 차단은 동일 save 경로의 `force_refresh_ids` 계약과 실제 3/3 refetch가 일치함을 확인했지만, pre-seeded fresh receipt가 있는 상태의 운영 A/B까지 별도로 만들지는 않았다. 또한 16:27 KST `national-pension-silver-loan`에서 확인된 **legacy gate HOLD / volatility metadata PASS 불일치**가 아직 해소되지 않았으므로 4.3C fallback 제거는 계속 **NO-GO**다. 에너지바우처의 성공은 호환 가능한 `seasonal` 경로가 정상 동작한다는 증거이지, 기존 `content_type`/category fallback을 제거해도 된다는 증거는 아니다. 4.3D discovery 전환도 4.3C와 분리해 그대로 보류한다.

### 4.3C 계약 재판정과 제한적 category fallback 제거 — 2026-10-02

운영 표본 이후 `long-term-care-grade-guide`와 `national-pension-silver-loan`을 같은 문제로 취급하지 않고 계약을 다시 분리했다.

- **장기요양보험:** 2026-09-20 원본 brief는 `life-health + evergreen`이었고, 2026-10-02 taxonomy 개편에서 내용에 맞춰 `welfare`로 이동했다. 제도에는 글 전체에 적용할 보편적 신청 마감일이 없고, 등급 신청·판정·급여 이용은 상시 제도인 반면 법·급여 기준은 개정될 수 있다. 따라서 `evergreen + policy-current + requires_live_state=true`가 맞다. 기존 `dated_category_cannot_bypass_time_check`는 이 경우 lifecycle 의미가 아니라 옛 category blanket rule 때문에 발생한 false HOLD다.
- **실버론:** 제도 신청 자체는 공식 안내상 `상시 신청 가능(매년 대부금 예산범위 내에서 접수)`이고 현재 대부이자율만 분기별로 바뀐다. 따라서 글 전체는 `evergreen + policy-current + requires_live_state=true`가 맞고, 현재 금리 주장만 별도 bounded claim으로 다뤄야 한다. 독립적인 실제 사례를 찾기 전까지는 이 한 건을 위해 범용 기능을 추가하지 않았다.
- **독립 사례 #474 도시가스 요금 경감:** 한국가스공사 현행 공식 페이지는 상시 신청 가능한 요금 경감 제도의 지원금액을 취사난방용 `동절기(12~3월)`와 `동절기제외(4월~11월)`로 나눠 월 한도를 제공한다. 제도 전체가 종료되는 것이 아니라 적용값만 주기별로 달라지는 두 번째 실제 사례가 확인됐으므로, 실버론 전용 `quarterly-policy` 예외가 아니라 claim-level 공통 temporal contract를 설계할 근거가 생겼다. 연도가 없는 반복 월 구간은 특정 연도의 exact current period로 자동 변환하지 않는다.
- **13개 brief 비교:** 2026-10-02에 review window가 살아 있는 세 건 중 임플란트는 legacy/volatility가 이미 일치하고, 장기요양은 category blanket gate 충돌을 해소했으며, 실버론은 새 claim-level current-value contract로 dated 신청기간 오해를 제거했다. 만료된 10건은 migration 후보일 뿐 fallback 제거의 승인 근거로 사용하지 않는다.

따라서 4.3C의 category 전환은 `welfare + evergreen`을 일반 허용하지 않는다. `volatility=policy-current`와 boolean `requires_live_state`가 **둘 다 명시된** reviewed brief에 한해서만 `dated_category_cannot_bypass_time_check`를 대체한다. metadata가 없는 welfare evergreen, `timeless-procedure`, events/concert, 실제 dated 글의 temporal 검증, 30일 minimum lifetime, `useful_until → expires_at`, 기존 #85 exact exception은 모두 그대로 유지한다.

이 단계는 **4.3C 전체 완료가 아니다.** policy-current welfare evergreen의 category fallback과 current-value claim의 시간 계약까지 분리했지만, 만료된 기존 brief 전체를 재검토하지 않았고 모든 category/content_type compatibility를 제거한 것도 아니다. 4.3D는 계속 별도 단계로 보류한다.

### 제한적 4.3C 운영 배포 — 2026-10-02 17:56 KST

제한적 category fallback 제거는 Git `8ca823e` (`policy: narrow welfare policy-current fallback`)로 `main`/`origin/main`에 반영한 뒤 운영 `/home/ubuntu/agent-publisher`에 배포했다.

- 배포 release: `/home/ubuntu/releases/editorial-stage4-3c-20261002-175550`
- 코드 rollback manifest: `/home/ubuntu/agent-publisher/backups/editorial-20261002T085617Z/manifest.json`
- 운영 `agents/editorial.py` SHA256: `ddc2b0e4af430c458bc0edf5a1bebdedd4e550b0601b49452ac9385ad763bc37`, 로컬 release와 일치
- 배포 smoke: `Editorial imports and critical-fact registry ready; minimum days: 30`
- 기존 운영 `search_briefs.json`은 12행, SHA `277d6fe726a9ed58ac0505c8bf7dcb631e4744d1a02c09efea2e16e6508d88be`였고 코드 installer가 이 파일을 덮어쓰지 않았다.
- 데이터 백업: `/home/ubuntu/agent-publisher/backups/volatility-briefs-20261002T085650Z`
- 장기요양 reviewed row **한 건만** 추가했고 기존 12행이 구조적으로 동일함을 비교한 뒤 13행으로 저장했다. 적용 후 SHA는 `5b9329af4e9ffb35232dc49245493a668f578597aa7b9e5eb58bc24ad6e6dea4`다.
- 운영 readback에서 장기요양은 `topic_reasons(..., 2026-10-02) == []`, `evergreen + policy-current + requires_live_state=true`, migration 제안과 현재 값이 일치했다. 동일 row에서 volatility/live metadata만 제거한 복사본은 다시 `dated_category_cannot_bypass_time_check`로 HOLD되어 metadata 없는 welfare fallback이 유지됨을 확인했다.
- 실버론은 `topic_reasons()==[]`이지만 migration conflict `policy_current_keeps_legacy_dated_contract`를 그대로 유지한다. 이번 배포는 dated temporal path를 수정하지 않았다.
- 전체 로컬 회귀는 테스트용 Kakao key를 사용한 격리 worktree에서 **824 tests OK, skipped=1**이었다. 첫 전체 실행의 단일 오류는 worktree에 로컬 `.env`가 없어 event renderer가 Kakao JS key를 읽지 못한 환경 오류였고, 테스트용 key를 명시해 재실행하면 전부 통과했다.

이 배포로 4.3C의 **첫 제한적 코드 전환과 운영 데이터 적용**은 완료됐다. 다만 장기요양을 실제 `prepare-draft` 저장 경로에 태운 운영 작성 표본은 아직 만들지 않았으므로, 이 단계를 전체 category/content-type fallback 제거의 승인으로 확대하지 않는다. 4.3D도 계속 보류한다.

### 장기요양 실제 저장과 periodic current-value 계약 — 2026-10-02 20:14~20:29 KST

제한적 4.3C 배포 이후 지금 실행 가능한 운영 검증을 추가로 완료했다.

- **장기요양보험 실제 draft #856:** 기존 root 홈페이지 대신 국민건강보험공단의 장기요양 신청절차, 급여 이용안내, 복지용구 급여기준 세 공식 페이지를 직접 source로 사용했다. 수동 GPT-5.6 Sol 작성 bundle의 deterministic preflight와 동일 6항 semantic review가 `ready`였고, `prepare-draft` 저장 직전 `source_fetch_requests=3`, `source_receipt_refetch=3`으로 세 source를 모두 network refetch했다. 수동 작성이므로 Gemini 이미지 생성은 호출하지 않고 기존 로컬 JPEG를 `--image-path`로 전달했다.
- #856의 첫 Rank Math title/description은 bundle 준비 과정의 PowerShell 한글 입력 인코딩 문제로 `?`가 저장된 것을 즉시 readback에서 발견했다. live 본문 SHA `efa33d7310c38c607c328cd0a68302ad2884ea007ed7489a0a62304815b2d3a6`를 CAS 조건으로 `edit-post`를 실행해 **본문·제목·카테고리·대표이미지는 바꾸지 않고 SEO 두 필드만 정상 한글로 복구**했다. 수정 전후 content SHA는 동일하고, 수정 run도 live-state source 3/3을 다시 refetch했다.
- **독립 periodic-current 사례 #474:** 한국가스공사 현행 `사회적 배려대상자` 페이지에서 산업통상부고시 제2025-024호 기준 월 경감 한도가 `동절기(12~3월)`와 `동절기제외(4월~11월)`로 반복 구분되는 것을 fresh source로 확인했다. 이 값은 상시 제도 안에서 기간별로 달라지는 현재값이므로 실버론의 분기 금리와 같은 상위 문제 유형이다. 다만 공식 문구에 연도가 없는 반복 구간은 자동으로 특정 연도에 귀속시키지 않는다.
- 이 두 번째 실제 사례를 근거로 `temporal_source.current_value_period` 계약을 추가했다. 이 계약은 `policy-current + evergreen` 글 안의 현재값만 `{start_date, end_date, evidence}`에 묶으며, exact 공식 인용에 연도+월 범위 또는 분기 표기가 있어야 한다. 기간 종료는 **현재값 재검토 기한**이지 글 전체의 만료가 아니므로 30일 최소 lifetime이나 WordPress `expires_at`을 적용하지 않는다. 사용자가 만든 날짜, publication date, 연도 없는 반복 구간으로 기간을 추정하지 않는다.
- **실버론 재판정:** 국민연금공단 신청방법 원문은 `상시 신청 가능(매년 대부금 예산범위 내에서 접수)`이라고 명시하고, 금리 원문은 `연 3.21%(2026년 10월 ~ 12월)` 및 `2026년 4분기 기준이며, 매 분기 변경`이라고 명시한다. 따라서 brief를 `evergreen + policy-current + requires_live_state=true`, `useful_until=null`로 바꾸고 현재 금리만 `2026-10-01~2026-12-31` current-value period에 묶었다. 기존의 `temporal_source_not_bound` / `availability_not_verified`는 예외 없이 사라졌다.
- **실버론 실제 draft #858:** 새 계약의 실제 `prepare-draft`가 `ready`로 저장됐고 save-time counters는 `source_fetch_requests=4`, `source_receipt_refetch=4`였다. draft는 welfare(term 3), 대표이미지 #859, Rank Math 한글 메타 정상이며 `expires_at` 계열 WordPress meta는 없다. 즉 글 전체를 12월 31일에 만료시키지 않으면서 현재 4분기 금리만 기간 바인딩하는 구조가 실제 저장에서도 유지됐다.
- 자동 스케줄러를 위해 실버론 brief에 `requires_current_value_period=true`를 명시하고, writer가 source fetch 직후 현재 날짜를 포함하는 exact 연도+월 범위 또는 분기를 결정론적으로 추출해 temporal contract에 주입하도록 했다. exact period가 없거나 서로 다른 active period가 충돌하면 `current_value_period_unverified`로 HOLD한다. 연도 없는 `12~3월` 같은 반복 구간만으로는 자동 기간을 만들지 않는다.

이 후속 작업으로 **장기요양 category false HOLD와 실버론 current-value false HOLD는 모두 의미를 보존한 일반 계약으로 해소**됐다. 다만 4.3C의 나머지 fallback 전체 제거는 만료된 기존 brief까지 재검토한 결과가 없으므로 아직 확대하지 않는다. 다음 정규 scheduler 표본은 2026-10-03 08:00 KST 이후에만 확인할 수 있고, 4.3D discovery 전환은 이 정규 표본과 4.3C 결과를 분리해 검토한다.

### current-value 계약 운영 배포 — 2026-10-02 20:38~20:39 KST

후속 current-value 계약은 최신 `origin/main`의 별도 refactor 12개를 먼저 반영한 격리 worktree에서 다시 검증한 뒤 운영에 배포했다. 최신 트리 전체 회귀는 **822 tests OK, skipped=1**이며 `git diff --check`도 통과했다.

- release: `/home/ubuntu/releases/editorial-stage4-current-value-20261002-203819`
- 코드 rollback manifest: `/home/ubuntu/agent-publisher/backups/editorial-20261002T113851Z/manifest.json`
- 운영 SHA256은 `editorial.py=ba74680b1676292151c59f239082fcb30cb323050f023a7a6b31b3c62bddf104`, `editorial_writer.py=edcd778921e71d07ac1293689f364ae84ee41df543fd573ac31aa45bd625741b`, `temporal_validation.py=6d86d2f1e6f8f11db3bdc0268896062a9525ce738a190e9da5e540871c21f387`, `volatility.py=6f8f76251c3a4cac067d963f8e67a7e774699dfbc95a5c82e8a2cc02604d220c`이며 local release와 일치한다.
- 운영 `search_briefs.json`은 전체 파일을 덮어쓰지 않았다. 장기요양과 실버론 두 reviewed row만 교체했고 나머지 11행은 구조적으로 완전히 동일함을 확인했다. data backup은 `/home/ubuntu/agent-publisher/backups/current-value-briefs-20261002T113921Z`다.
- data SHA는 적용 전 `5b9329af4e9ffb35232dc49245493a668f578597aa7b9e5eb58bc24ad6e6dea4`, 적용 후 `d52b848246a2dbf3b088ee044e76792808f0c12414dd685c6d25d2cde0696567`이다. 두 row의 `reviewed_at`은 실제 재검토일 `2026-10-02`로 맞췄다.
- 장기요양 row는 generic root 대신 실제 작성에서 검증한 NHIS 신청절차, 급여 이용안내, 복지용구 고시 세 URL을 사용한다. 운영 fresh fetch 결과는 각각 1,629자, 2,143자, 11,537자였고 source SHA도 수동 운영 표본과 일치했다.
- 실버론 row는 네 NPS 세부 페이지를 direct official source로 사용하고 `requires_current_value_period=true`를 명시한다. 운영 fresh fetch 후 자동 추론은 `{start_date: 2026-10-01, end_date: 2026-12-31}`과 NPS의 금리 월 범위·4분기 인용 두 개를 반환했고 `validate_current_value_period()`는 빈 reason 목록을 반환했다.
- 운영 readback에서 두 brief 모두 `topic_reasons()==[]`, migration conflict `[]`이며, `main.py --help`의 현행 8개 category도 그대로 유지됐다.

이 시점에서 지금 즉시 수행 가능한 4.3C 작업은 모두 끝냈다. category false HOLD, live-state save-time refetch, current-value claim의 bounded 기간, 자동 writer의 exact-period 주입까지 운영 경로에서 확인했다. **전체 legacy fallback을 지금 제거하지 않는 이유는 남은 기술 결함이 아니라, review window가 만료된 기존 brief들을 자동 재승인하지 않는 정책과 다음 정규 scheduler 표본이 아직 미래라는 점**이다. 따라서 4.3C의 전면 fallback 제거와 4.3D discovery 전환은 2026-10-03 08:00 KST 정규 실행 결과를 확인한 뒤 별도 변경으로 진행한다.

### 2026-10-04 정규 scheduler 재감사와 제한적 4.3D 전환

10월 3일·4일 운영 cron과 당시 배포 revision을 실제 로그·release backup으로 다시 대조했다. 운영 cron은 계속 `0 8 * * * /home/ubuntu/agent-publisher/run_daily.sh`이며, 10월 3일 08:00 실행은 `ea36c6d` revision에서 8개 카테고리를 모두 순회했지만 current brief가 없어 `candidates=0`, `errors=0`으로 끝났다. 10월 4일 08:00 실행은 `3ca7845` revision에서 Growth Planner가 `no_actionable_existing_or_eligible_new_topic`을 반환해 Radar 이전에 정상 종료됐다. 두 정규 실행 모두 파이프라인 안정성은 확인했지만 lifecycle별 discovery 분기를 실제 후보로 통과하지는 않았다.

운영 `search_briefs.json`도 재검사했다. 총 13개 중 review window가 현재 유효하면서 explicit volatility metadata가 있는 row는 3개뿐이며 모두 `policy-current + evergreen`이다. 나머지 10개는 explicit volatility가 없고 review window가 만료됐다. 따라서 이 10개를 migration report 제안값만으로 재승인하거나 legacy `content_type`/category fallback을 제거하는 것은 여전히 금지한다. **4.3C 전면 fallback 제거는 계속 NO-GO**다.

다만 4.3D는 현재 동작을 보존하는 좁은 단계로 진행할 근거가 충분하다. `agents.volatility.discovery_mode()`를 단일 routing 계약으로 추가해, explicit `timeless-procedure`/`policy-current`는 공식 source 직행, explicit `annual-policy`/`seasonal`/`one-off`는 news discovery를 사용한다. `volatility`가 없는 row는 기존 `content_type=evergreen → direct`, `dated → news` fallback을 그대로 유지하고, 잘못된 explicit volatility는 discovery에서 fail-closed한다. Radar와 Curator가 같은 helper를 사용하므로 producer/consumer drift도 막는다.

현재 운영 데이터에서는 이 전환이 동작상 중립이다. 유효한 explicit 3개는 기존에도 `evergreen`이라 direct였고 새 계약에서도 `policy-current`라 direct다. metadata가 없는 10개는 기존 routing을 그대로 사용한다. 따라서 이번 변경은 만료 legacy row의 재채택이나 lifetime/category gate 완화를 포함하지 않는다. 실제 정규 scheduler가 lifecycle 분기를 통과했다는 E2E 증거는 향후 합법적으로 reviewed+growth-eligible candidate가 Radar에 도달할 때 별도로 기록한다.
