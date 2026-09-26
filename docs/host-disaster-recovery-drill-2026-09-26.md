# Bloguito 호스트 단위 재해복구 훈련 — 2026-09-26

## 범위와 판정 기준

이번 훈련은 2026-09-25의 WordPress 애플리케이션/데이터 복구 훈련을 호스트 구성까지 확장했다. 같은 날짜의 [호스트 구성 DR 정적 검증](host-dr-drill-2026-09-26.md)과 상호 보완 관계이며, 이 문서는 최신 백업의 실제 애플리케이션 복원과 TLS handshake까지 포함한 통합 결과를 기록한다. 운영 서버에는 읽기 전용 점검과 새 백업 생성만 수행했고, 복원·설정 적용은 로컬 Docker Desktop의 일회용 환경에서 수행했다. 운영 비밀번호, 실제 TLS 개인키, `secrets.tar.gz` 내용은 격리 환경에 넣지 않았다.

전체 판정은 **PARTIAL**이다. WordPress 데이터와 애플리케이션, WP-CLI, Nginx/TLS 설정, SSH 설정, Fail2ban 설정, systemd unit 문법, Docker Compose 선언의 복구 경로는 실제 복원 또는 실행 가능한 수준까지 검증했다. 그러나 새 VM에서의 실제 Let’s Encrypt 발급, Tailscale 신규 노드 재등록, rebuilt host로의 실제 SSH 로그인, systemd가 PID 1인 새 VM 전체 부팅까지는 수행하지 않았다.

## 1. 최신 운영 백업

2026-09-26 20:15 KST에 운영 서버에서 새 v3 백업을 생성했다.

- 파일: `/home/ubuntu/backups/bloguito_backup_20260926_201559.tar.gz`
- 크기: `40,221,956 bytes`
- SHA256: `1a247a622eaa72660d644a8ea30d955b90f2fd3c3bdf2979f3c42549e6bbacab`
- 형식: v3.0
- `restore_backup.sh --verify-only`: `VERIFY_ONLY_OK`
- 로컬 보관본: `C:\Users\gip4k\BloguitoBackups\bloguito_backup_20260926_201559.tar.gz`
- 로컬 SHA256: 운영 서버와 동일

다운로드는 공인 SSH를 다시 열지 않고 Tailscale 경유 표준 SSH 스트림으로 수행했다.

## 2. 운영 호스트 읽기 전용 인벤토리

관측 시점의 핵심 상태:

- Nginx `1.24.0 (Ubuntu)`
- Docker `29.8.1`
- Docker Compose `v5.5.1`
- Tailscale `1.102.4`
- `nginx`, `ssh`, `docker`, `fail2ban`, `tailscaled`, `bloguito-ssh-private-only.service`: 모두 `active`
- `nginx -t`: 통과
- `sshd -t`: 통과
- Fail2ban: `sshd` jail 1개 활성, `maxretry=5`, `findtime=10m`, `bantime=1h`
- TLS 인증서: `lifeinfo24.org`, Let's Encrypt 발급, 관측 유효기간 `2026-09-15`~`2026-12-14`
- 백업 cron: 매일 04:00
- 자동 원고 cron: 매일 08:00
- `certbot.timer`: 존재
- 운영 WP-CLI: 2.12.0, WordPress core 7.1.2, `home=https://lifeinfo24.org`

운영 WordPress 컨테이너의 실제 image ID는 `sha256:5a93c470ae8220fddf71f6ebe3bc94e615ddc2ae4d9810f795b830fb11c41a17`이고, 저장소 `wordpress/docker-compose.yml`은 별도 격리 검증을 거친 `wordpress@sha256:8ae73d594a154e30b112e8d085afbc0895acf7651d8f53ef63aefb42e30822d5`를 가리킨다. MariaDB image ID는 운영과 저장소가 `sha256:07c0aaff7396b74cb7975cba78257178d188e30f531a5db2b617c48beef13c41`로 일치했다. 따라서 이번 복원은 **현재 운영 WordPress 이미지 바이트를 그대로 재현한 훈련이 아니라, 저장소에서 다음 재구축용으로 고정한 WordPress 이미지에 최신 데이터를 복원한 훈련**이다.

저장소의 다음 네 호스트 설정은 운영 파일과 SHA256이 정확히 일치했다.

| 구성 | SHA256 |
| --- | --- |
| Nginx `lifeinfo24.org.conf` | `5d9067dde68425af64cbb8715b3aacf7cbb6a1698310d55e8f83b48d918a871d` |
| SSH `99-bloguito-hardening.conf` | `9a3cdb50a9028b9f383a57c8102299e0eeae5c8c70f432c94695a5323e3fa98b` |
| `bloguito-ssh-private-only.service` | `9edbaefac486e9bfd3ebc8fea89883450379fab5fa027c1f51020c1c63f00970` |
| Fail2ban `bloguito-sshd.conf` | `20b8c37ad4f3105c6db1f4d1f672dde38f01dc0ad61a38f7620808511bf84623` |

## 3. 격리 호스트 구성 검증

재현용 스크립트 `scripts/host_dr_validate.sh`를 추가했다. 이 스크립트는 `/repo`가 읽기 전용으로 마운트된 일회용 Ubuntu 24.04 컨테이너에서 다음을 수행한다.

1. Nginx, OpenSSH, Fail2ban, systemd 도구, OpenSSL 설치
2. 저장소 Nginx 가상호스트 복원
3. 실제 운영 인증서 대신 1일짜리 자체 서명 인증서와 격리용 TLS 보조 설정 생성
4. `nginx -t` 통과
5. Nginx 실제 기동 후 `127.0.0.1:443` TLS handshake 성공, 종료
6. 저장소 SSH hardening 파일 복원 후 `sshd -t` 통과
7. 저장소 Fail2ban sshd jail 복원 후 `fail2ban-client -d` 파싱과 `maxretry=5` 반영 확인
8. `systemd-analyze verify`로 Tailscale 전용 SSH 제한 unit 검증

