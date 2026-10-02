# Bloguito 행사 일정형 포스트 표준

이 문서는 **한 도시·지역의 여러 행사, 축제, 체험을 한 달 단위로 비교하는 일정형 포스트**의 전용 확장 규약이다. 공통 편집 규약인 `EDITORIAL_SYSTEM.md`를 대체하지 않으며, 충돌하면 공통 규약의 더 엄격한 안전 기준을 우선한다.

대전광역시 2026년 10월 행사 Draft #641을 실제로 작성·수정하면서 확인된 실패 사례를 재발 방지 규칙으로 승격했다. 부산·대구·광주·세종 등 기존 Gemini 초안에도 다음 **Standard revision** 때 이 규약을 적용한다.

## 1. 적용 대상과 버전

다음 조건을 모두 만족하는 글에 적용한다.

- 한 도시·지역의 서로 다른 행사 2개 이상을 한 글에서 비교한다.
- `brief.content_type = "dated"`다.
- `temporal_source.multi_event_schedule = true`를 사용한다.
- 콘서트 한 공연의 지역별 회차 목록이 아니라 지역 행사·축제·공공 체험 일정 가이드다.

새로 표준화하는 bundle은 `brief.event_post_standard_version = 1`을 기록한다. 기존 reviewed bundle은 단순 조회만으로 강제 마이그레이션하지 않고, 다음 **Standard** 수정에서 공식 source를 다시 확인한 뒤 v1로 전환한다.

이 버전 필드는 형식만 붙이는 배지가 아니다. v1을 선언한 bundle은 아래의 event-name binding, SEO alignment, section-scoped CTA, 문장부호, 과거연도 이미지 표시, 결정지원 최소구조 검사를 모두 통과해야 한다.

## 2. 초안 재사용 원칙: Gemini는 골격, 최종 원고는 재검증

기존 Gemini Draft를 전부 버리고 처음부터 다시 쓰는 것을 기본으로 하지 않는다. 다음 자산은 **검증 후 재사용 후보**다.

- WordPress post ID와 draft 상태
- 행사 후보 목록과 섹션 순서
- 표·목차·위치 카드 등 공통 레이아웃
- 공식 URL 후보
- 기존 WordPress 미디어 중 출처와 화질이 확인된 이미지
- 이미 검증된 CTA 목적지
- 관련 글 후보와 SEO 메타 초안

반대로 Gemini 문장 자체, 행사 프로그램·무료 여부·신청 가능 여부·운영시간·주차 팁은 **현재 공식 자료와 대조하기 전에는 사실로 승계하지 않는다.**

기존 Draft 개선 절차는 다음 순서로 고정한다.

1. 현재 WordPress 상태·본문 SHA·reviewed manifest 존재 여부를 확인한다.
2. 행사 후보마다 `유지 / 사실 수정 / section 재작성 / 행사 제거·교체`로 분류한다.
3. 날짜·장소뿐 아니라 비용, 운영시간, 신청, 프로그램, 대상 조건을 현재 공식 자료에서 각각 다시 확인한다.
4. 기존 레이아웃은 쓸 수 있으면 유지하되, 부족한 행사 section은 문장 단위 교정보다 **section 단위 재작성**을 우선한다.
5. 이미지·CTA·지도·SEO를 표준에 맞게 다시 평가한다.
6. `event_post_standard_version = 1`과 명시적 `event_name` binding을 적용한다.
7. Standard full review, source freshness, CAS 저장, readback, browser QA를 완료한다.

reviewed manifest가 있는 기존 글은 `edit-post` Standard 경로를 우선한다. manifest가 없는 legacy draft는 정규 legacy replacement 경로의 조건을 만족할 때만 교체하며, WP-CLI나 임시 PHP로 검증을 우회하지 않는다.

## 3. 행사 선정과 공식 근거

### 현재 연도 사실

각 행사에는 최소한 **행사명, 시작일, 종료일**을 현재 연도 공식 source의 실제 연속 인용으로 결합한다. `multi_event_schedule`의 날짜 근거는 무료·유료, 접수 중, 현장 입장 가능, 재고·좌석, 프로그램 운영을 자동으로 증명하지 않는다.

