# 중단 후 CI 정합성·v3 격리 복원 가능성 독립 감사 — 2026-09-22

## 범위·증거의 구분

- 감사 작업 트리는 Windows `/projects/Bloguito`이다. 이번 작업에서는 로컬 코드·Git 상태와 이전 기록을 읽고 제한된 정적·합성 검사를 실행했다. **Git stage/commit/push, WordPress·운영 SSH/서버·cron 수정, 운영/격리 실제 복원은 하지 않았다.** 저장소에서 새로 작성한 파일은 이 보고서 하나다. `AGENTS.md`, `docs/EDITORIAL_SYSTEM.md`, `agent-publisher/editorial_policy.json`, `docs/OPERATIONS.md`를 확인했다.
- prime의 **새 후속 보고**: WordPress 운영 MU PHP 3개를 모두 설치했으며 #85 표 필터는 현재 예상대로 작동하지 않아 worker2가 조사 중이다. 별도 17:28 v3 사전 배포 백업은 생성·검증됐다. 이 감사자가 직접 운영 설치·플러그인 SHA·런타임 동작을 재조회한 결과가 아니므로 운영 성공 인증으로 확장하지 않는다. 과거 `docs/resume-layout-current-census-2026-09-22.md`의 16:29 MU 미설치 상태는 설치 이전 기록이다.
- prime이 제공한 2026-09-22 **17:28:40 KST** 격리 경로 아카이브: `/home/ubuntu/backups/bloguito-v3-predeploy-1e77bb8ccf354ed1980498315c2c97c9/bloguito_backup_20260922_172840.tar.gz`, SHA256 `7e924b474ad1c26f993ec0f7186c9d81d9c1a15a29c9cf497e6218b961cd8508`. 스테이징 복원 도구 `--verify-only`가 version `3.0`, 구성요소 해시·gzip·중첩 경로 검증 정상이라고 보고했다. **복원 수행 증거는 없다.** 04:00 정기 아카이브는 별도의 v2이며 검증 도구 종료 0; 정기 cron 변경 없음. 세 MU 설치 시각과 17:28 v3 아카이브의 선후, `wp-content.tar.gz` 내부 MU 3개 및 SHA는 이번에 직접 확인하지 못했다. 앞선 기록 `docs/interruption-automation-audit-2026-09-22.md:31-39`에 버전별 증거가 있다.

## 1. 현재 workflow와 Git의 재현 가능성

현재 `.github/workflows/test.yml`은 `main` push/PR에서 Python `unittest discover`와 PHP ID 열 테스트를 실행하며, **작업 트리에서 수정된 47~59행**이 TOC 소스/계약 실행 및 CSS·표 소스/표 계약 파일의 **PHP 문법 검사만** 추가한다. `git diff -- .github/workflows/test.yml`로 추가 내용만 확인했다. CI 실행 이력과 원격 GitHub Actions 결과는 이번에 조회하지 않았다.

| workflow에서 참조하는 파일 | Git 상태와 의존성 | 판단 |
| --- | --- | --- |
| `.github/workflows/test.yml` | tracked, 수정됨 | 신규 47~59행을 배포하려면 아래 세 미추적 파일과 동일한 checkout에 포함해야 한다. |
| `wordpress/mu-plugins/bloguito-legacy-toc.php` | tracked, 변경 없음 | TOC PHP는 기존 HEAD에 포함되어 별도 신규 스테이징 불필요. |
| `wordpress/tests/legacy-toc-contract-test.php` | tracked, 변경 없음; TOC 소스를 상대 경로로 `require`(31행) | `php wordpress/tests/legacy-toc-contract-test.php`는 자체 합성 계약을 실행하도록 workflow에 추가됨. |
| `wordpress/mu-plugins/bloguito-legacy-callout-spacing.php` | **untracked** | `php -l`의 직접 의존성. 빠진 채 workflow만 커밋하면 CI checkout에 파일이 없음. |
| `wordpress/mu-plugins/bloguito-legacy-table-accessibility.php` | **untracked**, #85 운영 inert 조사 진행 | `php -l`의 직접 의존성. PHP 파일을 커밋하더라도 문법 검사만으로 SHA·WordPress 필터 순서·운영 렌더 성공을 보증하지 않음. worker2의 최종 파일/검사 결과를 확인해야 함. |
| `wordpress/tests/legacy-table85-accessibility-test.php` | **untracked**; 소스 삽입 `TOC_PLUGIN_SOURCE`·`TABLE_PLUGIN_SOURCE`와 비공개 공개글 fixture 삽입 `FIXTURE_BASE64` 전제(23~24, 51행) | workflow는 `php -l`만 실행하며 fixture 기반 동작 검사를 실행하지 않는다. 테스트 파일을 추적해도 **#85 운영 동작 회귀를 CI에서 통과한 것으로 보고하면 안 됨**. 실제 공개 원문/비공개 백업을 Git에 넣어 fixture를 채우지 않는다. |

