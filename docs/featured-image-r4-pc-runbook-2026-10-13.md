# R4 격리 WordPress/MariaDB — Docker 가능 PC 실행·복구·인계 (2026-10-13)

## 판정 및 범위

**2026-10-13 PC 후속:** 아래 최초 인계 당시의 미실행 상태를 대체한다. 실제 격리 R4 합성 E2E와 고정 R3 PHP setter 실DB 검사는 PASS다. R1/R2 독립 발급·신규 import writer·운영 권한 분리·R5 인수는 미완료로 운영 `NO-GO`를 유지한다. 상세 결과는 [PC 인계 문서의 후속 결과](featured-image-pc-handoff-2026-10-13.md#6-2026-10-13-pc-실행-후속-결과)를 읽는다.

**현재 결과: 노트북 정적/모의 검증만 수행. 실제 Docker·WordPress·MariaDB E2E 미실행. R4/R5 운영 적용은 `NO-GO`.** 이 문서의 `SYNTHETIC_E2E_PASS_R4_ACCEPTANCE_NO_GO`는 새로운 합성 데이터 전용 인프라 검증 성공을 의미하며, R1 호스트 원본 서명·R2 독립 승인·R3 서버 제한형 writer·실제 SSH 유실·R5 운영 게시물 3건을 인증하지 않는다. 기존 운영 DB, 백업, 원본 이미지, WordPress 글, SSH/sudo/cron 및 배포는 건드리지 않는다.

작업 트리: `C:\Projects\Bloguito-image-r1-r5-20261012`. PC에서는 prime이 통합한 **정확한 커밋**으로 갱신하고 해당 커밋 SHA를 결과에 기록한다. 아래 명령은 PowerShell에서 **저장소 루트**로 이동한 다음 실행한다. 노트북에는 Docker가 없어 PC 실제 검증은 인계 단계로 남는다.

## 1. 생성되는 격리 경계

`scripts/ops/image_r4_pc_fixture.py init`는 Git 비추적 `scratch/tasks/featured-image-r4-pc/bloguito_r4pc_<12 hex>/` 아래 **매번 새로운 작업 디렉터리**를 만든다. 디렉터리에는 다음이 들어간다.

| 파일 | 목적 |
| --- | --- |
| `compose.yaml` | 전용 MariaDB 11.4, WordPress PHP 8.3 Apache, WP-CLI PHP 8.3. 고정 `container_name` 없음, 호스트 포트 노출 없음, `internal: true` Docker 네트워크, 전용 프로젝트 범위 named volume 두 개 |
| `.env` | 매번 무작위 생성한 DB root/사용자·테스트 관리자 비밀번호. 관리자 비밀번호는 WP-CLI `--prompt=admin_password`와 표준 입력으로만 전달하며 `--admin_password=값` 프로세스 인수 사용 금지. 공유·커밋 금지 |
| `fixture-state.json` | 고유 프로젝트명, 고정 템플릿·PHP·PNG 파일 SHA256, 합성 전용임을 확인하는 마커. 자격 증명 미포함 |
| `fixtures/synthetic-1..3.png` | 표준 라이브러리만으로 생성한 서로 다른 색상의 합성 PNG 3개. **ChatGPT 이미지 출처 증거가 아님** |
| `fixtures/fixture-cas.php` | **격리 실험 전용** 실제 WP DB transaction `SELECT ... FOR UPDATE`, 기준 본문/썸네일 비교, 미디어 첨부 지정, ALT·SHA·본문·상태 readback 및 SHA 조회 |
| `r4-smoke-evidence.json` | PC 스모크를 시작하면서 먼저 생성하는 **재시도 방지 기록**. 실패해도 보존하고 미디어 import를 자동 재실행하지 않음 |

공식 운영 Compose `wordpress/docker-compose.yml`에는 `wordpress_app`, `wordpress_db`와 `127.0.0.1:8080` 등이 있으므로 격리 테스트에 사용하면 안 된다. 본 fixture의 Compose에는 그러한 이름·포트·볼륨·SSH 연결·운영 데이터 마운트가 없다. 오직 생성한 `./fixtures`만 **read-only** 마운트한다. Docker 엔진은 로컬 `unix://` 또는 Windows `npipe://` context만 허용하며 `DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH`로 설정된 별도 원격 엔진은 차단한다.

PC 후속 수정에서 실제 다운로드한 MariaDB/WordPress/CLI 세 이미지를 `COMPOSE`의 불변 digest로 고정했다. 생성되는 `fixture-state.json`은 해당 Compose SHA도 봉인한다. Apache 이미지의 업로드 볼륨 owner(33)에 맞춰 Alpine CLI를 `33:33`으로 실행하며 world-write나 root 실행으로 권한 문제를 우회하지 않는다. `docker compose --progress quiet`로 Compose 진행 메시지를 억제하되 CAS 판독은 계속 정확한 WordPress 거부 메시지만 허용한다. 이미지 업데이트 시에는 digest/UID 계약과 실DB 시험을 함께 재검증한다.

## 2. PC 사전 준비와 정적 검증

PC에서 실제로 발견한 두 런타임 결함도 수정했다: `wp eval-file`의 `$args`는 include scope 변수이므로 global로 덮어쓰지 않는다. Apache(UID 33)와 Alpine CLI(UID 82)의 기본 사용자 차이는 CLI UID를 공유 볼륨 owner에 맞춰 해결한다. 새 `.github/workflows/test.yml`의 `isolated-r4-image-and-r3-setter` job은 별도 빈 환경에서 이 계약을 실제 실행하므로 노트북에 Docker를 설치하지 않아도 향후 결과를 확인할 수 있다. 합성 검사 성공을 R1/R2 출처·승인 또는 운영 GO로 승격하지 않는다.

Docker Desktop Linux containers 또는 로컬 Docker Engine + Compose v2가 필요하다. Docker/WordPress를 설치하지 않은 노트북에서는 이 단계의 Python 테스트만 실행한다. **운영 서버 SSH 연결이나 운영 백업 복원은 필요하지 않다.**

```powershell
cd C:\Projects\Bloguito-image-r1-r5-20261012
git rev-parse HEAD
git status --short
python --version
docker version
docker compose version
docker context show
python -m unittest discover -s agent-publisher/tests -p test_featured_image_r4_pc_fixture.py -v
python -m py_compile scripts/ops/image_r4_pc_fixture.py scripts/ops/image_r4_pc_smoke.py
```

작업 트리에 다른 에이전트의 미커밋 변경이 있으면 덮어쓰지 않는다. Docker가 로컬 엔진이 아니면 진행하지 않는다. 테스트 생성기는 Docker 없어도 검증 가능하다.

## 3. 새로운 합성 fixture 생성/안전 검사

```powershell
$init = (python scripts/ops/image_r4_pc_fixture.py init | ConvertFrom-Json)
$fixture = $init.fixture
$project = $init.project
python scripts/ops/image_r4_pc_fixture.py check --fixture "$fixture"
Get-ChildItem -LiteralPath "$fixture" -Force | Select-Object Name,Length
```

정상 출력 `READY_OFFLINE_ONLY`. `check`는 Docker 컨테이너를 생성하지 않는다. `fixture-state.json`과 각 파일의 SHA·고유 프로젝트 ID를 확인한다. Docker read-only bind mount의 `fixtures` 폴더는 심볼릭 링크/Windows junction 및 숨김 파일을 포함한 예상 외 항목을 전부 거부하며, `.env` 링크도 거부한다. `--fixture`는 생성기가 내놓은 **정확한 절대경로**를 지정한다. `.env` 비밀번호 값은 로그에 복사하지 않는다.

## 4. PC에서만 Docker 시작 → 실제 합성 E2E → 종료

```powershell
python scripts/ops/image_r4_pc_fixture.py start --fixture "$fixture" --confirm-local-isolated
python scripts/ops/image_r4_pc_smoke.py --fixture "$fixture" --confirm-local-isolated
$evidence = Join-Path "$fixture" 'r4-smoke-evidence.json'
Get-Content -LiteralPath "$evidence" -Encoding UTF8
python scripts/ops/image_r4_pc_fixture.py stop --fixture "$fixture" --confirm-local-isolated
```

`start`는 `docker compose -p <고유 프로젝트> -f <fixture compose> --env-file <fixture .env> up -d --wait db web`만 실행한다. 서비스와 볼륨은 고유 프로젝트 네임스페이스에 생성된다. `smoke`는 별도의 일회용 WP-CLI 컨테이너로 다음을 실제 WordPress/MariaDB에 실행한다.

1. **신규 빈 DB에서만** synthetic WordPress 설치, draft 1건 생성. 처음부터 설치된 DB이거나 과거 `r4-smoke-evidence.json`이 있으면 거부한다.
2. 원본 PNG 세 개를 각각 **1회씩** WordPress 미디어로 import하고, 부모 post ID/실제 첨부 파일 SHA를 확인한다.
3. 잘못된 본문 SHA로 썸네일 변경 요청 → 실패 확인. 정상 본문·기존 썸네일 기준으로 합성 DB transaction `SELECT ... FOR UPDATE`를 통해 attachment 지정/ALT 업데이트 → 실제 WP DB에서 readback.
4. 오래된 `_thumbnail_id` 기준 변경 요청 → 실패·기존 썸네일 보존 확인. 같은 baseline을 가진 **동시 두 요청**을 보내 정확히 하나만 성공하고 다른 하나는 충돌 거부되는지 확인. 실패 결과는 반드시 고정된 PHP에서 나온 WP-CLI 종료 코드 1과 정확한 `Error: stale_post_cas` 또는 `Error: stale_thumbnail_cas`여야 한다. 다른 Docker 종료 코드, 연결 오류, 알 수 없는 stderr, 추가 로그 또는 비정상 JSON은 **테스트 실패 `NO-GO`**로 처리하며 동시성 성공에 포함하지 않는다. 합성 PHP는 두 메타데이터 DB 쓰기를 COMMIT 전에 재조회하고 불일치 시 ROLLBACK한다.
5. 최종 내용 SHA, 제목·slug·발췌문·draft 상태, thumbnail ID, 실제 attachment 파일 SHA, ALT, URL, 부모 게시물의 attachment **3개**를 재조회. SHA 기반 재조회에서 기존 첨부 ID를 찾고 **재import하지 않는다.**

실패하더라도 이미 수행한 import 결과가 모호할 수 있으므로 `smoke`를 **같은 프로젝트에서 재실행할 수 없다.** 로그/DB를 조사하고 필요하면 새로운 `init` 작업으로 시험을 반복한다. 실제 SSH 응답 유실 또는 백그라운드 PHP 프로세스 종료 불확실성은 이 합성 runner가 실험하지 않는다. 응답 소실 시 재실행 금지 및 기존 첨부 SHA 조회까지가 오프라인 준비 범위다.

자격 증명 노출 방지: 합성 사이트의 관리자 비밀번호는 WP-CLI의 `--prompt=admin_password`로 표준 입력에서 받는다. 스크립트는 비밀번호를 Docker 명령 인수·에러·스모크 증거 JSON에 직렬화하지 않는다. Docker 실행 실패나 `TimeoutExpired`의 명령 인수/표준출력에는 민감한 값이 포함될 수 있어 예외 내용을 그대로 출력하지 않고 정해진 오류 코드만 기록한다. 프로젝트의 `.env`는 PC 로컬에만 보관하며 수집 보고서에 첨부하지 않는다.

`stop`의 기본값은 **컨테이너/프로젝트 네트워크만 중지·제거**하고 이 fixture의 DB/WordPress named volume은 보존하여 증거를 재검토할 수 있게 한다. 재실행을 위해 같은 DB를 덮어쓰지 않는다. 충분히 검수한 합성 데이터만 완전히 폐기하려면 다음 별도의 명시 플래그를 사용한다.

```powershell
python scripts/ops/image_r4_pc_fixture.py stop --fixture "$fixture" --confirm-local-isolated --destroy-synthetic-data
```

이는 **해당 무작위 프로젝트의 합성 볼륨에만** `docker compose down --volumes`를 수행한다. 호스트 파일을 삭제하지 않으며 어떤 운영 볼륨도 지정하지 않는다. `.env`, 테스트 결과, 증거 폴더는 Git 비추적 로컬 파일로 남는다. 이 스크립트는 Docker 시스템 전역 prune/clean을 실행하지 않는다.

## 5. 결과 수용 기준, blocker와 다음 작업

합성 스모크 성공 문자열은 `SYNTHETIC_E2E_PASS_R4_ACCEPTANCE_NO_GO`, 실패는 `NO-GO` 및 종료 코드 2다. 성공 시에만 종료 코드 0을 반환한다. **종료 코드 0은 합성 DB 동작 검증 성공**을 뜻하며 실제 R4/R5 공개 허가가 아니다. `r4-smoke-evidence.json`에는 실행한 항목만 `checks`로 남기고, 성공 여부와 상관없이 `production_writer_tested=false`, `r1_r2_trusted_issuance_tested=false`, `ssh_loss_tested=false`, `r4_acceptance=false`를 유지한다. 파일이 없다면 Docker 시작 전 단계에서 중단된 것이므로 결과를 PASS로 집계하지 않는다.

현재 오프라인에서 결정할 수 없는 영역과 PC에서 추가할 실제 R4 통합 테스트의 순서는 아래와 같다.

| 검증 | 이 fixture에서 가능 | 실제 R4 인수에 추가 요구 |
| --- | --- | --- |
| 격리 DB/WP + 합성 원본 media import | PC에서 가능 (미실행) | 실제 실행 출력과 이미지 digest 기록 |
| 본문/썸네일 CAS, 동시성, ALT/현물 readback | PC에서 **fixture-only PHP**로 실험 가능 (미실행) | `scripts/security/featured_image_set.php` 등 실제 보호된 writer 계약의 별도 E2E, 고정 runtime digest, 최소 WP 권한 검증 |
| 거짓 `image_gen` 출처·가짜 reviewer PASS·타 회차/승인 재사용 | 오프라인 R1/R2 부정 테스트만 수행 가능 | 실제 호스트 원본 발급 이벤트, **서로 다른 독립 서명자** 및 보호된 신뢰 앵커에서 차단 실측 |
| 제한 SSH, root 권한, sudoers, 무단 PHP/WP-CLI 접근 | 로컬 Python mock/정적 검증만 가능 | 격리 Linux VM/OS에서 계정 격리·읽기 전용 파일 소유권·forced-command 및 권한 차단 검증. 이 fixture의 Docker root 권한으로 설치/검증했다고 주장 금지 |
| 응답 유실, 프로세스 미종료, 동일 요청 재호출 | SHA read-only reconcile 기반만 실험 가능 | 제한형 writer + 실제 로컬 SSH/네트워크 장애 주입·중복 매체 0건·재실행 fence 실측 |
| R5 서로 다른 실제 새 글 3건 | **불가** | 진짜 이미지 생성 원본·독립 승인·최종 WP 저장/ALT/readback 3건 후 별도 GO 판단 |

정식 인수 전에는 독립 신뢰 발급기, root-owned 요청 spool, 실제 최소 권한 writer 및 고정 PHP mount, 실패/경합/SSH-loss 검증 도구와 안전한 rollback이 필요하다. 이 runbook으로 합성 WordPress를 만들었다는 사실만으로 해당 미완료 항목을 해결했다고 표시하지 않는다. 운영 WordPress의 draft/publish 상태나 이미지가 바뀌었다는 주장을 하지 않는다.

## 6. PC 인계 기록 형식

PC 실험 후 **자격 증명 없이** `git rev-parse HEAD`, Docker/Compose 버전, context host scheme(local 여부), 생성된 고유 프로젝트 ID, 사용한 WordPress/MariaDB/CLI 이미지 digest, `r4-smoke-evidence.json`의 각 check 상태, 실패 이유, 실제 E2E 실행 날짜, teardown(볼륨 유지/제거) 상태를 통합 검증 문서에 기록한다. 성공하지 못한 테스트나 미실시 검증은 PASS로 기재하지 않는다.
