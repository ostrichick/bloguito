# 게시글 ID URL 정책 — 2026-09-30

- 최종 사용자 결정: 신규 WordPress 게시글의 정식 URL은 `/p/{post_id}/` 형식으로 사용한다. Post ID는 자릿수를 고정하지 않고 앞자리 0 없이 WordPress의 실제 양의 정수 ID를 그대로 사용한다.
- 영문 slug는 독자 URL에 노출하지 않는다. 신규 원고 스키마와 writer prompt에서도 URL용 slug 생성을 요구하지 않는다.
- WordPress 전역 permalink 구조 `/%postname%/`는 유지한다. `_bloguito_permalink_scheme=post-id-v1` 메타가 있는 신규 글만 MU 플러그인의 `post_link` 필터를 통해 `/p/ID/`를 canonical permalink로 반환한다.
- 기존 공개 글은 `post_name`, 기존 URL, canonical을 변경하지 않는다. 대신 `/p/ID/` 요청을 공통 호환 주소로 받아 기존 canonical URL로 301 이동한다. 따라서 기존 링크와 검색 색인은 유지하면서 운영상 모든 게시글을 `/p/ID/`로 식별할 수 있다.
- `/p/ID/` 라우터는 `post_type=post`, `post_status=publish`만 공개 처리한다. 새 정책의 공개 글은 200, 기존 공개 글은 기존 URL로 301, 초안·페이지·첨부·없는 ID는 404가 기본이다. 단, 새 정책의 비공개 글은 WordPress가 실제 preview 요청으로 판정하고 현재 사용자에게 해당 글의 `edit_post` 권한이 있을 때만 관리자 미리보기 렌더링을 허용한다.
- `/p/00123/`, `/p/12abc/`, `/p/123/foo/`처럼 정규 형식이 아닌 주소는 정식 호환 주소로 취급하지 않는다. trailing slash가 없는 `/p/123`은 WordPress canonical 처리에 따라 `/p/123/`로 정규화할 수 있다.
- 신규 publisher는 `post_name`을 직접 지정하지 않고 WordPress 내부 값으로 맡기며 URL에는 사용하지 않는다. 생성 직후 `_bloguito_permalink_scheme=post-id-v1` 메타를 저장한다.
- 이전 `/{post_id}/{short-slug}/`, `id-slug-v1` 정책은 폐기한다. 기존 공개 글에 이전 신규 scheme 메타를 소급 설정하지 않았으므로 기존 URL에는 영향이 없다.
- 운영 배포 전 원본은 `/home/ubuntu/agent-publisher/data/editorial_runs/post-id-permalink-20260930T212839`에 백업했다. 운영 MU 플러그인은 `Bloguito Post ID Permalinks` 2.0.1이며 rewrite rules를 flush했다.
- 운영 공개글 54개를 전수 검사한 결과 기존 canonical URL은 모두 HTTP 200, 대응하는 `/p/ID/`는 모두 HTTP 301, `Location`은 각 기존 canonical과 정확히 일치했고 실패는 0건이었다.
- `/p/0610/`, `/p/610abc/`, `/p/610/foo/`, 존재하지 않는 `/p/999999999/`는 모두 404로 확인했다. 특히 WordPress의 canonical 추측이 `/p/0610/`을 다른 페이지로 보내지 않도록 malformed `/p/` 경로에서는 `redirect_canonical`을 비활성화한다.
- 기존 #610 표본의 HTML canonical, `og:url`, REST API `link`, Rank Math post sitemap은 모두 기존 `https://lifeinfo24.org/national-pension-estimate-check/` 체계를 유지하며 sitemap에는 `/p/610/` alias가 포함되지 않는다.
- 로컬 공통 Python 회귀는 741개 통과, 1개 skip이었다. 운영 PHP 8.3에서 MU 플러그인 문법 검사와 독립 라우팅 테스트를 통과했고, 운영 writer `Plan`에는 `slug` 필드가 없으며 publisher에도 `--post_name` 강제가 남아 있지 않음을 확인했다.
- 2026-10-02 후속 수정에서 `post-id-v1` 초안의 관리자 미리보기가 `/p/ID/?preview=true`로 들어온 뒤 `post_status !== publish` 조건에 의해 강제 404가 되던 회귀를 수정했다. MU 플러그인 2.0.2는 `is_preview()`이고 현재 사용자에게 해당 글의 `edit_post` 권한이 있을 때만 비공개 새 정책 글의 미리보기를 통과시킨다. 운영 #817에서 관리자 preview handler는 404가 아니고, 익명 preview와 관리자의 preview 없는 직접 접근은 404임을 확인했다. 익명 실제 HTTPS `https://lifeinfo24.org/p/817/?preview=true`는 404를 유지했고, 기존 공개글 #730의 `/p/730/` 호환 주소는 기존 canonical로 301을 유지했다.
