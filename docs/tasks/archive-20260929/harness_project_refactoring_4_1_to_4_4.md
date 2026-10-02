# 🎯 Prompt Harness Specification: Repository Optimization (4.1 ~ 4.4)

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Bloguito 프로젝트의 저장소 위생 정리(4.1), 시크릿 보안 거버넌스(4.2), 문서 아카이빙 구조화(4.3), 선언적 포스트 컴포넌트 패치 도구화(4.4)를 체계적으로 실행하고 기존 585개 테스트 및 신규 테스트의 무결성을 검증한다.
- **In-Scope Deliverables**:
  1. Post #621 관련 일회성 스크립트/테스트 12개를 `scripts/archive/post-621/`로 격리 보존
  2. Post #621 관련 하네스 문서 5개를 `docs/tasks/post-621/`로 격리 보존
  3. 카카오 지도 API 키 평문 노출 제거 및 `os.getenv` 환경변수 처리
  4. `git worktree prune` 안전 실행
  5. `docs/` 내 날짜별 단일 작업 일지를 `docs/tasks/2026-09/`로 이동 및 `docs/INDEX.md` 링크 동기화
  6. `scripts/patch_post_component.py` (선언적 본문 블록 패치 도구) 구현
  7. `agent-publisher/tests/test_patch_post_component.py` 단위 테스트 구현
- **Strictly Out-of-Scope (Non-Goals)**:
  - 사용자 작업 파일의 무단 영구 삭제 (모두 archive 디렉토리로 보존 이동).
  - 실서버 WordPress 게시물 원격 변경 (로컬 컴포넌트 로직 및 도구화에 집중).
  - 기존 585개 테스트의 검증 임계값 변경.
- **Forbidden Boundaries**:
  - `docs/POST_CATALOG.md`, `docs/EDITORIAL_SYSTEM.md`, `docs/OPERATIONS.md`, `agent-publisher/editorial_policy.json`의 편집 규약 변경 금지.

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Component Patcher CLI (`scripts/patch_post_component.py`)**:
  - `apply_component_patch(content: str, action: str, target_pattern: str, replacement: str) -> str`
  - Actions:
    - `inject-after`: 지정된 정규식/패턴 직후에 컴포넌트 삽입
    - `inject-before`: 지정된 정규식/패턴 직전에 컴포넌트 삽입
    - `replace`: 지정된 정규식/패턴을 컴포넌트로 치환
    - `remove`: 지정된 정규식/패턴 블록 제거
  - Flags:
    - `--action {inject-after, inject-before, replace, remove}`
    - `--target-pattern REGEX`
    - `--component-file FILE` 또는 `--component-string STRING`
    - `--input-file FILE` (또는 stdin)
    - `--output-file FILE` (또는 stdout)
    - `--expected-sha256 SHA` (CAS 안전 검사)

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| Target pattern not found | Raise ValueError / Exit code 2 | `ERR_PATTERN_NOT_FOUND` |
| Multiple matches without flag | Reject ambiguity | `ERR_AMBIGUOUS_MATCH` |
| Component file missing | FileNotFoundError / Exit code 3 | `ERR_FILE_NOT_FOUND` |
| SHA256 mismatch | Abort without modifying content | `ERR_CAS_MISMATCH` |
| Missing API key in env | Fallback gracefully with warning | `WARN_API_KEY_MISSING` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests (`agent-publisher/tests/test_patch_post_component.py`)**:
  - `test_inject_after_pattern`: 마커 직후 정상 삽입 검증
  - `test_inject_before_pattern`: 마커 직전 정상 삽입 검증
  - `test_replace_pattern`: 마커 블록 정상 치환 검증
  - `test_remove_pattern`: 마커 블록 정상 제거 검증
  - `test_pattern_not_found_raises`: 패턴 미발견 시 예외 발생 검증
  - `test_sha256_verification`: SHA 불일치 시 거부 검증
- **Verification Commands**:
  - `./agent-publisher/.venv/Scripts/python.exe -m unittest agent-publisher/tests/test_patch_post_component.py`
  - `./agent-publisher/.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests -q`
- **Success Criteria**: 전체 585개 + 신규 테스트 100% 통과 (Exit code 0).

## 5. 🚀 Execution Protocol (Single Active Task Tracking)
- [x] Step 1: 4.1 저장소 위생 정리 (Post #621 파일 아카이빙 및 worktree prune)
- [x] Step 2: 4.2 보안 조치 (카카오 API 키 평문 마스킹 및 환경변수 주입)
- [x] Step 3: 4.3 문서 아카이빙 구조 개편 및 `docs/INDEX.md` 정합성 검증
- [x] Step 4: 4.4 범용 컴포넌트 패처 구현 및 단위 테스트 작성
- [x] Step 5: 전체 테스트 슈트 실행 및 검증 완료 증명 (593 passed, OK ✅)