다음 항목은 언급할 때 각각 근거를 확인한다.

- 운영시간·입장마감
- 비용·무료 여부
- 사전신청·현장접수·예약 여부
- 연령·참여 대상
- 실제 프로그램·전시·공연·체험
- 모집 인원·마감 상태
- 주차·셔틀·교통 통제처럼 운영에 영향을 주는 실전 정보

공식 자료가 제공하지 않는 값을 표의 빈칸을 채우기 위해 추측하지 않는다. `미표기`, `확인하지 못했다`, `자료를 찾지 못했다` 같은 제작 메모도 독자 본문에 넣지 않는다. 독자가 알아야 할 공식적인 제한이 실제로 존재할 때만 자연스러운 독자용 문장으로 설명한다.

### 이전 연도 자료

이전 회차의 사진과 프로그램은 다음 조건에서만 참고할 수 있다.

- 2026 확정 프로그램과 섞어서 현재 프로그램처럼 쓰지 않는다.
- 본문에는 `지난 회차`, `2025 행사 기준`처럼 시점을 분명히 구분한다.
- 이전 연도 사진 caption에는 **연도 + 참고 성격**을 함께 쓴다.

예: `2025 행사 현장 사진, 2026 행사 분위기 참고`

이전 연도 자료는 현재 연도 날짜·비용·신청 상태의 근거를 대체할 수 없다.

## 4. 상단 구조: 독자가 먼저 비교할 수 있어야 한다

행사 일정형 글의 기본 순서는 다음과 같다.

1. 제목
2. `한눈에 보기` lead
3. **행사 비교 overview**
4. 행사별 상세 section
5. 필요한 FAQ
6. 관련 글
7. 공식 출처

독자가 행사별 상세 정보만으로 충분히 판단할 수 있으면 `어떤 행사를 고를까`, `일정이 겹칠 때 선택 기준` 같은 별도 조언 section을 만들지 않는다. 실제로 사용자가 비교 조언을 요청했거나 확인된 제약을 따로 비교해야 할 때만 `brief.allow_selection_guide = true`를 명시하고 추가한다.

첫 overview는 `kind: "overview"`와 비교표를 기본으로 하며 모바일 카드 렌더를 활성화한다. 표만 보고도 1차 선택이 가능하도록 다음 의미를 포함한다.

- 날짜·기간
- 행사명
- **무엇을 볼 수 있고 무엇을 할 수 있는지**
- 필요할 때 티켓·예매·비용·운영시간처럼 뜻이 분명한 조건
- 장소

열 이름은 원고에 맞게 바꿀 수 있지만 날짜·행사·장소와 **결정에 도움이 되는 구체적인 열 하나 이상**은 유지한다. `볼거리와 체험`, `프로그램`, `티켓과 예약`, `운영시간`처럼 독자가 뜻을 바로 이해할 수 있는 표현을 쓴다. `확인된 실전 조건`, `실전 정보`, `판단 포인트`, `추천/핵심`, `핵심 관전 포인트`처럼 작성자만 의미를 아는 추상적인 열 이름은 사용하지 않는다. `무료 관람`, `먹거리 축제`처럼 성격을 거의 설명하지 않는 짧은 문구만으로 핵심 열을 채우지도 않는다.

행사 개수와 본문 단어 수는 품질 기준으로 고정하지 않는다. `5대 행사`, `7대 축제`, `1,200단어 이상` 같은 과거 일회성 작업 기준을 새 글의 공통 규칙으로 승격하지 않는다.

## 5. 행사 section의 계약

v1 행사 상세 section에는 `event_name`을 넣어 `temporal_source.event_entries[].name`과 **정확히 1:1로 결합**한다. overview·목적별 비교·FAQ용 section에는 `event_name`을 넣지 않는다.

각 `event_name` section은 본문 설명 외에 **대표 이미지 1개와 위치 카드 1개를 반드시 포함**한다. 이미지나 위치 정보가 없는 상태는 완성된 행사 section으로 보지 않는다.