최종 출력: `HOST_DR_CONFIG_VALIDATION_OK`

Windows bind mount의 POSIX permission 표현 때문에 `systemd-analyze`가 unit 파일을 executable/world-writable로 보았다는 경고가 있었다. 이는 Windows 마운트 메타데이터 경고이며 unit 내용 검증 자체는 통과했다. 실제 운영 파일의 권한을 변경한 것은 아니다.

## 4. 최신 백업의 실제 애플리케이션 복원

운영 이름과 분리된 다음 일회용 리소스를 만들었다.

- MariaDB 컨테이너 `bloguito_hostdr_20260926_db`
- WordPress 컨테이너 `bloguito_hostdr_20260926_wp`
- 전용 DB/WP 볼륨
- 전용 내부 Docker 네트워크
- 호스트 포트 공개 없음
- drill-only DB 자격증명 사용

최신 백업에서 `db.sql.gz`, `wp-content.tar.gz`, `uploads.tar.gz`만 안전하게 추출해 실제 복원했다. `secrets.tar.gz`는 사용하지 않았다.

복원 후 확인:

- WP-CLI `2.12.0`
- WordPress `7.1.2`
- `home=https://lifeinfo24.org`
- 공개 post 41개
- draft post 5개
- 활성 테마 `generatepress`
- 활성 일반 플러그인 7개
- 새 기본 OG 파일 `wp-content/uploads/2026/09/bloguito-og-default-1200x630-1.png` 존재
- Apache config syntax OK
- 격리 WordPress `/` HTTP 200
- 격리 WordPress `/sitemap_index.xml` HTTP 200

이 훈련에서 생성한 `bloguito_hostdr_20260926_db`, `bloguito_hostdr_20260926_wp`, 두 전용 볼륨과 전용 네트워크는 검증 후 삭제했다. 같은 이름 접두어를 가진 별도의 기존 Compose 리소스는 다른 실행에서 이미 존재하던 것이므로 건드리지 않았다.

## 5. WP-CLI provisioning

`wordpress/provision-wp-cli.sh`는 WP-CLI `2.12.0`의 버전 지정 release URL과 SHA256을 고정한다.

- 고정 SHA256: `ce34ddd838f7351d6759068d09793f26755463b4a4610a5a5c0a97b68220d85c`
- 실제 새 다운로드 후 해시 일치 확인
- `wordpress/docker-compose.yml`이 생성된 PHAR을 `/usr/local/bin/wp:ro`로 마운트
- 격리 복원 컨테이너에서 `wp --info`, `wp core version`, `wp option get home` 실제 성공

따라서 rebuilt server에서 수동으로 임의 버전의 WP-CLI를 내려받는 절차에 의존하지 않는다.

## 6. 검증 매트릭스

| 항목 | 판정 | 실제 검증 |
| --- | --- | --- |
| 최신 백업 무결성 | PASS | v3 verify-only + 원격/로컬 SHA 동일 |
| MariaDB 데이터 복원 | PASS | 최신 dump 실제 import, WordPress bootstrap 성공 |
| uploads/plugins/themes/MU 경로 | PASS | wp-content/uploads 실제 복원 및 WordPress 실행 |
| WordPress HTTP/sitemap | PASS | 격리 환경에서 200/200 |
| WP-CLI 재구축 | PASS | 공식 고정 버전 다운로드·SHA 검증·복원 환경 명령 성공 |
| Docker Compose 선언 | PASS | placeholder 비밀값으로 `docker compose config --quiet` 통과 |
| Nginx | PASS | 새 Ubuntu에서 복원 후 `nginx -t`, 실제 기동 성공 |
| TLS 설정 경로 | PASS | 격리 자체서명 인증서로 443 TLS handshake 성공 |
| 실제 Let's Encrypt 신규 발급 | NOT TESTED | production ACME 발급/도메인 검증은 반복하지 않음 |
| SSH hardening | PASS | 저장소=운영 SHA 동일, 새 Ubuntu에서 `sshd -t` 통과 |
| rebuilt host 실제 SSH 로그인 | NOT TESTED | 새 VM/키 교환까지는 수행하지 않음 |
| Fail2ban | PARTIAL | 운영 jail active, 격리 환경 config parser 통과; systemd journal 기반 실제 ban 동작은 미실행 |
| SSH private-only systemd unit | PARTIAL | 운영 active + 격리 `systemd-analyze verify`; 새 VM 부팅 cycle은 미실행 |
| Tailscale 관리 경로 | PARTIAL | 현재 운영 Tailscale SSH 경로 사용 성공; 새 노드 재등록은 미실행 |
| 전체 새 VM 부팅 후 서비스 일괄 기동 | NOT TESTED | Docker 기반 격리 훈련은 PID 1 systemd VM이 아님 |

## 남은 실제 VM 수준 훈련

다음 단계가 필요할 때는 새 Ubuntu VM을 별도로 만들어 이 문서의 템플릿과 provisioning을 그대로 적용한 뒤 `certbot` staging 또는 새 도메인 테스트, Tailscale enrollment, SSH key 로그인, Fail2ban ban/unban, 재부팅 후 모든 systemd 서비스/cron/timer를 확인한다. 그 단계가 끝나기 전에는 이번 결과를 “전체 서버 DR 완전 성공”으로 표현하지 않는다.

`secrets.tar.gz`가 암호화 저장이 아니라는 기존 제한도 그대로 남는다. 이번 훈련은 비밀정보 보관 방식 자체를 개선하지 않았다.
