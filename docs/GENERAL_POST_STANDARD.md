# Bloguito 일반 정보 포스트 표준

이 문서는 도시별 월간 행사 포스트가 아닌 **생활정보, 정부서비스, 복지, 세금, 건강, 비용 비교, 조회·신청·계산형 정보글**의 현행 작성·수정 규약이다. 모든 글에 공통인 출처 신선도, 독립 검토, WordPress 저장 안전성은 [EDITORIAL_SYSTEM.md](EDITORIAL_SYSTEM.md)를 함께 적용한다. 행사 일정형 글은 [EVENT_POST_STANDARD.md](EVENT_POST_STANDARD.md)를 사용한다.

## 1. 기본 목표

- 하나의 구체적인 검색 질문을 제목과 첫 문단에서 바로 해결한다.
- 독자가 결정에 필요한 가격·비용, 대상, 기한, 비교 수, 조회·계산·신청 경로를 가능한 한 위쪽에 둔다.
- 공개되어 확인 가능한 자료를 독자에게 다시 찾아보라고 넘기지 않는다. 원문이 PDF·첨부표·하위 공고를 가리키면 작성자가 직접 읽고 필요한 값을 추출한다.
- 근거가 없는 숫자, 현재 가능 상태, 자격 판정, 이유·조언을 만들어내지 않는다.

## 2. 권장 정보 구조

필요한 요소만 사용하며 같은 답을 여러 상자와 문단으로 반복하지 않는다.

1. 제목
2. 짧은 `lead`와 고정 라벨 **한눈에 보기**
3. 필요한 경우 `overview` 표
4. 대상·예외 또는 상황별 분기(`eligibility`, `comparison`)
5. 실제 행동 순서가 있을 때만 `procedure`
6. 실패·문의·예외(`exceptions`)
7. 새로운 판단을 돕는 경우에만 FAQ
8. 검토된 관련 글
9. 공식 출처

`procedure`만 STEP 번호를 사용한다. 비교·조건·일정·FAQ를 단계처럼 번호 매기지 않는다.

## 3. 구조화 원고 계약

일반 정보글 writer, validator, renderer는 같은 필드를 지원한다.

- `lead`, 일반 문단, FAQ 답변: `text`, `evidence`, `answers`, 선택적 `emphasis`, 선택적 `calculations`
- section: `heading`, `paragraphs`, 선택적 `kind`, `table`, `facts`, `image`, `location`, `actions`, `official_links`
- 표 행과 `facts`도 `evidence`, `answers`, 선택적 `calculations`를 가질 수 있다.
- `lead_image`: 검토된 HTTPS 이미지 URL, ALT, width, height
- `official_navigation`: 최종 행동 화면이 아닌 검증된 공식 누리집 메뉴 경유 안내
- `related_posts`: 검토된 내부 관련 글 최대 2개

지원되는 계산은 validator가 허용한 결정론적 연산만 사용한다. 계산 metadata가 존재한다고 근거 없는 수치가 허용되는 것은 아니다. 모든 입력과 결과는 해당 operation의 검증 규칙을 통과해야 한다. 공식 표가 `천원` 단위로 제공되는 경우에는 원문의 천원 값이 evidence에 있고 표시 금액이 정확히 `원문 값 × 1,000`일 때만 `thousand_won_to_won` 단위 변환을 사용할 수 있다.

`emphasis`는 이미 검토된 문장 안에 존재하는 짧은 구문만 강조한다. 강조 때문에 문구나 의미를 바꾸지 않는다.

## 4. 표와 숫자

- 둘 이상의 선택지·금액·조건을 같은 기준으로 비교할 때 표를 우선 검토한다.
- 표에는 `caption`, 의미 있는 열 제목, 행별 `evidence`와 `answers`를 둔다.
- 긴 주의사항과 예외는 셀에 압축하지 말고 문단으로 둔다.
- 날짜, 금액, 단위, 비율, 연령, 개수는 연결된 evidence 또는 허용된 계산으로 증명한다.
- 공식 정액이 없는 가격 비교는 `reference` 출처를 사용할 수 있지만 공식 정책·자격·법적 조건과 섞지 않고 참고값임을 밝힌다.
- 독자에게 보이는 목록·라벨에는 가운데점 대신 쉼표 또는 자연스러운 연결 표현을 사용한다. evidence 원문은 그대로 보존한다.

