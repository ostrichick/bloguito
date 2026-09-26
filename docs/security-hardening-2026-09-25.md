# Bloguito 1차 보안 강화 기록 - 2026-09-25

## 범위

공개 공격면, WordPress 관리자 보호, Nginx, SSH, Docker/Compose, OS 패치,
백업/복구 상태를 점검한 뒤 낮은 위험의 강화 항목을 운영 서버에 적용했다.
실제 비밀번호와 인증 토큰은 작업 로그에 기록하지 않았다.

## 사전/사후 백업

- 사전 전체 백업: `/home/ubuntu/backups/bloguito_backup_20260925_093552.tar.gz`
- 구성 롤백 스냅샷: `/home/ubuntu/backups/security-hardening-20260925-1`
- 사후 전체 백업: `/home/ubuntu/backups/bloguito_backup_20260925_100232.tar.gz`
- 사후 전체 백업은 `restore_backup.sh --verify-only`에서 `VERIFY_ONLY_OK` 통과.
- 전체 백업 파일 권한 `600`, 백업 디렉터리 권한 `700` 확인.

## 적용 내용

### Docker/자격증명

- 운영 `docker-compose.yml`에 직접 들어 있던 DB 비밀번호를
  `/home/ubuntu/wordpress/.env`로 분리했다.
- `.env` 권한은 `600`, Compose 권한은 `640`으로 제한했다.
- 운영 Compose를 저장소의 digest 고정 이미지로 동기화했다.
- 운영 Compose SHA256과 저장소 SHA256이
  `67f2e16baa2e02c7688a0f61d831e7415f0bb9863c6a597a392ed6f6cfdaa10a`로 일치한다.
- WordPress 컨테이너 재생성 시 사라지던 WP-CLI를 공식 PHAR + GPG 검증 후
  `./wp-cli.phar:/usr/local/bin/wp:ro`로 영구 마운트했다.
- 재부팅 후 WP-CLI 2.12.0 실행 확인.

- 2026-09-25 10:20경 실제 회전을 다시 시도하기 전에
  `/home/ubuntu/backups/bloguito_backup_20260925_102026.tar.gz` 사전 백업을 만들고
  `restore_backup.sh --verify-only`의 `VERIFY_ONLY_OK`를 확인했다.
- 기존 비밀번호를 사용자가 알고 있을 필요는 없다. 운영 `.env`가 현재 동작 중인
  `MYSQL_ROOT_PASSWORD`와 `MYSQL_PASSWORD`를 보유하고 있고, 백업 스크립트도
  같은 보호 파일에서 root 자격증명을 읽는다.
- 자동 실행 도구에서 자격증명 변경이 차단되어, 서버에 검증된 회전 스크립트를 준비한 뒤
  사용자가 Tailscale SSH 터미널에서 직접 실행했다.
- 최종 v3 실행에서 MariaDB root 및 `wordpress@%` 비밀번호를 각각 새 무작위 값으로
  회전하고, `.env`를 새 값으로 교체한 뒤 WordPress/MariaDB 컨테이너를 재생성했다.
- 최종 출력에서 `DB_PASSWORD_ROTATION_OK`, MariaDB root authentication OK,
  WordPress database authentication OK, Public site OK를 확인했다.
- 변경 후 `.env` 권한은 `600 ubuntu:ubuntu`이며 비밀번호 값은 작업 로그에 출력하지 않았다.
- 변경 후 전체 백업
  `/home/ubuntu/backups/bloguito_backup_20260925_111849.tar.gz`를 새 자격증명으로 생성했고
  `restore_backup.sh --verify-only`의 `VERIFY_ONLY_OK`를 확인했다.
- 이전 실패 시도에서 남아 있던 `.env.before-db-rotation-*` 파일과 서버의 임시 회전 스크립트는
  변경 후 백업 검증이 끝난 뒤 삭제했다.

### WordPress

- `DISALLOW_FILE_EDIT=true` 적용.
- `FORCE_SSL_ADMIN=true` 적용.
- `wp-config.php`를 `640 root:www-data`로 제한.
- 새 MU 플러그인 `bloguito-security-hardening.php` 배포:
  - XML-RPC 애플리케이션 레벨 비활성화.
  - WordPress generator 버전 노출 제거.
  - 비로그인 REST `/wp/v2/users` 열거 차단.
  - core user sitemap 비활성화.
- `Two Factor 0.16.0` 설치/활성화.
- `Limit Login Attempts Reloaded 3.3.10` 설치/활성화.
- Nginx가 `X-Forwarded-For`를 실제 `$remote_addr`로 덮어쓰도록 변경하고,
  LLAR가 `HTTP_X_FORWARDED_FOR`, `REMOTE_ADDR` 순으로 신뢰하도록 설정했다.
- 관리자 계정의 Two Factor provider는 아직 등록되지 않았다.
- 사용하지 않던 WPCode/Insert Headers and Footers 및 LuckyWP TOC 제거.
- 모든 활성 일반 플러그인 및 GeneratePress 자동 업데이트 활성화.

### Nginx/TLS

- `server_tokens off` 적용: 외부 응답은 `Server: nginx`까지만 노출.
- PHP `X-Powered-By` upstream 헤더 제거.
- 다음 보안 헤더 적용:
  - HSTS `max-age=31536000; includeSubDomains`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `/author/` 및 `?author=<숫자>`를 404 처리.
- `/readme.html`, `/license.txt`를 404 처리.
- dotfile 경로 차단.
- `/wp-content/uploads/` 아래 PHP/PHTML/PHAR 실행 경로를 Nginx에서 404 처리.
- `nginx -t` 통과 후 reload.

### SSH/호스트

