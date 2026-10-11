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