행사 section은 날짜·장소를 다시 적는 것으로 끝나면 안 된다. section만 읽고 독자가 최소한 다음을 판단할 수 있어야 한다.

> - 이 행사는 무엇인가?
> - 가면 무엇을 볼 수 있는가?
> - 무엇을 직접 해볼 수 있는가?
> - 어떤 방문 목적에 잘 맞는가?
> - 비용·신청·운영시간 중 어떤 실전 조건을 알아야 하는가?
> - 방문 전에 알아둘 팁이 있는가?

모든 항목을 억지로 한 문단에 채우지는 않는다. 공식 자료에 없는 대상·취향을 추정해서 `가족에게 추천`, `커플에게 최고`라고 단정하지 않는다. 대신 실제 프로그램을 근거로 `만들기 체험을 원하는 가족`, `게임·캐릭터 콘텐츠에 관심 있는 방문객`처럼 **방문 목적과 확인된 활동을 연결**한다.

### 좋은 section의 예

- 콘텐츠페어: `공공캐릭터, 인디게임, TCG, 코스프레, AI 아트 스쿨`처럼 실제 볼 것·할 것을 구체적으로 제시한다.
- 빵축제: 2026 확정 날짜·오픈시간과 2025 프로그램 사례를 분리하고, 과거 시식·구매·체험·공연을 `지난 회차 참고`로만 사용한다.

### 부적합한 section의 예

- `10월 17~18일 엑스포과학공원에서 열리는 먹거리 축제입니다.`로 끝나는 설명
- 일정표를 문장으로 반복하고 프로그램·체험·방문 판단 정보가 없는 설명
- 공식 자료에서 찾지 못한 운영시간을 `미표기`로 넣은 사실 카드
- 독자에게 `공식 홈페이지에서 프로그램을 확인하세요`라고 조사 업무를 돌려보내는 설명

## 6. 행사 이미지

본문 행사 이미지는 **정보 장식이 아니라 방문 판단 자료**다. 사용권이 확인된 이미지 안에서 우선순위는 다음과 같다.

1. 현재 회차의 공식 현장 활동 사진
2. 이전 회차의 공식 체험·공연·전시·부스·관람객 사진
3. 행사장 분위기를 보여주는 공식 사진
4. 현재 회차 공식 고해상도 포스터

후보 탐색은 먼저 공식 주최·지자체·공공기관·관광 아카이브·보도자료·공식 홍보물에서 수행한다. 검색으로 찾을 수 있는 공식 이미지가 있으면 생성 이미지보다 우선하며, 공공누리 제1유형처럼 상업적 재사용 조건이 명확한 자료를 우선한다. 상업적 이용 제한이 붙은 제2·4유형 자료는 광고·수익화 블로그 본문 이미지로 복제 사용하지 않는다.

한 행사 이미지 하나를 찾느라 전체 편집을 오래 멈추지 않는다. **공식·재사용 가능 활동 사진 탐색은 행사당 기본 5분을 상한으로 두고**, 그 안에 적합한 후보가 없으면 아래의 안전한 fallback 순서로 전환한다. 후보를 찾았으면 작업별 `download_*`, `process_*`, `image_years.py` 같은 일회성 스크립트를 만들지 말고 `scripts/event_post_tool.py images` manifest에 `source_url`, `source_year`, `rights`, `depiction`을 기록해 다운로드/정규화/contact sheet 생성을 한 번에 수행한다. `rights`는 bundle과 동일한 `generated_original|site_owned|open_license|permission_granted` 값만 쓰며, `open_license`/`permission_granted`에는 공식 권리 근거 `rights_url`을 함께 기록한다. `공공누리 제1유형` 같은 사람이 읽는 라이선스 이름은 선택 `license_label`로 남길 수 있다. 도구는 권리 의미를 추측하지 않으므로 rights 판단 자체는 공식 페이지를 읽은 사람이 책임진다.

