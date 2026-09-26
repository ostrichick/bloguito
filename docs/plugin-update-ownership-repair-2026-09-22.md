# WordPress 플러그인 업데이트 실패 복구 — 2026-09-22

## 증상과 실제 원인

- 사용자 화면: `Site Kit by Google` 1.188.0 설치 중 "일부 파일이 복사가 안돼 업데이트가 설치되지 않았습니다"라고 표시, `includes/Modules/...` 등 다수 파일이 복사 실패. 두 플러그인 중 1/2 업데이트 화면에서 중단.
- 21:47~21:49 KST 운영 서버에서 직접 확인: `/var/www/html/wp-content/plugins`와 `wp-content/upgrade`는 `www-data:www-data`/755, `google-site-kit`과 `wp-statistics` 하위 폴더는 `root:root`/755. 컨테이너 웹 실행 계정 `www-data`의 Site Kit 디렉터리 쓰기 검사 실패(종료 1), 상위 plugins 쓰기 검사 성공(종료 0). 디스크 45GB 중 35GB 여유, inode 3% 사용. 따라서 **기존 플러그인 파일을 웹 계정이 교체할 수 없는 소유권 불일치**가 관측된 파일 복사 실패의 직접 원인이다. 소유권이 이렇게 된 과거 경위는 확인하지 않았다.
- 업데이트 전 WP-CLI 현황: Site Kit `1.187.0` → `1.188.0` 업데이트 가능, WP Statistics `14.16.13` → `14.16.14` 가능; 둘 다 활성. 두 기존 플러그인 `wp plugin verify-checksums` **2/2 통과**. `.maintenance`와 두 이름의 개별 업그레이드 임시 폴더는 존재하지 않았다.
- 동일한 `root:root`/755 폴더가 `insert-headers-and-footers`, `luckywp-table-of-contents`(비활성), `wps-hide-login`에도 있었다. 나머지 두 일반 플러그인은 기존부터 `www-data` 소유였다.

## 백업과 실행

1. 실행 전 운영 백업·복구 스크립트 SHA256이 기존 검증 기록과 같음을 확인: `backup_daily.sh=d2f84fbc0152e39c08491b503547757df398d91a579d714fd0cc221593c6bba9`, `restore_backup.sh=4ca62cee29145eacbeb48b839ad580068880ec18696e8f6c1e96b6780ed2dd09`.
2. 21:49:49~21:50:12 KST 별도 디렉터리 `/home/ubuntu/backups/plugin-update-20260922-2149/`에 **업데이트 직전 독립 v3 전체 스냅샷** 생성: `bloguito_backup_20260922_214949.tar.gz`, 약 35MB, SHA256 `53384668d7fbfb015182325942abd64a6fade3f2b337dd77e1a6cb42dfc74794`. 운영 `restore_backup.sh <archive> --verify-only` 종료 0: `version=3.0`, 구성요소 해시·gzip·중첩 경로 정상. 실제 복원은 수행하지 않았다. 백업은 DB·업로드·플러그인/테마/MU·구성·암호화되지 않은 별도 비밀 아카이브를 포함하므로 접근을 제한하고 Git에 넣지 않는다.
3. 컨테이너에서 **대상 두 경로만** `chown -R www-data:www-data` 적용. 각 경로에 대한 `docker exec -u www-data ... test -w` 종료 0 확인; 디렉터리 모드 755 유지. `www-data` 계정의 `wp plugin update google-site-kit --path=/var/www/html` 실행이 `1.187.0 → 1.188.0`, `Updated`, 종료 0. 이어 `wp plugin update wp-statistics`가 `14.16.13 → 14.16.14`, `Updated`, 종료 0. 두 실행 모두 유지 관리 모드를 자체 해제했다.
4. 나중에 같은 증상이 발생하지 않도록 **기존에 root 소유였던 다른 일반 플러그인 세 경로만** `chown -R www-data:www-data`: `insert-headers-and-footers`, `luckywp-table-of-contents`, `wps-hide-login`. 설치 콘텐츠·활성 상태는 이 단계에서 변경하지 않았다. 상위 WordPress·DB·업로드·MU·서버 서비스에는 소유권 변경을 적용하지 않았으며 전역 `chmod 777`은 사용하지 않았다.

## 21:53 KST 실제 검증

- `wp plugin list`: Site Kit `1.188.0`, WP Statistics `14.16.14`, 둘 다 `active`, 둘 다 업데이트 표시 `none`. 다른 일반 플러그인 활성 상태도 사전과 동일하며 LuckyWP는 `inactive`.
- 새 버전 두 플러그인 공식 체크섬 **2/2 통과**. 7개 일반 플러그인 최상위 디렉터리 전부 `www-data:www-data`/755. 업데이트 대상 두 디렉터리 내부에서 소유자가 `www-data`가 아닌 파일 탐색 결과 0. WPS Hide Login 폴더에 대한 웹 계정 쓰기 검사 통과.
- `/var/www/html/.maintenance` 부재. 공개 QA UTM 홈 `https://lifeinfo24.org/?utm_source=bloguito_qa_agent&utm_medium=internal_test&utm_campaign=site_checks` 최종 HTTP **200**, 글 `?p=218` 리디렉션 뒤 HTTP **200**. 최근 6분 WordPress 컨테이너 로그에서 `PHP Fatal`, `PHP Warning`, `Uncaught`, `Permission denied`에 해당하는 줄은 검색 결과 없음. 이는 전체 기능·로그의 장기 검사를 뜻하지 않는다.
- WP-CLI 실행 시 `/var/www/.wp-cli/cache/` 생성 권한 경고가 출력됐으나 각 명령은 정상 종료했고 두 공식 버전·체크섬도 확인했다. 해당 캐시 경고를 해결하기 위해 전역 경로의 권한은 변경하지 않았다.
- Google 계정 연결 유지 여부, GA4 실제 데이터 수집 및 WP Statistics 대시보드의 로그인 상태 세부 화면은 이번 서버 CLI·HTTP 점검으로 확인하지 않았다. 기존 `docs/sitekit-and-editorial-handoff-2026-09-20.md`에 기록된 GA4 태그/개인정보처리방침 불일치도 이번 업데이트만으로 해결됐다고 보지 않는다.

## 복구 범위와 기록

- 이번 작업은 **실서비스 컨테이너의 플러그인 파일 소유권 수정 및 두 플러그인 정식 업데이트**를 실제 실행한 것이다. 로컬 저장소의 애플리케이션 코드·콘텐츠·DB는 수정하지 않았다. 여러 사람이 작업 중이던 기존 미커밋·미추적 파일도 그대로 보존했다. 이 신규 문서를 기록하고 기존 `docs/INDEX.md`에 안내 링크 한 줄을 추가했다. Git 커밋·푸시, 컨테이너 재생성·DB 복원은 수행하지 않았다.
- 추가 문제가 나타나면 위 독립 스냅샷과 현재 버전·사이트 상태를 먼저 대조한다. 전체 `restore_backup.sh --yes`는 DB·콘텐츠까지 바꾸므로 플러그인 하나의 문제를 되돌리기 위한 즉시 조치로 실행하지 않는다. 별도의 파일별 롤백 방안과 현재 파일 지문을 확인한 뒤 범위를 제한한다.
