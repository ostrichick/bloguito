# 🎯 Prompt Harness Specification: 2026 Sejong October Festivals & Events Draft Post

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #621(전주) 및 부산 10월 축제 포스트의 고품질 표준(요약 상자, 5대 축제 일정 비교표, 카카오맵 인터랙티브 지도 연동, 축제별 3대 필드 행사 요약 카드, 실시간 길찾기 버튼, 주차/교통 팁, FAQ, 공식 출처)과 사용자 특별 요청(도시 랜드마크인 금강보행교 이응다리/호수공원 백그라운드 대표이미지 및 한컴 산뜻돋움 Bold 폰트 적용, 문단마다 축제 설명 16:9 WebP 이미지 첨부)을 완벽히 충족하는 「2026 세종 10월 축제 및 행사 일정 총정리」 포스트 초안을 작성하여 WordPress에 임시글(`draft`)로 안전하게 등록하고, 카탈로그를 최신 동기화한다.
- **In-Scope Deliverables**:
  - `docs/harness_sejong_festival_draft.md`: 5대 하네스 사양 문서
  - `scripts/build_and_upload_sejong_images.py`: 대표이미지 합성 및 5개 축제 설명 WebP 이미지 가공/워드프레스 미디어 라이브러리 업로드 스크립트
  - `scripts/build_sejong_festival_post.py`: 시맨틱 HTML 본문, 카카오 지도, 5개 요약 카드, 길찾기 버튼, 이미지 피규어 블록 생성 모듈
  - `scripts/test_sejong_festival_post.py`: 포스트 HTML 구조, 5개 요약 카드, 5개 이미지 태그, 카카오 지도, 가운데점 금지 규칙, 어휘 수 검증 단위 테스트
  - `scripts/create_sejong_festival_draft.py`: 원자적 WordPress 임시글(`draft`) 생성 및 메타데이터 주입 스크립트
  - WordPress 임시글(`draft`) 등록 및 카탈로그 동기화 (`docs/POST_CATALOG.md`)
  - `docs/sejong-october-festivals-draft-2026-09-28.md`: 공식 출처 및 작업 결과 기록 문서
