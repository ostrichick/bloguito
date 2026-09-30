# 신규 글 URL 정책 — 2026-09-30

- 사용자 결정: 신규 WordPress 글의 정식 URL은 `/{post_id}/{short-slug}/` 형식으로 사용한다.
- 기존 공개 글은 이번 작업에서 URL을 바꾸지 않는다. 마이그레이션과 301 리디렉션은 별도 작업으로 남긴다.
- 전역 WordPress permalink 구조 `/%postname%/`는 유지한다. 신규 publisher가 짧은 영문 slug를 명시하고 `_bloguito_permalink_scheme=id-slug-v1` 메타를 저장한 글만 MU 플러그인이 새 URL을 반환한다.
- `short-slug`는 영문 소문자, 숫자, 하이픈만 허용하며 의미어 1~5개, 최대 60자로 제한한다. 숫자만 있는 값, 한글, 대문자, 임의 구분자는 거부한다.
- 운영 WordPress에 `bloguito-new-post-permalinks` MU 플러그인 1.0.0을 설치하고 rewrite rule을 flush했다. 전역 permalink 구조는 계속 `/%postname%/`다.
- 운영 자동화 `/home/ubuntu/agent-publisher`에는 서버의 기존 코드 버전을 보존한 채 slug schema/prompt, slug 검증, `post_name` 저장, permalink scheme 메타 설정만 최소 패치했다. 교체 전 원본은 `/home/ubuntu/agent-publisher/data/editorial_runs/permalink-id-slug-20260930T200905`에 백업했다.
- 운영 확인에서 기존 공개 #610은 `https://lifeinfo24.org/national-pension-estimate-check/`, #648은 `https://lifeinfo24.org/busan-october-festivals-2026/`를 그대로 반환했고 #610 기존 URL은 HTTP 200이었다. 기존 글에는 신규 scheme 메타를 소급 설정하지 않았다.
- 로컬 공통 회귀는 742개 통과, 1개 skip이었다. 운영 PHP 8.3에서 MU 플러그인 문법 검사와 독립 permalink 회귀 테스트를 통과했고, 서버 자동화에서 안전 slug 허용 및 숫자-only, 대문자, 한글, 6단어 slug 거부를 확인했다.
