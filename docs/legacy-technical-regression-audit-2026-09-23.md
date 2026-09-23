# Bloguito 현대화 독립 기술 회귀 감사 — 2026-09-23

## 1. 범위·기준·변경 격리

- 작업 위치: Windows `/projects/Bloguito`; 기준 HEAD `979dfac`(2026-09-22 18:14:13 KST). 감사 시작 `git status --short`는 **기존 추적 파일 수정 14개**와 여러 타 작업자의 미추적 문서·스크립트·테스트를 보여 주었다. `git diff --stat`은 당시 추적 수정 14개, 추가 822줄·삭제 10줄이다. 이 작업자는 기존 변경을 초기화·스테이징·커밋·푸시하지 않았다. 이 문서가 유일한 새 Git 추적 후보이며 합성 재현 코드·검사 로그는 Git 제외 `tmp/legacy_audit_20260923/technical-qa/`에만 생성했다.
- `AGENTS.md`, `docs/EDITORIAL_SYSTEM.md`, `agent-publisher/editorial_policy.json`, `docs/OPERATIONS.md` 및 9/22–23 진행 기록을 읽었다. 9/22에 합의된 6단계는 **전체 게시물 재고 진단 → 우선순위 → 공통 레이아웃/접근성 → 시범 글 → 잔여 글의 출처 결합 전면 개선·글별 갱신 → 반복 감사·수정 이력**이다(`docs/legacy-modernization-execution-2026-09-23.md:5-9`). 이 문서는 그 계획의 **기술적 로컬 회귀**만 재검토한다. 콘텐츠 독립 검토·글별 승인·실브라우저 접근성이나 백업 실복구를 대체하지 않는다.
- 오늘 09:16 이후 실행 장부(`docs/legacy-modernization-execution-2026-09-23.md:19-33,46-52`)는 #63·#81·#140이 다른 작업자에 의해 적용되고 공개 29편 중 현대식 저장 본문 16·구형 13편이라고 기록한다. 이번 감사는 해당 운영 쓰기를 직접 수행하거나 저장본을 인증하지 않았다. 이전 9/22 기록의 '운영 수정 0/MU 미설치'와 `approval-dashboard`는 역사 시점 기록이며 현행 상태로 재사용하지 않는다.
- Git 추적 파일 목록을 다시 검사한 결과 `.github/workflows/test.yml`, TOC·요약 여백·표 접근성 MU 세 파일 및 해당 WordPress PHP 테스트는 **현 HEAD 추적 상태**다. 9/22 중간 감사의 'CI가 미추적 MU에 의존' 문제는 그때의 관찰로, 이번 현재 문제로 반복 보고하지 않는다. 그러나 원격 Actions 최신 실행은 조회하지 않았다.
- **실행 금지:** WP/SSH/서버 명령, Docker 서비스 시작·중단, 실제 `backup_daily.sh`/`restore_backup.sh --yes`/실제 백업 동기화, WordPress 글 쓰기, 관리자 명령, 정기 스케줄·알림 등록, `.env`나 비공개 백업 출력. 테스트에는 합성 데이터·가짜 Docker·프로세스 mock 또는 공개 REST GET만 사용했다.

## 2. 실제 실행한 검사와 숫자

