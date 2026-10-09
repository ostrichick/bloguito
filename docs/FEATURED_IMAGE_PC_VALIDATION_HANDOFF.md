# Bloguito PC 통합 검증 결과 및 수정 요청

Bloguito 대표이미지 잠금의 PC 통합 검증에서 재현된 두 결함을 수정하고 재검증해줘.

이 문서는 Git 추적 대상이며 다른 기기에서도 pull 후 읽을 수 있다. `scratch/`의 실행 파일·원시 증거·DB snapshot은 PC 로컬 비추적 자료이므로 이 문서와 검증 기록을 기준으로 필요한 시험 환경을 다시 구성한다.

## 현재 판정

- 검사 대상: `bd1dfd5260192c9eab26554d8c205209d2c32dc5`, `C:\Projects\Bloguito`.
- Docker 복구와 시험 실행은 완료됐지만 코드의 통합 검증 결과는 불합격이다. 아직 배포 GO로 처리하면 안 된다.
- 로컬 Python 전체 suite는 1,142개 중 1,141 PASS, 1 SKIP(Windows 심볼릭 링크 불가), 실패/오류 0이었다. PHP 문법/계약 검사도 통과했지만 실제 DB 동시성 시험에서 아래 결함이 발견됐다.
- 주요 통합 검증 15그룹 중 12 PASS, 3 FAIL이며, 실패 3그룹은 아래 결함 2종류를 뜻한다. 실제 loopback SSH 연결 유실 시험은 별도 안전/복구 검증을 통과했다.

## 반드시 수정할 결함

1. `agent-publisher/agents/wordpress_mutation.py`의 `FEATURED_IMAGE_LOCK_SCRIPT` 최초 획득 경로(현재 72행)는 `add_option()` 성공을 독점 획득으로 간주한다. 실제 WordPress 7.1.2의 `add_option()`은 존재 여부 검사 뒤 `INSERT ... ON DUPLICATE KEY UPDATE`를 실행하므로 두 연결이 모두 새 잠금을 획득했다고 반환하고 token을 덮어쓸 수 있다. 자연 동시 실행 6회 중 3회, `add_option` INSERT 직전 hook으로 동기화한 시험, 이후 새 draft 2개의 재시험 모두 `acquired/acquired`를 재현했다. 기존 소유자를 덮어쓰지 않는 원자적 최초 생성으로 고쳐라. 단순 사후 token readback만으로 경쟁이 해결됐다고 판단하지 말고, 실제 독립 DB 연결의 동시 획득 시험으로 증명하라. 정상 시 한 작업만 acquired이고 다른 작업은 busy 또는 안전한 명시적 충돌로 종료돼야 한다.
2. 같은 script의 기존 state decode/expiry 처리(현재 77행 부근)는 invalid JSON을 expired/nonpending처럼 취급해 자동 교체한다. malformed JSON fixture의 acquire가 `acquired`, `stale_replaced=true`를 반환했고 새 draft에서 재현됐다. malformed/불완전한 state는 명시적 오류로 차단하고 기존 option bytes를 보존하라. 유효한 expired/nonpending lock의 정상 takeover, expired/pending lock의 무기한 fence, 원래 소유자의 안전한 재개는 유지하라. 정확한 token/expiry/pending/phase 타입과 구조 계약도 검토하라.

## 추가 관측

Windows native OpenSSH가 실제 loopback SSH 연결 종료에서 255 대신 4294967295를 반환했다. `featured_image.py`의 255 전용 분기로 자동 SHA reconciliation은 실행되지 않았지만 pending fence와 재import 차단은 유지됐고, 프로세스 종료를 독립 확인한 뒤 원래 token으로 복구해 attachment 1개를 유지했다. 플랫폼별 종료 코드 처리 필요성을 검토하되, 응답 유실이나 SHA 일치만으로 원격 process 종료를 추정하거나 fence를 해제하면 안 된다.

## 증거와 환경

- 기존 기록: `docs/FEATURED_IMAGE_LOCK_RECOVERY.md`의 2026-10-09 PC validation, Docker recovery/NO-GO, Repeat verification 절.
- PC 전용 비추적 증거: `scratch/tasks/pc-validation-2026-10-09/`의 `staging-acceptance.json`, `staging_acceptance.py`, `staging-acceptance.log`, `ssh-disconnect-acceptance.json`, `ssh_disconnect_acceptance.py`, `blockers-recheck.json`, `recheck_blockers.py`.
- 같은 PC에서는 임시 Compose project `bloguito-pc-validation-20261009`와 DB/WordPress volumes가 보존돼 있다. 시험 후 컨테이너는 중지했고 Docker Engine 29.7.2는 정상 실행 중이다. 기존 `staging-compose.json`으로 `docker compose -p bloguito-pc-validation-20261009 -f scratch/tasks/pc-validation-2026-10-09/staging-compose.json start`하여 재개하라. 기존 볼륨에 대해 `staging_setup.py`를 무작정 다시 실행하면 DB 비밀번호가 새로 생성되므로 기존 설정을 보존해야 한다.
- 다른 기기에서는 scratch 증거가 Git에 없으므로 해당 파일을 있다고 가정하지 말고 위 재현 설명으로 독립 환경을 구성하라.
- 시험 사이트는 `http://bloguito-validation.invalid`, repository pinned WordPress 7.1.2/MariaDB, InnoDB, internal-only Docker network, published port 없음, 운영 mount/credential 없음이다. 실행 전 snapshot과 격리를 확인하라.

## 수행 및 완료 기준

- 먼저 AGENTS.md, README.md, scripts/README.md, docs/OPERATIONS.md와 잠금 복구 지침을 읽어라. 작업트리의 미커밋 변경을 보존하고, 공통 코드 수정은 전용 worktree로 격리하라.
- 위 두 결함을 수정하고 의미 있는 regression tests를 추가하라. 임시 probe/harness는 scratch에 두고, 재사용 가능한 회귀만 정식 tests에 넣어라.
- 표적 테스트를 먼저 통과시킨 뒤 실제 WordPress/MariaDB의 독립 연결로 최초 획득 경쟁·malformed 보존·stale takeover·pending fence·wrong-owner·같은 owner resume·CAS/readback을 재검증하라. 수정 후 image pipeline 장애/SSH 유실 검증도 영향에 맞춰 재실행하라. 그 뒤 공유 코드 변경에 대한 전체 Python suite를 한 번 실행하고 PHP 검사·git diff --check를 수행하라.
- 검증 harness의 기대 결과를 완화하거나 실패를 무시해서 PASS로 만들지 마라. 최초 획득 경쟁과 malformed 처리 모두 통과해야 한다.
- production 게시물/이미지/options/cron은 변경하지 말고 배포하지 마라. 운영 승인이나 실제 production 복구 권한을 이 전달문에서 추정하지 마라. private DB dump·token·로컬 설정·시험 의존성은 Git에 넣지 마라.
- 기존 문서에 수정과 증거를 추가하고, 최종 보고를 `시험 실행 완료 여부 / 코드 합격 여부 / 수정 revision / 통과·실패·미검증 / 운영 적용 여부`로 명확히 분리해라. 반복 시험 성공만으로 production 배포 완료를 주장하지 마라.
