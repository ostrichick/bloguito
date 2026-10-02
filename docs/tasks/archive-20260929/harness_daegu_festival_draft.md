# 🎯 Prompt Harness Specification: 2026 Daegu October Festivals & Events Draft Post

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #621(2026 전주 10월 축제 일정) 및 부산 10월 축제의 고품질 표준(요약 상자, 7대 축제 일정 비교표, 카카오맵 인터랙티브 지도 연동, 축제별 3대 필드 행사 요약 카드, 실시간 길찾기 버튼, 주차/교통 팁, FAQ, 내부 링크, 공식 출처)과 동일한 수준의 「2026 대구 10월 축제 및 행사 일정 총정리」 포스트 초안을 작성하여 WordPress에 임시글(`draft`)로 안전하게 등록하고, 카탈로그를 최신 동기화한다.
- **In-Scope Deliverables**:
  - `docs/harness_daegu_festival_draft.md`: 5대 하네스 사양 문서
  - `scripts/test_daegu_festival_post.py`: 포스트 HTML 구조, 7대 요약 카드, 카카오 지도, 가운데점 금지 규칙, 어휘 수 검증 단위 테스트
  - `tmp/daegu-october-festivals-20260928/bundle.json`: 구조화 번들 (metadata, sources, multi_event_schedule entries)
  - `tmp/daegu-october-festivals-20260928/bundle.html`: 완전한 시맨틱 본문
  - WordPress 임시글(`draft`) 등록 및 카탈로그 동기화 (`docs/POST_CATALOG.md`)
  - `docs/daegu-october-festivals-draft-2026-09-28.md`: 공식 출처 및 작업 결과 기록 문서
