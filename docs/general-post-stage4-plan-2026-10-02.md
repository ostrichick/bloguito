# 일반 정보 포스트 정책 최적화 4단계 후속 계획

**상태 (2026-10-02):** 4.1 일반/행사 writer schema 분리와 4.2 post-specific exception registry 분리를 구현·검증했다. 카테고리 8분류 개편과 병합 및 기존 회귀 문제 정리 후 4.3A/B까지 구현했다. 기존 brief 자동 변환은 하지 않았고 [volatility migration report](volatility-migration-report-2026-10-02.json)를 별도로 생성했다. 4.3C/D는 최소 한 릴리스 관찰 뒤 검토하며, 4.4는 계획 상태다.

1~3단계에서 일반 정보글의 writer/validator/renderer 계약을 맞추고, 정책 문서를 글 유형별로 분리했으며, bundle에 실제 적용되는 정책만 semantic review fingerprint와 모델 지침에 포함하도록 변경했다. Standard 수정의 source recheck도 draft/public 공용 planner로 통합했다.

4단계는 이 기반 위에서 **데이터 모델과 장기 유지보수 구조**를 정리한다. 한 번에 전부 바꾸지 않고 아래 4개 마이그레이션을 순서대로 진행한다.

## 4.1 일반/행사 writer schema 분리

**진행 상태:** 완료. 신규 generation은 `GeneralPlan`/`EventPlan`을 분리해 사용하고 기존 `Plan`은 저장된 reviewed bundle을 위한 호환 superset parser로 유지한다.

### 목표

일반 정보글 모델이 행사 전용 필드를 보지 않게 하고, 행사 글은 행사 표준에 필요한 추가 필드를 명시적으로 갖게 한다. 저장된 기존 bundle의 JSON 모양은 가능한 한 그대로 유지해 대규모 데이터 마이그레이션을 피한다.

### 설계

1. 공통 타입을 먼저 분리한다.
   - `BaseParagraph`: text, evidence, answers, emphasis, calculations
   - `BaseSection`: heading, paragraphs, kind, table, facts, image, location, actions, official_links
   - `GeneralPlan`: title, lead, sections, faq, lead_image, official_navigation, related_posts
2. 행사 전용 타입을 확장한다.
   - `EventSection`: `BaseSection` + `event_name`
   - 행사 지도에 필요한 검증 좌표는 event location 확장 타입에서 관리한다.
   - 이미지 rights/year처럼 일반 글에서도 의미가 있는 필드는 공통 타입에 남기고, 행사 표준은 필수 여부만 강화한다.
3. `policy_profile(bundle)` 결과로 writer response schema를 선택한다.
   - general → `GeneralPlan`
   - event → `EventPlan`
4. 기존 `event_post_standard_version=1` bundle은 compatibility adapter로 현재 JSON을 그대로 읽는다.

### 마이그레이션 원칙

- 기존 저장 bundle을 일괄 재작성하지 않는다.
- 먼저 **읽기 호환**, 다음 신규 작성 schema 분리, 마지막으로 오래된 bundle 감사 순으로 진행한다.
- 일반 글에서 event-only 필드가 이미 저장된 사례가 발견되면 삭제하기 전에 사용 여부를 조사한다.

### 완료 기준

- 일반 writer JSON schema에 `event_name`, event-only 좌표 요구가 노출되지 않는다.
- 행사 writer는 현재 Event Post Standard v1 테스트를 모두 통과한다.
- 기존 reviewed general/event bundle fixture가 새 parser에서 동일하게 render된다.
- 저장 HTML diff가 schema 분리만으로 발생하지 않는다.

## 4.2 post-specific exception registry 분리

**진행 상태:** 완료. dated 10건과 legacy procedure 1건을 `agent-publisher/data/policy_exceptions/`로 이동했고 기존 rule payload 동등성을 검증했다.

### 목표

`editorial_policy.json`에 누적되는 특정 게시물 예외를 독립 registry로 옮기고, 대상 글을 처리할 때만 읽는다. 예외의 생성 이유·활성 기간·종료 조건을 명시한다.

### 권장 구조

```text
agent-publisher/data/policy_exceptions/
  dated-posts.json
  legacy-procedures.json
```

각 항목은 최소 다음 필드를 갖는다.

- `id`
- `status`: active / expired
- `existing_post_id`
- 정확한 적용 조건(brief ID, category, content type, official URLs 등)
- `reason`
- `approved_on`
- `expires_on` 또는 명시적인 종료 조건

### 구현 순서

1. registry loader와 schema validator만 추가한다.
2. 현재 `dated_post_exceptions`, `legacy_welfare_procedural_exceptions`를 **값 변경 없이** 이동한다.
3. 기존 함수 `dated_post_exception()`과 legacy 예외 함수가 새 loader를 사용하게 한다.
4. `applicable_policy_rules()`는 현재 bundle과 정확히 일치하는 active 예외 한 건만 fingerprint에 포함한다.
5. expired 항목은 자동 적용하지 않고 역사 기록만 남긴다.

### 완료 기준

- 현재 허용되는 모든 예외 fixture의 PASS/HOLD 결과가 이동 전과 동일하다.
- 다른 post ID가 예외를 상속할 수 없다.
- unrelated exception 추가·수정이 일반 글 policy fingerprint를 바꾸지 않는다.
- 만료 예외가 자동으로 active 상태로 되돌아오지 않는다.

## 4.3 category 중심 freshness를 volatility 중심으로 전환

**진행 상태:** 4.3A/B 완료. lifecycle은 `timeless-procedure`, `policy-current`, `annual-policy`, `seasonal`, `one-off` 5종이며, 현재 상태 검증은 별도 `requires_live_state`로 분리한다. 기존 category/content-type fallback은 그대로 유지한다.

