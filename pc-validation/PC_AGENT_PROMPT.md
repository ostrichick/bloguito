# PC ChatGPT / CoS 지시문 — Bloguito 필수 사전 배포 검증

현재 컴퓨터는 데스크톱 PC이고 WSL2/Docker가 설치되어 있다고 사용자가 설명했다. 노트북에서 전용 Git 브랜치 `chore/pc-release-validation-20261009`로 전달한 Bloguito 통합 릴리스의 미완료 WordPress/MariaDB **실제 대표이미지 잠금/장애/재개 시험**을 수행하라. 테스트 이후 결과와 수정이 필요한 사항을 보고하라. 운영 배포는 **별도 명시적 승인**이 있을 때만 수행하라.

1. PC에서 먼저 `git`, `wsl --list --verbose`, `docker version`, `docker compose version`, `docker context inspect`, CPU/RAM/디스크 및 Docker 메모리 제한을 실제로 조회한다. 이미지 테스트는 충분한 메모리와 로컬 Linux Docker에서만 가능하며, SSH/TCP remote Docker 엔진은 금지한다.

2. 사용자 PC의 기존 `C:\Projects\Bloguito` 또는 실제 프로젝트 경로에서 `git status`를 확인한다. 미커밋 작업/워크트리 보존. `git fetch origin chore/pc-release-validation-20261009` 후 **별도 detached worktree** `C:\Projects\Bloguito-PC-Validation-20261009` 생성. `pc-validation/README.md`, `pc-validation/PREDEPLOY_REVIEW.md`, `AGENTS.md`, `docs/OPERATIONS.md`, `docs/FEATURED_IMAGE_LOCK_RECOVERY.md`를 읽는다.

3. 목표로 하는 실행 코드의 Git 조상 SHA는 `077539a25c49e67bc6f75bc36aa9ecb70557125f`. Git에서 LF로 정규화한 `pc-validation/release-manifest.json` SHA-256 `a99a68cd14757f5575c6445c228da58d27c151494f8a92ea2f355538b1c58b84`와 tracked runtime **80개 파일의 개별 SHA**를 검증한다. 원본 배포 tarball에 포함된 CRLF manifest SHA `c4a606dbd35d1fa042f910553430cdde35ee57ada8adc0eea880095c3ff13b15`와 구별한다. Git 브랜치의 후속 문서/테스트 커밋은 허용하되 운영 runtime은 이 기준과 정확히 같아야 한다.

4. `pc-validation/PC_PREFLIGHT.ps1 -Strict` 실행. 격리 Compose `pc-validation/pc-test/compose.locktest.yml`의 DB/WordPress 이미지 digest·독립 볼륨·`internal:true` 네트워크·포트 0·운영 `.env`/volumes/URL 연결 0을 감사. 필요하면 격리 harness만 최소 보완한다. 운영 `wordpress/docker-compose.yml`을 PC에서 up/down 하지 않는다.

5. `python pc-validation/pc-test/pc_lock_test.py --repo .`로 소스·Docker 사전 점검 후 `--execute`로 테스트 실행. 랜덤 전용 Compose project에서 synthetic `.invalid` WordPress 사이트와 draft를 만든다. 실제 WordPress CLI 병렬 프로세스로 `FEATURED_IMAGE_LOCK_SCRIPT`의 동시 첫 획득, owner mismatch, pending/expired fence, import_mark/complete, 정상/비정상 release, stale takeover, draft 보존을 테스트한다. 모든 결과를 `pc-validation/pc-test/evidence/`에 보존한다.

6. **이 자동 테스트만으로 전체 승인 조건을 충족했다고 주장하지 말 것.** `docs/FEATURED_IMAGE_LOCK_RECOVERY.md:36-50`의 미완료 시나리오를 별도 합성 데이터로 검증한다. 실제 media import, 해시 기반 0/1/복수 attachment reconciliation, post+thumbnail CAS, SSH 255/timeout/응답 유실 및 불확실한 원격 종료 후 중복 import 방지, fault/low-memory fail-closed를 구분해 재현한다. 진짜 별도 Docker DB 상태 검증과 단순 mock을 구분하고, rollback에 필요한 synthetic snapshot을 시험 전부터 유지하라. 검증 불가 항목이 있으면 NO-GO와 구체적인 장애 원인을 남긴다.

7. 관련 표적 회귀검사와 WordPress PHP 계약·Compose 검사를 실행한다. 전체 Python suite는 소스가 앞서 검증된 동일 tree일 때 중복하지 않아도 된다. 테스트/harness 변경 시 그 범위를 새로 검증한다. 시험 성공과 운영 배포·사후 verification을 혼동하지 않는다.

8. 테스트용 DB/WordPress 컨테이너·네트워크·볼륨 **본인이 새로 만든 project만** 정리하고 다른 Docker 프로젝트는 만지지 않는다. `docker system prune`, 운영 `ssh bloguito`, 실제 운영 WordPress DB/WP-CLI/REST/자격증명 사용은 금지. 증거는 별도 Git 무시 디렉터리에 남기고 민감 정보가 들어가지 않았는지 검토한다.

9. PASS/FAIL/미검증, command/exits, Docker 격리 및 cleanup, 임시 DB snapshot, source/asset hash, 결과 증거를 정리해 `pc-validation/PREDEPLOY_REVIEW.md` 및 결과 보고에 추가한다. 릴리스/문서 수정·커밋은 별도 브랜치에서만 하며, Git push는 별도 사용자의 승인 없이는 하지 않는다. **운영 배포도 승인 전 금지**. 모든 사전 배포 gate가 통과할 때만 운영 배포 승인을 요청한다. 운영 직전 baseline/backup/readback/cron/image lock preflight를 다시 확인해야 한다.

사람의 WordPress 수동 발행 권한과 AI 자동 공개 gate를 반드시 보존하며, 실제 글 발행·신규 draft 생성·이미지 import를 운영에서 시험하지 않는다. 오래된 운영 관측 revision `b9de470...`을 현재 상태로 단정하지 않는다. 기록과 함께 완료 보고하라.
