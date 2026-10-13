# Bloguito 독립 WordPress DB·복구 검증 (2026-10-11)

기준: commit 26189a99e471cfdf136158bfc6b4b427f112deef, 별도 worktree C:/Projects/Bloguito-db-validation-20261011. 운영 게시물·DB·플러그인·cron은 변경하지 않았다.

## 실제 검증 범위

- 로컬 노트북: Docker, Podman, MariaDB, PHP 및 설치된 WSL 배포판 없음. SSH 서버에서 확인된 메모리는 전체 952 MiB, available 약 461 MiB. 운영 호스트의 자원 경합을 피하기 위해 분리 MariaDB는 생성하지 않았다.
- 네트워크·운영 볼륨 접근 없는 일회용 PHP 컨테이너: 원본 신규 draft metadata PHP 스크립트와 모형 WordPress API/DB transaction fixture를 결합해 13개 시나리오 PASS. 신규 저장, 정확한 replay, 부분 metadata, 외부 충돌, 본문/상태/제목/slug/발췌문 drift, 대상 없음, 두 번째 meta 저장 실패 후 rollback, commit ambiguous, invalid key, wp_slash 값 보존을 검사했다. 실제 MySQL row lock/캐시/동시성은 검증하지 않았다.
- 같은 격리 컨테이너에서 WordPress MU 플러그인 PHP syntax/contract runner PASS. user 선택과 delegated agent 선택 모두 유효한 검토·이미지 binding 시 승인되고, delegated 증거 형식·본문 SHA 변형·잘못된 approval kind는 거부됐다. 원본 plugin 파일은 별도 fixture를 통해 읽었으며 운영 plugin 파일을 변경하지 않았다.
- 로컬 Python: draft_create_recovery 6 PASS(유실된 create 응답 재시도 금지, 동일 post ID 복구와 complete replay, 변경 감지), backup_recovery_v3 12 PASS(비정상 gzip 내부 스트림을 manifest가 정확히 해시하더라도 복원 사전 검증 실패), scheduler_run_lock Windows 7 PASS + Linux 전용 1 SKIP. 전체 Python unittest 총 1,299개, 결과 OK(3 SKIP).
- Linux staging 임시 디렉터리에서 run_daily.sh와 직접 main.py의 lock 경쟁 테스트를 수행하려 했으나 서버 Python의 누락된 dotenv 및 fake-app symlink가 시스템 site-packages를 잃는 문제로 cron 검증 실패. 외부 실행환경 문제이므로 **Linux S1 통과라고 주장하지 않는다**. 테스트 과정에서 운영 app 실행/자료 변경은 없었다.

## 백업/복원·롤백 읽기 전용 감사

- agent-publisher/backup_daily.sh: DB는 single-transaction SQL 덤프로 저장, uploads·plugins·themes·MU·config·secrets를 이후 차례로 수집한다. DB와 미디어를 같은 시점으로 묶는 사이트 전역 트랜잭션은 없다.
- agent-publisher/restore_backup.sh: DB 자격증명을 읽기 전에 archive, manifest SHA, 필수 구성요소, 압축 스트림 및 내부 경로를 검사한다. verify-only는 DB/WordPress를 변경하지 않는다.
- 실제 복원은 DB → uploads → plugins/themes/MU → runtime JSON 순서다. 후반 단계 실패 시 선행 DB/미디어 변경이 자동 원복되는 다중 자원 트랜잭션은 없다. 복원된 확장 파일의 기존 디렉터리는 별도 pre-restore 디렉터리에 보존되며, 복원 전에 독립 백업·중단 절차가 필요하다.
- scripts/install_editorial_release.py의 파일 단위 배포 rollback 경로는 위 데이터베이스/미디어 전체 복원과 범위가 다르다. 운영 archive의 최신 manifest 및 실제 WordPress 복원 성공은 이번 검사에서 확인하지 않았다.

## 미완료 증거

실제 WordPress/MariaDB 독립 통합: 별도 2GiB 이상 RAM을 확보한 CI/staging에서 WordPress와 MariaDB를 격리 실행한 뒤 동시 metadata writer, SELECT FOR UPDATE 직렬화, 재시도와 crash 경계, 실제 WP cache/readback, v3 백업 restore를 확인해야 완료된다. 이번 결과는 **fixture 및 정책 검증 PASS / 실제 DB 통합 UNVERIFIED**로 분류한다.

## 2026-10-11 추가: 독립 GitHub Actions 실제 DB 통합 실행