- `/etc/ssh/sshd_config.d/99-bloguito-hardening.conf` 적용:
  - `PermitRootLogin no`
  - `PasswordAuthentication no`
  - `KbdInteractiveAuthentication no`
  - `X11Forwarding no`
  - `MaxAuthTries 4`
  - `LoginGraceTime 30`
  - `AllowUsers ubuntu`
- `sshd -t` 통과 및 새 SSH 세션 연결 성공 확인.
- Fail2ban 설치 및 sshd jail 활성화:
  - `maxretry=5`
  - `findtime=10m`
  - `bantime=1h`
  - systemd backend + nftables action.
- NFS 사용이 없음을 확인하고 `rpcbind.service/socket` 비활성화.
  재검증 결과 111번 리스너 없음.
- 공개 TCP/22 제거를 위한 사설 관리 경로 준비로 Tailscale 1.102.4를
  서버와 로컬 Windows의 WSL2 Ubuntu 24.04에 설치했다. 양쪽 `tailscaled`는 active.
- 양쪽을 동일 tailnet으로 인증했고 WSL에서 `tailscale ssh ubuntu@bloguito-server hostname`이
  `wordpress-blog`를 반환하는 것을 확인했다.
- Tailscale SSH server를 활성화하고, 새 공개 SSH 연결을 차단하는
  `bloguito-ssh-private-only.service`를 배포/enable했다.
  이 서비스는 `tailscale0`이 아닌 인터페이스에서 들어오는 신규 TCP/22 연결을 drop한다.
- 최종 외부 검사에서 공인 IP `161.33.0.234:22`는 연결 불가,
  Tailscale SSH는 계속 성공했다. 기존 SSH daemon 구성과 Fail2ban은 그대로 유지한다.

### 로컬 PC 백업

- 최초 공개-SSH 기반 동기화에는 기존 `scripts/sync_backups.py`를 사용했고,
  공개 TCP/22 제거 전 `scripts/sync_backups_tailscale.py`를 추가해 Tailscale SSH
  스트리밍 + 원격/로컬 SHA-256 비교 + 기존 archive/manifest 검증을 사용하도록 전환했다.
- 예약 실행 wrapper: `scripts/sync_backups_wsl.sh`.
- 로컬 저장 위치: `C:\Users\gip4k\BloguitoBackups`.
  프로젝트/OneDrive 트리 밖에 두어 WordPress 자격증명이 포함된 백업을 자동으로
  OneDrive 동기화하지 않도록 했다.
- 로컬 보관 정책: 30일.
- Windows 예약 작업: `Bloguito Daily Backup Sync`.
- 실행 시각: 매일 04:30 (서버의 04:00 백업 이후).
- `StartWhenAvailable=True`; 예약 시각에 PC가 사용 불가하면 다음 사용 가능 시점에 실행.
- 현재 사용자 interactive logon으로 `wsl.exe`를 직접 실행하고,
  WSL2의 인증된 Tailscale SSH 경로를 사용한다. 공개 IP SSH alias나 Oracle SSH key에 의존하지 않는다.
- 최초 실행에서 서버의 11개 전체 스냅샷을 다운로드한 뒤 모두 검증 완료.
- Tailscale 전환 후 예약 작업 자체를 다시 수동 시작하여 `LastTaskResult=0` 확인했고,
  11개를 모두 `VERIFIED_EXISTING`으로 재검증했다.
- DB 비밀번호 회전 후 새 스냅샷을 내려받는 과정에서 WSL의 Windows 마운트 경로에
  POSIX `chmod`를 적용하려는 문제가 한 번 드러나 이를 허용 가능한 `PermissionError`로
  처리하도록 수정했다.
- 수정 후 `bloguito_backup_20260925_111849.tar.gz`를 로컬 PC로 내려받아 검증했고,
  예약 작업을 다시 직접 실행해 `LastTaskResult=0`, 총 14개 스냅샷
  `VERIFIED_EXISTING`을 확인했다.

### OS 업데이트

- Ubuntu 패키지 26개 업데이트 적용.
- Docker CE/CLI, curl, Kerberos, netplan 등 업데이트 포함.
- 계획 재부팅 수행.
- 재부팅 후 `reboot_required=no` 확인.
- Ubuntu phased update 대상 AppArmor/audit 일부와 새 Oracle 커널 메타패키지는
  강제 설치하지 않고 정상 phased/hold 상태로 남겼다.

## 최종 검증

- 공개 홈: HTTP 200.
- `/wp-login.php`: 404.
- `/xmlrpc.php`: 403.
- `/wp-json/wp/v2/users`: 404.
- `?author=1`: 404.
- `/author/tips24/`: 404.
- `/readme.html`, `/license.txt`: 404.
- `.env` 공개 경로: 404.
- uploads PHP probe: 404.
- WordPress core 7.1.2 확인.
- Nginx, SSH, Docker, Fail2ban, unattended-upgrades 모두 active.
- 외부 포트 검사: 80/443 접근 가능, 공개 22/111/3306/8080 연결 불가.
- WSL2 → `bloguito-server` Tailscale SSH 정상.
- WordPress/MariaDB 컨테이너 정상 기동.
- 사후 전체 백업 복구 검증 통과.

## 남은 작업

1. 관리자 계정에서 TOTP 2FA를 실제 등록하고 backup codes를 안전한 오프라인 장소에 보관.
2. 필요하면 OCI NSG에서도 공개 TCP/22 ingress rule 자체를 제거해 네트워크 계층에서도 이중 차단한다.
3. 필요하면 로컬 백업 자체의 추가 암호화 또는 별도 오프사이트 저장소를 검토한다.
4. Ubuntu phased update와 새 Oracle 커널은 배포가 안정화된 뒤 별도 유지보수 창에서 적용/검증.
