# Bloguito 호스트 구성 재해복구 훈련 — 2026-09-26

## 범위

운영 서비스에는 쓰지 않았다. 운영 호스트는 Tailscale SSH로 상태와 설정 해시만 읽었고, 실제 구성 복구 검증은 로컬 Docker의 일회성 Ubuntu 24.04 컨테이너에서 수행했다. 저장소는 컨테이너에 읽기 전용으로 마운트했다.

이 훈련은 2026-09-25의 WordPress 데이터/애플리케이션 격리 복원 훈련을 호스트 구성 영역으로 확장한다. 실제 새 VM의 DNS 전환, Let's Encrypt 실인증서 발급, Tailscale 재등록, OCI 네트워크 규칙 변경은 수행하지 않았다.

## 운영 호스트 읽기 전용 대조

2026-09-26 관측값:

- 호스트: `wordpress-blog`, Linux `6.17.0-1020-oracle`, x86_64.
- Docker `29.8.1`, Docker Compose `v5.5.1`, WP-CLI `2.12.0`.
- Nginx, Fail2ban, SSH, Docker, Tailscale, `bloguito-ssh-private-only.service`는 모두 active.
- `nginx -t` 성공.
- SSH 유효 설정은 저장소 hardening 값과 일치: root 로그인/비밀번호/KbdInteractive/X11 비활성화, `MaxAuthTries 4`, `LoginGraceTime 30`, `AllowUsers ubuntu`.
- Fail2ban `sshd` jail은 동작 중이며 조회 시 누적 ban 기록이 존재했다.
- INPUT 체인에는 `tailscale0` 이외 인터페이스에서 신규 TCP/22를 drop하는 규칙이 존재했다.
- Let’s Encrypt `lifeinfo24.org`, `www.lifeinfo24.org` 인증서는 유효하며 당시 만료 예정은 2026-12-14 10:32:07 UTC였다.
- `wp-cli.phar` SHA-256은 `ce34ddd838f7351d6759068d09793f26755463b4a4610a5a5c0a97b68220d85c`; 저장소 provisioner의 고정값과 일치한다.
- 운영의 Nginx vhost, SSH hardening drop-in, private-SSH systemd unit, Fail2ban jail, WP-CLI provisioner는 저장소 파일과 SHA-256이 일치했다.

운영 Compose는 현재 로컬 작업본과 동일하지 않았다. 운영 WordPress 컨테이너는 digest `sha256:5a93c470ae8220fddf71f6ebe3bc94e615ddc2ae4d9810f795b830fb11c41a17`을 사용하고, 로컬 `wordpress/docker-compose.yml`은 별도 격리 복구 검증을 거친 `sha256:8ae73d594a154e30b112e8d085afbc0895acf7651d8f53ef63aefb42e30822d5`를 가리킨다. 따라서 현 시점 DR에서 “현재 운영 그대로 재현”과 “차기 검증 구성으로 재구축”은 구분해야 한다.

## 격리 검증

`scripts/host_dr_config_drill.sh`는 일회성 Ubuntu 24.04 컨테이너에서 다음을 검증한다.

1. 저장소 Nginx vhost를 임시 self-signed TLS 파일과 함께 설치하고 `nginx -t` 실행.
2. SSH drop-in 설치 후 `sshd -t` 실행.
3. Fail2ban jail 설치 후 `fail2ban-client -t` 실행.
4. private-SSH systemd unit 설치 후 `systemd-analyze verify` 실행. 이 unit은 격리 환경에서 시작하지 않는다.
5. `provision-wp-cli.sh`가 공식 WP-CLI 2.12.0 PHAR를 내려받아 고정 SHA-256과 일치시키는지 확인.
6. 같은 destination의 두 번째 실행이 검증된 파일을 재사용하는지 확인.
7. 체크섬이 다른 다운로드를 주입했을 때 기존 destination을 보존하고 실패하는지 확인.

2026-09-26 실행 결과는 `HOST_DR_ISOLATED_CONFIG_OK`였다. Nginx, OpenSSH, Fail2ban, systemd unit 정적 검증과 WP-CLI 실제 다운로드/고정 체크섬 검증을 모두 통과했다.

## 새 호스트 복구 순서와 현재 경계

새 호스트에서 `bloguito-ssh-private-only.service`를 Tailscale 등록보다 먼저 enable/start하면 `tailscale0`이 준비되지 않은 상태에서 공개 TCP/22를 차단해 원격 접근을 잃을 수 있다. 복구 순서는 OS/Docker 준비 → Tailscale 설치·tailnet 등록 및 새 세션 확인 → SSH hardening 적용 → private-SSH unit 적용 순서를 지켜야 한다.

Nginx vhost는 `/etc/letsencrypt/live/lifeinfo24.org/*`, `options-ssl-nginx.conf`, `ssl-dhparams.pem`이 이미 존재한다고 가정한다. 격리 훈련은 가짜 TLS 파일로 문법만 검사했다. 실제 새 VM에서는 DNS/80·443 도달성 확보 후 새 인증서를 발급하거나 별도 보호된 인증서 복구 절차를 사용한 뒤 vhost를 활성화해야 한다.

현재 저장소만으로 완전히 자동 재현되지 않는 호스트 요소는 다음과 같다.

- Ubuntu 기본 설치와 Docker/Tailscale/Nginx/Certbot/Fail2ban 패키지 저장소·설치 단계.
- Tailscale 장치 등록/ACL과 복구용 인증 정보. 비밀정보를 Git에 넣지 않는 별도 bootstrap이 필요하다.
- Let's Encrypt 실제 인증서 발급/갱신 bootstrap과 계정 상태.
- OCI NSG/VCN 규칙, DNS 레코드처럼 호스트 밖의 인프라.
- `rpcbind` 비활성화 등 운영 호스트에서 적용된 일부 OS hardening 상태.
- 운영 Compose와 현재 로컬 검증 Compose의 digest 차이를 어느 시점에 승격할지에 대한 배포 결정.

따라서 이번 결과는 **호스트 구성 자산의 복구 가능성과 정적 유효성, WP-CLI 재프로비저닝 경로를 격리 환경에서 검증한 것**이다. 완전한 새 VM 재해복구 성공 판정은 별도 disposable VM에서 Tailscale 등록, 실제 TLS 발급, Docker/Compose 기동, v3 데이터 복원, 외부 80/443 확인까지 수행한 뒤 내려야 한다.