- 추가 구현 기준: `e5a53f1b28e07aefd35eac1befe3be5be293414c`. CI 첫 실행 커밋 `24fbad862ae4bb629977329ce0d946b615217723`; [GitHub Actions Test Suite run 38125050282](https://github.com/ostrichick/bloguito/actions/runs/38125050282) **전체 SUCCESS**, 4개 job 모두 성공. 로그와 해제 단계 확인 시각: 2026-10-11 08:31 UTC. 일회성 브랜치 push trigger는 검증 후 제거하며 정규 `main`/PR 테스트 정책을 유지한다.
- 별도 GitHub-hosted `ubuntu-latest` runner에 Docker Compose로 MariaDB 10.11, WordPress PHP 8.3 Apache, WordPress CLI를 부팅했다. DB/WordPress named volume은 해당 run ID의 프로젝트 이름으로 격리했고 포트를 외부에 노출하지 않았으며 CI 가짜 인증정보만 사용했다. 운영 서버, 운영 SSH, 실제 데이터·기존 자격 증명에 연결하지 않았다. `down --volumes --remove-orphans` 실제 실행 로그에서 DB/WordPress 컨테이너와 두 volume·network 제거를 모두 확인했다.
- 원본 `GUARDED_NEW_DRAFT_META_SCRIPT`를 **실제 WordPress bootstrap 및 MariaDB InnoDB**에서 PHP로 호출해 검증: 신규 draft에 정상 저장/다른 WP-CLI 프로세스에서 영속 readback, `wp_slash`가 포함된 따옴표·백슬래시·UTF-8 보존, 동일 값 재실행 `already_applied`, 다른 값 `meta_conflict`, 기존 부분 메타 충돌, 원고 외부 수정 후 `cas_mismatch` 검증. 두 독립 PHP 프로세스가 같은 post를 동시에 갱신할 때 **정확히 하나만 성공**, 나머지는 충돌했고 승자의 메타만 남았다.
- 실제 WordPress `update_post_metadata` hook으로 **두 번째 메타 저장 실패**를 주입하니 `update_failed`가 나오고, 별도 WP-CLI readback에서 앞서 성공한 첫 번째 키까지 **DB 롤백**된 것을 확인했다. 같은 post에서 정상 재시도는 성공했다. 이 검사는 PHP mock 기반이 아닌 실제 InnoDB 경로다.
- `wordpress/mu-plugins/bloguito-post-row-actions.php`를 실제 WP 함수·임시 draft·고정 1픽셀 PNG fixture attachment와 함께 실행했다. 사용자가 선택한 대표이미지, 위임받은 에이전트가 선택한 대표이미지 승인 계약은 유효한 binding에서 통과했고, 본문 SHA 변형·승인 증빙 형식 오류·잘못된 approval kind는 거부됐다. 모든 테스트 글의 저장 상태는 `draft`였다. 이 첨부파일은 격리 runner 테스트 용도로만 생성됐으며 이후 해당 runner 볼륨과 함께 삭제됐다.
- 실제 MariaDB에서 `mariadb-dump --single-transaction` 수행 후 **새로운 별도 `wordpress_ci_restore` DB로 SQL 복원**해 대상 임시글의 post ID, draft 상태, 신규 메타 존재를 검증했다. 이는 **DB 범위의 복원 성공**이지 v3 multi-component archive(uploads/MU/config/secret) 전체 실제 복원, 복구 후 사이트 브라우저 검증 또는 운영 사이트 restore 검증은 아니다.
- Linux `test_scheduler_run_lock.py`: **8개 모두 PASS**, `run_daily.sh` vs 직접 `main.py` 실측 포함. Linux backup_recovery_v3 독립 **12개 PASS**(fake Docker v3 archive 검사 및 장애 주입). 기존 전체 Python unittest **1,308개 PASS**, WordPress PHP syntax/contract/metadata fixture PASS. 이전 절의 Linux cron 미검증 및 DB 통합 미검증은 당시 로컬/운영 서버 제약을 기록한 과거 결과이며, 본 절의 신규 runner에서 해당 범위를 검증했다.

**잔여 검증 범위:** 외부 프로세스 강제 종료/DB connection loss에 대한 불명확 COMMIT 이후 실제 재확인, 이미지 파일·첨부 DB·WordPress 확장·암호화된 v3 통합 백업의 전체 복원·사이트 브라우저 회귀는 이번 테스트에 포함되지 않는다. 복원·릴리스 전후 RTO/RPO와 운영 크론/서버 코드 실제 버전도 별도 검증 대상이다.

## 2026-10-11 후속: 분리된 v3 전체 백업 복원·COMMIT 응답 유실·릴리스 롤백 실측

- 추가 구현은 **통합 HEAD `43909f3ce6feb3e95da57437448ce375dcd5dba9`** 에서 격리된 `C:/Projects/Bloguito-full-restore-20261011`, 브랜치 `feat/bloguito-full-restore-20261011`. 독립 `ubuntu-latest` GitHub-hosted 실행 [Actions Test Suite #38125946395](https://github.com/ostrichick/bloguito/actions/runs/38125946395), 실행 대상 커밋 `6901343f82aba1402b4420e35aa4ac0f2b64cc66` **5개 job 모두 SUCCESS**. 테스트 브랜치 일회성 push 트리거는 실측 후 제거하고 원래 `main`/PR 범위 유지.
- 재실행 가능한 하네스: `wordpress/tests/real-db/full_restore.py`, `restore.override.yml`, `.github/workflows/test.yml`의 `isolated-v3-full-restore`. 프로젝트·MariaDB·WordPress 컨테이너 이름은 Actions run ID로 분리했고, 외부 포트/운영 서버·환경변수/시크릿/마운트는 접근하지 않았다. 실제 cleanup 출력에서 **CI CLI·WordPress·MariaDB 3개 컨테이너, 2개 DB·WP 볼륨, 전용 네트워크 제거** 확인. 스크립트는 `GITHUB_ACTIONS=true`와 해당 run ID·정확한 컨테이너 이름이 아니면 거부한다.
- **실제 MariaDB COMMIT 응답 유실 모델:** 신규 synthetic draft에 원본 `GUARDED_NEW_DRAFT_META_SCRIPT`를 실행하고 PHP 출력 버퍼만 버려 클라이언트가 결과를 받지 못하는 경우를 만들었다. 별도 PHP 세션의 메타 readback에서 성공을 확인했고, 동일 post ID·동일 expected·동일 metadata 재실행은 `already_applied`가 됐다. `wp_posts` 1개·대상 `wp_postmeta` 정확히 4개로 중복 생성이 없었다. **이것은 DB COMMIT 후 애플리케이션 응답 유실을 실측한 것이며, TCP reset/DB 서버 강제 종료와 반대 결과(실제 미커밋)에 대한 판별까지 실측한 것은 아니다.**
- **실제 통합 v3 archive 생성·검증·복원:** 운영 구현 그대로의 `agent-publisher/backup_daily.sh`를 CI 전용 DB 및 WordPress 컨테이너에서 실행해 MariaDB SQL, uploads, plugins/themes/MU, runtime JSON/configs, secrets의 **5개 구성요소·manifest 검증된 v3 archive** 생성. `restore_backup.sh --verify-only`가 모두 유효함을 확인. 그 다음 test-only 본문·업로드·플러그인·테마·MU 및 runtime JSON을 변경하고 **격리 `wordpress` DB만 지운 후** 실제 `restore_backup.sh <archive> --yes`를 실행했다. WordPress CLI가 복원된 DB에서 boot 가능하고 post ID·draft 상태·원래 제목으로 되돌아온 것을 확인했으며 uploads/plugins/themes/MU 각 sentinel 파일과 runtime JSON 값까지 모두 원복됐다. 교체 이전 extensions는 `.bloguito-prerestore-*`에 보존됐다.
- **비밀정보·호스트 설정:** v3 archive에는 CI synthetic `.env`, config.py, WordPress wp-config.php 및 테스트용 Nginx 설정 사본이 들어 있다. `--yes` 복원 후 현재 타깃의 synthetic agent `.env`가 덮어쓰기되지 않음을 확인했다. 이어 실제 `restore_backup.sh --export-configs <new dir> --include-secrets`로 설정과 별도 secrets를 0700 새 디렉터리에 내보내고 경로·내용을 검증했다. 복원 스크립트는 이 파일을 **사이트 호스트에 자동 설치하지 않는다.** 이 정책을 따라 '비밀정보까지 자동 복구된 사이트'라고 주장하지 않는다.
- **실행 가능한 릴리스 rollback:** `scripts/build_editorial_release.py`로 실제 정규 파일 인벤토리·SHA manifest가 담긴 릴리스 생성, `scripts/install_editorial_release.py`의 **실제 `install()`** 호출. 독립 WordPress MU 파일에서 직접 계산한 SHA와 릴리스의 사전검사를 통과한 뒤 실제 교체 파일을 기록했다. 배포 대상 내부의 실제 실행 shell `venv/bin/python`이 의도적으로 37을 반환하게 하여 smoke 단계가 실패했을 때, 설치 함수의 역순 rollback이 기존 `main.py`, 공유 정책 파일, `run_daily.sh` 본문·실행 권한, 기존 `.env`와 이전 release receipt를 보존하고 신규 `agents/edit_post.py`를 제거함을 확인했다. 기록용 per-file `backups/editorial-*/manifest.json`도 확인. **릴리스의 정상 배포/운영 적용은 하지 않았다.**
- 같은 실행의 기존 `isolated-real-wordpress-db`, `wordpress-test`, `infrastructure-test`, 전체 Python `test` 작업도 모두 통과. 실패 전·후 실제 Docker 삭제 증거는 해당 runner 실행 로그의 `Delete synthetic database and all CI-only volumes` 단계에서 확인할 수 있다.

**후속 잔여 리스크:** 1) DB 서버 강제 종료·TCP 접속 유실의 COMMIT 불명확 상태 양측 검증, 2) 아카이브가 담긴 내용이 서로 다른 시점에 수집되므로 백업 DB/미디어 **site-wide 원자성·RPO 보장 없음**, 3) 운영 크기 미디어/실제 크리덴셜 마이그레이션·Nginx 활성화·호스트 설정 복원 및 HTTPS 브라우저 부팅은 **미실행**, 4) `restore_backup.sh --yes`는 복원 대상이 신규/비어 있는 DB라는 전제를 충족해야 하며, 여러 구성요소 간 실패 시 자동 일괄 rollback이 없다. 이번 성공은 synthetic WordPress 전체 데이터·확장 **분리된 CI 복원 검증**에 한정된다.