- **Strictly Out-of-Scope (Non-Goals)**:
  - `post_status`를 `publish`로 전환 금지 (기본 원칙: `draft`).
  - 기존 공개 글(#621, #598 등)이나 타 draft 글 일체 무단 변경 금지.
- **Forbidden Boundaries**:
  - 독자 노출 텍스트(제목, 소제목, 본문, 표, FAQ, CTA, 출처) 내 가운데점(`·`) 사용 금지 (쉼표 또는 자연스러운 접속 표현 사용).
  - 공식 출처에서 확인되지 않은 일정/비용 임의 추측 금지.

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **5대 핵심 축제 및 행사 메타데이터**:
  1. 2026 세종한글축제 (세종축제):
     - 일정: 2026.10.09(금) ~ 10.11(일) [3일간]
     - 장소: 세종특별자치시 연기면 세종리 114-480 (세종중앙공원 도시축제마당 및 세종호수공원)
     - 교통: BRT B0, B1, B2번 정부세종청사 또는 세종고속시외버스터미널 하차 후 시내버스 환승 또는 도보
     - 좌표: 36.4950, 127.2750
     - 핵심 프로그램: 블랙이글스 에어쇼, 한글드론쇼, 수상 불꽃극, 한글 노래 경연대회, 위대한 태권도 공연
  2. 2026 세종보헤미안뮤직페스티벌:
     - 일정: 2026.10.30(금) ~ 11.01(일) [3일간]
     - 장소: 세종특별자치시 중앙공원로 212 (세종중앙공원 도시축제마당)
     - 교통: BRT B0번 정부세종청사 남측 정류장 도보 10분
     - 좌표: 36.4942, 127.2721
     - 핵심 프로그램: 충청권 대표 야외 모던록/인디 페스티벌, 정상급 밴드 라이브 공연, 피크닉존
  3. 국립세종수목원 가을 야간개장 및 문화행사 ('별빛 아래 걷는 밤, 우리함께夜'):
     - 일정: 2026.10.01 ~ 10.31 [매주 금, 토 야간개장 21:00까지]
     - 장소: 세종특별자치시 수목원로 136 (국립세종수목원 사계절전시온실 및 한국전통정원)
     - 교통: 세종 시내버스 221번 국립세종수목원 정류장 하차
     - 좌표: 36.4965, 127.2885
     - 핵심 프로그램: 사계절전시온실 야간 조명, 한국전통정원 궁궐 유등 '진주의 빛을 품다', 한복 무료 대여
  4. 베어트리파크 가을 축제: <시간의 정원> & 단풍 축제:
     - 일정: 2026.10.03(토) ~ 11.22(일)
     - 장소: 세종특별자치시 전동면 신송로 217 (베어트리파크)
     - 교통: 조치원역 버스정류장에서 801번, 80번 시내버스 환승 후 베어트리파크 하차
     - 좌표: 36.6341, 127.2625
     - 핵심 프로그램: 가을 한정 '비밀의 숲길' 단풍 산책로 개방, 반달가슴곰 생태 관람, 분재원 단풍
  5. 2026 금강보행교(이응다리) 가을 페스타 및 야경 산책:
     - 일정: 2026.10.01 ~ 10.31 [매일 06:00 ~ 23:00 개방, 10.3 개천절 랩소디 및 상설 버스킹]
     - 장소: 세종특별자치시 세종동 및 보람동 일원 (금강보행교 이응다리)
     - 교통: BRT B0번 세종시청 앞 하차 도보 5분 (남측) 또는 국책연구단지 하차 (북측)
     - 좌표: 36.4883, 127.2917
     - 핵심 프로그램: 1,446m 국내 최장 원형 복층 보행교, 미디어 파사드 및 레이저 분수 야경, 거리 버스킹
- **Kakao Map SDK Integration**:
  - App Key: `dda896ffe09a01b73ac2592af1b07d97` (Post #621 실서버 검증 완료된 키)
  - Options: 단일 줄 인라인 JS, `\x3c` 및 `\x3e` 태그 이스케이프로 WordPress wpautop 오동작 방지
- **Rank Math Metadata Spec**:
  - Focus Keyword: `2026 세종 10월 축제`
  - Post Title: `2026 세종 10월 축제 일정 총정리: 세종한글축제, 보헤미안뮤직, 수목원야경 한눈에 보기`
  - SEO Title: `2026 세종 10월 축제 일정 총정리: 세종한글축제 보헤미안뮤직 수목원야경`
  - SEO Description: `2026 세종 10월 축제 일정(세종한글축제, 세종보헤미안뮤직페스티벌, 국립세종수목원 야간개장, 베어트리파크 가을축제, 금강보행교 이응다리 야경)과 장소별 프로그램, 주차 및 대중교통 꿀팁을 총정리합니다.`
  - Target SEO Score: 75점 이상

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| Middle Dot Character Used | Reject build if `·` exists in visible text | `ERR_MIDDLE_DOT_DETECTED` |
| Missing Card Field | Ensure all 5 cards have date, venue, transit, and 2 map buttons | `ERR_REQUIRED_CARD_FIELD_MISSING` |
| Missing Section Image | Ensure all 5 festival sections contain an optimized 16:9 WebP figure | `ERR_MISSING_SECTION_IMAGE` |
| Kakao Map API Failure | Script handles fallback gracefully with direct map links | Fallback button visible |
| Duplicate Slug in WordPress | Abort creation if slug exists | `ERR_DUPLICATE_SLUG` |
| WordPress API Timeout | Retry via SSH transport with atomic transaction | SSH retry mechanism |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Execute**:
  - `test_middle_dot_absence`: 본문 텍스트 내 가운데점(`·`) 0건 검증
  - `test_event_cards_count`: 5대 핵심 축제 카드 존재 확인
  - `test_event_images_count`: 5대 축제 설명 figure/img 태그 완비 검증
  - `test_kakao_map_embed`: 지도 컨테이너 및 API 스크립트 무결성 확인
  - `test_html_length_and_sections`: 1,200단어 이상, 5대 섹션 및 비교표 완비 검증
- **Verification Command**:
  - `python scripts/test_sejong_festival_post.py` (Exit code 0)
- **Success Criteria**: 모든 테스트가 Exit code 0으로 통과할 것.

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
### 📋 Live Task Progress
- [x] Step 1: 공식 출처 팩트체크 및 5대 축제 데이터 수집 (완료)
- [x] Step 2: 랜드마크 대표이미지 및 문단별 축제 설명 이미지 생성/가공 (완료)
- [x] Step 3: 미디어 라이브러리 업로드 및 이미지 URL 확보 (완료, Attachment #659~#664)
- [x] Step 4: HTML 본문 및 메타데이터 생성 스크립트 작성 (완료)
- [x] Step 5: 단위 테스트 작성 및 100% 통과 검증 (완료, 9개 테스트 통과)
- [x] Step 6: WordPress 임시글(`draft`) 등록 및 카탈로그 동기화 (완료, Post #665)
- [x] Step 7: 최종 상태 검증 및 작업 결과 보고 (완료)
