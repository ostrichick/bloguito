# 신규 글 URL 정책 — 2026-09-30

- 사용자 결정: 신규 WordPress 글의 정식 URL은 `/{post_id}/{short-slug}/` 형식으로 사용한다.
- 기존 공개 글은 이번 작업에서 URL을 바꾸지 않는다. 마이그레이션과 301 리디렉션은 별도 작업으로 남긴다.
- 전역 WordPress permalink 구조 `/%postname%/`는 유지한다. 신규 publisher가 짧은 영문 slug를 명시하고 `_bloguito_permalink_scheme=id-slug-v1` 메타를 저장한 글만 MU 플러그인이 새 URL을 반환한다.
- `short-slug`는 영문 소문자, 숫자, 하이픈만 허용하며 의미어 1~5개, 최대 60자로 제한한다. 숫자만 있는 값, 한글, 대문자, 임의 구분자는 거부한다.
- MU 플러그인 설치 뒤 rewrite rule은 운영 서버에서 한 번 flush해야 한다. 플러그인 제거 및 해당 메타 미사용 시 기존 permalink 동작으로 되돌아간다.