풍경만 보이는 사진, 행사를 식별하기 어려운 이미지, 저해상도 thumbnail, 출처를 확인할 수 없는 임의 이미지는 사용하지 않는다. **공식 페이지에 사진이 있다는 사실만으로 재사용 권한이 생기지는 않는다.** 상업적 재사용 가능 여부가 불명확한 공식 사진·포스터는 Bloguito에 복제 업로드하지 않는다.

사용권이 확인된 공식 활동 사진을 충분히 검색했는데도 적합한 자료를 구하지 못한 경우에만 공식 프로그램 사실에 근거해 Bloguito가 **직접 제작한 원본 안내 이미지**를 사용할 수 있다. 생성 이미지는 실제 이미지 시각 검토를 통과해야 하며, 이미지 생성기나 시각 검토가 실패했다고 해서 Pillow 도형·막대기 사람·단순 아이콘 조합 같은 저품질 로컬 폴백을 본문 소개 이미지로 자동 채택하지 않는다. 이 경우 이미지 교체를 보류하거나 사용권이 확인된 차선의 공식 자료를 다시 찾는다. 생성 이미지를 쓰면 실제 현장 사진처럼 보이게 설명하지 않고 caption에 `공식 프로그램을 바탕으로 제작한 행사 안내 이미지`처럼 제작물임을 표시한다. `image.source_id`는 장면의 근거가 된 현재 공식 source를 가리키고 `image.rights = "generated_original"`을 기록한다.

이미지마다 다음을 확인한다.

- HTTPS source와 공식 운영 주체
- `image.rights`에 `generated_original`, `site_owned`, `open_license`, `permission_granted` 중 하나를 기록
- `open_license`·`permission_granted`는 실제 이용조건을 확인할 `image.rights_url` 기록
- v1 구조화 이미지의 실제 촬영·포스터 연도를 `image.year`에 기록
- 실제 원본 해상도·화질
- alt가 사진 자체를 설명하는지
- caption이 행사·연도·참고 여부를 정확히 말하는지
- 이전 회차 사진이면 연도와 `참고` 성격이 표시됐는지
- desktop/mobile에서 crop·깨짐·과도한 확대가 없는지
- URL이 실제로 200 응답하고 hotlink 403 또는 만료 URL이 아닌지

사람이 실제로 체험·공연·전시를 즐기는지, 사진이 풍경뿐인지, 사진의 시각적 품질이 충분한지는 정규식으로 안전하게 판정하기 어렵다. 따라서 **실제 이미지 시각 검토는 human/browser QA 필수 항목**으로 남긴다.

대표 이미지는 별도의 `featured_image_policy`를 그대로 따른다. 본문 현장 사진 규칙과 대표 커버 규칙을 혼동하지 않는다. 현재 policy는 대표 커버의 **주 제목에 일반 UI 고딕이 아닌 검증된 한글 display font를 요구**하며, display font를 사용할 수 없을 때 기본 고딕으로 조용히 대체하지 않고 생성을 중단한다.

## 7. CTA와 지도

### 행사별 CTA

행사 한 곳에만 해당하는 신청·예약·구매 CTA는 **그 행사 상세 설명 바로 뒤**에 둔다. 상단 공통 CTA 영역으로 끌어올리지 않는다.

구조는 다음처럼 사용한다.

```text
sources[].actions = [{kind, label, url}]
plan.sections[].actions = [같은 검증된 action URL]
```

v1 일정형 글에서는 `booking`, `apply`, `purchase` action을 행사 section에 scope하지 않은 채 global CTA로 남기는 것을 허용하지 않는다. 소개·보도자료·홍보 페이지는 행동 버튼이 아니라 공식 출처다.

대전 #641의 `탄동천 탐사 신청`이 기준 사례다. 설명을 읽은 뒤 신청 버튼이 나오고, 상단 비교표 근처에는 같은 버튼이 나타나지 않는다.

### 지도

