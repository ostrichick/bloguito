# Webmaster and monitoring tools — 2026-09-29

- **Bing Webmaster Tools**: `https://lifeinfo24.org/`를 수동 등록하고 HTML meta 방식으로 소유권 검증을 완료했다. 검증 태그는 테마 파일 대신 `wordpress/mu-plugins/bloguito-webmaster-verification.php`에서 홈페이지에만 출력한다.
- Bing에 `https://lifeinfo24.org/sitemap_index.xml`을 제출했다. 제출 직후 상태는 `Processing`, sitemap 오류·경고는 각각 0이었다. Rank Math의 기존 IndexNow 설정은 그대로 유지한다.
- **UptimeRobot**: 공식 agent setup flow로 무료 계정과 `lifeinfo24.org` HTTP 모니터를 생성·활성화했다. 무료 플랜의 5분 간격 모니터이며, 첫 확인 뒤 상태 `Up`, uptime 100%, incident 0을 확인했다.
- **Ahrefs Free**: 이메일 가입 및 계정 활성화 메일까지 완료했다. Ahrefs 앱 진입 시 Cloudflare 사람 확인이 표시되어 자동화로 우회하지 않았다. 사람 확인 완료 뒤 사이트 프로젝트 등록·소유권 검증·Site Audit 설정을 이어서 완료한다.
- 인증 토큰, 계정 이메일, 활성화 URL 같은 개인/일회성 자격정보는 저장소 문서에 기록하지 않는다.
