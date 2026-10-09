# Bloguito — PC WSL2/Docker predeployment validation

이 디렉터리는 **Git으로 PC에 전달되는 추적 파일**이다. ZIP/OneDrive 이동, Git bundle 또는 별도 release tarball은 필요 없다. `main`/운영 서버를 건드리지 않고 전용 worktree에서 실행한다.

## 고정 기준

- 배포 대상 소스 commit: `077539a25c49e67bc6f75bc36aa9ecb70557125f`.
- 운영 당시 baseline: `b9de4709fff354f7449d6f275b36ea17fdec5b7c`; 이는 과거 관측이지 현재 상태가 아님.
- 함께 추적된 `release-manifest.json`은 canonical builder의 **80개 파일 SHA-256**, revision, retirement 범위를 보유한다. 이 Git 사본은 원본 Windows manifest의 CRLF를 LF로 정규화한 동일 JSON이며 SHA-256은 `a99a68cd14757f5575c6445c228da58d27c151494f8a92ea2f355538b1c58b84`다. 별도 immutable tarball 내부 **원본 manifest SHA**는 `c4a606dbd35d1fa042f910553430cdde35ee57ada8adc0eea880095c3ff13b15`로 변함없다.
- 원래 immutable tarball SHA-256 `aeed93a1eb59950d19e0606d6f1122c5e5c9636fcf9da0fab88d0183518dd21b`는 `PREDEPLOY_REVIEW.md`에 기록됨. 이 tarball은 테스트용 Git repo에 복사하지 않는다. 실제 운영 배포에는 사전 검토한 tarball을 별도 사용한다.
- 이전 사전 검증: 동일 코드 전체 Python 1,153 PASS(1 skip), 관련 표적 PASS, WordPress 오프라인 PHP 계약, Bash/Compose 정적 검사, 격리 installer 성공/실패 rollback, v3 backup verify-only PASS. **실제 MariaDB/WP 이미지 잠금 동시성·장애 시험 미완료**가 이번 PC 작업의 목적이다.

## PC에서 가져오기

GitHub 공유 브랜치는 `chore/pc-release-validation-20261009`. PC에 기존 저장소가 `C:\Projects\Bloguito`에 있다고 가정하면 PowerShell에서:

```powershell
git -C C:\Projects\Bloguito fetch origin chore/pc-release-validation-20261009
git -C C:\Projects\Bloguito worktree add --detach C:\Projects\Bloguito-PC-Validation-20261009 FETCH_HEAD
git -C C:\Projects\Bloguito-PC-Validation-20261009 status --short --branch
git -C C:\Projects\Bloguito-PC-Validation-20261009 rev-parse HEAD
```

기존 PC 저장소에 미커밋 수정이 있더라도 그 파일은 그대로 유지된다. 다른 checkout 경로를 원하면 사용 중인 경로를 먼저 확인해 지정한다. 전체 main을 pull/merge하지 않는다.

## PC 사전 검증/시험

PowerShell에서 PC의 Docker Linux 엔진이 **local context**임을 확인한다. `PC_PREFLIGHT.ps1`은 Docker의 원격 SSH/TCP 엔진을 거절한다. 설치/시작은 사용자 PC의 시스템 권한에 맞춰 수행한다.

```powershell
Set-Location C:\Projects\Bloguito-PC-Validation-20261009
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\pc-validation\PC_PREFLIGHT.ps1 -Strict

# 이 호출은 실제 Docker 테스트 컨테이너를 생성하지 않는다.
python .\pc-validation\pc-test\pc_lock_test.py --repo .

# 사전 검증 성공 후, 오직 별도 프로젝트/볼륨/내부 네트워크에서 실행한다.
python .\pc-validation\pc-test\pc_lock_test.py --repo . --execute
```

Python 3.10+, Docker Linux engine/Compose v2, 권장 PC 가용 RAM 4GB 이상을 필요로 한다. compose는 `wordpress/docker-compose.yml`과 **별개**이며, 고정 digest WordPress/MariaDB 이미지를 사용한다. 테스트용 WP-CLI PHAR 2.12.0은 SHA-256 검증 후 로컬 `pc-validation/pc-test/wp-cli.phar`에 받는다. 컨테이너 네트워크는 `internal: true`, 호스트 공개 포트 0, 운영 `wp_data`/`db_data` volume 및 실제 `.env` 참조 0, 외부 알림/메일·접속 0.

자동 script는 synthetic `.invalid` site, 임시 draft, DB snapshot을 만들어 실제 WP-CLI 두 process에서 소유권·만료·pending fence를 검증한다. 결과 파일은 Git 무시 경로 `pc-validation/pc-test/evidence/<run-id>/result.json`, `synthetic-before-lock.sql`에 저장된다. 테스트 전용 Compose project는 랜덤이며 종료 시 **그 프로젝트에 한해** `down -v`를 수행한다. 실패 시 정리 성공 여부를 별도로 보고해야 한다.

## 자동 검증과 최종 gate를 구분할 것

자동 harness가 검증하는 것은 동시 acquire, busy, owner mismatch, duplicate mark, pending takeover 차단, complete/release, stale lease takeover, synthetic draft status 보존 등 **기본 lock real DB contract**다. 전체 배포 GO가 아니다.

`docs/FEATURED_IMAGE_LOCK_RECOVERY.md:36-50`의 다음 시험은 PC 담당 에이전트가 같은 격리 WordPress/MariaDB에서 추가로 진행한다: 실제 media import, attachment SHA 0/1/복수 matching, post/thumbnail CAS, SSH 255 및 응답 유실·timeout 뒤 중복 import 없는 복구, fault injection과 메모리/시간 초과 fail-closed. 실험별 실제 오류와 mocked 출력을 구별하고 synthetic DB/미디어 snapshot 및 오염 방지 근거를 남긴다. 확인하지 않은 시나리오는 **미검증/NO-GO**로 보고한다.

테스트 종료 후 증거와 `PREDEPLOY_REVIEW.md`를 갱신하되, 원래 이력 문서를 운영의 현재 상태로 바꿔 쓰지 않는다. **운영 배포, Git push, 운영 글 생성·발행, 이미지 업로드, WP/DB 복원·cron 변경은 별도 승인 없이는 금지.**
