# 🎯 Prompt Harness Specification: Post #464 FAQ Practicality Remediation

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #464(이승철 40주년 콘서트 THE VOICE)의 FAQ 섹션에서 상단 요약 및 가격표에서 이미 2회 설명된 가격 중복 질문("THE VOICE 좌석 가격은 얼마인가요?")을 제거하고, 실제 방문자가 가장 빈번하게 검색하는 실무 의문인 **"예매 완료 후 좌석이나 관람 일정을 변경할 수 있나요?"**로 대체하여 콘텐츠 실용성을 강화한다.
- **In-Scope Deliverables**:
  - `docs/harness_post_464_faq_practicality.md`: 5-Pillar Harness 규격 문서
  - `agent-publisher/tests/test_patch_post_464_faq.py`: TDD 기반 단위 테스트 스위트
  - `scripts/patch_post_464_faq.py`: 백업, CAS 해시 검증, FAQ 교체 패치, 원격 WordPress draft 업데이트 및 검증 스크립트
- **Strictly Out-of-Scope (Non-Goals)**:
  - 포스트 공개 전환 (반드시 `post_status: draft` 유지)
  - 기존 완성된 시간순 일정표, 요약 박스, 공식 포스터, 가격표, 실전 팁 카드, 2개 CTA 임의 수정 금지
  - 타 포스트 수정 금지
- **Forbidden Boundaries**:
  - 원본 사전 백업 없는 원격 업데이트 금지
  - CAS 해시 불일치 시 강제 덮어쓰기 금지
  - `post_status`를 `publish`로 변경하는 행위 엄격 금지

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Inputs & Types**:
  - `raw_content: str`: Post #464 현재 원본 HTML (SHA256: `be5bbe855cd6d4ac173ef5c0482d93261038f35a5d0144aeeae51791309bbeb8`)
  - `expected_sha256: str`: CAS 일치 여부 검증용 SHA256
- **Outputs & Returns**:
  - `patched_content: str`: 실용적 FAQ로 교체된 HTML
  - `new_sha256: str`: 패치 후 콘텐츠 해시
- **FAQ Modification Spec**:
  - **제거 대상 (기존 FAQ 1)**:
    - Q: `THE VOICE 좌석 가격은 얼마인가요?`
    - A: `전국투어 6개 도시(서울, 광주, 대전, 대구, 인천, 부산) 모두 공통으로 FS석 198,000원, VIP석 187,000원, R석 165,000원으로 동일합니다.`
  - **신규 FAQ 1**:
    - Q: `예매 완료 후 좌석이나 관람 일정을 변경할 수 있나요?`
    - A: `예스24 시스템상 예매 완료 후 직접적인 날짜, 회차, 좌석 변경은 불가합니다. 변경을 원하실 경우 기존 예매 건을 먼저 취소한 뒤 새로 예매해야 하며, 취소 시점에 따라 취소수수료가 발생할 수 있습니다.`
- **State Changes**:
  - `backups/post_464_before_faq_remediation_<timestamp>.html` 백업 생성
  - Remote WordPress Post #464 `post_content` 원자적 업데이트 (`draft` 상태 유지)

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| CAS Hash Mismatch | 원격 본문 해시 불일치 시 즉시 중단 | `ERR_CAS_MISMATCH` |
| Old FAQ Pattern Not Found | 교체 대상 FAQ 1 regex 매칭 실패 시 중단 | `ERR_PATTERN_NOT_FOUND` |
| Redundant Price Text Remainder | 본문 FAQ에 가격 질문이 여전히 남아있으면 실패 | `ERR_REDUNDANT_FAQ_REMAINS` |
| Remote SSH / WP-CLI Error | 원격 업데이트 실패 시 에러 보고 및 임시 파일 정리 | `ERR_REMOTE_UPDATE_FAILED` |
| Status Change Violation | post_status가 draft가 아니면 즉시 차단 | `ERR_INVALID_POST_STATUS` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Write First (TDD)**:
  - `test_cas_hash_matches_current`: 현재 본문 해시 일치 검증
  - `test_price_faq_completely_removed`: FAQ 섹션에서 가격 반복 질문이 완전히 제거되었는지 검증
  - `test_new_practical_seat_change_faq_present`: 신규 좌석/일정 변경 질문과 예스24 공식 답변이 삽입되었는지 검증
  - `test_other_faqs_preserved`: 아이 동반 관람 연령(FAQ 2), 배송 티켓 온라인 취소 불가(FAQ 3)가 그대로 보존되는지 검증
  - `test_unrelated_content_preserved`: 시간순 일정표, 포스터 figure, 요약 박스, 2개 CTA 등 기존 요소 보존 검증
- **Verification Commands**:
  - Syntax Check: `python -m py_compile scripts/patch_post_464_faq.py`
  - Unit Test Suite: `python -m unittest agent-publisher/tests/test_patch_post_464_faq.py -v`
  - Full Test Suite: `./agent-publisher/.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests -q`
  - Remote WP Post Verification: `python scratch/verify_post_464_faq.py`
- **Success Criteria**: 모든 테스트 통과 (Exit code 0), 원격 WordPress #464가 draft 상태로 정상 업데이트됨.

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
### 📋 Live Task Progress
- [ ] Step 1: Write failing automated tests (`agent-publisher/tests/test_patch_post_464_faq.py`)
- [ ] Step 2: Implement patch logic in `scripts/patch_post_464_faq.py`
- [ ] Step 3: Run test suite & verify 100% green status
- [ ] Step 4: Execute remote update against Post #464 with backup & CAS verification
- [ ] Step 5: Final verification of remote post state & proof of execution logs
