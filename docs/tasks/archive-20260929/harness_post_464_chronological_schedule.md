# 🎯 Prompt Harness Specification: Post #464 Chronological Schedule Sorting

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #464(이승철 40주년 콘서트 THE VOICE)의 전국투어 일정 테이블 행을 비순차적 순서(서울 12월이 최상단)에서 실제 공연 일시 기준의 완전한 시간순(11/14 광주 ➔ 11/22 대전 ➔ 11/28 대구 ➔ 12/4~6 서울 ➔ 12/12 인천 ➔ 12/24 부산)으로 재정렬하여 독자의 가독성을 극대화한다.
- **In-Scope Deliverables**:
  - `docs/harness_post_464_chronological_schedule.md`: 5-Pillar Harness 규격 문서
  - `agent-publisher/tests/test_patch_post_464_chronological_schedule.py`: TDD 기반 단위 테스트 스위트
  - `scripts/patch_post_464_chronological_schedule.py`: 백업, CAS 해시 검증, 테이블 시간순 재정렬 패치, 원격 WordPress draft 업데이트 및 검증 스크립트
- **Strictly Out-of-Scope (Non-Goals)**:
  - 포스트 공개 전환 (반드시 `post_status: draft` 유지)
  - 기존 검증된 날짜, 시간, 공연장, 가격, 취소수수료, 링크 변경 금지
  - 타 포스트 수정 금지
- **Forbidden Boundaries**:
  - 원본 사전 백업 없는 원격 업데이트 금지
  - CAS 해시 불일치 시 강제 덮어쓰기 금지
  - `post_status`를 `publish`로 변경하는 행위 엄격 금지

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Inputs & Types**:
  - `raw_content: str`: Post #464 현재 원본 HTML (SHA256: `6e40c7e8232d5fb53be1afc6d02778e1f1a37674615c934b4fc464aa74b49068`)
  - `expected_sha256: str`: CAS 일치 여부 검증용 SHA256
- **Outputs & Returns**:
  - `patched_content: str`: 시간순 정렬된 HTML
  - `new_sha256: str`: 패치 후 콘텐츠 해시
- **Chronological Table Order**:
  1. 광주 (2026.11.14(토) 16:00 | 광주여대 유니버시아드 체육관)
  2. 대전 (2026.11.22(일) 16:00 | DCC 대전컨벤션센터 제2전시장)
  3. 대구 (2026.11.28(토) 16:00 | 엑스코 서관 1홀)
  4. 서울 (2026.12.04(금) 19:00<br>2026.12.05(토) 16:00<br>2026.12.06(일) 16:00 | KSPO DOME(올림픽체조경기장))
  5. 인천 (2026.12.12(토) 16:00 | INSPIRE ARENA(인스파이어 아레나))
  6. 부산 (2026.12.24(목) 19:00 | 벡스코 제1전시장)
- **State Changes**:
  - `backups/post_464_before_chronological_sort_<timestamp>.html` 백업 생성
  - Remote WordPress Post #464 `post_content` 원자적 업데이트 (`draft` 상태 유지)

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| CAS Hash Mismatch | 원격 본문 해시 불일치 시 즉시 중단 | `ERR_CAS_MISMATCH` |
| Table Pattern Search Failure | 일정 테이블 regex 매칭 실패 시 중단 | `ERR_PATTERN_NOT_FOUND` |
| City Row Missing | 6개 도시 중 하나라도 누락되면 즉시 중단 | `ERR_INCOMPLETE_CITIES` |
| Chronological Inversion | 정렬 결과가 날짜순이 아니면 검증 실패 | `ERR_SORT_ORDER_INVALID` |
| Remote SSH / WP-CLI Error | 원격 업데이트 실패 시 에러 보고 및 임시 파일 정리 | `ERR_REMOTE_UPDATE_FAILED` |
| Status Change Violation | post_status가 draft가 아니면 즉시 차단 | `ERR_INVALID_POST_STATUS` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Write First (TDD)**:
  - `test_cas_hash_matches_current`: 현재 본문 해시 일치 검증
  - `test_chronological_row_order`: 테이블의 행이 광주 ➔ 대전 ➔ 대구 ➔ 서울 ➔ 인천 ➔ 부산 순서인지 정확히 검증
  - `test_all_city_details_intact`: 6개 도시의 날짜, 시간, 공연장 내용이 손실 없이 보존되는지 검증
  - `test_table_accessibility_and_styling`: table, caption, thead, tbody, th, td 스타일 및 속성이 100% 보존되는지 검증
  - `test_unrelated_content_preserved`: 요약, 포스터, 가격표, 실전 팁 카드, 2개 CTA, FAQ, 출처 등 보존 검증
- **Verification Commands**:
  - Syntax Check: `python -m py_compile scripts/patch_post_464_chronological_schedule.py`
  - Unit Test Suite: `python -m unittest agent-publisher/tests/test_patch_post_464_chronological_schedule.py -v`
  - Full Test Suite: `./agent-publisher/.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests -q`
  - Remote WP Post Verification: `python scratch/verify_post_464_chronological.py`
- **Success Criteria**: 모든 테스트 통과 (Exit code 0), 원격 WordPress #464가 draft 상태로 정상 업데이트됨.

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
### 📋 Live Task Progress
- [ ] Step 1: Write failing automated tests (`agent-publisher/tests/test_patch_post_464_chronological_schedule.py`)
- [ ] Step 2: Implement patch logic in `scripts/patch_post_464_chronological_schedule.py`
- [ ] Step 3: Run test suite & verify 100% green status
- [ ] Step 4: Execute remote update against Post #464 with backup & CAS verification
- [ ] Step 5: Final verification of remote post state & proof of execution logs
