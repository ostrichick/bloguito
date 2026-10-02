# 🎯 Prompt Harness Specification: Post #464 UX & Information Enrichment

## 1. 🌐 Objective & Scope Boundaries
- **Core Mission**: Post #464(이승철 40주년 콘서트 THE VOICE)에 사용자가 승인한 4대 보강 사항(① 전 지역 공통 좌석 가격 안내 통일, ② 하단 2차 예매 CTA 버튼 추가, ③ 예스24 예매 실전 체크리스트 추가, ④ 본문 내 공식 포스터 비주얼 배치)을 원자적으로 적용하여 방문자 편의성을 극대화한다.
- **In-Scope Deliverables**:
  - `docs/harness_post_464_ux_enrichment.md`: 5-Pillar Harness 규격 문서
  - `agent-publisher/tests/test_patch_post_464_ux_enrichment.py`: TDD 기반 단위 테스트 스위트
  - `scripts/patch_post_464_ux_enrichment.py`: 백업, CAS 해시 검증, 콘텐츠 보강 패치, 원격 WordPress draft 업데이트 및 검증 스크립트
- **Strictly Out-of-Scope (Non-Goals)**:
  - 포스트 공개 전환 (반드시 `post_status: draft` 유지)
  - 승인되지 않은 제목, 날짜, 시간, FAQ 주제 임의 수정 금지
  - 타 포스트 수정 금지
- **Forbidden Boundaries**:
  - 원본 사전 백업 없는 원격 업데이트 금지
  - CAS 해시 불일치 시 강제 덮어쓰기 금지
  - `post_status`를 `publish`로 변경하는 행위 엄격 금지

## 2. 🔌 Interface & Contract Spec (Data Flow)
- **Inputs & Types**:
  - `raw_content: str`: Post #464 현재 원본 HTML (SHA256: `7f269f405041d9c2d6dd04f38a0c471c159b11924734155ab1da0d0478b6e103`)
  - `expected_sha256: str`: CAS 일치 여부 검증용 SHA256
- **Outputs & Returns**:
  - `patched_content: str`: 보강된 HTML
  - `new_sha256: str`: 패치 후 콘텐츠 해시
- **Content Modifications Spec**:
  1. **요약 박스 & Excerpt**: `서울, 광주, 부산은 FS석` -> `전국투어 전 지역 공통으로 FS석`
  2. **공식 포스터 `<figure>`**: 제1섹션 일정표 아래, 제2섹션 좌석 가격 상단에 공식 포스터 및 캡션 배치
  3. **가격표 테이블 및 안내**: 캡션 및 본문 설명을 `전국투어 전 지역 공통 좌석 가격`으로 통일
  4. **예매 실전 팁 카드**: 제6섹션 하단에 `예스24 티켓 예매 실전 체크리스트` 카드 삽입
  5. **2차 예매 CTA 버튼**: FAQ 직전에 동일한 공식 서비스 예매 목록 버튼 배치
  6. **FAQ 1 답변**: `전국투어 6개 도시(...) 모두 공통으로` 표현 동기화
- **State Changes**:
  - `backups/post_464_before_ux_enrichment_<timestamp>.html` 백업 생성
  - Remote WordPress Post #464 `post_content` 및 `post_excerpt` 원자적 업데이트 (`draft` 상태 유지)

## 3. ⚠️ Failure Modes & Edge Case Matrix
| Scenario / Edge Case | Expected System Behavior | Error Code / Message |
|---|---|---|
| CAS Hash Mismatch | 원격 본문 해시 불일치 시 즉시 중단 | `ERR_CAS_MISMATCH` |
| Pattern Search Failure | 보강 대상 위치 regex 매칭 실패 시 중단 | `ERR_PATTERN_NOT_FOUND` |
| Link Integrity Failure | 2차 CTA 링크가 1차 CTA 링크와 다르면 중단 | `ERR_CTA_MISMATCH` |
| Remote SSH / WP-CLI Error | 원격 업데이트 실패 시 에러 보고 및 임시 파일 정리 | `ERR_REMOTE_UPDATE_FAILED` |
| Status Change Violation | post_status가 draft가 아니면 즉시 차단 | `ERR_INVALID_POST_STATUS` |

## 4. 🧪 Automated Test Harness (Definition of Done)
- **Unit Tests to Write First (TDD)**:
  - `test_cas_hash_matches_current`: 현재 본문 해시 일치 검증
  - `test_all_regions_pricing_terminology`: 가격 안내가 전 지역 공통으로 통일되었는지 검증
  - `test_official_poster_figure_present`: 공식 포스터 figure 및 캡션이 삽입되었는지 검증
  - `test_practical_tip_card_present`: 예매 실전 팁 카드가 삽입되었는지 검증
  - `test_secondary_cta_present_and_exact`: 2차 CTA 버튼이 올바른 예매 링크로 삽입되었는지 검증
  - `test_unrelated_content_preserved`: 일정표, 목차, 취소수수료, 출처 목록 등 기존 내용 보존 검증
- **Verification Commands**:
  - Syntax Check: `python -m py_compile scripts/patch_post_464_ux_enrichment.py`
  - Unit Test Suite: `python -m unittest agent-publisher/tests/test_patch_post_464_ux_enrichment.py -v`
  - Full Test Suite: `./agent-publisher/.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests -q`
  - Remote WP Post Verification: `python scratch/verify_post_464.py`
- **Success Criteria**: 모든 테스트 통과 (Exit code 0), 원격 WordPress #464가 draft 상태로 정상 업데이트됨.

## 5. 🚀 Execution Protocol (Codex / CoS Single-Task Tracking)
### 📋 Live Task Progress
- [ ] Step 1: Write failing automated tests (`agent-publisher/tests/test_patch_post_464_ux_enrichment.py`)
- [ ] Step 2: Implement patch logic in `scripts/patch_post_464_ux_enrichment.py`
- [ ] Step 3: Run test suite & verify 100% green status
- [ ] Step 4: Execute remote update against Post #464 with backup & CAS verification
- [ ] Step 5: Final verification of remote post state & proof of execution logs