| 항목 | 직접 실행한 명령/범위 | 결과와 한계 |
| --- | --- | --- |
| 전체 Python unittest | 프로젝트 `.venv` Python `-B -m unittest discover -s agent-publisher/tests -q`; `PYTHONPATH=agent-publisher`, `PYTHONDONTWRITEBYTECODE=1` | **292건 실행, 291 PASS·1 SKIP, 실패 0, 종료 0**. `technical-qa/unittest-full.log`에 결과 저장. `FAILED … simulated transfer interruption` 문자열은 의도적으로 전송 장애를 주입한 **정상 통과 테스트의 stderr**다. 처음 실행 래퍼의 PowerShell `$ErrorActionPreference=Stop`은 이 stderr를 `NativeCommandError`로 간주해 조기 중단; `Continue`로 재실행하여 전체 결과 확인. |
| 활성 Python 문법 | `compile(bytes, filename, 'exec')`로 `agent-publisher/**/*.py`의 `.venv` 제외 파일과 `scripts/*.py` 총 **88개** | 88/88 PASS, `.pyc` 의도적 생성 없음. 구형 `scripts/archive/`는 활성 코드 범위에서 제외. |
| 광범위 레거시 검사 추가 관찰 | 보관 `scripts/archive/`까지 포함하는 별도 재귀 문법 조사 | 검사 시점 **87개 중 1개 오류**: *Git 추적* `scripts/archive/attach_remaining_thumbs.py:9`의 `unexpected indent`; 8행 `tasks = [tasks[1]]` 뒤 미완성 매핑. 해당 파일은 23–35행에 Docker/WP 미디어 변경 호출이 있으므로 실행·수정하지 않았다. 활성 88개 PASS와 혼동 금지. 이 보관 스크립트가 실행 경로에 다시 연결될 때 소유자의 완전한 재작성과 실행 차단 필요. |
| Bash | Git Bash `bash -n agent-publisher/backup_daily.sh agent-publisher/restore_backup.sh` | **2개 구문 PASS**, 종료 0. 실제 백업/복원 아님. `shellcheck` Windows PATH에서 확인 불가. |
| Node / WhatsApp | `node --check index.js`, `node --check command_policy.js`; bridge 폴더 `npm test` | 구문 **2/2 PASS**, npm 정책 단위테스트 **3/3 PASS, 0 실패**, 종료 0. 운영 WhatsApp 계정·실제 `/publish` 메시지 전송 없음. `technical-qa/npm-test.log`. |
| Compose | `MYSQL_ROOT_PASSWORD=ci-placeholder MYSQL_PASSWORD=ci-placeholder docker compose -f wordpress/docker-compose.yml config --quiet` | 종료 **0**, 설정 구문만. Compose 원문/비밀 출력이나 컨테이너 변경 없음. |
| PHP | Windows `Get-Command php` 검사 | **PHP CLI 부재**, MU `php -l`, PHP 8.3 계약·실제 WP hook 검사는 이번 로컬 회차 **미실행**. CI에 정의됐다는 사실이 실행 증거는 아님. |
| Git diff | `git diff --check` | 종료 **0**; 기존 CRLF/LF 정규화 예고 경고만. 미추적 전체 파일의 내용 검사는 아님. |
| 실제 사이트 감사 안전 드라이런 | `python -B scripts/audit_legacy_posts.py --recurring-state-dir tmp/legacy_audit_20260923/technical-qa/read-only-dry-run-state --dry-run --strict-alert` | 익명 공개 REST **29/29건 complete**, 구형 후보 **13**, 사람 검토기한 미등록 **29**, 새 비교 기준선 없음, 경보 `[]`, 종료 **0**. 지정 상태 폴더 생성 **False**, 스케줄·알림·WP 쓰기 **0**. `technical-qa/public-dry-run.log`. 기준선 부재의 `변경 없음`은 이전 시점 대비 불변 증명이 아니다. |

전체 unittest는 **현재 미커밋·미추적 파일을 포함한 작업 트리**를 검증했다. `HEAD`만 체크아웃한 CI의 테스트 건수·원격 Actions 성공/실패나 서버 런타임 동작을 의미하지 않는다. updater/SSH 제한, 읽기 전용 승인 준비, 합성 v3 백업·복원 검증·동기화, 반복 감사의 기존 테스트가 전체 292건에 포함됐지만, 실제 승인 없는 updater나 백업/복원을 시험한다는 뜻으로 운영 명령을 호출하지 않았다. `docs/legacy-modernization-execution-2026-09-23.md:17`의 09/23 04:00 v3 아카이브 `--verify-only` 성공은 총괄 작업자의 운영 관측이며 이번 독립 감사자가 재실행한 작업이 아니다.

## 3. 독립 재현한 실제 결함 — 반복 감사 보존 삭제 경계

**판정: 결함 확인, 소유 코드 무수정, 수정 전 자동 보존 기능에 주의 필요.**

`scripts/audit_legacy_posts.py:501-518`의 `_prune_owned_runs(state, keep, current_id)`는 `runs/` 하위 이름이 `YYYYMMDDTHHMMSSZ-8hex`와 맞고 `public-rest-snapshot.json`이라는 **파일만 존재**하면 `shutil.rmtree(item)`으로 삭제한다. 도구가 실제 생성한 실행본인지 확인할 run 단위 소유 표식, JSON 유효성, `schema_version/site/complete`, 필수 출력 4종, 내용 SHA에 관한 판별이 없다. 이는 `docs/legacy-audit-scheduler-approval-2026-09-22.md:54-55`의 '도구 소유 완전 실행본만 정리, 알 수 없는 폴더·다른 작업자 파일 보존' 설명과 다르다.

