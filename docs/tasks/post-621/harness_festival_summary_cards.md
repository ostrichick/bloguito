# 🎯 Prompt Harness Specification: Post #621 Festival Summary Cards Refactoring

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #621 본문의 5대 축제 길찾기 카드(`festival-location-card`)를 사용자의 요청에 맞춰 **[행사 요약]** 박스로 전면 개편하고, 기존 2대 항목에서 **[개최 일정, 개최 장소, 교통 안내]** 3대 핵심 정보를 누락 없이 일관되게 제공하며, 카카오맵/네이버지도 길찾기 버튼을 보존하여 실서버 배포 및 라이브 검증을 완료한다.
- **In-Scope Deliverables**:
  - `docs/harness_festival_summary_cards.md`: 5대 하네스 사양 문서
  - `scripts/test_festival_summary_cards.py`: 5개 요약 박스의 3대 필드 및 길찾기 링크 검증 단위 테스트
  - `scripts/update_festival_summary_cards_post_621.py`: Post #621 원자적 업데이트 스크립트
  - 라이브 사이트 검증: curl 및 wp-cli를 통한 요소 확인, Rank Math SEO 점수 75 유지, HTTP 200 검증
- **Strictly Out-of-Scope (Non-Goals)**:
  - 상단 카카오 공식 인터랙티브 지도 위젯(`bloguito-kakao-map-container`) 수정 금지 (현재 정상 200 OK 동작 중).
  - 본문 1~5번 이미지 수정 금지.
  - 상단 일정 비교표 및 본문 목차/CTA 수정 금지.
- **Forbidden Boundaries**:
  - `post_status`를 `publish`에서 변경 금지.
  - Rank Math SEO 점수(75점 이상 녹색 등급) 훼손 금지.

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Inputs**: Post ID 621, 5대 축제 메타데이터:
  1. 전주페스타 2026:
     - 개최 일정: 2026.10.02(금) ~ 10.04(일) [3일간 / 개막 드론쇼 10.02(금) 20:00]
     - 개최 장소: 전북 전주시 덕진구 기린대로 451 (전주종합경기장 일원)
     - 교통 안내: KTX 전주역에서 시내버스 119번·79번 이용 (약 10~15분 소요, 종합경기장 정류장 하차)
  2. 2026 전주비빔밥축제:
     - 개최 일정: 2026.10.02(금) ~ 10.04(일) [3일간]
     - 개최 장소: 전북 전주시 덕진구 권삼득로 390 (전주 덕진공원 일원)
     - 교통 안내: KTX 전주역에서 시내버스 61번·79번 이용 (약 15분 소요, 덕진공원 정류장 하차)
  3. 2026 전주국가유산야행:
     - 개최 일정: 2026.10.02(금) ~ 10.03(토) [2일간 / 18:00 ~ 23:00 야간 운영]
     - 개최 장소: 전북 전주시 완산구 태조로 44 (전주 한옥마을, 경기전, 전라감영 일원)
     - 교통 안내: 전주고속버스터미널에서 시내버스 79번·1000번 이용 (약 15분 소요, 한옥마을 정류장 하차)
  4. 제30회 전주한지문화축제:
     - 개최 일정: 2026.10.08(목) ~ 10.10(토) [3일간]
     - 개최 장소: 전북 전주시 완산구 현무1길 20 (한국전통문화전당 일원)
     - 교통 안내: 한옥마을 도보 10분 또는 KTX 전주역에서 시내버스 119번 이용 (약 15분 소요, 동부시장 하차 후 도보 3분)
  5. 2026 전주막걸리축제:
     - 개최 일정: 2026.10.17(토) ~ 10.18(일) [2일간]
     - 개최 장소: 전북 전주시 완산구 거마평로 일대 (삼천동 막걸리 골목)
     - 교통 안내: 한옥마을에서 택시 또는 시내버스 (약 12~15분 소요, 삼천주공아파트 방면 하차)
- **Card Structure**:
  - Class: `festival-summary-card` (기존 CSS 호환 및 스타일 보장)
  - Title: `📍 행사 요약`
  - Body:
    • **개최 일정**: {일정}<br/>
    • **개최 장소**: {장소}<br/>
    • **교통 안내**: {교통}
  - Button Group: `카카오맵 길찾기 ↗`, `네이버지도 길찾기 ↗` 유지

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| Card Count Mismatch | Exact 5 cards must be replaced; abort if != 5 | `ERR_CARD_COUNT_MISMATCH` |
| Field Omission | Ensure all 3 fields present in all 5 cards | `ERR_REQUIRED_FIELD_MISSING` |
| Map Widget Damaged | Verify `bloguito-kakao-map` container and SDK script untouched | `ERR_MAP_WIDGET_DAMAGED` |
| SEO Score Drop | Re-verify and maintain Rank Math meta (score 75) | `ERR_SEO_DEGRADED` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Write First (TDD)**:
  - `Test 1`: `test_festival_summary_cards.py` - 5개 요약 박스의 3대 필드(개최 일정, 개최 장소, 교통 안내) 포함 여부 및 버튼 링크 검증
  - `Test 2`: 본문 치환 시뮬레이션 및 상단 카카오 인터랙티브 지도 보존 검증
- **Verification Commands**:
  - Unit test: `agent-publisher\.venv\Scripts\python.exe scripts/test_festival_summary_cards.py` (Exit code 0)
  - Remote WP Post check: `ssh bloguito "sudo docker exec wordpress_app wp post get 621 --field=post_status --allow-root"`
  - Live site curl: `curl -I https://lifeinfo24.org/jeonju-october-festivals-2026/` (HTTP 200 OK)
- **Success Criteria**:
  - 5개 카드 제목 "📍 행사 요약"
  - 5개 카드 모두 "개최 일정", "개최 장소", "교통 안내" 3개 항목 완비
  - 길찾기 버튼 및 상단 카카오 지도 100% 정상 보존

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
- [x] Step 1: Write and run automated tests for the 5 summary cards (`test_festival_summary_cards.py`) (Done ✅)
- [x] Step 2: Implement and execute update script (`update_festival_summary_cards_post_621.py`) (Done ✅)
- [x] Step 3 & 4: Verify WordPress post state & live website via curl (Done ✅)
- [x] Step 5: Final proof of execution logs and summary report (Done ✅)
