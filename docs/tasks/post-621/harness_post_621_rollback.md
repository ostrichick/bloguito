# 🎯 Prompt Harness Specification: Post #621 Transit Guide Rollback

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #621(`jeonju-october-festivals-2026`) 실서버 라이브 본문에서 사용자가 원치 않는 '대안 1: 반응형 HTML/CSS 권역 동선 및 이동 가이드'(`bloguito-transit-guide` 컨테이너)를 완전히 제거하고, 비교표에서 CTA 박스로 직결되는 깨끗한 기본 원고 상태로 원자적 롤백 수행.
- **In-Scope Deliverables**:
  - `scripts/rollback_post_621_transit_guide.py`: 원격 WordPress Post #621의 `post_content` 백업, 정규식 기반 `bloguito-transit-guide` 제거, WP-CLI 원자적 업데이트 수행.
  - `backups/post_621_before_rollback_*.html`: 롤백 직전 원격 포스트 원문 스냅샷 보존.
  - 실서버 라이브 사이트 검증: curl 및 wp-cli를 통한 잔여물 0건 및 HTTP 200 확인.
- **Strictly Out-of-Scope (Non-Goals)**:
  - 대안 2, 3, 4 등 다른 위치 안내 그래픽의 실서버 임의 적용 (프리뷰 아티팩트만 보존하고 실서버에는 일체 반영하지 않음).
  - 5개 축제별 본문 문단 내 5대 길찾기 카드(`festival-location-card`) 및 5개 현장 실사 이미지 수정/삭제 금지.
  - Post #621 외의 다른 글 변경 일체 금지.
- **Forbidden Boundaries**:
  - `post_status`를 `publish`에서 `draft`나 `pending`으로 변경하는 행위 금지.
  - Rank Math SEO 점수(75점 이상 녹색 등급) 및 메타데이터(`rank_math_title`, `rank_math_description`, `rank_math_focus_keyword`) 유실 금지.

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Inputs**:
  - Target Post ID: `621`
  - SSH Host: `bloguito`
  - Docker Container: `wordpress_app`
- **Outputs & Returns**:
  - JSON summary: `{ "success": true, "post_id": 621, "bytes_removed": int, "final_word_count": int, "has_transit_guide": false, "status": "publish" }`
- **State Changes**:
  - Remote WordPress DB `wp_posts` table `post_content` updated atomically.
  - Backup file created at `backups/post_621_before_rollback_<timestamp>.html`.
- **Dependencies**:
  - Standard Python library (`re`, `subprocess`, `sys`, `json`, `pathlib`, `datetime`). Zero third-party bloat.

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| Target Block Not Found | If `bloguito-transit-guide` is already absent, abort update to prevent dirty writes | `ERR_BLOCK_NOT_FOUND` |
| SSH Connection Failure | Check connection and abort gracefully with error details | `ERR_SSH_CONNECTION` |
| Word Count Drop < 1,000 | Guard against accidental content wiping; abort if length is suspicious | `ERR_CONTENT_TRUNCATED` |
| Rank Math Meta Missing | Explicitly re-apply or preserve Rank Math meta keys after update | `ERR_SEO_DEGRADED` |
| Live Site Non-200 | Verify HTTP status via curl; alert if response is not 200 OK | `ERR_LIVE_VERIFICATION` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Write First (TDD)**:
  - `Test 1`: `test_rollback_regex.py` - 샘플 HTML에서 `bloguito-transit-guide` 컨테이너가 정확히 제거되고 `bloguito-table`과 `bloguito-cta`가 온전히 보존되는지 검증 (통과 완료 ✅).
- **Verification Commands**:
  - Unit test: `agent-publisher\.venv\Scripts\python.exe scripts/test_rollback_regex.py` (Exit code 0)
  - Remote WP Post check: `ssh bloguito "sudo docker exec wordpress_app wp post get 621 --field=post_status --allow-root"`
  - Live site curl: `curl -I https://lifeinfo24.org/?p=621` (HTTP 200 OK)
- **Success Criteria**:
  - `bloguito-transit-guide` count = 0
  - `festival-location-card` count = 5
  - Post status = `publish`
  - Rank Math SEO score = 75

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
- [x] Step 1: Write failing automated tests (Test Harness Setup - `test_rollback_regex.py` PASS ✅)
- [>] Step 2: Implement and execute `rollback_post_621_transit_guide.py` (Active ⚡)
- [ ] Step 3: Run WP-CLI remote verification (Check post_content, status, SEO score)
- [ ] Step 4: Run live site curl verification (Check HTTP 200, 0 guide, 5 location cards)
- [ ] Step 5: Final proof of execution logs and summary report