### 목표

`복지`, `생활정보` 같은 카테고리 자체보다 **주장의 시간 변동성**에 따라 useful lifetime과 source 재검증 강도를 결정한다.

### 현행 lifecycle 값

- `timeless-procedure`: 서비스 이용 경로·반복 절차처럼 기한이 없는 설명
- `policy-current`: 종료일은 없지만 법·정책·요금·급여 기준이 개정될 수 있는 현행 제도
- `annual-policy`: 최저임금, 연도별 세율·기준처럼 정기 개정되는 값
- `seasonal`: 예방접종, 명절·계절 지원처럼 특정 시즌에 유효
- `one-off`: 한 번의 공고·한시 사업·단일 일정

현재 판매·예매·접수·재고처럼 수시 변동하는 상태는 lifecycle enum과 분리해 `requires_live_state=true`로 표시한다.

### 구현된 도입 순서

1. 새 필드는 optional로 추가하고 기존 `content_type`/category/30일 규칙을 그대로 유지한다. **완료**
2. explicit metadata가 있는 bundle만 volatility contract를 policy fingerprint에 추가 결합한다. **완료**
3. 기존 글은 deterministic migration report로 후보값만 제안하고 자동 저장하지 않는다. **완료**
4. `requires_live_state=true`와 기존 live-state regex는 저장 전 network recheck를 강제하고 receipt reuse를 허용하지 않는다. **완료**
5. category 기반 규칙은 최소 한 릴리스 동안 fallback으로 유지한 뒤 제거 여부를 결정한다. **보류**

### 기본 정책 방향

- `requires_live_state=true`: 저장 직전 항상 관련 source를 network recheck. receipt로 현재 상태 검증을 생략하지 않는다.
- `annual-policy`, `seasonal`, `one-off`: useful_until과 적용 연도/기간을 강하게 검증한다.
- `timeless-procedure`: useful_until을 강제하지 않되 source·메뉴 경로가 바뀌면 새 검토가 필요하다.
- `policy-current`: useful_until을 새로 강제하지 않고 기존 source/review freshness와 category/content-type 안전 규칙을 계속 적용한다.

### 완료 기준

- category만으로 evergreen/dated가 결정되지 않는다.
- 기존 복지·세금·건강 fixture에서 안전 기준이 완화되지 않는다.
- live-state fixture는 반복 검증에서도 network recheck를 건너뛰지 않는다.
- migration report에서 자동 추론값과 사람이 확정한 값을 구분한다.

## 4.4 critical facts의 데이터와 엔진 분리

### 목표

`critical_facts.py`는 검증 엔진으로 유지하고 연도별·주제별 고정값을 versioned data로 분리한다. 복잡한 의미 판단까지 억지로 JSON 규칙으로 바꾸지는 않는다.

### 권장 구조

```text
agent-publisher/data/critical_facts/
  schema.json
  national-pension-2026.json
  minimum-wage-2027.json
  vaccination-2026.json
```

### 1차 데이터화 대상

- 특정 연도의 금액·비율·연령·날짜
- 허용된 명칭과 단위
- 정확한 공식 source ID/URL 요구
- 적용 시작·종료 연도

### 코드에 남길 대상

- 문맥에 따른 조건 충돌 판단
- 여러 source 간 우선순위
- 계산/표 구조 검사
- 예외 적용 여부와 fail-closed 제어

### 구현 순서

1. 현재 `critical_facts.py` 규칙을 declarative / procedural로 분류한다.
2. 단순 상수 규칙 하나를 pilot으로 데이터화한다.
3. 기존 unit test를 같은 입력으로 구·신 엔진에 동시에 실행해 결과 동등성을 확인한다.
4. 연도별 신규 값을 코드 수정 없이 registry 추가로 갱신할 수 있게 한다.
5. 충분히 단순한 규칙만 점진적으로 이동한다.

### 완료 기준

- 데이터 파일 schema validation 실패 시 fail closed 한다.
- 이전 critical-fact fixture의 이유 코드와 PASS/HOLD 결과가 유지된다.
- 연도별 값 변경 diff가 Python 로직 변경과 분리된다.
- 출처 없는 숫자를 registry 값만으로 본문에 새로 만들어낼 수 없다.

## 권장 실행 순서와 배포 단위

| 순서 | 작업 | 위험도 | 독립 배포 |
| --- | --- | --- | --- |
| 4.1 | General/Event schema 분리 | 중간 | 가능 |
| 4.2 | Exception registry 분리 | 낮음~중간 | 가능 |
| 4.3 | Volatility 기반 freshness | 높음 | 별도 릴리스 권장 |
| 4.4 | Critical facts 데이터화 | 중간 | 주제별 점진 적용 |

4.1과 4.2는 구조 이동이 중심이라 먼저 처리한다. 4.3은 실제 글의 유효기간·source refresh 판단을 바꾸므로 별도 작업과 전체 콘텐츠 fixture 감사가 필요하다. 4.4는 한 주제씩 작은 단위로 진행한다.

## 4단계 전체 종료 조건

다음 조건을 모두 만족하기 전에는 category 기반 기존 규칙이나 기존 critical-fact 코드를 제거하지 않는다.

1. 기존 reviewed bundle의 읽기 호환성이 유지된다.
2. 일반/행사 전체 fixture에서 의도하지 않은 HTML 변경이 없다.
3. 예외 적용 범위가 기존보다 넓어지지 않는다.
4. live/seasonal/annual 정보의 freshness 검사가 약해지지 않는다.
5. 전체 Python suite의 신규 실패가 없고, 기존 baseline 실패는 별도로 식별된다.
6. 실제 WordPress mutation 없이 dry-run/fixture 단계에서 migration 결과를 먼저 검토한다.
