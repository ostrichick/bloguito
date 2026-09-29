# Microsoft Clarity integration — 2026-09-29

- 운영 WordPress에 공식 `Microsoft Clarity` 플러그인 `0.10.33`을 설치·활성화했다.
- 설치 직후 운영 홈페이지는 HTTP 200을 유지했다.
- 이후 Microsoft 계정에서 Clarity 프로젝트 연결을 완료했고, 운영 WordPress의 `clarity_project_id`가 저장된 것을 재확인했다.
- 테마 파일을 직접 수정하지 않고 `wordpress/mu-plugins/bloguito-clarity-content-insights.php`를 추가했다. GeneratePress의 `generate_article_microdata` 필터를 사용해 단일 글의 바깥 `<article>`에만 `data-clarity-region="article"`을 추가한다.
- 아카이브/목록 article과 본문 안의 행사 카드용 `<article>`에는 이 속성을 추가하지 않는다.
- 공개 HTML에서 `https://www.clarity.ms/tag/<project-id>?ref=wordpress` 추적 스크립트와 `data-clarity-region="article"`이 함께 출력되는 것을 확인했다.
