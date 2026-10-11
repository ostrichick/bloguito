# R2 WordPress MU 플러그인 호환성·격리 복원 점검 (2026-10-11)

## 관측 상태와 즉시 판정

**운영 배포는 보류**한다. 운영 WordPress 컨테이너의 MU 플러그인
`/var/www/html/wp-content/mu-plugins/bloguito-post-row-actions.php`의
SHA-256은 읽기 전용 `sudo docker exec wordpress_app sha256sum`으로
`a77b668fd1c12c137a54ed0a14e63c3056e060f0bb43848ed5e2823b602f867f`
이며 `php -l` 결과는 문법 오류 없음이다. 통합 commit `43909f3`의
별도 MU 소스 파일 SHA-256은
`d10d4b3bff10378f965b7e9db8d6d912c3ee99fdeb833136e0774939639794fa`.
두 파일은 불일치한다. 새 Python 릴리스 installer는 MU가 먼저 exact
digest 일치 상태가 되기 전 런타임 파일 쓰기를 차단하므로
현재 릴리스는 운영 설치 적합으로 표시할 수 없다.

읽기 전용으로 보존한 운영 MU와 tracked 새 MU를 줄 단위 비교하면
**차이는 정확히 한 줄**이다. `bloguito_validate_publishability()`의
`approval_kind` 허용 배열이 운영의
`['manual_user_selected', 'automated_visual_review']`에서 신규 코드의
`['manual_user_selected', 'manual_agent_delegated', 'automated_visual_review']`
로 확대되었다. 배포 전에 이 실측 차이를 다시 확인해야 한다.

운영 플러그인은 `manual_agent_delegated` 승인을 허용하지 않으며
신규 로컬 코드의 approval kind 계약과 일치하지 않는다.
**새 PHP의 승인 종류 허용과 SHA/ALT/제목/본문/첨부파일 검증 계약**은
`wordpress/tests/post-row-actions-test.php` 및
`wordpress/tests/real-db/mu_policy.php`가 테스트한다.
로그인한 관리자의 WordPress 직접 발행은 별도 수동 권한이며,
AI 자동화가 그 UI/권한으로 게이트를 우회하는 것은 허용하지 않는다.
영수증에 적힌 generator tool 이름은 실제 ChatGPT 이미지 생성 호출의
암호학적 증명이 아니다. stage receipt의 candidate/actor/SHA 계약을
실제 호스트 호출 로그와 함께 검토해야 한다.

## 수행한 순수 읽기·격리 훈련

- 운영 컨테이너의 **현재 MU 바이트만** SSH 표준출력으로 읽어
  `scratch/tasks/live-qa-641/live-mu-readonly-copy.php.bin`에 저장했다.
  다운로드 바이트의 SHA가 서버 읽기 전용 `sha256sum`과 일치하며
  크기는 20,461바이트다. 서버 백업·컨테이너·WordPress DB에는 쓰기를
  실행하지 않았다.
- `scripts/ops/mu_rollout_disposable_drill.py`를 기존 바이트 사본과
  tracked 신규 MU를 입력으로 **격리 임시 디렉터리**에서 실행했다.
  원본 SHA 확인→원본 복사/백업 SHA 확인→staged 후보 SHA 확인→
  동일 파일시스템 임시 파일의 원자 교체→교체본 readback SHA 확인→
  정확한 백업 바이트 복원→복원 SHA 확인을 성공했다.
- `--inject-failure`로 파일 교체 직후 오류를 삽입해
  원래 바이트의 복원 SHA를 다시 확인했다. 입력 파일 둘은 변경하지 않는다.
  이 훈련은 **운영 MU 교체, PHP-FPM/OPcache 반영, WordPress DB transaction,
  hook 실행, 관리자 메뉴 권한 검증**을 재현한 것이 아니다.