**독립 재현 절차:** Git 제외 `technical-qa/reproduce_audit_boundaries.py`가 `tempfile.TemporaryDirectory` 안에서 WP REST 응답 1건을 mock하여 도구의 첫 합성 성공 기록 생성 → 기존 감사 상태 안에 제3자가 만든 형태의 `runs/20260901T000000Z-deadbeef/` 생성 → 그 안에 **유효하지 않은 JSON**의 `public-rest-snapshot.json`과 `unrelated-sentinel.txt` 삽입 → `retain=2`로 두 번째 합성 감사 실행. 단 한 번의 사이트 HTTP/서버 호출도 없다. `boundary-probe.log`, `boundary-probe-repeat.log` **2회 동일하게**:

```text
FORGED_DIR_REMOVED True
FORGED_RETENTION_PRUNED_COUNT 1
CHECKPOINT_VALID True
SYMLINK_PROBE_UNAVAILABLE OSError
```

즉 **도구가 만들지 않은 폴더와 별도 sentinel이 삭제되는 실제 데이터 보존 결함**이다. 영향은 작업자가 지정한 전용 감사 상태 폴더의 `runs/` 아래에 한정되고, 운영 폴더에서 동일 사건이 발생했다고 주장하지 않는다. 현재 합성 테스트가 상태 최신 포인터를 유지했다는 사실도 임의 자료 삭제를 정당화하지 않는다. 기존 292건 PASS는 이 부정 사례를 검증하지 않았음을 보여 준다.

**prime/소유자용 최소 패치 제안(이 작업자는 공유 코드 미변경):**

1. 새 실행본의 원자적 `.pending`→완성 이름 변경 **전에** 버전·site·run ID 및 **불변** 출력(`public-rest-snapshot.json`, `triage.json`, `report.md`)의 SHA256을 넣은 *run-local* 소유 manifest를 함께 쓴다. 네 번째 `alert-summary.json`은 현재 코드 `:605-606`에서 보존 처리 후 재작성되므로 최초 SHA를 고정할 경우 정상본을 스스로 무효화한다. 이 파일은 구조·존재를 별도 검증하거나, 최종 갱신 시 서명 manifest도 안전하게 갱신하는 설계가 필요하다. 오래된 manifest 부재 실행본은 자동 삭제 불가 대상으로 보존하고, 필요한 경우 수동 검증 후 별도 이관하도록 한다. 출처 수집 실패·부분 실행에도 미서명 소유 표식이 생기지 않아야 한다.
2. 정리 후보 **전체**를 삭제 이전에 우선 검증한다. `runs` 및 각 폴더/파일에 대한 심볼릭 링크 금지, 실제 resolved 부모 경계 검사, manifest의 site/schema/ID/불변 해시·실제 4개 파일 완전성·공개 snapshot `load_previous` 검사 중 하나라도 실패하면 **삭제 0건 + `retention_warning`/`retention_requires_attention`**으로 fail closed 한다. 다른 작업자가 만든 파일이 함께 있을 때도 보존; 오래된 정상 기록의 소유 표식 이관 방식은 운영자가 명시적으로 관리한다. 검사 중간에 앞부분만 삭제하고 뒤에서 실패하는 순차 변경은 피한다.
3. 추가 신규 회귀: 이름만 정규식과 맞는 가짜 폴더·손상 JSON·별도 sentinel이 `retain=2`에서 **삭제되지 않음**; 잘못된 manifest/해시·`runs` 링크·미완성/외부 파일을 안전 차단; 정상 서명 실행 3회에서 2개 보존하며 최신 포인터·완성 체크포인트 유효. 실제 Linux 환경에서 링크 관련 재현을 별도로 수행할 것.

