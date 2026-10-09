# Bloguito 통합 editorial release — 배포 승인 전 검토

검토 기준: 2026-10-09 KST. **현재 상태는 사전 검증 artifact 준비 완료 / 운영 배포 NO-GO**이며 installer를 운영 앱에 실행하지 않았다. 진술은 본 검토에서 실제 관측·실행한 결과에 한정한다.

## 코드와 통합

- 기준 운영 revision: `b9de4709fff354f7449d6f275b36ea17fdec5b7c` (`data/editorial-release.json` read-only).
- 기존 로컬 `main`: `80bfadd213fe849d1bf2e6f323a13c712ea9f64d`; clean.
- 통합 release branch: `release/bloguito-integrated-20261009`; **release revision** `077539a25c49e67bc6f75bc36aa9ecb70557125f`; clean.
- 이미지 업로드/재개/실패/잠금 및 publisher/WordPress edit 경로 강화 `df95b55`, `cfa49b3`, 무인 이미지 보류 `0f57bf7`, 복구 가이드 `bd1dfd5`가 기반 main에 이미 반영됨. 독립 에이전트의 `8b0d84c`, `2ed9539`는 동일 효과가 별도 commit으로 main에 반영됨. 관측성 `4a70ce3`을 충돌 없이 cherry-pick한 새 commit `077539a`가 이번 통합 대상.
- 별도 `65349f0` SSH 최소권한 보안 제안/스크립트는 **이 release에 포함되지 않음**. 별도 권한 이관 작업이며 광범위한 운영 sudo 권한도 남아 있음.
- 기존 WordPress PHP MU-plugin은 `b9de470`부터 현재까지 Git 변경이 없고, 운영 `bloguito-post-row-actions.php` SHA-256가 현재 local SHA와 일치함(`a77b668fd1c12c137a54ed0a14e63c3056e060f0bb43848ed5e2823b602f867f`). PHP 코드를 이번 editorial installer가 재설치하지 않음.

## 불변 artifact와 정규 installer

- 로컬 패키지: `scratch/tasks/predeploy-release-20261009/release-077539a.tar.gz` (repo의 무시되는 작업 영역).
- SHA-256 패키지: `aeed93a1eb59950d19e0606d6f1122c5e5c9636fcf9da0fab88d0183518dd21b`.
- Manifest: `release-077539a/release-manifest.json`, SHA-256 `c4a606dbd35d1fa042f910553430cdde35ee57ada8adc0eea880095c3ff13b15`.
- `schema_version=2`, revision `077539a25c49e67bc6f75bc36aa9ecb70557125f`, 80개 파일, inventory digest `3104dbc8c9ea1e9c3d3da173826b7e10772b064220a410f491bd489b40ca8cdb`.
- 정규 `scripts/build_editorial_release.py --archive` 실행. `scripts/install_editorial_release.py` SHA-256 `9972c428213013dc6b0948722f5671a6f0c792b0593d7df2212dae1eb11bf971`.
- Linux staging `/home/ubuntu/.bloguito-release-staging/predeploy-artifact-077539a/`에 tar.gz 및 installer 복사. 운영 app은 변경하지 않고 unpack/manifest 80 hash/config external/기존 module compatibility 검증 PASS; unexpected modules 0, retired 파일 0.
- 추가로 같은 staging 안의 격리 fake app에 정규 installer를 실제 실행: 등록된 80개 파일 SHA와 revision readback **PASS**. 실행기(venv)를 제거한 별도 실패 fake app에서 installer rollback **PASS**(원본 main SHA 복원, 신규 module/receipt 제거). 이는 WordPress와 분리된 코드 installer 회귀 리허설이다.
- 상세 80개 파일명과 개별 SHA는 manifest `files`가 정본. 전체 중 운영과 동일 67개, 변경 13개, missing 0개. 변경 파일:
  `agent-publisher/agents/designer.py`, `agents/edit_orchestration.py`, `agents/edit_post.py`, `agents/edit_router.py`, `agents/featured_image.py`, `agents/publisher.py`, `agents/task_state.py`, `agents/wordpress_mutation.py`, `agent-publisher/editorial_cli.py`, `agent-publisher/editorial_policy.json`, `agent-publisher/main.py`, `agent-publisher/notifier.py`, `docs/FEATURED_IMAGE_STANDARD.md`.
- installer retirement allowlist: `agents/copywriter.py`, `agents/editorial_draft_updater.py`, `agents/editorial_legacy_draft.py`; 현재 운영에 세 파일은 존재하지 않음.

