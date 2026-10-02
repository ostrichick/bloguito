# 🎯 Prompt Harness Specification: Post #648 Busan Festival Remediation (4 Issues)

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #648(2026 부산 10월 축제 일정)에서 발견된 4대 문제(① 카카오 지도 미출력, ② 대표 이미지 흰 배경 개선 및 개성 있는 폰트 적용, ③ 5개 문단별 공식/실사 행사 이미지 첨부, ④ 6번 섹션 주차장 지도 링크 추가)를 완벽히 해결하여 WordPress #648 초안을 원자적으로 갱신하고 검증한다.
- **In-Scope Deliverables**:
  - `docs/harness_busan_festival_remediation.md`: 5대 하네스 사양 문서
  - `scripts/upload_busan_festival_images.py`: 5개 축제 실사 이미지 및 대표 커버 WebP 변환 및 WordPress 미디어 라이브러리 업로드 스크립트
  - `scripts/test_busan_remediation.py`: 4대 개선 항목(지도 SDK 로딩 함수, 이미지 5개 첨부, 주차장 링크, 가운데점 0건, 단어 수) 자동 검증 단위 테스트
  - `scripts/update_busan_post_648.py`: WordPress #648 원자적 업데이트 및 메타데이터 보존 스크립트
  - `docs/busan-october-festivals-draft-2026-09-28.md`: 4대 수정 이력 기록
- **Strictly Out-of-Scope (Non-Goals)**:
  - `post_status`를 `publish`로 변경 금지 (사용자 지시: 초안 유지).
  - 다른 게시물(#621 등) 일체 무단 변경 금지.
- **Forbidden Boundaries**:
  - 독자 노출 텍스트 내 가운데점(`·`) 사용 금지.
  - Rank Math SEO 점수 75점 미만 하락 금지.

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Problem 1: Kakao Map Fix**:
  - SDK URL: `//dapi.kakao.com/v2/maps/sdk.js?appkey=dda896ffe09a01b73ac2592af1b07d97` (autoload 파라미터 충돌 제거)
  - Initialization: `kakao.maps.load(function(){ ... })` 래퍼로 비동기 SDK 안전 로드 보장
- **Problem 2: Featured Image**:
  - Background: 광안대교 오션뷰 석양/야경 실사 (`busan_fest_cover_bg_1790598974262.jpg`)
  - Typography: Windows `HanSantteutDotum-Bold.ttf` (한산뜻돋움 Bold) 개성 있는 현대적 타이포그래피 적용
  - Size: 1200x675 (16:9), WebP 포맷
- **Problem 3: Section Images (5 Festivities)**:
  1. 페스티벌 시월 & 부산국제영화제: 해운대 영화의전당 야외극장 레드카펫 실사
  2. 2026 부산국제록페스티벌: 사상 삼락생태공원 야외 메인 스테이지 록 공연 실사
  3. 제33회 부산자갈치축제: 자갈치시장 유라리광장 수산물 야외 포차 야경 실사
  4. 제32회 동래읍성역사축제: 동래읍성 북문 성벽 배경 동래성 전투 재현 실사
  5. 광안리 M 드론라이트쇼: 광안리해수욕장 백사장 광안대교 배경 초대형 드론쇼 실사
  - Format: `<figure><img><figcaption>` 스타일로 본문 문단별 삽입
- **Problem 4: Parking Map Links (Section 6)**:
  - 벡스코 환승주차장, 수영역 환승공영주차장, 부산역 북항 공영주차장, 삼락생태공원 주차장 4곳의 카카오맵 및 네이버지도 길찾기 버튼 그룹 삽입

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| SDK Not Loaded | Fallback polling with setTimeout until `kakao.maps.load` | `ERR_SDK_NOT_LOADED` |
| Image Upload Failure | SCP & WP-CLI media import with exit code 0 check | `ERR_MEDIA_IMPORT_FAILED` |
| Low Contrast Text on Cover | Apply linear dark gradient scrim on left side | `ERR_TYPOGRAPHY_UNREADABLE` |
| Parking Link Count Mismatch | Ensure all 4 parking lots have both Kakao and Naver links | `ERR_PARKING_LINKS_MISSING` |
| Middle Dot Reintroduced | Enforce regex rejecting `·` | `ERR_MIDDLE_DOT_DETECTED` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests (`scripts/test_busan_remediation.py`)**:
  - `Test 1`: 카카오맵 스크립트에 `kakao.maps.load` 및 SDK URL 정합성 확인
  - `Test 2`: 본문 5개 섹션 이미지 태그 및 유효 URL(https://lifeinfo24.org/wp-content/uploads/...) 검증
  - `Test 3`: 6번 섹션 주차장 4곳의 카카오맵/네이버지도 링크 버튼 총 8개 존재 확인
  - `Test 4`: 본문 가운데점(`·`) 0건 확인
  - `Test 5`: 대표 이미지 파일 존재 및 규격(1200x675) 확인
  - `Test 6`: 한국어 단어 수 >= 1,400단어 확인
- **Verification Command**:
  - `./agent-publisher/.venv/Scripts/python.exe scripts/test_busan_remediation.py` (Exit code 0)

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
- [x] Step 1: Establish Prompt Harness specification (`docs/harness_busan_festival_remediation.md`)
- [x] Step 2: Implement image generation & upload script (`scripts/build_and_upload_busan_images.py`) - Cover #650 and 5 section images #651~#655 uploaded
- [x] Step 3: Implement updated content builder addressing all 4 issues (`scripts/build_busan_festival_post.py`)
- [x] Step 4: Write and run automated tests (`scripts/test_busan_remediation.py`) - 6 tests passed (13 total)
- [x] Step 5: Execute atomic update of Post #648 on WordPress (`scripts/update_busan_post_648.py`) - Post #648 updated with exit code 0
- [x] Step 6: Verify remote draft state, Rank Math score, and present proof of execution