**추가 정적 위험(재현 구분):** `_safe_state_dir()`은 state 루트 심볼릭 링크는 확인하나 내부 `runs` 디렉터리에 대한 링크를 별도로 확인하지 않는다(`:394-405`, `:574-584`); `_prune_owned_runs()`도 `runs.resolve()`만 사용할 뿐 `runs.is_symlink()` 검사가 없다. Windows 개발자 권한에서 `runs.symlink_to()`는 `OSError`가 발생하여 외부 경로 쓰기·삭제는 **재현하지 못했다**. 보안 결함이 실증됐다고 과장하지 말고 위 안전 보강의 검증 항목으로 취급한다.

## 4. 추가 정적 점검 및 수정하지 않은 위험

- **게시물 업데이터:** `scripts/update_existing_via_ssh.py:35-67`의 transport는 고정 WP `list/get/특정 ID update`만 허용하고, 정규 `editorial_updater.py:28-100`은 확인 플래그·원본 SHA CAS·전 상태 재고·24h 리뷰·공식 원문 SHA·원본 백업·사후 재조회로 묶는다. 전체 unittest에서 대응 mock 검사를 통과했다. 그러나 워커는 **운영 update를 한 번도 호출하지 않았으므로** 사이트 데이터 경쟁 편집, 운영 SSH 권한, 실제 복구 성공까지 인증할 수 없다. `prepare_post_approval.py`는 읽기 전용 WP 명령 allowlist를 가지지만 이번 독립 작업은 전혀 원격 조회하지 않았다.
- **백업:** `backup_daily.sh`와 `restore_backup.sh` 구문은 통과하고, 합성 테스트는 fake Docker/v3 생성, 해시·위험 tar 거부, 전송 실패 시 기존 로컬 백업 보존 등을 검사한다. 일일 보존 정리는 코드 `backup_daily.sh:212-218`의 백업 루트 `-maxdepth 1`에만 적용되어 격리 하위 폴더는 제외하도록 설계돼 있다. `secrets.tar.gz`는 여전히 암호화하지 않은 압축본이며 격리 호스트의 실제 DB·파일·로그인 복원, 재해 복구 및 오프사이트 암호화·독립 키 검증은 이번 범위 밖이다.
- **잠재 동기화 중단 지연(정적, 미재현):** `scripts/sync_backups.py:111-115`의 공통 `subprocess.run`에는 Python `timeout`이 없다. SSH `ConnectTimeout=10`은 연결 단계만 제한하며 이미 연결된 뒤 멈춘 SCP/원격 `find`·SHA는 무한정 대기할 수 있다. 기존 `.part`/원본 보존 설계가 있어도 감사·백업 작업 자체가 끝나지 않을 수 있다. 소유자가 제한된 시간 상한과 `subprocess.TimeoutExpired → BackupError` 처리, 모의 장기 전송/정상 장기 파일 크기 테스트를 검토할 것. 이 회차에 실제 전송 장애를 발생시키거나 운영 SSH를 호출한 결과는 아니다.
- **보관 스크립트 문법:** `scripts/archive/attach_remaining_thumbs.py`의 위 구문 오류는 전체 recursive compile/재활용시 실패하지만 현재 CI Python unittest와 활성 스크립트 88개에는 포함되지 않는다. 해당 파일의 직접 WordPress 미디어 수정 로직은 실행하거나 파일 자체를 고쳐 활성화하지 않는다. 소유자의 사용 여부·폐기 여부 확인 후 별도 조치가 필요하다.

## 5. 완료·인계 및 검증 한계

**수정 사항:** 새 문서 본문 1개, Git 무시 합성 결함 재현 스크립트 1개와 검사 출력 로그만 생성. `scripts/audit_legacy_posts.py`, 기존 테스트, 백업·업데이터·PHP·정책·운영 파일은 변경하지 않았다. 확인된 삭제 결함은 소유 코드가 수정되지 않아 **여전히 재현**되며 이번 결과를 '결함 수정 완료'로 보고할 수 없다. prime은 감사 보존 자동 정리 기능을 장기 스케줄에 적용하기 전 제3절의 최소 fail-closed 수정과 회귀를 우선 검토해야 한다.

**남은 검증:** 소유자 수정 후 문제 재현 재실행 및 정상 보존 회귀, Linux/PHP 8.3 lint·MU 런타임, 원격 GitHub Actions, 진짜 WordPress 동시 편집/원본 CAS·현행 cron/알림 전달, 별도 분리된 호스트에서 실제 v3 완전 복원, 전체 모바일·키보드·네이티브 200%/스크린리더 검증. 로컬 테스트 PASS나 공개 REST 29편 완전 수집을 이러한 결과로 확대하지 않는다.

