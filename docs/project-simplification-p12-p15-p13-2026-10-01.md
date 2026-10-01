# 프로젝트 단순화 P12·P14·P15·P13 — 2026-10-01

## 범위

- 기준: P1~P11 및 P10 실제 state migration이 통합된 `main`.
- 순서: P12 legacy CLI/shim 제거 → P14 worktree/tmp 정리 → P15 CI/backup/DR 중복 통합 → P13 legacy runtime 이관·퇴역.
- 유지한 안전장치: WordPress content SHA CAS, guarded readback, public backup, 명시적 공개 승인, backup SHA/manifest/path 검증, v2 backup verify, non-idempotent media import 무재시도.

## P12 — 공개 실행 표면 축소

- 정상 콘텐츠 mutation은 `prepare-draft`, `edit-post`, `replace-featured-image` 세 경로로 고정했다.
- 공개 CLI에서 `publish`, `edit-draft`, `revise-draft`, `fast-revise-draft`, `update-existing`, `update-draft`, `quick-image-replace`를 제거했다.
- draft Fast/Standard는 사용자 action이 아니라 SSH adapter 내부 profile `draft-fast` / `draft-standard`로만 남겼다.
- legacy `--tailscale-ssh` boolean override를 제거하고 `--ssh-mode tailscale`만 명시적 비상 경로로 유지했다.
- P10 전환 완료로 역할이 끝난 `sync_editorial_state_via_ssh.py`와 `update_existing_via_ssh.py` forwarding shim 및 전용 테스트를 제거했다.
- `replace-legacy-draft`는 P10 reviewed state가 없는 #665 한 건 때문에 maintenance-only holdout으로 남겼다. source-bound reviewed bundle이 없으므로 과거 HTML·작업 기록에서 provenance를 임의 생성하지 않았다.

## P14 — 저장소 운영 정리

- clean + `main` 병합 완료 worktree 5개를 제거했다: simple-task-fast-path, event-location-card, featured-cover-v4, P9~P11, pipeline-simplify.
- 대응하는 로컬 병합 branch와 실제 존재하던 원격 병합 feature branch를 정리하고 `git fetch --prune`을 수행했다.
- dirty worktree, 미병합 branch, `preserve/main-wip-20261001`은 보존했다.
- `tmp/php8426`은 코드·문서 참조가 없는 PHP 배포 캐시임을 확인한 뒤 91.1MB를 제거했다.
- `post225_work`, `legacy_audit_*` 등 날짜별 문서에서 재현 증거로 직접 참조하는 legacy tmp는 삭제하지 않았다.

## P15 — CI·backup·DR 중복 통합

- `wordpress/tests/run.php`를 추가해 MU plugin/test PHP syntax와 standalone `*-test.php` contract를 자동 발견한다. GitHub Actions의 수동 PHP 파일 나열을 이 runner 하나로 교체했다. live WordPress가 필요한 smoke test는 syntax-only로 분리했다.
- `sync_backups.py`에 공통 `sync_transport()`와 Direct/Tailscale transport를 두고 별도 `sync_backups_tailscale.py`를 제거했다. Tailscale은 `BLOGUITO_BACKUP_TRANSPORT=tailscale`일 때만 명시적으로 사용한다.
- 두 transport 모두 remote SHA → 임시 다운로드 → local SHA → remote 재확인 → v2/v3 manifest·nested archive·path 검증 → atomic replace 순서를 공유한다.
- `host_dr_validate.sh`를 nginx/TLS/sshd/fail2ban/systemd 검증 정본으로 만들고, `host_dr_config_drill.sh`은 disposable container에서 이를 `--with-wp-cli`로 호출하도록 중복을 제거했다.

## P13 — legacy runtime 퇴역

- 운영 WordPress의 legacy TOC allowlist 25개를 읽기 전용 census했다. 현재 공개 상태인 23개는 모두 이미 저장된 `bloguito-article` + native TOC 구조였고 #77/#103은 trash였다.
- #85는 이미 `bloguito-article` + `bloguito-info-table` 구조이며 legacy table MU의 fail-closed fingerprint 대상이 아니었다.
- 전체 공개 글 56개를 조사해 구형 `#11775a` callout pattern 사용이 0건임을 확인했다.
- 따라서 repository와 운영 서버에서 `bloguito-legacy-toc.php`, `bloguito-legacy-table-accessibility.php`, `bloguito-legacy-callout-spacing.php` 및 전용 테스트를 제거했다.
- 운영 제거 전 세 파일 SHA가 과거 배포 기록과 일치함을 확인했고 rollback 사본을 `/home/ubuntu/bloguito-retired-mu-20261001/`에 보존했다.
- #55/#85의 `the_content` render SHA는 제거 전후 각각 `1dca39d63621cf4dbb992f4c1cdb1ed1ff7c9c05145e37880b2bba9a41bf4f7b`, `260047bf97ff67961f337340ed422c23582bff10a046e623fb95b0302c39af1a`로 동일했다.
- 현행 P10 reviewed state에서 사용 0건인 #70/#99 전용 `legacy_nol_product_listing`과 NOL product schedule parser/test를 제거했다. 일반 NOL 공식 판매 상태 검증과 Yes24/Ticketlink 일정 경로는 유지했다.
- live draft #665는 WordPress에 존재하지만 P10 reviewed index에 없고, 남은 자료는 HTML/이미지/작업 기록뿐이라 source-bound reviewed bundle을 복구하지 못했다. 안전을 위해 provenance를 합성하지 않고 `replace-legacy-draft` 한 경로만 holdout으로 유지했다.

## 검증

- P12 transport/script hygiene: 45 tests PASS.
- P12/P15/P13 통합 표적: 95 tests PASS.
- backup recovery v3/direct/Tailscale synthetic 검증: 9 tests PASS. 의도된 transfer-failure 주입 메시지는 정상이다.
- DR shell syntax: PASS.
- `git diff --check`: PASS.
- 전체 Python suite는 obsolete `publish` action 전용 테스트를 제거한 뒤 742 tests를 실행했고 새 실패는 0건이다. 남은 8 errors + 1 skip은 작업 전 `origin/main`에서 동일하게 재현한 기존 `test_designer_safety` baseline이다.
- 로컬 Windows/WSL에 PHP runtime과 Docker가 없어 새 `wordpress/tests/run.php`의 실제 실행은 feature branch push 뒤 GitHub Actions PHP 환경에서 확인한다.
