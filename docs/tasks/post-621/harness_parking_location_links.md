# 🎯 Prompt Harness Specification: Post #621 Parking Location Links Addition

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #621의 6번 문단('2026 전주 10월 축제 방문객을 위한 주차 및 교통 꿀팁') 내에 추천 주차장(치명자산성지 평화의전당 무료 임시주차장, 대성공영주차장, 전주 한옥마을 공영주차장)의 실제 위치 및 내비게이션(카카오맵, 네이버지도) 링크를 구조화된 UI로 추가하여 방문객 편의성을 극대화한다.
- **In-Scope Deliverables**:
  - `docs/harness_parking_location_links.md`: 5대 하네스 사양 문서
  - `scripts/test_parking_location_links.py`: 주차장 위치 링크 및 HTML 구조 검증 단위 테스트
  - `scripts/update_parking_links_post_621.py`: Post #621 원자적 업데이트 스크립트
  - 라이브 사이트 검증: curl 및 wp-cli를 통한 요소 확인, Rank Math SEO 점수 75 이상 유지, HTTP 200 검증
- **Strictly Out-of-Scope (Non-Goals)**:
  - 1~5번 축제의 '📍 행사 요약' 카드 및 길찾기 버튼 수정 금지.
  - 상단 카카오 인터랙티브 지도 위젯 및 보도사진 5종 수정 금지.
  - 본문 다른 문단(TOC, 일정표, CTA 배너 등) 수정 금지.
- **Forbidden Boundaries**:
  - `post_status`를 `publish`에서 변경 금지.
  - Rank Math SEO 점수(75점 이상 녹색 등급) 훼손 금지.

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Inputs**: Post ID 621, 6번 문단 주차 추천 박스 HTML
- **Parking Lots Data**:
  1. 치명자산성지 평화의전당 무료 임시주차장:
     - 도로명: 전북 전주시 완산구 바람쐬는길 120
     - 카카오맵: https://map.kakao.com/link/search/%EC%B9%98%EB%AA%85%EC%9E%90%EC%82%B0%ED%8F%89%ED%99%94%EC%9D%98%EC%A0%84%EB%8B%B9
     - 네이버지도: https://map.naver.com/v5/search/%EC%B9%98%EB%AA%85%EC%9E%90%EC%82%B0%ED%8F%89%ED%99%94%EC%9D%98%EC%A0%84%EB%8B%B9
  2. 대성공영주차장:
     - 도로명: 전북 전주시 완산구 춘향로 5299
     - 카카오맵: https://map.kakao.com/link/search/%EB%8C%80%EC%84%B1%EA%B3%B5%EC%98%81%EC%A3%BC%EC%B0%A8%EC%9E%A5
     - 네이버지도: https://map.naver.com/v5/search/%EB%8C%80%EC%84%B1%EA%B3%B5%EC%98%81%EC%A3%BC%EC%B0%A8%EC%9E%A5
  3. 전주 한옥마을 제1·제2공영주차장:
     - 도로명: 전북 전주시 완산구 기린대로 99
     - 카카오맵: https://map.kakao.com/link/search/%EC%A0%84%EC%A3%BC%ED%95%9C%EC%98%A5%EB%A7%88%EC%9D%84%EA%B3%B5%EC%98%81%EC%A3%BC%EC%B0%A8%EC%9E%A5
     - 네이버지도: https://map.naver.com/v5/search/%EC%A0%84%EC%A3%BC%ED%95%9C%EC%98%A5%EB%A7%88%EC%9D%84%EA%B3%B5%EC%98%81%EC%A3%BC%EC%B0%A8%EC%9E%A5
- **Outputs & Returns**:
  - WordPress Post #621 본문 내 6번 주차 꿀팁 박스에 주차장 바로가기 버튼 링크 추가
  - 라이브 curl 검증 성공 (HTTP 200 OK)

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| Section 6 Box Not Found | Match exact green tip box wrapper; abort if missing | `ERR_PARKING_BOX_NOT_FOUND` |
| Link Duplication | Check if links already present before injecting | `ERR_DUPLICATE_INJECTION` |
| Summary Cards Damaged | Verify 5 summary cards and map intact after edit | `ERR_SUMMARY_CARDS_DAMAGED` |
| SEO Score Drop | Preserve all meta keys (score 75) | `ERR_SEO_DEGRADED` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Write First (TDD)**:
  - `Test 1`: 주차장 3개소 데이터 및 길찾기 링크(카카오맵/네이버지도) 생성 검증
  - `Test 2`: 포스트 본문 내 6번 주차 꿀팁 박스 치환 및 기존 요소(행사 요약 5개, 지도, 이미지) 보존 검증
- **Verification Commands**:
  - Unit test: `agent-publisher\.venv\Scripts\python.exe scripts/test_parking_location_links.py` (Exit code 0)
  - Remote WP Post check: `ssh bloguito "sudo docker exec wordpress_app wp post get 621 --field=post_status --allow-root"`
  - Live site curl: `curl -I https://lifeinfo24.org/jeonju-october-festivals-2026/` (HTTP 200 OK)
- **Success Criteria**:
  - 6번 문단 주차 꿀팁 박스 내 주차장 3개소 위치 및 카카오/네이버 길찾기 링크 정상 렌더링
  - 5개 행사 요약 박스, 카카오 지도, 실물 보도사진 100% 정상 보존

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
- [x] Step 1: Write and run automated tests for parking links (`test_parking_location_links.py`) (Done ✅)
- [x] Step 2: Implement and execute update script (`update_parking_links_post_621.py`) (Done ✅)
- [x] Step 3 & 4: Verify WordPress post state & live website via curl (Done ✅)
- [x] Step 5: Final proof of execution logs and summary report (Done ✅)