## 6. 후속 긴급 수정 — 보존 삭제 경계 (위 §3·§5의 수정 전 상태를 대체)

- 총괄 요청에 따라 이 작업자가 `scripts/audit_legacy_posts.py`의 `_prune_owned_runs`와 `agent-publisher/tests/test_legacy_post_audit.py` **두 기존 파일만** 좁게 수정했다. 기존 14개 tracked 변경 및 다른 담당자 수정은 유지했다. 실행본이 생성될 때 **완성 폴더로 원자 이름 변경하기 전**, `run-manifest.json`에 도구 스키마·site·run ID·조회 시각과 불변 3개 파일(`public-rest-snapshot.json`, `triage.json`, `report.md`)의 **실제 저장 바이트 SHA256**을 기록한다. 마지막 `alert-summary.json`은 보존 작업 후 다시 기록되는 가변 파일이므로 별도 존재·JSON 상태·시각 검사 대상으로 두고 불변 해시 대상으로 잘못 표시하지 않는다.
- 정리 시 `runs` 링크·Windows junction, 실행 폴더 및 자식 파일 링크, 외부 부모 경로, 알 수 없는 추가 파일·불완전한 파일 세트, manifest 부재/ID·site·시간·SHA 불일치, snapshot의 완전성/게시물 스키마, report/alert의 대응 관계를 **모든 실행 폴더에서 삭제 이전에 선검증**한다. 하나라도 문제면 **삭제 0건**, `retention_warning=ValueError`, `retention_requires_attention`으로 반환한다. 검사 통과한 오래된 정규 실행 폴더만 지운다. 동시 악의적 파일 교체에 대한 OS 수준 원자 삭제나 manifest 서명은 구현하지 않았으며 별도의 보안 인증으로 간주하지 않는다.
- 원래 정확히 같은 격리 합성 재현 스크립트를 **2회 재실행**하여 모두 `FORGED_DIR_REMOVED False`, `FORGED_RETENTION_PRUNED_COUNT None`, `CHECKPOINT_VALID True`, 종료 0. 원래 `True/1`이었던 임의 sentinel 삭제가 중단됐다. Windows 권한으로 심볼릭 링크 생성은 `OSError`여서 실제 링크 재현은 여전히 미실시했지만, 연결 경로를 모의한 별도 테스트에서 수집·쓰기를 시작하기 전에 거부됨을 확인했다.
- 신규 표적 테스트 4개(가짜 실행본 sentinel 보존, 정상 새 실행 3회에서 2개 보존·1개 삭제, manifest 부재/해시 손상/보고서 변조/이물 파일 전부 삭제 0건, 링크 `runs` 사전 차단)를 기존 14개에 추가하여 **18/18 PASS**. 전체 unittest **296건 실행, 295 PASS·1 SKIP, 실패 0, 종료 0**(기존 292건 기준 +4). 수정 후 활성 Python **88/88 문법 PASS**, `git diff --check` 종료 0; 기존 CRLF/LF 경고는 유지. 검사 로그는 Git 무시 `tmp/legacy_audit_20260923/technical-qa/{retention-targeted.log,retention-full-unittest.log,retention-repro-after-1.log,retention-repro-after-2.log}`에 있다.
- **실제 기존 로컬 상태의 호환성:** `tmp/legacy_audit_20260923/prime/recurring-state/runs/20260923T001638Z-b2cf243a`는 읽기 전용 목록 확인상 기존 네 파일만 있으며 신규 manifest가 **없다**. 이 기존본을 자동 삭제하거나 현재 근거 없는 소유 표식으로 소급 인증하지 않는다. 향후 새 실행 시 정리 단계가 경고하고 원본을 보존하는 것이 의도한 안전 동작이다. 운영자가 별도 신뢰 근거로 이관하거나 정책에 따른 수동 보관을 결정해야 정기 자동 정리를 재개할 수 있다. 이 후속 조치에서 실제 로컬 운영 상태·WordPress·서버에 대한 삭제·변경, Git stage/commit/push는 **0건**이다.