## 검증 (설치 성공과 구분)

- Python `agent-publisher` 트리는 전체 1,153건(1 skip) 통과했던 `4a70ce3`와 Git byte tree 차이 0. 따라서 전체 suite 결과 재사용; 새 통합 commit에서 `test_pipeline_exit_status.py` 23건, `test_notifier_delivery.py` 5건 다시 PASS.
- 추가 통합 표적: `test_featured_image*.py` 60건 PASS, `test_publish_gate.py` 4건 PASS, `test_editorial_release_manifest.py` 15건 PASS. 테스트는 운영 앱 대신 로컬 mock/임시 디렉터리를 사용.
- UTF-8 검사, repo secret 검사, `git diff --check`, CLI `main.py --help` 확인 PASS (CLI는 선행 검증에서 확인).
- Git Bash `bash -n` run_daily/backup/restore/host DR 스크립트 PASS.
- 현행 WordPress 소스만 owner-only 격리 staging에 복사. 기존 cached `wordpress:latest` 이미지로 **새 컨테이너**를 `--network none`, `--read-only`, no named volume/no production DB, 제한 리소스, tmpfs 사용해 `php wordpress/tests/run.php` 수행: MU 9개와 테스트 PHP 문법 검사 및 7개 독립 계약 PASS. 실제 관리 UI 발행이나 WP/DB integration test가 아님.
- 현재 checkout의 `docker-compose.yml`을 격리 staging에 복사해 운영 Docker Compose `config --quiet`에 **검증 전용 placeholder password** 지정: PASS. 컨테이너 재생성 없음.
- WordPress 이미지 lock preflight: `wp_options`, `wp_postmeta` InnoDB, lock_count=0, blockers=[]; 검사 시점 snapshot이며 실제 설치 직전에 재확인 필요.
- **미완료 필수 gate:** `FEATURED_IMAGE_LOCK_RECOVERY.md`가 요구하는 실제 격리 WordPress/MariaDB 병렬 이미지 lock·장애 리허설은 실행하지 않음. 2026-10-09 운영 호스트 메모리 952MiB, 가용 약 504MiB, swap 약 527MiB 사용 중. 운영 WP/DB 옆에 MariaDB+WordPress+복수 WP-CLI를 추가하는 것이 서비스 메모리 경합 위험이 있어 선행 조사 단계에서 중단. 격리용 컨테이너/네트워크/볼륨은 생성 0건. 메모리 여유가 확보된 **별도 VM**에서 합성 게시물·가짜 `.invalid` 사이트로 동시 acquire, pending lock, 장애/실패 응답, 소유권, 복구를 검증해야 한다. 이 gate 미통과 상태에서는 사용자 배포 승인 여부와 무관하게 정규 운영 설치를 진행하지 않는다.

## 운영에서 보존 및 변경 금지

- 기존 `agent-publisher/.env`, `data/search_briefs.json`, `data/draft_posts.json`, `data/published_posts.json`, `data/growth/daily-growth-plan.json`, `data/growth/growth-work-log.json`, `data/editorial-release.json` 존재 확인; installer는 managed `data/editorial-release.json`만 설치 성공 후 기록하고 나머지 private runtime을 패키지에 넣지 않음.
- installer는 **tracked** `data/renderer_provenance.json`, `data/reviewed_content_provenance.json`, `data/critical_facts/*.json`, `data/policy_exceptions/*.json` 및 허용된 provenance attestation을 관리 코드처럼 복사/백업함. 현행 두 provenance JSON 해시는 패키지와 동일(80개 동일 파일에 포함). 설치 전 재검증 필수.
- WordPress DB, posts, attachments, uploads, options, live MU plugins, cron, `.env`, private source receipt는 installer가 수정하지 않음. 해당 자원의 SHA/건수와 존재 확인은 설치 전후 비교.
- 사람이 인증된 WordPress 편집자 세션으로 수행하는 수동 발행/임시글 전환을 보존하고, 무인 WP-CLI/AI 자동 공개는 canonical attestation/review gate를 유지. 배포 검증 목적의 발행, 신규 draft 생성, 실제 media import 금지.

## 운영 rollback 지점 및 절차

