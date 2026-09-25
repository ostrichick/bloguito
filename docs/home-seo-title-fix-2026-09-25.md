# 홈페이지 SEO/OG 제목 단축 — 2026-09-25

## 요청과 원인

- 네이버 서치어드바이저 실시간 사이트 진단에서 `사이트 제목`, `Open Graph 제목`이 모두 40자 초과 경고로 표시됐다.
- 운영 HTML의 `<title>`과 `og:title`은 모두 `생활정보 24 | 정부 지원금, 절세, 복지 생활 백과 - 놓치기 쉬운 정부 지원금, 숨은 국세환급금, 복지 혜택, 공연 예매 및 생활 세금 정보를 공식 고시 기준으로 빠르고 정확하게 전해드립니다.`로 출력되고 있었다.
- Rank Math `rank-math-options-titles`의 `homepage_title`이 `%sitename% %page% %sep% %sitedesc%`여서 WordPress `blogname`과 `blogdescription`이 한 제목에 합쳐지는 것이 원인이었다.
- `homepage_facebook_title`은 기존 옵션 배열에 없었고 Rank Math가 홈페이지 SEO 제목을 Open Graph 제목에도 사용하고 있었다.

## 변경

- WordPress 사이트명(`blogname`)과 사이트 설명(`blogdescription`) 자체는 변경하지 않았다.
- Rank Math 홈페이지 전용 SEO 제목을 다음 29자 문구로 변경했다.
  - `생활정보 24 | 정부지원금, 복지, 절세, 생활정보`
- Rank Math `homepage_facebook_title`도 같은 문구로 새로 추가했다.
- `homepage_description`은 변경하지 않았고, 공개 HTML의 기존 meta description / Open Graph description도 그대로 유지했다.
- 개별 글 제목 템플릿(`pt_post_title`)과 개별 글 메타는 변경하지 않았다.

## 백업과 캐시

- 변경 전 `rank-math-options-titles` 전체 JSON을 서버 `/home/ubuntu/rank-math-options-titles.pre-home-title-20260925.json`에 저장했다.
- 백업 SHA256: `769fd9f7f61c636776e9ebea82283cb6f9094cfd5efdf6de107703b634cbb3ae`.
- Rank Math 옵션 변경 직후 캐시 우회 URL에서는 새 제목이 확인됐지만 일반 홈페이지는 기존 WP Super Cache HTML을 반환했다.
- `/var/www/html/wp-content/cache/supercache/lifeinfo24.org/`의 홈페이지 루트 캐시 파일 5개만 삭제해 재생성시켰다. 다른 게시글 캐시는 건드리지 않았다.

## 최종 검증

- 일반 `https://lifeinfo24.org/`에서 HTTP 200을 확인했다.
- `<title>`: `생활정보 24 | 정부지원금, 복지, 절세, 생활정보`.
- `og:title`: `생활정보 24 | 정부지원금, 복지, 절세, 생활정보`.
- `meta description`: 기존 `놓치기 쉬운 정부 지원금, 숨은 국세환급금, 복지 혜택, 공연 예매 및 생활 세금 정보를 공식 고시 기준으로 빠르고 정확하게 전해드립니다.` 유지.
- `og:description`: 같은 기존 설명 유지.
- WordPress `blogname`은 `생활정보 24 | 정부 지원금, 절세, 복지 생활 백과`, `blogdescription`은 기존 설명문 그대로 유지된다.
- 대표 개별 글 #241을 별도로 확인해 기존 개별 글 SEO/OG 제목 형식이 그대로임을 확인했다.

## 롤백

문제가 생기면 백업 JSON의 `homepage_title` 값을 되돌리고 새로 추가한 `homepage_facebook_title` 키를 제거한 뒤 홈페이지 캐시만 다시 비우면 된다.
