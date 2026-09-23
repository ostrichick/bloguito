# Bloguito 반복 감사 실행 E2E 검증 — 2026-09-23

## 1. 실제 작업 범위와 안전 경계

- **검증 시각:** 2026-09-23 약 10:50~10:56 KST, 로컬 Windows 작업 트리 `/projects/Bloguito`, 기준 HEAD `979dfac`. `AGENTS.md`, `docs/OPERATIONS.md`, `docs/EDITORIAL_SYSTEM.md`, 이전 `docs/legacy-technical-regression-audit-2026-09-23.md`와 실제 `scripts/audit_legacy_posts.py`·전용 테스트를 확인했다. 현대화의 반복 감사 단계에 관한 **실행·기술 E2E**이며 개별 글의 공식 사실 검토나 브라우저 접근성 인증이 아니다.
- **허용한 실사이트 작업은 익명 공개 WordPress REST의 GET뿐.** 신설한 Git 무시 `tmp/legacy_audit_20260923/technical-e2e/` 아래 `tempfile.TemporaryDirectory` 두 종류에서 실 공개 GET 드라이런·최초 스냅샷 및 mock REST 기반 반복 CLI를 수행했다. 임시 폴더가 정확히 이 증거 디렉터리의 직접 자식인지 코드로 확인하고 종료 시 그 임시 폴더만 자동 정리한다. 외부 WordPress·SSH·서버·백업·실제 감사 상태에는 쓰기나 삭제를 하지 않았고 cron/Task Scheduler·알림 전송·Git stage/commit/push도 없다.
- **절대 보존한 기존 실행본:** `tmp/legacy_audit_20260923/prime/recurring-state/runs/20260923T001638Z-b2cf243a/`는 읽기 전용 파일명 확인 시 네 파일이며 신규 `run-manifest.json`이 없다. 이번에는 이 폴더 및 해당 `prime/recurring-state`의 포인터, 스냅샷, 잠금, 보존 상태를 수정하지 않았다. 신규 manifest가 없는 과거 실행본을 추정으로 인증·삭제하지 않는다.
- 이 작업에서 수정한 Git 추적 코드 **정확히 2개**: `scripts/audit_legacy_posts.py`, `agent-publisher/tests/test_legacy_post_audit.py`. 새 보고서는 이 문서 하나; 증거 스크립트와 JSON/로그는 Git 무시 경로에만 있다. 다른 작업자의 기존 미커밋 편집과 원격 운영 파일은 유지했다.

## 2. 출발 입력 → 검증 출력의 실 E2E

실행 스크립트: `tmp/legacy_audit_20260923/technical-e2e/e2e_recurring.py`. 이를 프로젝트 `.venv` Python `-B`로 실행하며 `PYTHONDONTWRITEBYTECODE=1`, 프로젝트 루트 `PYTHONPATH`를 설정한다. 스크립트는 `scripts/audit_legacy_posts.py`의 실제 CLI를 subprocess로 두 번 호출한다. **첫 실행은 `--recurring-state-dir <새 임시 경로> --dry-run --strict-alert`이고 둘째 실행은 같은 경로에서 `--retain 2 --strict-alert`**이다. 실제 공개 API 응답을 fixture로 대체하지 않은 두 호출이며 WordPress REST GET만 수행했다.

| 확인 항목 | 직접 확인한 결과 |
| --- | --- |
| 실제 공개 수집 | 29/29건, 두 번의 CLI 종료 코드 각각 `0`; 최초 기준선 없는 완전 공개 REST 스냅샷. |
| 무변경 dry-run | `status=complete`, `dry_run=true`, **지정 상태 디렉터리 생성 없음**. |
| 신규 첫 실행 | `status=complete`, `dry_run=false`, `baseline_available=false`, 검토 기한 미등록 29/29. 새로운 전용 임시 상태 디렉터리에만 기록. |
| 저장 검증 | `latest.json`의 run ID가 실제 완성 `runs/<ID>/`와 일치. `run-manifest.json`의 사이트/ID/시간·snapshot, triage, Markdown report 세 파일의 **실제 저장 바이트 SHA256 일치**. `load_previous`·`_read_checkpoint` 및 `_validate_owned_run` 모두 통과. |
| 출력과 상태 | 완성 snapshot·triage가 각각 `complete=true`, 29건; `report.md`의 실제 글별 행 **29개**; `alert-summary.json`은 `status=complete`, 최초 `pruned_runs=0`; `last-attempt.json` 존재, 실행 잠금 잔류 없음. |