- 배포 전 full v3 snapshot: `/home/ubuntu/backups/bloguito_backup_20261009_132124.tar.gz` (116,560,131 bytes; SHA-256 `b1e7fa2de64cfef2bcba3ab123364f542dd0e2685b615d194b6e0e95cd3b0292`). 실제 `restore_backup.sh <archive> --verify-only` 실행: 3.0, 모든 component SHA, gzip, nested paths PASS. /tmp 검증 staging만 사용 후 정리, WordPress 복원 안 함. 독립 전체 서비스 복원 성공은 이번 검증 범위에 없음.
- 설치 성공/실패 시 installer의 변경 대상별 원본 바이트는 `/home/ubuntu/agent-publisher/backups/editorial-<UTC>/` 아래 번호별 파일과 `manifest.json`에 기록됨. 실패 예외에서는 역순 복원하나, 강제 종료나 성공 후 발견된 문제의 자동 롤백 명령은 없음.
- 승인 후 설치 직전: 실제 revision/80개 SHA, private state SHA, 이미지 lock 0 및 cron writer idle 재확인. 새 Lock이 하나라도 있다면 특히 `import_pending` 상태를 조정하기 전까지 설치/롤백 중단. 08:00 cron과 겹치지 않는 maintenance window 사용.
- 설치: 저장해둔 동일 SHA의 installer만 사용해 `python3 /home/ubuntu/.bloguito-release-staging/predeploy-artifact-077539a/install_editorial_release.py /home/ubuntu/.bloguito-release-staging/predeploy-artifact-077539a/release-077539a /home/ubuntu/agent-publisher`. 사용자 **명시 승인 후에만**.
- 성공 후 이전 `editorial-release.json`의 backed-up SHA/내용, 설치 SHA 80개, registry smoke, CLI (`--help`), 실패/hold 구조화 결과 mock, private state 불변, WordPress 수동 발행 MU SHA·실행 중 프로세스/cron 등을 readback. 해당 검사는 신규 글·공개 전환 없이 수행.
- **코드 롤백 트리거**: 예상 밖 code hash/missing, installer registry 실패, WordPress mutation 여부에 의문, critical CLI/lock safety 실패, private state unexpected SHA, active import lock이나 자동화 충돌. 게시물/미디어에 영향을 줄 수 있는 실행이 시작됐다면 예전 잠금 미지원 코드로 즉시 되돌리지 말고 lock 및 receipt 먼저 정리.
- 코드 롤백: 기존 작업 중지·잠금/receipt 정합성 확보 → 해당 설치의 `backups/editorial-<UTC>/manifest.json` 파일을 검증 → 기록된 target들을 **역순으로**, backup token이 있으면 원본 바이트로 원자적으로 교체하고 신규 파일은 제거 → 이전 `data/editorial-release.json` 복원 → 80개 기존 revision/readback, registry/CLI 재검사. 백업 manifest의 허용된 app/docs 경로만 사용하고, 백업이 없거나 손상되면 임의 복구 금지. 사용자 승인 없이 롤백을 미리 실행하지 않음.
- **DB/미디어 복원**은 별도: installer 코드 롤백은 DB, options, uploads, media와 task state를 되돌리지 못함. 데이터 손상이 실제로 확인되면 v3 snapshot 기반 격리 복원 검증 및 사용자 별도 승인을 거쳐서 데이터 복구 여부를 결정. 최신 운영 데이터 손실 가능성 비교 없이 full restore 수행 금지.

## 승인 경계 및 잔여 확인

- 이 작업에서 운영 editor installer는 **아직 미실행**. 임시 staging에 test 소스와 release artifact만 복사함. 운영 임시글·공개 status 변경 0건.
- 이번 준비는 최종 운영 deploy GO가 아니다. 본 문서/패키지는 검토 가능하지만 **격리 DB 동시성·장애 시험 미완료가 승인 전 해소할 차단 사항**이며, 시험 완료 및 서버 preflight 재확인 후에만 설치 승인을 요청한다.
- `65349f0` 별도 SSH 최소권한 이관 미반영. 기존 계정의 sudo/docker 접근은 정책 기술 강제가 완전하지 않은 잔여 위험.
- 정규 installer는 WordPress MU-plugin, cron `run_daily.sh`, 자체 파일을 release inventory에 포함하지 않음. 이번 변경과 달라진 PHP/plugin은 없어 기존 라이브 플러그인 SHA를 보존하고 교체하지 않음. cron locking은 별도 TODO.
- 현재까지 관측한 PHP 단독 계약 결과는 실제 운영 수동 UI 발행 테스트를 대신하지 못함. 배포 후 readback 및 다음 08:00(KST) cron 성공은 각각 독립 확인해야 하며 실행 시점 전에는 미확인.
