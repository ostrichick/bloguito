# 🎯 Prompt Harness Specification: Post #621 Kakao Maps Web API Integration

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #621(`jeonju-october-festivals-2026`) 본문 상단(일정 비교표 직후, CTA 박스 직전)에 카카오 JavaScript 키(환경변수 `KAKAO_MAP_JS_KEY` 참조)를 연동한 1개의 반응형 통합 인터랙티브 지도(`bloguito-kakao-map-container`)를 삽입하여, 5대 축제 위치 마커와 상세정보 인포윈도우, 줌 컨트롤을 제공하고 실서버 배포 및 라이브 검증을 완료한다.
- **In-Scope Deliverables**:
  - `docs/tasks/post-621/harness_kakao_map_integration.md`: 5대 하네스 사양 문서
  - `scripts/archive/post-621/test_kakao_map_html.py`: 지도 HTML 및 JavaScript 스크립트 정적 검증 단위 테스트
  - `scripts/archive/post-621/apply_kakao_map_post_621.py`: Post #621 원자적 업데이트 스크립트
  - 실서버 라이브 검증: curl 및 wp-cli를 통한 요소 확인, Rank Math SEO 점수 75 유지, HTTP 200 검증
- **Strictly Out-of-Scope (Non-Goals)**:
  - 5개 축제별 본문 문단 내 5대 길찾기 카드(`festival-location-card`) 및 실사 이미지 수정/삭제 금지.
  - 다른 포스트 수정 일체 금지.
- **Forbidden Boundaries**:
  - `post_status`를 `publish`에서 `draft`로 변경 금지.
  - Rank Math SEO 점수(75점 이상 녹색 등급) 훼손 금지.

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Inputs**:
  - Post ID: `621`
  - Kakao JS Key: `[REDACTED_KAKAO_JS_KEY]` (from `KAKAO_MAP_JS_KEY` env var)
  - 5대 축제 좌표 (WGS84):
    1. 전주종합경기장 (35.8390, 127.1264)
    2. 덕진공원 (35.8478, 127.1220)
    3. 경기전 한옥마을 (35.8145, 127.1481)
    4. 한국전통문화전당 (35.8197, 127.1492)
    5. 삼천동 막걸리골목 (35.7974, 127.1229)
- **Outputs & Returns**:
  - WordPress DB `wp_posts` updated atomically.
  - Live HTTP 200 OK with `bloguito-kakao-map` element.
- **State Changes**:
  - Post 621 `post_content` updated with Kakao Maps container and SDK init script.

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| Map Container Missing in DOM | Init script retries with setTimeout until DOM ready | `ERR_DOM_NOT_READY` |
| Kakao SDK Script Load Delay | Polling until `window.kakao.maps` is defined | `ERR_SDK_NOT_LOADED` |
| Mobile Screen Pinch/Scroll Conflict | Touch event friendly height (400px), bounds auto-fit | `ERR_UX_PINCH_CONFLICT` |
| WordPress Strips Script Tag | Use atomic raw SQL or wp eval without kses filter | `ERR_WP_KSES_STRIP` |
| SEO Score Drop | Re-verify and maintain Rank Math meta (score 75) | `ERR_SEO_DEGRADED` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Write First (TDD)**:
  - `Test 1`: `test_kakao_map_html.py` - HTML 및 SDK 스크립트 생성 로직 검증 (5개 마커 좌표, 앱키 삽입, 인포윈도우 앵커 확인).
- **Verification Commands**:
  - Unit test: `agent-publisher\.venv\Scripts\python.exe scripts/test_kakao_map_html.py` (Exit code 0)
  - Remote WP Post check: `ssh bloguito "sudo docker exec wordpress_app wp post get 621 --field=post_status --allow-root"`
  - Live site curl: `curl -I https://lifeinfo24.org/jeonju-october-festivals-2026/` (HTTP 200 OK)
- **Success Criteria**:
  - `bloguito-kakao-map` container present in live HTML
  - Kakao Maps SDK script tag present with valid appkey
  - Post status = `publish`
  - Rank Math SEO score = 75

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
- [x] Step 1: Securely extract and validate Kakao JS Key from clipboard (PASS ✅)
- [>] Step 2: Write automated tests for Kakao Map HTML/script component (`test_kakao_map_html.py`) (Active ⚡)
- [ ] Step 3: Implement and execute `apply_kakao_map_post_621.py` for atomic server update
- [ ] Step 4: Verify remote WordPress post state and Rank Math score (75점 유지)
- [ ] Step 5: Verify live website via curl (HTTP 200 OK & elements check) and present proof of execution
