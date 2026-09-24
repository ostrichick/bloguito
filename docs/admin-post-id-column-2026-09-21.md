# 관리자 글 목록 ID 열 추가 — 2026-09-21

- 요청: WordPress 관리자 **글 → 모든 글** 목록에 각 글의 데이터베이스 ID를 표시한다.
- 구현: `wordpress/mu-plugins/bloguito-post-id-column.php`를 별도 MU 플러그인으로 추가한다. `manage_post_posts_columns`에서 제목 다음에 `글 ID` 열을 배치하고 `manage_post_posts_custom_column`에서 번호를 출력한다. 페이지·다른 유형·공개 화면·글 데이터에는 변경이 없다.
- 검증: `wordpress/tests/post-id-column-test.php`는 후크 등록, 배치, 실제 ID 출력 및 다른 열 미변경을 검사한다. 서버의 WordPress PHP 8.3.33 CLI로 플러그인·단위 테스트·실서비스 확인 스크립트를 `php -l` 검사하고 단위 테스트를 실행하여 `PASS: post ID column tests`를 확인했다. 실제 WP-CLI에서 읽기 전용 `wordpress/tests/wp-post-id-column-smoke.php`를 실행하여 `PASS: live WordPress post column hook and ID rendering`을 확인했다. 인증된 브라우저 화면은 직접 열지 않았다.
- 배포: 기존 `bloguito-social-share.php`는 수정하지 않았다. 운영 컨테이너의 `wp-content/mu-plugins/bloguito-post-id-column.php`가 없음을 확인한 뒤 새 단일 파일만 복사했다. 서버 SHA256 `6e3c383122341d37c0a1921a4c0cc62bf1d82b964775e52b459f2d478d6d47cd`와 로컬 파일 해시가 일치하며 PHP 문법 오류가 없다. 서비스·컨테이너 재시작, DB·글 편집·공개 상태 변경은 실행하지 않았다.
- 되돌리기: 해당 MU 플러그인 파일 하나를 제외하면 기존 열 구성으로 돌아간다. 인증정보·데이터베이스·WordPress Compose나 기존 공유 플러그인을 변경할 필요가 없다. 테스트용 `/tmp/bloguito-postid-20260921` 파일은 운영 플러그인 디렉터리 바깥에 있다.

## 2026-09-24 상단 관리자 바 확장

- 요청: 로그인한 편집 가능 사용자가 공개 글을 읽을 때 WordPress 상단 관리자 바에서 현재 글 ID를 바로 확인한다.
- 구현: 같은 `bloguito-post-id-column.php`에 `admin_bar_menu` 훅을 추가했다. 프런트의 개별 `post` 화면이고 현재 글을 `edit_post` 할 권한이 있을 때만 `글 ID: <번호>`를 링크 없는 표시 항목으로 추가한다. 관리자 화면, 홈페이지·카테고리 등 비개별 글 화면, 편집 권한이 없는 사용자에게는 추가하지 않는다. 기존 WordPress `글 편집` 메뉴와 permalink 동작은 변경하지 않는다.
- 검증: 운영과 같은 WordPress PHP 8.3.33 컨테이너의 격리 `/tmp`에서 플러그인·테스트 PHP 문법 검사와 `post-id-column-test.php` 회귀 테스트를 통과했다. 운영 반영 후 `wp eval-file`을 관리자 사용자와 실제 공개 글 쿼리로 실행해 ID 열 훅과 관리자 바 항목 생성이 모두 통과했다. 비로그인 공개 페이지는 HTTP 200이며 `bloguito-post-id`/`글 ID:`가 HTML에 노출되지 않음을 확인했다. 인증된 브라우저 DOM 직접 검사는 이번 세션에서 원격 디버깅 탭이 없어 수행하지 않았다.
- 배포: 교체 직전 운영본 SHA256은 기존 기록과 같은 `6e3c383122341d37c0a1921a4c0cc62bf1d82b964775e52b459f2d478d6d47cd`, 새 운영본은 로컬과 동일한 `ec7f0ecf0d97acb46bedf5e9ce156a85ab30d189ae9105d018b7665999977ec0`이다. 기존 파일은 서버 `/home/ubuntu/bloguito-post-id-column.php.pre-adminbar-20260924`에 롤백용으로 보존했다. DB·글 본문·테마·다른 플러그인·서비스 재시작은 변경하지 않았다.

## 2026-09-24 글 목록 마지막 수정 열

- 요청: 이미 발행한 글도 **글 → 모든 글** 목록에서 최초 발행일과 별도로 마지막 업데이트 시각을 확인하고, 오래 수정하지 않은 글을 찾을 수 있도록 정렬한다.
- 구현: 같은 MU 플러그인에서 기본 `날짜` 열 바로 뒤에 `마지막 수정` 열을 추가한다. 값은 WordPress의 `post_modified`를 사이트 현지 시각으로 `YYYY/MM/DD HH:MM` 형식으로 출력하므로 공개·임시 상태 모두 동일 기준을 사용한다. `manage_edit-post_sortable_columns`에서 이 열을 코어 `modified` 정렬 키에 연결해 헤더 클릭으로 오름차순·내림차순 정렬할 수 있게 한다.
- 검증: 운영과 같은 WordPress PHP 8.3 컨테이너의 격리 `/tmp`에서 플러그인과 테스트 PHP 문법 검사를 통과했고 `post-id-column-test.php`가 `PASS: post ID column tests`로 종료했다. 운영 반영 후 실제 WordPress에서 열 순서, `modified` 정렬 키, #220의 표시값 `2026/09/24 13:20`, 공개·임시글을 섞은 최근/오래된 수정순 쿼리를 모두 확인해 `PASS: live modified column, rendering and sorting`을 얻었다. 공개 QA 시작 URL은 HTTP 200을 유지했다.
- 배포: 교체 직전 운영본 SHA256 `ec7f0ecf0d97acb46bedf5e9ce156a85ab30d189ae9105d018b7665999977ec0`을 조건으로 확인하고 `/home/ubuntu/bloguito-post-id-column.php.pre-lastmodified-20260924`에 동일 바이트 롤백본을 보존한 뒤 MU 파일 하나만 원자적으로 교체했다. 새 운영본 SHA256은 `0434796948252accf3136787b1ad01e15bd3f02a0609db3e76fb9b6e91885158`이다. DB·글 본문·공개 상태·테마·다른 플러그인·서비스 재시작은 변경하지 않았다.