**현재 workflow를 그대로 반영할 경우 최소 동일 커밋 파일 경로 4개:** 파일 소유자가 worker2 표 문제를 해결·최종 소스 승인하고 변경 내용을 다시 검사한 뒤 다음 정확한 경로만 선택적으로 스테이징한다. 이는 실행 명령 예시이며 이번에 실행하지 않았다.

```powershell
git add -- .github/workflows/test.yml wordpress/mu-plugins/bloguito-legacy-callout-spacing.php wordpress/mu-plugins/bloguito-legacy-table-accessibility.php wordpress/tests/legacy-table85-accessibility-test.php
git diff --cached --check
git diff --cached --name-status
```

- `wordpress/mu-plugins/bloguito-legacy-toc.php` 및 `wordpress/tests/legacy-toc-contract-test.php`는 현재 추적된 HEAD의 파일이다. 변경 없이 재스테이징할 필요 없다. 만약 다른 작업자가 이후 수정하면 별도 diff를 검토해 위 그룹을 재산정한다.
- 단계명 `Syntax-check undeployed legacy layout candidates`는 세 MU가 운영에 설치됐다는 prime의 새 보고와 맞지 않는다. 소유자가 workflow 최종 반영 전 실설치 상태를 정확히 드러내도록 명칭/설명을 정리할 수 있지만, 이 감사는 workflow를 수정하지 않았다.
- #85 표 플러그인은 현재 운영에서 inert로 보고되었으므로 **4파일을 지금 확정 커밋하라는 뜻이 아니다**. worker2 조사 결과에 따라 코드/테스트 수정이 생기면 그 최종 내용의 PHP 문법·제한된 #85 출력 검사 후 함께 반영한다. 실운영 진단을 CI `php -l` 성공으로 대체하지 않는다.

**workflow 외 Python 변경은 별도의 완결된 단위로 취급한다.** `scripts/audit_legacy_posts.py`와 `agent-publisher/tests/test_legacy_post_audit.py`는 둘 다 tracked·수정 상태로 서로 대응한다. 반복 감사 기능을 버전 관리할 때는 두 경로를 함께 검토하고 선택적으로 추가해야 한다. 이번 PHP workflow 참조 문제를 해결하는 **필수 의존성은 아니다**. 현재 미추적 `agent-publisher/tests/test_post_approval_preflight.py`는 미추적 `scripts/prepare_post_approval.py`를 직접 import하고, `test_update_existing_via_ssh.py`는 `scripts/update_existing_via_ssh.py`를 파일 경로로 로드하며, `test_legacy_full_approval_index.py`는 `scripts/build_legacy_full_approval_index.py`를 파일 경로로 로드한다. 이 세 테스트를 별도 채택할 때는 각각 스크립트와 묶어 검토한다. 그 밖의 미추적 테스트와 변경된 `agent-publisher/agents/*`, 편집 정책·문서 파일은 담당자가 실제 import/동작 의존성을 확인한 뒤 묶어야 한다. 공유 작업 트리의 `git add -A`, `git add .` 또는 일괄 커밋은 범위를 오염시킨다.

## 2. 현 작업 트리에서 실행한 가벼운 CI 검사

