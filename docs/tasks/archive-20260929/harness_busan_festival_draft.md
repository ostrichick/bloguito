# 🎯 Prompt Harness Specification: 2026 Busan October Festivals & Events Draft Post

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #621(2026 전주 10월 축제 일정)의 고품질 표준(요약 상자, 일정 비교표, 카카오맵 인터랙티브 지도 연동, 5대 축제별 3대 필드 행사 요약 카드, 실시간 길찾기 버튼, 주차/교통 팁, FAQ, 내부 링크, 공식 출처)과 동일한 수준의 「2026 부산 10월 축제 및 행사 일정 총정리」 포스트 초안을 작성하여 WordPress에 임시글(`draft`)로 안전하게 등록하고, 카탈로그를 최신 동기화한다.
- **In-Scope Deliverables**:
  - `docs/harness_busan_festival_draft.md`: 5대 하네스 사양 문서
  - `scripts/test_busan_festival_post.py`: 포스트 HTML 구조, 5개 요약 카드, 카카오 지도, 가운데점 금지 규칙, 어휘 수 검증 단위 테스트
  - `scripts/build_busan_festival_post.py`: 부산 10월 축제 포스트 HTML 및 메타데이터 생성 모듈
  - `scripts/create_busan_festival_draft.py`: 원격 WordPress 원자적 draft 등록 및 메타데이터 설정 스크립트
  - `docs/busan-october-festivals-draft-2026-09-28.md`: 공식 출처 및 작업 결과 기록 문서
  - `docs/POST_CATALOG.md`: 로컬 카탈로그 동기화 반영
