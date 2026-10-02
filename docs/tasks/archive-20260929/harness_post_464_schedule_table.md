# 🎯 Prompt Harness Specification: Post #464 Concert Schedule Table Remediation

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #464(이승철 40주년 콘서트 THE VOICE)의 전국투어 일정 표에 6개 도시(서울, 광주, 대전, 대구, 인천, 부산)의 일시와 시간을 일체형으로 통합 명시(`공연일` -> `공연일시`)하고, 하단에 분리되어 혼란을 주던 부분 시간 텍스트를 제거하여 독자 혼선을 해소한다.
- **In-Scope Deliverables**:
  - `scripts/patch_post_464_schedule.py`: 백업, CAS 해시 검증, 표 변환, 원격 WordPress 초안 업데이트 및 검증 스크립트
  - `agent-publisher/tests/test_patch_post_464_schedule.py`: TDD 기반 단위 테스트 스위트 (테이블 파싱, 시간 삽입, 텍스트 제거, 원문 보존성)
  - `docs/harness_post_464_schedule_table.md`: 5-Pillar Harness 규격 문서
- **Strictly Out-of-Scope (Non-Goals)**:
  - 포스트 공개 전환 (반드시 `draft` 유지)
  - 요청 범위를 벗어난 본문 요약, 제목, 가격표, 취소수수료, FAQ 등의 임의 변경 금지
  - 타 포스트 변경 금지
- **Forbidden Boundaries**:
  - 원본 사전 백업 없는 원격 업데이트 금지
  - CAS 해시 불일치 시 강제 덮어쓰기 금지
  - `post_status`를 `publish`로 변경하는 행위 엄격 금지

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Inputs & Types**:
  - `raw_content: str`: Post #464 현재 원본 HTML
  - `expected_sha256: str`: CAS 일치 여부 검증용 SHA256
- **Outputs & Returns**:
  - `patched_content: str`: 일시/시간 통합 표 및 정리된 HTML
  - `new_sha256: str`: 패치 후 콘텐츠 해시
- **Schedule Data Contract**:
  - 헤더: `<th scope="col" ...>공연일시</th>`
  - 서울: `2026.12.04(금) 19:00<br>2026.12.05(토) 16:00<br>2026.12.06(일) 16:00`
  - 광주: `2026.11.14(토) 16:00`
  - 대전: `2026.11.22(일) 16:00`
  - 대구: `2026.11.28(토) 16:00`
  - 인천: `2026.12.12(토) 16:00`
  - 부산: `2026.12.24(목) 19:00`
- **State Changes**:
  - `backups/post_464_before_schedule_patch_<timestamp>.html` 로컬 백업 저장
  - Remote WordPress Post #464 `post_content` 원자적 업데이트 (`draft` 상태 유지)

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| CAS Hash Mismatch | 원격 본문이 변경되었으면 즉시 중단 | `ERR_CAS_MISMATCH` |
| Table Pattern Not Found | 일정 테이블 regex 매칭 실패 시 중단 | `ERR_PATTERN_NOT_FOUND` |
| Incomplete City Times | 6개 도시 중 누락된 시간이 있을 시 예외 발생 | `ERR_INCOMPLETE_SCHEDULE` |
| Remote SSH / WP-CLI Error | 원격 업데이트 실패 시 에러 보고 및 임시 파일 정리 | `ERR_REMOTE_UPDATE_FAILED` |
| Accidental Status Change | post_status가 draft가 아니면 즉시 차단 | `ERR_INVALID_POST_STATUS` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Write First (TDD)**:
  - `test_table_header_updated_to_datetime`: 헤더가 `공연일시`로 정확히 변경되는지 검증
  - `test_all_six_cities_have_exact_times`: 6개 도시의 날짜 및 시간이 정확히 삽입되는지 검증
  - `test_redundant_bottom_text_removed`: 하단 중복 문구가 깔끔하게 제거되는지 검증
  - `test_unrelated_content_preserved`: 목차, 요약, 가격표, FAQ, CTA 등이 100% 보존되는지 검증
  - `test_cas_verification_behavior`: 잘못된 SHA256 입력 시 에러를 던지는지 검증
- **Verification Commands**:
  - Syntax Check: `python -m py_compile scripts/patch_post_464_schedule.py`
  - Test Suite: `python -m unittest agent-publisher/tests/test_patch_post_464_schedule.py -v`
  - Remote Verification: `ssh bloguito "sudo docker exec wordpress_app wp post get 464 --format=json --allow-root"`
- **Success Criteria**: 모든 테스트 통과 (Exit code 0), 원격 WordPress #464가 draft 상태로 정상 업데이트됨.

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
### 📋 Live Task Progress
- [ ] Step 1: Write failing automated tests (`agent-publisher/tests/test_patch_post_464_schedule.py`)
- [ ] Step 2: Implement patch logic in `scripts/patch_post_464_schedule.py`
- [ ] Step 3: Run test suite & verify 100% green status
- [ ] Step 4: Execute remote update against Post #464 with backup & CAS verification
- [ ] Step 5: Final verification of remote post state & proof of execution logs