| 검사 | 직접 실행 결과 | 범위 |
| --- | --- | --- |
| `test_legacy_post_audit.py` | `.venv` Python `-B` 표적 **14 tests OK**, 종료 0 | 단위 fixture를 이용한 감사·반복 상태 검사. 운영 스케줄/알림 미검증. |
| `test_backup_recovery_v3.py` | **7 tests OK**, 종료 0 | 합성 백업·가짜 Docker·mock SSH. `FAILED ... simulated transfer interruption`는 테스트가 의도적으로 주입한 전송 실패 기록이며 테스트 결과는 OK. 실제 v3 복원이 아님. |
| Git Bash `bash -n agent-publisher/backup_daily.sh agent-publisher/restore_backup.sh` | 종료 0 | Bash 구문만 검사. 실제 백업·복원 실행 안 함. |
| `node --check agent-publisher/whatsapp-bridge/index.js`와 `command_policy.js` | 각각 종료 0 | 구문만 검사. `npm ci`·`npm test` 또는 인증/운영 동작 검사는 이번에 수행하지 않음. |
| `MYSQL_ROOT_PASSWORD=ci-placeholder`, `MYSQL_PASSWORD=ci-placeholder`를 제공한 `docker compose -f wordpress/docker-compose.yml config --quiet` | 종료 0 | 설정 구문/변수 해석만. Docker 컨테이너 생성·기동·연결 안 함. |
| `git diff --check` | 종료 0, 기존 파일 LF/CRLF 변환 경고 | 추적된 수정 파일의 공백 검사. 미추적 파일의 실제 내용까지 검증한 것은 아님. |
| 현지 PHP `php -l` | **미실행: Windows PATH에서 `where.exe php`가 파일을 찾지 못함(종료 1)** | 이번 회차 PHP CLI 동작 통과를 주장할 수 없다. 과거 운영 PHP stdin/fixture 검사 기록과 이번 실설치 검증은 다른 작업자의 증거이며, 새 소스가 확정되면 해당 담당자가 PHP 8.3 기준으로 재검증해야 한다. |

이번 검사들은 현재 **미커밋/미추적 파일까지 포함한 작업 트리**의 일부를 대상으로 했다. GitHub가 checkout하는 commit의 상태, Python 3.12/Linux 환경, 신규 PHP의 정상 운영 출력까지 동일하다는 보증은 아니다. 기존 `docs/interruption-automation-audit-2026-09-22.md:25-29`에 더 넓은 281건 로컬 Python 검사 기록은 있으나 이후 코드가 바뀌었을 수 있어 이번 표적 검사와 시점을 구분한다.

## 3. 17:28 v3 격리 복원 연습 가능성

**조건부 가능, 아직 실행 불가:** v3가 `--verify-only`에서 구성요소·gzip·경로 검증을 통과했다는 prime의 사실은 파일 무결성의 근거다. `agent-publisher/restore_backup.sh:170-223`의 실제 복원은 DB 덤프를 MariaDB `wordpress`에 직접 주입하고 uploads·plugins/themes/MU 파일과 런타임 JSON을 변경한다. 실행 시 자동 격리 장치는 없다. 스크립트 기본값이 `WORDPRESS_DIR=/home/ubuntu/wordpress`, `AGENT_DIR=/home/ubuntu/agent-publisher`, 컨테이너 `wordpress_db`·`wordpress_app`이며 `--yes`는 확인 프롬프트를 건너뛴다. 운영 서버에서 이를 실행하거나 운영 Docker daemon/볼륨을 공유하는 환경에서 돌리면 실제 사이트를 덮어쓸 위험이 있으므로 **원격 운영 호스트에서 복원 연습을 시작하지 않는다**.

전용 격리 VM/별도 호스트 및 분리된 Docker daemon이 마련된 경우에 한해 다음 사항을 충족하는 사전 검토 절차를 사용할 수 있다. 이번 감사에서는 실행하지 않았다.