- Windows 노트북에는 PHP CLI가 탐지되지 않아 로컬 신규 MU `php -l`
  실행은 이번 훈련 범위에 없다. 운영 컨테이너의 **기존** MU 문법 검사만
  읽기 전용으로 통과했으며 신규 후보의 실제 WP 부팅/DB와 PHP 문법은
  격리 Linux CI 실행 결과를 별도로 확인해야 한다.

재현 가능한 격리 훈련(원본 사본과 local MU 경로에 접근 가능할 때):

```powershell
python scripts/ops/mu_rollout_disposable_drill.py `
  --original scratch/tasks/live-qa-641/live-mu-readonly-copy.php.bin `
  --staged wordpress/mu-plugins/bloguito-post-row-actions.php `
  --expected-original-sha a77b668fd1c12c137a54ed0a14e63c3056e060f0bb43848ed5e2823b602f867f `
  --expected-staged-sha d10d4b3bff10378f965b7e9db8d6d912c3ee99fdeb833136e0774939639794fa
# 동일 명령에 --inject-failure 추가: 교체 직후 복원 훈련
```

이 명령은 WordPress/SSH를 호출하지 않는다. 두 expected digest를 현재
운영 readback과 **검증된 release manifest**에서 각각 가져와야 한다.
Git tracked 파일을 마음대로 다시 봉인해 새로운 source 승인을 만들지 않는다.

## 향후 별도 승인된 운영 롤아웃 순서

1. 새 clean Git HEAD에서 immutable release archive와 manifest를 생성하고
   `verify_release_manifest` 및 새 MU source SHA를 검증한다.
   현행 Git 단계의 digest는 향후 commit마다 재확인한다.
2. WordPress DB·uploads·전체 컨테이너 구성·실제 MU 파일과 소유권/권한을
   **별개로 백업**하고 백업 SHA 및 복구 가능한 격리 환경을 확인한다.
   위의 `.bin` 사본 한 개가 전체 사이트 백업을 대체하지 않는다.
   동시에 자동 생성/수정 writer·cron과 운영 변경 창을 관리한다.
3. 동일한 후보 MU 파일을 실제 운영 MU autoload 경로의 **`.php`로 끝나지
   않는 비활성 이름**에 stage한다. 정확한 원본 live SHA가 그때도
   사전 관측값과 일치하는지 다시 확인하고, 새 후보 SHA·`php -l`·
   소유권/권한·백업 원본 SHA가 하나라도 불일치하면 교체 전에 중단한다.
   임시 `*.php` 파일을 MU 디렉터리에 남겨 WordPress가 이중 로드하지 않는다.
4. 같은 파일시스템에서 검증된 staged 후보를 원자 교체하고 즉시 새 live
   SHA와 syntax/read-only WP bootstrap을 확인한다. 실패나 응답 유실이
   발생하면 재차 무작정 적용하지 말고 실제 live SHA·구성 상태부터
   다시 조회한다. 원본 MU 백업도 비활성 파일명으로 별도 보존한다.
5. 필요한 경우 정확한 원본 바이트를 임시 복원 파일에 준비하고
   같은 방식으로 원자 복원 후 old SHA를 readback한다.
   PHP 프로세스/OPcache에 반영된 실행 바이트 및 사이트 동작을 검증한다.
   복원 시 신규 Python 런타임과 오래된 MU가 섞이지 않게 이전 릴리스
   기준도 함께 맞춘다.
6. 신규 MU SHA가 manifest와 **실제 일치하고** 격리 WP+MariaDB 테스트,
   백업·복구 조건이 충족되었을 때만
   `python scripts/install_editorial_release.py <release> <app> --preflight-only`
   로 운영 **읽기 전용** 호환성 진단을 수행한다.
   설치·cron 조정·테스트용 공개 발행·미승인 글 업데이트는 별개 승인 사항이다.

이 문서는 복구 절차와 차단 기준이며 **운영 승인이나 배포 성공 증거가 아니다**.
