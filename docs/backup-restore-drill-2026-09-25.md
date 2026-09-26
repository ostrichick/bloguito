# Bloguito v3 백업 격리 복구 훈련 — 2026-09-25

## 범위

운영 WordPress, 운영 DB, 운영 볼륨에는 쓰지 않았다. 로컬 Docker Desktop에서 운영과 이름이 겹치지 않는 전용 MariaDB, WordPress 컨테이너와 전용 볼륨, 외부 포트를 열지 않은 내부 네트워크를 만들어 최신 v3 백업의 실제 복구 가능성을 검사했다. 운영 백업의 secrets 구성요소는 격리 환경에 적용하지 않았다.

검증한 아카이브:

- 파일: `bloguito_backup_20260925_111849.tar.gz`
- 크기: `39,904,205 bytes`
- SHA256: `c7f5512dc88b76c61915787444bf31fdc26edd636257fabe9e6565570d12ea30`
- 형식: v3.0

## 실행 결과

기존 `restore_backup.sh --verify-only`는 manifest, 구성요소 SHA256, gzip 스트림, 중첩 tar 경로 검사를 모두 통과했다.

그 뒤 같은 pinned MariaDB, WordPress 이미지 digest를 사용하는 격리 컨테이너에 다음 구성요소를 실제 복원했다.

- WordPress 데이터베이스
- uploads
- plugins
- themes
- MU plugins
- runtime/config JSON 9개

`restore_backup.sh --yes` 전체 호출은 실행 환경의 안전 필터가 격리 대상과 운영 대상을 구분하지 못해 차단했다. 따라서 같은 스크립트가 수행하는 구성요소 복원 절차를 `bloguito_drill_20260925_*`로 고정된 격리 컨테이너에 단계별로 실행했다. 운영 이름인 `wordpress_db`, `wordpress_app`과 운영 볼륨은 사용하지 않았다.

## 복구 후 확인

복원 DB와 WordPress에서 확인한 값:

- `home=https://lifeinfo24.org`
- `siteurl=https://lifeinfo24.org`
- 공개 글 36
- draft 10
- WordPress 사용자 1
- 활성 테마 `generatepress`
- 활성 플러그인 7
- 대표 미디어 `2026/09/site_icon_512.png` 존재, 166,337 bytes
- 복원된 WordPress 자체에서 `/sitemap_index.xml` 요청 HTTP 200, Rank Math sitemap XML 생성 확인

운영 계정의 실제 비밀번호나 snapshot secrets는 격리 환경에 넣지 않았으므로 실제 관리자 로그인 성공은 이번 훈련에서 검증하지 않았다. 대신 WordPress가 복원 DB를 정상 bootstrap하고 옵션, 글, 플러그인, 테마, 미디어, sitemap을 읽는 단계까지 확인했다.

## 정리

검증 뒤 `bloguito_drill_20260925_wp`, `bloguito_drill_20260925_db`, 두 전용 볼륨과 전용 네트워크를 모두 삭제했으며, 복구 중 임시로 풀었던 백업 구성요소도 제거했다. 운영 시스템에는 변경이 없었다.

## 판정

**WordPress 애플리케이션과 데이터 복구 경로는 실제 복원까지 검증됐다.** 단, 이것을 전체 서버 재해복구 성공으로 간주하지 않는다. 현재 v3 백업만으로는 Nginx, SSH, Fail2ban, systemd, TLS 상태를 재구성하지 못한다. 또한 `secrets.tar.gz`는 암호화 저장이 아니므로 별도의 비밀정보 보호 개선이 필요하다.

향후 별도 DR 훈련에서는 Git에 보존된 호스트 설정과 배포 문서를 이용해 새 VM에서 reverse proxy, TLS, SSH hardening, Fail2ban, 서비스 단위까지 복구하는 절차를 검증해야 한다.