**범위 제한:** 공개 REST 원본이 실제 WP DB `post_content`를 대체하지 않으며 29개 글의 날짜·사실·링크 실행 가능성·검토 만료가 실제로 검증됐다는 뜻이 아니다. 두 GET 사이 발생 가능한 타 편집을 트랜잭션 단위로 배제하지 않았고, 실제 사이트에 변화나 공개 글 수정은 유발하지 않았다.

### 합성 3회 실제 CLI + 실패/이물 시나리오

- 별도 **신규 임시 상태**에서 `fetch_public_posts`만 mock한 1건짜리 합성 게시글 #991을 사용했다. `main()` CLI 인자를 실제 `--recurring-state-dir --retain 2 --strict-alert`로 처리하고 JSON stdout 및 `SystemExit`을 검사했다. 순서는 최초 본문 → **본문만 변경** → 본문 동일한 세 번째 정상 실행 → 합성 수집 예외 순서다. 사용자에게 보이는 종료 코드 정확히 **`0 → 2 → 0 → 3`**.
- 두 번째 실행에서 `changed_posts=[{"id":991,"fields":["rendered_sha256"]}]`, `public_inventory_changed` 경보, `triage.json` 변경 필드와 `report.md`의 글 991 변경 표시를 대조했다. 세 번째에는 alert `[]`, `pruned_runs=1`, 최초 실행 폴더가 실제 제거되고 **최근 두 개만 남음**. 이후 현재 최신 포인터와 manifest는 유효하다.
- 네 번째 합성 수집 실패에서 CLI는 URL·원문·예외 메시지 대신 `status=failed`, `error_type=ValueError`와 종료 **3**을 출력했고, 이전 `latest.json` 바이트·검증된 완성본이 유지되며 `last-attempt.json`만 `failed`로 기록됐다. 잠금 잔류 없음.
- 추가 별도 임시 상태: 이름만 유효한 미서명 예전 실행 폴더, 무효 snapshot, 타인 `unrelated-sentinel.txt`를 삽입했다. 정상 다음 수집/체크포인트는 성공하나 자동 보존은 `retention_warning=ValueError`, `retention_requires_attention`으로 실패하여 **strict 종료 2**. 해당 가짜 폴더·sentinel·기존 정상 실행 3개 모두 보존했고 최신 체크포인트는 유효하다. 이 실험은 실제 prime의 미서명 실행본이 아닌 별도 합성 자료다.

최종 E2E 출력: `technical-e2e/e2e-console-final.log`, 비식별 요약 `technical-e2e/e2e-results.json`. `E2E_ALL_ASSERTIONS_PASS`, 실행 종료 코드 **0**. 실사이트 응답 원문·비공개 글·인증정보는 보고서/요약에 복사하지 않았다.

## 3. E2E에서 새로 드러난 결함 및 최소 수정

**재현(수정 전):** 동일 초 내 `main()` 정상 3회를 빠르게 연속 호출하면 반환은 `pruned_runs=1`, `runs=2`, strict 종료 0이었지만, **가장 오래된 첫 실행 폴더가 남아 있었다**. 정확한 원인은 `runs/<UTC초>-<무작위 8hex>` 이름을 `_prune_owned_runs()`가 사전식 정렬하기 때문. UTC 초가 같으면 무작위 문자열은 시간 순서를 나타내지 않아 첫 실행이 아닌 두 번째 실행을 삭제할 수 있었다. 삭제 자체는 합성 새 임시 디렉터리 안에서만 일어났으며 운영 실행본 삭제는 관측·시도하지 않았다.

**적용한 좁은 수정:** `scripts/audit_legacy_posts.py`의 신규 `audited_at`을 마이크로초를 보유한 `current.isoformat(timespec='microseconds')`로 기록해 snapshot·triage·run-local manifest·체크포인트의 동일 정확한 시각 계약을 유지한다. 보존 대상은 검사된 `run-manifest.json`의 `audited_at` 실제 시각을 기준으로 정렬하고 **경계 동률이 생겨 안전한 선후를 판단할 수 없으면 모든 후보 삭제를 중단**해 기존 `retention_requires_attention` 경고·strict 종료 2로 알린다. 신규 폴더/불변 3개 SHA·가변 alert 파일 검사와 사전 전수 검증, 실제 읽기 전용 상태 보존 경계는 그대로다.