- **Strictly Out-of-Scope (Non-Goals)**:
  - `post_status`를 `publish`로 전환 금지 (사용자 지시: "초안을 임시글로 작성해줘").
  - 기존 공개 글(#621, #598 등)이나 타 draft 글 일체 무단 변경 금지.
- **Forbidden Boundaries**:
  - 독자 노출 텍스트(제목, 소제목, 본문, 표, FAQ, CTA, 출처) 내 가운데점(`·`) 사용 금지 (쉼표 또는 자연스러운 접속 표현 사용).
  - 공식 출처에서 확인되지 않은 일정/비용 임의 추측 금지.

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **5대 핵심 축제 및 행사 메타데이터**:
  1. 페스티벌 시월 & 제31회 부산국제영화제(BIFF):
     - 일정: 2026.10.01(목) ~ 10.08(목) [페스티벌 시월] / 2026.10.06(화) ~ 10.15(목) [10일간, BIFF]
     - 장소: 부산 해운대구 수영강변대로 120 (영화의전당 및 센텀시티 일원)
     - 교통: 지하철 2호선 센텀시티역 6번, 12번 출구 도보 5분
     - 좌표: 35.1711, 129.1272
  2. 2026 부산국제록페스티벌:
     - 일정: 2026.10.02(금) ~ 10.04(일) [3일간]
     - 장소: 부산 사상구 삼락동 29-46 (삼락생태공원 일원)
     - 교통: 부산김해경전철 괘법르네시떼역 1번 출구 도보 5분(강변나들교 건너편) 또는 2호선 사상역 3번 출구 도보 15분
     - 좌표: 35.1685, 128.9723
  3. 제33회 부산자갈치축제:
     - 일정: 2026.10.15(목) ~ 10.18(일) [4일간]
     - 장소: 부산 중구 자갈치해안로 52 (자갈치시장 및 유라리광장 일원)
     - 교통: 지하철 1호선 자갈치역 10번 출구 또는 남포역 2번 출구 도보 3분
     - 좌표: 35.0967, 129.0305
  4. 제32회 동래읍성역사축제:
     - 일정: 2026.10.16(금) ~ 10.18(일) [3일간]
     - 장소: 부산 동래구 문화로 80 (동래문화회관, 동래읍성 북문언덕 일원)
     - 교통: 지하철 1호선 명륜역 또는 동래역에서 마을버스(동래구1번, 7번) 환승 후 동래문화회관 하차
     - 좌표: 35.2078, 129.0882
  5. 광안리 M 드론라이트쇼 가을 상설공연:
     - 일정: 2026.10.01 ~ 10.31 [매주 토요일 저녁 19:00, 21:00 동절기 2회 운영]
     - 장소: 부산 수영구 광안해변로 219 (광안리해수욕장 백사장 일원)
     - 교통: 지하철 2호선 광안역 3번, 5번 출구 또는 금련산역 1번, 3번 출구 도보 10분
     - 좌표: 35.1532, 129.1186
- **Kakao Map SDK Integration**:
  - App Key: `dda896ffe09a01b73ac2592af1b07d97` (Post #621 실서버 검증 완료된 키)
  - Options: 단일 줄 인라인 JS, `\x3c` 및 `\x3e` 태그 이스케이프로 WordPress wpautop 오동작 방지
- **Rank Math Metadata Spec**:
  - Focus Keyword: `2026 부산 10월 축제`
  - Post Title: `2026 부산 10월 축제 일정 총정리: 페스티벌 시월, 록페스티벌, 자갈치축제 한눈에 보기`
  - SEO Title: `2026 부산 10월 축제 일정 총정리: 페스티벌 시월 록페스티벌 자갈치`
  - SEO Description: `2026 부산 10월 축제 일정(페스티벌 시월, 부산국제록페스티벌, 부산국제영화제, 부산자갈치축제, 동래읍성역사축제, 광안리 드론쇼)과 장소별 프로그램, 주차 및 대중교통 꿀팁을 총정리합니다.`
  - Target SEO Score: 75점 이상

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| Middle Dot Character Used | Reject build if `·` exists in visible text | `ERR_MIDDLE_DOT_DETECTED` |
| Missing Card Field | Ensure all 5 cards have date, venue, transit, and 2 map buttons | `ERR_REQUIRED_CARD_FIELD_MISSING` |
| Word Count Shortage | Reject if Korean word count < 1200 | `ERR_WORD_COUNT_TOO_LOW` |
| Kakao Map Stripped | Validate presence of `bloguito-kakao-map` and SDK script | `ERR_KAKAO_MAP_MISSING` |
| Post Status Not Draft | Abort creation if post status is not `draft` | `ERR_ILLEGAL_POST_STATUS` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Write First (TDD)**:
  - `Test 1`: 컴포넌트 8대 구조 검증 (`bloguito-summary`, `bloguito-info-table`, `bloguito-kakao-map-container`, `bloguito-cta`, `bloguito-toc`, `bloguito-faq`, `bloguito-interlink`, `source-list`)
  - `Test 2`: 5대 축제 요약 카드 및 길찾기 버튼 완결성 검증
  - `Test 3`: 본문 가운데점(`·`) 완전 배제 검증
  - `Test 4`: 카카오맵 스크립트 문법 및 마커 좌표 검증
  - `Test 5`: 한국어 단어 수 >= 1,200자 검증
- **Verification Commands**:
  - Unit Test: `./agent-publisher/.venv/Scripts/python.exe scripts/test_busan_festival_post.py`
  - Remote WP Post Check: `ssh bloguito "sudo docker exec wordpress_app wp post get <NEW_ID> --format=json --allow-root"`
  - Catalog Sync: `python scripts/sync_post_catalog.py`
- **Success Criteria**:
  - Unit tests pass with exit code 0
  - WordPress remote post ID assigned, status == `draft`
  - Rank Math focus keyword, SEO title, meta description saved
  - `POST_CATALOG.md` contains the new draft row under Draft table

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
- [x] Step 1: Establish Prompt Harness specification (`docs/harness_busan_festival_draft.md`)
- [x] Step 2: Implement automated test suite (`scripts/test_busan_festival_post.py`)
- [x] Step 3: Implement Busan festival HTML and metadata builder (`scripts/build_busan_festival_post.py`)
- [x] Step 4: Run unit test suite & verify 100% green status (Exit code 0)
- [x] Step 5: Implement and execute remote WordPress draft creation script (`scripts/create_busan_festival_draft.py`) - Post ID #648 created
- [x] Step 6: Verify remote draft in WordPress and synchronize `docs/POST_CATALOG.md`
- [x] Step 7: Record work report in `docs/busan-october-festivals-draft-2026-09-28.md` and present proof to user
