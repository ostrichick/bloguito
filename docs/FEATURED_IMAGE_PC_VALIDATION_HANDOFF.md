# Bloguito PC 통합 검증 결과 및 후속 인계

**최신 판정 — 2026-10-10:** 노트북 수정 commit `43bd95c0d7a59482da36acdeae88fe54542cbcdd`의 PC 재검증을 완료했다. 이전 두 결함은 실제 WordPress/MariaDB 시험에서 모두 해소됐고, 통합 15그룹과 별도 실제 loopback SSH 연결 유실 시험이 통과했다. **수정 검증 합격이며 운영 배포는 미수행이다.** 아래 2026-10-09 실패 기록은 수정 전 이력이다. 다음 에이전트는 같은 두 결함을 미수정 상태로 가정하지 말고 마지막 PC 후속 결과와 별도 배포 전제조건을 읽는다.

이 문서는 Git 추적 대상이며 다른 기기에서도 pull 후 읽을 수 있다. `scratch/`의 실행 파일·원시 증거·DB snapshot은 PC 로컬 비추적 자료이므로 이 문서와 검증 기록을 기준으로 필요한 시험 환경을 다시 구성한다.

## 2026-10-09 최초 PC 검사 당시 판정

- 검사 대상: `bd1dfd5260192c9eab26554d8c205209d2c32dc5`, `C:\Projects\Bloguito`.
- Docker 복구와 시험 실행은 완료됐지만 코드의 통합 검증 결과는 불합격이다. 아직 배포 GO로 처리하면 안 된다.
- 로컬 Python 전체 suite는 1,142개 중 1,141 PASS, 1 SKIP(Windows 심볼릭 링크 불가), 실패/오류 0이었다. PHP 문법/계약 검사도 통과했지만 실제 DB 동시성 시험에서 아래 결함이 발견됐다.
- 주요 통합 검증 15그룹 중 12 PASS, 3 FAIL이며, 실패 3그룹은 아래 결함 2종류를 뜻한다. 실제 loopback SSH 연결 유실 시험은 별도 안전/복구 검증을 통과했다.

## 최초 검사에서 발견한 결함 — 아래 노트북 수정·PC 재검증 이력 참조

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

## 2026-10-09 노트북 수정 후 인계

- `fix/featured-image-lock-concurrency-20261009` 작업 트리에서 `FEATURED_IMAGE_LOCK_SCRIPT`의 최초 `add_option()`을 `wp_options.option_name` 유니크 제약에 의존하는 원자적 `INSERT IGNORE`로 교체했다. 영향을 받은 행이 정확히 1일 때만 신규 획득으로 간주하며, 기존 잠금은 `SELECT ... FOR UPDATE`와 CAS를 사용한다. 잘못된 DB 삽입 응답은 성공으로 취급하지 않는다.
- 잠금 JSON은 정확한 네 필드의 타입과 phase/pending 일치를 확인한다. invalid JSON·필드 누락·타입 오류·불일치 상태는 `invalid_lock_state`로 중단하고 원본 option을 변경하지 않는다. 이 검사는 acquire와 release/mark/complete 모두에 적용한다.
- Windows 노트북 Python 3.12.10에서 `test_wordpress_mutation.py` 표적 테스트 **26 PASS**와 Python 전체 회귀 **1,143 PASS, 0 FAIL**을 확인했다. `git diff --check`도 통과했다. 이 검사는 PHP/실제 DB 동시성 결과를 대신하지 않는다.
- 이 노트북에서는 Docker CLI, PHP CLI, WSL Linux 배포판이 확인되지 않았다. 따라서 PC가 기록한 15그룹 중 실패했던 **최초 획득 경쟁과 malformed lock byte preservation의 실제 WordPress/MariaDB 재검증은 미실시**이며 배포 판정은 여전히 **NO-GO**다.
- 다음 PC 실행은 위 코드 수정 branch를 가져와 기존 격리 staging의 *현재* 볼륨/인증 설정을 유지하면서 동일한 실패 재현 및 전체 이미지 잠금/SSH 유실 통합 그룹을 재검증한다. 두 문제의 실제 DB 검증이 통과할 때까지 운영 배포, production post/options/cron 변경을 하지 않는다.