1. 아카이브의 제한 접근 사본을 **운영 서버·운영 Docker daemon·운영 볼륨·운영 SSH 자격증명과 접점 없는 격리 호스트**에 옮긴다. 사본 SHA256을 위 `7e924b47…` 전체 값과 대조하고 그 격리 호스트에서 `restore_backup.sh <사본> --verify-only`를 다시 수행한다. 검증은 복원 완료의 증거가 아니다.
2. 비밀을 출력하거나 추출하지 않는 범위에서 manifest 버전·구성요소와 `wp-content.tar.gz` 안 파일 **이름만** 확인하여 세 신규 MU가 언제/어떤 버전으로 백업되었는지 식별한다. 17:28 아카이브와 실제 MU 설치 순서는 별도로 확인할 때까지 미확인이다. 설치 이후 상태를 목표로 하는 연습에는 설치 후 확장 파일 백업이 필요할 수 있다. `secrets.tar.gz`를 콘솔·CI 아티팩트·공개 문서에 추출/인쇄하지 않는다.
3. 새 격리 호스트의 **독립 MariaDB·WordPress 컨테이너, named volumes, compose 디렉터리, 랜덤 시험 자격증명**을 준비한다. `wordpress/docker-compose.yml:5,20,26,36-38`은 고정 컨테이너명 `wordpress_db`/`wordpress_app`, `127.0.0.1:8080` 포트 및 named volumes를 사용하므로 **같은 Docker daemon에서 단순 Compose project 이름만 바꿔 격리되는 구성이 아니다**. 운영 포트·도메인·메일 전송/크론·외부 분석 수집을 격리하고, 시험 환경이 production 서비스에 접속하지 못함을 점검한다. 복원기는 대상 컨테이너명·호스트 경로를 환경변수로 바꿀 수 있지만, 이름만 바꾸는 조치는 운영 daemon 연결 위험을 없애지 않는다.
4. 복원용 자격증명은 **격리 대상 전용**으로 준비한다. 원본 archive의 `secrets.tar.gz`는 별도 멤버이지만 암호화되지 않은 평문이고(`agent-publisher/backup_daily.sh:116-144`), `restore_backup.sh:137-155`는 `--include-secrets` 없이 일반 설정만 새 0700 폴더로 내보내며 비밀 설정은 자동 반영하지 않는다. 일반 설정의 런타임 JSON에도 민감정보가 섞일 가능성을 배제하지 말고 제한 권한으로 취급한다. 운영 `.env`·SSH 키·인증서·실제 고객 계정을 시험 대상에 연결하지 않는다.
5. 독립 담당자가 격리 대상 이름·경로·volume 목록·복원 전 빈 상태·원본 백업/정리 범위와 접근 차단을 확인한 후에만 격리 호스트에서 실제 복원을 검토한다. DB 복구/업로드·미디어/테마·플러그인/MU·런타임 JSON, 제한된 관리자 로그인, 게시물·사이트맵·링크·파일 권한 및 서비스 로그를 대조한다. WordPress URL·메일·외부 호출은 시험 전/후까지 격리 유지한다. `restore_backup.sh`는 host Compose/Nginx/TLS/인증서를 자동 복원하지 않고, DB→파일 교체가 하나의 원자적 트랜잭션도 아니다. 시험 종료 후 민감 사본·볼륨의 보존/폐기 기준과 실제 검사 결과를 별도 비공개 기록에 남긴다.

**남은 증거:** 격리 호스트·데이터/네트워크 접근통제·대상 컨테이너 확인, 17:28 snapshot 내부 세 MU 포함 및 SHA 확인, 독립 환경에서의 실제 DB/미디어/플러그인/테마/로그인 복원 성공, 호스트 설정/Nginx/TLS 별도 복구, 오프사이트 암호화·키 복구 및 현재 운영 상태의 최신 post-install 사본. 아카이브 파일 검증만으로 이러한 항목을 통과 처리하지 않는다. 정기 04:00 cron은 prime 확인대로 여전히 v2를 생성한 구버전 실행 경로이며 별도 v3 준비와 혼용하면 안 된다.

## 조치 인계

1. prime/worker2: #85 inert 원인·현재 원본/출력 SHA와 파일 소유자의 최종 수정 사항 확인; 세 MU 소스와 test fixture를 확정한 후 CI 신규 4파일을 대응 workflow와 함께 선택적으로 stage/commit하고 실제 Linux Actions 결과를 확인한다. PHP 구문과 공개 #85 실제 출력 동작을 **각각** 검증한다.
2. prime: 감사 반복 모드 반영 시 `scripts/audit_legacy_posts.py` 및 `agent-publisher/tests/test_legacy_post_audit.py`를 한 쌍으로 검토하고 운영 스케줄·별도 검토 레지스터·경보 감독은 따로 진행한다. 기타 새 Python 테스트/스크립트는 소유자별 의존성 검증 뒤 포함한다.
3. 백업 담당: 제한 v3의 실제 확장 파일/세 MU 내용과 SHA를 비밀 비노출 방식으로 확인한다. 새 격리 호스트가 준비되기 전에는 `restore_backup.sh --yes`, 운영 컨테이너/Compose 재생성, 정기 cron 변경을 수행하지 않는다. 격리 복원 후 서비스와 분리된 결과를 기록하여 v3 정기 전환 여부를 결정한다.
