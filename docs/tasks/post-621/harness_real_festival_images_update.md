# 🎯 Prompt Harness Specification: Post #621 Real Festival Images Replacement

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #621의 4번(제30회 전주한지문화축제) 및 5번(2026 전주막걸리축제) AI 생성 이미지의 부자연스러운 인공감을 제거하기 위해, 전주시 및 축제 공식 실물 현장 사진을 16:9 에디토리얼 WebP로 정밀 가공하여 워드프레스에 업로드하고, 본문 이미지 소스를 실물 기반으로 교체 및 라이브 검증 완료.
- **In-Scope Deliverables**:
  - `scripts/build_real_festival_images.py`: 실제 축제 사진 2종을 1200x675 (16:9) WebP 에디토리얼 카드로 변환
  - `scripts/test_real_images_harness.py`: 변환된 이미지 사양 및 HTML 이미지 태그 치환 정규식 단위 테스트
  - `scripts/upload_and_replace_images_post_621.py`: 워드프레스 미디어 라이브러리 업로드 및 Post #621 원자적 업데이트
  - 라이브 사이트 검증: curl 및 wp-cli를 통한 요소 확인, Rank Math SEO 점수 75 유지, HTTP 200 검증
- **Strictly Out-of-Scope (Non-Goals)**:
  - 1번(드론쇼), 2번(비빔밥), 3번(국가유산야행) 이미지 유지 (사용자가 문제 제기하지 않음).
  - 상단 카카오 인터랙티브 지도 위젯 보존 (현재 200 OK 정상 동작 중).
  - 5개 길찾기 카드 및 본문 목차/비교표 보존.
- **Forbidden Boundaries**:
  - `post_status`를 `publish`에서 변경 금지.
  - Rank Math SEO 점수(75점 이상 녹색 등급) 훼손 금지.

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Inputs**:
  - 4번 원본: `official_hanji.jpg` (한국전통문화전당 한지축제 야외마당 실사)
  - 5번 원본: `makgeolli_thumb.jpg` (전주막걸리축제 대형 황금주전자 포토존 및 야외 행사장 실사)
- **Outputs & Returns**:
  - 신규 WebP 2종: `jeonju-hanji-real-action.webp`, `jeonju-makgeolli-real-fest.webp`
  - 워드프레스 미디어 업로드 및 Post #621 HTML 본문 교체
- **State Changes**:
  - Post 621의 4번/5번 `<figure>` 내 `<img>` src/alt 및 `<figcaption>` 출처 텍스트 업데이트

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| Media Upload Failure | Upload via SCP to /tmp then import using wp media import | `ERR_MEDIA_IMPORT` |
| Image URL 404 on Live Site | Test new image URLs with curl -I; ensure 200 OK | `ERR_IMAGE_404` |
| Unintended HTML Corruption | Use strict regex targeting only 4번/5번 figures | `ERR_REGEX_CORRUPT` |
| SEO Score Drop | Re-verify and maintain Rank Math meta (score 75) | `ERR_SEO_DEGRADED` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Write First (TDD)**:
  - `Test 1`: `test_real_images_harness.py` - 생성된 WebP 해상도(1200x675), 용량(<200KB), 포맷(WEBP) 검증
  - `Test 2`: HTML 치환 로직 단위 테스트 (카카오 지도 및 1~3번 이미지 완전 보존 검증)
- **Verification Commands**:
  - Unit test: `agent-publisher\.venv\Scripts\python.exe scripts/test_real_images_harness.py` (Exit code 0)
  - Remote WP Post check: `ssh bloguito "sudo docker exec wordpress_app wp post get 621 --field=post_status --allow-root"`
  - Live site curl: `curl -I https://lifeinfo24.org/jeonju-october-festivals-2026/` (HTTP 200 OK)
- **Success Criteria**:
  - 4번/5번 이미지 실제 축제 현장 실물 사진으로 교체
  - Rank Math 점수 75 유지
  - HTTP 200 OK

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
- [x] Step 1: Generate 16:9 WebP editorial cards from real photos (`build_real_festival_images.py` PASS ✅)
- [>] Step 2: Write automated tests for image properties and replacement regex (`test_real_images_harness.py`) (Active ⚡)
- [ ] Step 3: Implement and execute upload and replacement script (`upload_and_replace_images_post_621.py`)
- [ ] Step 4: Verify WordPress post state, Rank Math score (75점 유지), and image URLs via curl
- [ ] Step 5: Final proof of execution logs and summary report