**회귀 추가:** 같은 초에 `100000 → 200000 → 300000` 마이크로초를 명시하고 UUID suffix를 `f0000000 → 80000000 → 10000000` 역순으로 **고정**한 테스트가 가장 오래된 첫 실행만 삭제하고 최근 두 실행을 보존하는지 검사한다. 또 동률 시각의 삭제 경계는 자동 정리를 멈추고 실행본 3개 전부 보존하는 테스트를 추가했다. 무작위 suffix의 우연한 순서에 의존하는 비결정적 테스트는 사용하지 않았다.

**manifest 계약 판정:** `run-manifest.json`은 `schema_version/site/run_id/audited_at` 및 불변 `public-rest-snapshot.json`·`triage.json`·`report.md` SHA 세 개를 결합한다. `alert-summary.json`은 정리 종료 후 새 내용으로 다시 쓰므로 *불변 SHA에 포함하지 않고*, 소유 실행 필수 파일 및 JSON `status/audited_at` 조건으로 검증하는 현 정책이 실제 E2E와 일치했다. 오래된 무manifest 파일의 자동 삭제는 허용하지 않는다. `run_id`에는 초까지만 표시되므로 같은 초의 서로 다른 마이크로초는 이름이 아닌 manifest를 통해 구분한다. 파일 내용에 대한 SHA는 손상 감지이며 서명이나 동시 악의적 바꿔치기를 막는 보호라고 주장하지 않는다.

## 4. 테스트·검증 및 협업 경계

| 검사 | 결과 |
| --- | --- |
| 감사 전용 unittest | `test_legacy_post_audit.py` **20/20 PASS**, 종료 0. 기존 18개 + 새 정확 시각/동률 2개. |
| 전체 `.venv` unittest 최초 회차 | **310개 실행, 실패 1·건너뜀 1, 종료 1**. 다른 작업자 소유 `test_legacy_reference_period.py`에서 #103이 `ready`라고 기대했으나 현재 `editorial.py`의 `mokpo_city_program_age_conflict_unresolved`로 차단. 본 작업 파일과 무관하며 prime에 즉시 알리고 해당 테스트·정책은 수정하지 않음. |
| 전체 `.venv` unittest 최종 재실행 | 다른 작업자가 병행 변경한 **현 공유 작업 트리** 기준 **311건 실행, 310 PASS·1 SKIP, 실패 0, 종료 0**. 첫 실패가 본인의 코드 수정으로 고쳐졌다고 주장하지 않음. Git HEAD/원격 CI 또는 운영 서버 검사 결과가 아님. `technical-e2e/full-final.log`. |
| 소유 두 파일 Python `compile(...,'exec')` | **2/2 PASS**, `.pyc` 의도적 생성 없음. |
| `git diff --check` | **종료 0**, 기존 작업 트리의 LF/CRLF 변환 경고만 존재. |
| 파일·상태 경계 | `git status --short`에서 이 작업 코드 변경은 `scripts/audit_legacy_posts.py`와 `agent-publisher/tests/test_legacy_post_audit.py`, 추가 문서는 본 파일. `technical-e2e/`는 `.gitignore`의 `/tmp/`에 의해 제외됨. 기존 prime 미서명 실행 폴더 여전히 존재·manifest 없음 재확인. |

**운영 미검증:** cron 또는 스케줄러 설치/실행, 실제 경보 수신, 반복 14회·장기간 디스크/NTFS 장애·강제 종료, 실제 WordPress 쓰기/DB CAS, OS 레벨 파일 경쟁·악의적 심볼릭 링크 변조, 기밀성 보호, 전체 백업 실제 복구. 실행 가능한 자동 감사 도구가 있다는 이유로 사람 검토 레지스터·알림 감독·운영 보존 정책이 설정됐다고 주장하지 않는다. 미서명 기존 실행본은 담당자가 별도 확인·보관/이관 결정을 하기 전까지 **자동 삭제 금지** 상태다.