모든 v1 행사 section은 검증된 장소 또는 행사 구역을 바탕으로 위치 카드를 제공한다. 카드 첫 줄은 `📍 행사장 위치: 행사장명`처럼 행사장명을 제목과 한 줄로 표시한다. 공식 source에서 실제 주소를 확인한 경우에만 둘째 줄에 `주소: ...`를 표시하고, 주소가 행사장명과 같으면 반복 출력하지 않는다. 도로명주소가 공식 source에 없으면 억지로 추정하지 않고 `address`를 비워 행사장명만 보여준다. 지도 검색용 `query`는 화면에 별도 정보 줄로 반복하지 않는다. 카드는 카카오맵과 네이버지도 검색 링크를 제공한다. Google Directions는 현재 공통 renderer에서 제공하지 않는다. 여러 행사장을 한눈에 보여주는 인터랙티브 지도는 **선택 기능**이지 발행 품질 게이트가 아니다.

지도 SDK·API 키·복잡한 마커 UI 때문에 각 도시별 one-off 스크립트를 만드는 것보다, 독자가 실제 장소를 여는 단순 위치 카드를 우선한다.

## 8. 문체와 편집 규칙

독자 노출 문구 전체에 공통 편집 규칙을 적용한다.

- `전시,체험` → `전시, 체험`
- `먹거리,공연` → `먹거리, 공연`
- `.다음 문장` → `. 다음 문장`
- 가운데점 `·` 대신 쉼표나 자연스러운 연결 표현 사용
- 공식 source 원문과 evidence quote는 원문 표기를 보존
- URL, 날짜 범위, 시간 범위, 숫자 데이터 문자열은 문장부호 spacing lint의 예외로 취급

다음 제작 메모는 독자 본문에 노출하지 않는다.

- `미표기`
- `확인하지 못했다`
- `자료를 찾지 못했다`
- `추가 확인 필요`
- `편집자 메모`

정보가 없으면 억지 placeholder를 만들지 말고, 확인된 독자용 사실만 쓴다.

## 9. Rank Math와 검색 설계

행사형 글은 본문을 완성한 뒤 SEO를 덧붙이지 않는다. 작성 전에 다음 순서로 맞춘다.

`primary_keyword → SEO title → meta description → lead → 관련 H2`

v1의 기본 규칙은 다음과 같다.

- 짧은 하나의 primary keyword를 사용한다. 예: `10월 대전 행사`.
- exact keyword를 SEO title에 자연스럽게 포함한다.
- meta description에도 exact keyword를 한 번 포함한다.
- lead 첫 문장 또는 첫 문단에 exact keyword를 포함한다.
- 관련 H2/H3 하나에 exact keyword를 자연스럽게 포함한다.
- 본문 전체에 같은 문자열을 기계적으로 반복하지 않는다.
- 관련 공개 글이 실제로 도움이 될 때만 `related_posts` 1~2개를 검토한다.
- 기존 slug는 Rank Math 점수만을 이유로 바꾸지 않는다.

Rank Math는 **75점 이상을 실무 목표, 80점 이상을 양호**로 본다. 숫자 점수는 발행 게이트가 아니며, 100점을 위해 키워드 밀도를 억지로 높이거나 Content AI를 강제하지 않는다. 실제 점수는 WordPress 관리자 편집기에서 계산된 값을 관측했을 때만 기록한다.

## 10. 자동 검증과 사람 QA의 경계

### 결정론적 검증으로 막는 항목

- `dated + multi_event_schedule` 구조와 날짜 evidence
- v1 `event_name` 1:1 binding
- overview table과 모바일 카드 구조
- overview의 추상적인 열 이름 금지
- primary keyword와 SEO title/description/lead/H2 exact alignment
- 행사 section의 최소 설명과 활동·결정지원 신호
- 각 행사 section의 대표 이미지·위치 카드 존재와 이미지 권리 provenance
- 명시적 opt-in 없는 별도 선택·추천 comparison section 금지
- `booking/apply/purchase` CTA의 section scope
- 이전 연도라고 명시된 이미지 caption의 `연도 + 참고` 표시
- 독자 문구의 쉼표·마침표 뒤 공백 오류
- 독자용 제작 메모 노출
- 기존 source/action/location/image provenance 검사
- middle dot 금지, related_posts 최대 2개, 숫자·날짜 evidence 등 공통 validator 규칙

