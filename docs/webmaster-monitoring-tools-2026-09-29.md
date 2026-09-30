# Webmaster and monitoring tools — 2026-09-29

- **Bing Webmaster Tools**: `https://lifeinfo24.org/`를 수동 등록하고 HTML meta 방식으로 소유권 검증을 완료했다. 검증 태그는 테마 파일 대신 `wordpress/mu-plugins/bloguito-webmaster-verification.php`에서 홈페이지에만 출력한다.
- Bing에 `https://lifeinfo24.org/sitemap_index.xml`을 제출했다. 제출 직후 상태는 `Processing`, sitemap 오류·경고는 각각 0이었다. Rank Math의 기존 IndexNow 설정은 그대로 유지한다.
- **UptimeRobot**: 공식 agent setup flow로 무료 계정과 `lifeinfo24.org` HTTP 모니터를 생성·활성화했다. 무료 플랜의 5분 간격 모니터이며, 첫 확인 뒤 상태 `Up`, uptime 100%, incident 0을 확인했다.
- **Ahrefs Free**: 기존 로그인된 Chrome 세션에서 `Lifeinfo24` 프로젝트가 이미 생성·검증되어 있음을 확인했다. Site Audit 초기 크롤링도 완료되어 Health Score 98, 내부 URL 93개, 오류 URL 3개 상태를 확인했다. 동일 이름 프로젝트가 2개 표시되므로 삭제 전에는 별도 검토가 필요하다.
- 인증 토큰, 계정 이메일, 활성화 URL 같은 개인/일회성 자격정보는 저장소 문서에 기록하지 않는다.

## 2026-09-30 장애 수정

- `bloguito-webmaster-verification.php`가 UTF-8 BOM(`EF BB BF`)으로 저장되어 PHP가 헤더보다 먼저 3바이트를 출력했다. 이 때문에 WordPress의 관리자 인증 리다이렉트와 쿠키 헤더가 `headers already sent` 경고와 함께 실패했다.
- MU 플러그인의 BOM만 제거해 복구했다. 서버에서 PHP 문법 오류 없음, 비인증 `/wp-admin/` 요청의 WordPress 리다이렉트 복구, 홈페이지의 `msvalidate.01` 태그 유지, 수정 이후 같은 파일을 원인으로 한 새 header 경고가 발생하지 않는 것을 확인했다.