## 2026-10-10 PC 재검증 완료 — 수정 검증 PASS, 운영 미적용

- `origin/main`은 문서 commit `1460aba`에 머물러 있어 전체 원격 refs를 fetch하고 노트북의 `origin/fix/featured-image-lock-concurrency-20261009` commit `43bd95c`를 별도 PC worktree에 가져와 검사했다. application source는 PC에서 추가 수정하지 않았다.
- Docker의 stale runtime socket 시작 오류를 소켓 디렉터리 백업·재생성으로 복구하고, 기존 Compose project `bloguito-pc-validation-20261009`의 볼륨·인증 설정을 그대로 재사용했다. 초기 setup을 다시 실행하거나 데이터 볼륨을 삭제하지 않았다.
- **실제 DB 통합 15/15그룹 PASS.** 최초 획득 자연 동시 실행 6회에서 모두 정확히 한 owner만 성공했다. 수정본에서는 `add_option` hook이 호출되지 않으므로 query filter를 사용해 **실제 INSERT 직전** 두 연결을 동기화했고, 이 경우에도 `acquired/busy`였다. 기존 hook이 실행되지 않은 것을 동시성 PASS로 오인하지 않았다.
- malformed JSON, phase 누락, expiry 문자열/boolean, pending 문자열, 짧은 token, phase/pending 불일치, 추가 필드의 **8종 × acquire/release/mark/complete 4작업 = 32개 조합** 모두 `invalid_lock_state`를 반환했고 DB의 원본 option bytes가 변경되지 않았다.
- 활성 lease, wrong owner, premature complete, stale nonpending takeover, expired pending fence, 단일 mark, 같은 owner resume, 정상 media import, malformed stdout, lost-response 주입, SHA 0/1/여러 건, timeout, 실제 PHP 메모리 할당 실패, 본문/thumbnail/ALT CAS와 readback을 통과했다. 본문·제목·slug·발췌문·draft 상태가 보존됐다.
- 별도 **실제 loopback SSH 연결 유실 시험 PASS**: 원격 역할의 staging import가 끝난 직후 응답 없이 연결을 종료했고 import는 1회였다. native OpenSSH는 여전히 4294967295를 반환해 255 전용 자동 SHA 조회 분기로 들어가지 않았지만 pending fence와 재import 차단을 유지했고, 프로세스 종료를 독립 확인한 뒤 원래 token으로 재개해 attachment 1개를 유지했다. 이 플랫폼 동작을 자동 복구 개선 검토사항으로 남기며, 안전 검증 통과와 자동 복구 지원을 구분한다.
- PC 표적 `test_wordpress_mutation.py` **26 PASS**. 전체 Python은 **1,143개 실행, 1,142 PASS + 1 SKIP, 실패/오류 0**이며 전체 suite는 1회 실행했다. SKIP은 `CollectorTests.test_reject_link_targets`의 `symlinks unavailable`이다. PHP 문법·독립 계약, UTF-8, tracked-secret scan, pip check, git diff 검사를 통과했다.
- PC 로컬 증거의 보존 위치는 `scratch/tasks/pc-validation-2026-10-10/`: `staging-acceptance.json`/`.log`, `staging_acceptance.py`, `full-validation.json`/`.log`, `ssh-disconnect-acceptance.json`/`.log`, `ssh_disconnect_acceptance.py`, `wordpress-tests.log`, `skip-check.log`, private `staging-before.sql`. 이전 날짜 증거는 보존했다. 원시 증거·DB snapshot·설정·token은 Git에 올리지 않는다.
- 시험 완료 후 disposable 컨테이너는 중지하고 볼륨을 보존한다. production에 대한 SSH 호출·post/options/media mutation·cron 변경·배포는 이번 PC 검증에서 하지 않았다.
- **남은 경계:** 이 결과는 위 수정의 PC 회귀·격리 통합 검증 PASS다. production OpenSSH/network, container OOM, 실운영 배포 readback은 검증하지 않았다. 실제 배포에는 별도 승인과 `FEATURED_IMAGE_LOCK_RECOVERY.md`/`OPERATIONS.md`의 정확한 release revision·최신 backup·운영 lock/provenance/plugin 호환성 사전 확인이 필요하다. 이전 두 결함 때문에 남았던 PC 검증 blocker는 해소됐다.