- **Strictly Out-of-Scope (Non-Goals)**:
  - `post_status`를 `publish`로 전환 금지 (기본 원칙: `draft`).
  - 기존 공개 글(#621, #598 등)이나 타 draft 글 일체 무단 변경 금지.
- **Forbidden Boundaries**:
  - 독자 노출 텍스트(제목, 소제목, 본문, 표, FAQ, CTA, 출처) 내 가운데점(`·`) 사용 금지 (쉼표 또는 자연스러운 접속 표현 사용).
  - 공식 출처에서 확인되지 않은 일정/비용 임의 추측 금지.

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **7대 핵심 축제 및 행사 메타데이터**:
  1. 제21회 대구국제오페라축제:
     - 일정: 2026.10.15(목) ~ 11.08(일)
     - 장소: 대구 북구 호암로 15 (대구오페라하우스)
     - 교통: 지하철 1호선 대구역 1번 출구 도보 15분 또는 시내버스 북구1번 환승
     - 좌표: 35.8821, 128.5956
  2. 2026 달성 100대 피아노:
     - 일정: 2026.10.03(토) ~ 10.04(일)
     - 장소: 대구 달성군 화원읍 사문진로1길 40 (사문진상설야외공연장)
     - 교통: 지하철 1호선 화원역 1번 출구에서 달성1번 시내버스 환승 후 사문진주막촌 하차
     - 좌표: 35.8268, 128.4682
  3. 2026 대구포크페스티벌:
     - 일정: 2026.10.03(토) ~ 10.04(일)
     - 장소: 대구 달서구 야외음악당로 180 (두류공원 코오롱야외음악당)
     - 교통: 지하철 2호선 두류역 14번 출구 도보 12분
     - 좌표: 35.8503, 128.5526
  4. 2026 대구힐링공연예술제:
     - 일정: 2026.10.09(금) ~ 10.11(일)
     - 장소: 대구 남구 대봉교 하단 신천 수변특설무대
     - 교통: 지하철 3호선 대봉교역 2번 출구 도보 3분
     - 좌표: 35.8569, 128.6053
  5. 2026 대구생활문화제:
     - 일정: 2026.10.10(토) ~ 10.11(일)
     - 장소: 대구 중구 동성로2길 80 (2.28기념중앙공원)
     - 교통: 지하철 1호선, 2호선 반월당역 13번 출구 도보 5분
     - 좌표: 35.8694, 128.5975
  6. 2026 대구콘텐츠페어:
     - 일정: 2026.10.16(금) ~ 10.17(토)
     - 장소: 대구 북구 엑스코로 10 (엑스코 서관 1홀)
     - 교통: 지하철 1호선 칠성시장역 3번 출구에서 시내버스 304, 306, 413, 653 환승
     - 좌표: 35.9064, 128.6139
  7. 2026 달성 대구현대미술제:
     - 일정: 2026.09.12(토) ~ 10.11(일)
     - 장소: 대구 달성군 다사읍 강정본길 57 (디아크 문화관 및 강정고령보 광장 일원)
     - 교통: 지하철 2호선 대실역 1번 출구에서 달성2번 버스 환승 또는 택시 5분
     - 좌표: 35.8459, 128.4632
- **Kakao Map SDK Integration**:
  - App Key: `dda896ffe09a01b73ac2592af1b07d97` (Post #621 실서버 검증 완료된 키)
  - Options: 단일 줄 인라인 JS, `\x3c` 및 `\x3e` 태그 이스케이프로 WordPress wpautop 오동작 방지
- **Rank Math Metadata Spec**:
  - Focus Keyword: `2026 대구 10월 축제`
  - Post Title: `2026 대구 10월 축제 및 행사 일정 총정리: 오페라축제 100대피아노 포크페스티벌 한눈에 보기`
  - SEO Title: `2026 대구 10월 축제 일정 총정리: 오페라축제 100대피아노 포크페스티벌`
  - SEO Description: `2026 대구 10월 축제 일정(대구국제오페라축제, 달성 100대 피아노, 대구포크페스티벌, 대구힐링공연예술제, 대구생활문화제, 대구콘텐츠페어, 현대미술제)과 장소별 프로그램, 주차 및 대중교통 꿀팁을 총정리합니다.`
  - Target SEO Score: 75점 이상

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| Middle Dot Character Used | Reject build if `·` exists in visible text | `ERR_MIDDLE_DOT_DETECTED` |
| Missing Card Field | Ensure all 7 cards have date, venue, transit, and 2 map buttons | `ERR_REQUIRED_CARD_FIELD_MISSING` |
| Kakao Map API Failure | Script handles fallback gracefully with direct map links | Fallback button visible |
| Duplicate Schedule Entries | Validate each event exists once in comparison table | `ERR_DUPLICATE_EVENT` |
| Expired Event Inclusion | Exclude finished events (e.g. Suseongmot 9.20 ended) | `ERR_EXPIRED_EVENT` |
| WordPress API Timeout | Retry via SSH transport with atomic transaction | SSH retry mechanism |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Execute**:
  - `test_middle_dot_absence`: 본문 텍스트 내 가운데점(`·`) 0건 검증
  - `test_event_cards_count`: 7대 핵심 축제 카드 존재 확인
  - `test_kakao_map_embed`: 지도 컨테이너 및 API 스크립트 무결성 확인
  - `test_html_length_and_sections`: 5,000자 이상, 7대 섹션 및 비교표 완비 검증
- **Verification Command**:
  - `python scripts/test_daegu_festival_post.py`
  - `validate_bundle(scopes={'content', 'source'})` -> ready
- **Success Criteria**: 모든 테스트가 Exit code 0으로 통과할 것.

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
### 📋 Live Task Progress
- [x] Step 1: 공식 출처 팩트체크 및 7대 축제 데이터 수집
- [x] Step 2: 번들 및 HTML 초안 작성 (`tmp/daegu-october-festivals-20260928/`)
- [x] Step 3: 단위 테스트 작성 및 통과 검증 (`scripts/test_daegu_festival_post.py` Exit Code 0)
- [x] Step 4: Semantic Review 피드백 분석 및 원고 보강 (무료 단정 지양, 교통/주차 상세 팁 보강)
- [x] Step 5: WordPress 임시글(`draft`) 등록 (Post ID: 657, Media ID: 658) 및 카탈로그 동기화
- [x] Step 6: 사후 작업 기록 및 결과 보고 (`docs/daegu-october-festivals-draft-2026-09-28.md`)
