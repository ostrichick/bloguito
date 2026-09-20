# 관리자 글 목록 ID 열 추가 — 2026-09-21

- 요청: WordPress 관리자 **글 → 모든 글** 목록에 각 글의 데이터베이스 ID를 표시한다.
- 구현: `wordpress/mu-plugins/bloguito-post-id-column.php`를 별도 MU 플러그인으로 추가한다. `manage_post_posts_columns`에서 제목 다음에 `글 ID` 열을 배치하고 `manage_post_posts_custom_column`에서 번호를 출력한다. 페이지·다른 유형·공개 화면·글 데이터에는 변경이 없다.
- 검증: `wordpress/tests/post-id-column-test.php`는 후크 등록, 배치, 실제 ID 출력 및 다른 열 미변경을 검사한다. 서버의 WordPress PHP 8.3.33 CLI로 플러그인·단위 테스트·실서비스 확인 스크립트를 `php -l` 검사하고 단위 테스트를 실행하여 `PASS: post ID column tests`를 확인했다. 실제 WP-CLI에서 읽기 전용 `wordpress/tests/wp-post-id-column-smoke.php`를 실행하여 `PASS: live WordPress post column hook and ID rendering`을 확인했다. 인증된 브라우저 화면은 직접 열지 않았다.
- 배포: 기존 `bloguito-social-share.php`는 수정하지 않았다. 운영 컨테이너의 `wp-content/mu-plugins/bloguito-post-id-column.php`가 없음을 확인한 뒤 새 단일 파일만 복사했다. 서버 SHA256 `6e3c383122341d37c0a1921a4c0cc62bf1d82b964775e52b459f2d478d6d47cd`와 로컬 파일 해시가 일치하며 PHP 문법 오류가 없다. 서비스·컨테이너 재시작, DB·글 편집·공개 상태 변경은 실행하지 않았다.
- 되돌리기: 해당 MU 플러그인 파일 하나를 제외하면 기존 열 구성으로 돌아간다. 인증정보·데이터베이스·WordPress Compose나 기존 공유 플러그인을 변경할 필요가 없다. 테스트용 `/tmp/bloguito-postid-20260921` 파일은 운영 플러그인 디렉터리 바깥에 있다.