### 사람·브라우저 QA로 남기는 항목

- 각 section만 읽고 실제로 `갈지 말지` 판단할 수 있는가
- 프로그램 설명이 구체적이지만 과장되지 않았는가
- 추천 대상 표현이 근거 없는 인구집단 일반화가 아닌가
- 사진이 실제 활동 장면인지, 풍경만 있는지
- 사진 화질·crop·연도·출처가 시각적으로 적절한가
- CTA가 설명 직후의 자연스러운 위치에 렌더되는가
- desktop/mobile 표·이미지·CTA·위치 카드가 깨지지 않는가
- broken image/hotlink 403이 없는가
- Rank Math 실제 관리자 점수와 남은 실패 항목이 무엇인가

## 11. 저장과 최종 QA

기존 reviewed Draft 수정은 일반적으로 `edit-post` Standard를 사용한다. 콘텐츠·출처·CTA·SEO가 함께 바뀌는 행사 리라이트를 Fast로 억지 분류하지 않는다.

저장 전후에는 다음을 확인한다.

1. 최신 live content SHA 재조회
2. source freshness 또는 유효 receipt
3. full semantic review
4. `standard-event` actual-candidate preflight (`content + source + event contract`); 필요할 때 `event_post_tool.py validate ... --run-tests`로 event 3-file smoke만 추가
5. CAS 저장
6. saved content SHA readback
7. draft/public 상태와 제목 보존 확인
8. Rank Math meta readback
9. 대표 desktop + mobile browser QA
10. CTA 실제 도착 화면 smoke test
11. 모든 section image HTTP/렌더 확인
12. 카탈로그에 표시되는 메타가 바뀌었으면 `sync_post_catalog.py` 1회 실행

renderer·validator·공통 정책 코드를 바꾼 작업은 표적 테스트 뒤 전체 suite를 1회 실행한다. 개별 도시 원고만 수정했다고 전체 regression을 반복하지 않는다.

행사형 글의 반복 작업은 다음 공용 명령으로 묶는다.

```text
python scripts/event_post_tool.py validate <bundle.json> --post-id <ID> --expected-content-sha256 <SHA>
python scripts/event_post_tool.py images <image-manifest.json> --output-dir <task>/images/processed
python scripts/event_post_tool.py qa <bundle.json> --html-out <task>/qa.html --screenshot-dir <task>/qa
```

`validate`는 실제 후보 원고의 content/source/event contract를 검사하고, 기본 실행에서는 repository unit suite를 돌리지 않는다. `--run-tests`를 명시해도 event 전용 3개 파일만 smoke로 실행한다. 공통 Python/renderer/policy/test infrastructure를 수정한 개발 작업에서만 repository full regression을 별도로 수행한다. `qa`는 렌더 구조 검사와 대표 desktop/mobile screenshot 2장만 생성하며, 사진이 실제 활동 장면인지와 시각 품질은 사람이 최종 확인한다.

## 12. 금지되는 과거 관행

다음은 부산·대구·세종 초기 작업 기록에 있더라도 새 공통 표준으로 사용하지 않는다.

- 도시마다 `test_<city>_festival_post.py` 같은 일회성 테스트를 새로 만드는 것
- 5개·7개처럼 행사 개수를 고정하는 것
- 1,200단어 이상처럼 분량을 품질 게이트로 두는 것
- 모든 행사 글에 인터랙티브 카카오 지도를 의무화하는 것
- 공식 포스터·풍경 이미지만 채우고 실제 활동 정보를 생략하는 것
- 관련 글을 개수 채우기용으로 3개 이상 붙이는 것
- Rank Math 100점을 목표로 키워드를 반복하는 것
- Gemini 초안의 문장을 현재 공식자료 재검증 없이 그대로 승계하는 것

행사형 포스트의 핵심 품질 기준은 **행사 수, 글자 수, UI 장식 수가 아니라 독자가 각 행사에 갈지 말지 판단할 수 있는 검증된 정보의 밀도**다.