## 5. 행동 링크와 공식 메뉴 안내

`sources.actions`는 조회·신청·예매·구매·설치 등 클릭 직후 실제 행동을 시작할 수 있는 검증된 목적지만 사용한다. 기관 메인 페이지, 소개·보도자료·정책 설명 페이지를 행동 버튼으로 만들지 않는다.

최종 서비스 화면을 직접 검증할 수 없지만 공식 누리집의 메뉴 경로가 확인된 경우 `plan.official_navigation`을 사용할 수 있다. 이 링크는 정보성 메뉴 안내이며 행동 CTA가 아니다. 같은 URL을 행동 CTA와 메뉴 안내로 동시에 표시하지 않는다.

## 6. 관련 글

- 관련 글은 현재 공개 중이고 독자의 **다음 질문**을 실제로 해결하는 글만 최대 2개 검토한다.
- `plan.related_posts`에 ID, 라벨, 정확한 `https://lifeinfo24.org/?p=ID`를 기록한 뒤 semantic review에 포함한다.
- 적절한 글이 없으면 빈 배열로 둔다.
- renderer는 로컬 목록이나 제목 유사도만 보고 관련 글을 추가하지 않는다. 후보 탐색은 review 이전 단계에서만 수행한다.
- 기존 공개 글에 검증된 내부 링크가 있으면 수정 과정에서 실수로 제거하지 않는다.

## 7. SEO와 제목

- `primary_keyword`는 여러 단어를 나열한 태그 묶음이 아니라 하나의 짧은 핵심 검색 구문으로 정한다.
- 신규 글과 전면 개편 글은 가능한 경우 `seo.title`, `seo.description`을 함께 검토한다.
- Rank Math 점수는 공개 게이트가 아니다. 정확성·검색 의도·가독성을 해치면서 점수를 올리지 않는다.
- 기존 공개 글의 canonical URL은 별도 마이그레이션 지시가 없으면 유지한다.

## 8. FAQ와 마무리

FAQ는 본문과 똑같은 한 문장을 다시 묻기 위한 개수 채우기가 아니다. 적용 예외, 다른 행동 경로, 실제 막힘처럼 새로운 판단을 돕는 질문만 사용한다. 답은 자체 완결적이어야 하며 “위 표를 보세요”, “공식 사이트에서 확인하세요”로 대체하지 않는다.

일반 정보글에 별도의 결론 문단이 필요하다면 독자의 다음 행동을 짧게 정리한다. `lead`와 overview 내용을 다시 반복하지 않는다.

## 9. 기존 글 수정

- 단순 표현·정리 변경이고 기존 evidence 범위를 넘지 않으면 Fast 경로를 사용한다.
- 제목, brief, source, CTA, 숫자·조건, SEO 사실 범위가 바뀌면 Standard 검토를 사용한다.
- Standard 수정에서도 변경되지 않고 아직 신선한 source snapshot은 재사용할 수 있다. 새 source, 변경 source, stale source, 현재 상태를 담은 source는 다시 확인한다.
- 공개 글은 원본 SHA, 상태, 제목/slug 보존 조건을 확인하고 backup → CAS 저장 → readback 검증을 거친다.
- 사람이 직접 작성한 excerpt는 보존한다. 빈 excerpt 또는 renderer가 만든 기존 lead excerpt만 검토된 새 lead로 갱신할 수 있다.

## 10. QA 범위

- 문구·데이터·메타데이터만 바뀌고 HTML 구조가 그대로면 결정론적 validator와 저장 후 readback을 기본으로 한다.
- 표 열/행 구조, 목차, renderer, CSS, 접근성 구조가 바뀌면 모바일·데스크톱·확대·키보드 QA로 확대한다.
- CTA 목적지가 바뀌면 실제 도착 화면과 버튼 동작을 확인한다.
- 대표 이미지 규칙은 [FEATURED_IMAGE_STANDARD.md](FEATURED_IMAGE_STANDARD.md)를 따른다.
