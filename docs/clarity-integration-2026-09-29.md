# Microsoft Clarity integration — 2026-09-29

- 운영 WordPress에 공식 `Microsoft Clarity` 플러그인 `0.10.33`을 설치·활성화했다.
- 설치 직후 운영 홈페이지는 HTTP 200을 유지했다.
- Microsoft 계정에서 Clarity 프로젝트를 선택하거나 새로 만드는 인증 단계는 아직 완료되지 않아 `clarity_project_id`는 비어 있다. 따라서 이 시점에는 Clarity 추적 태그가 공개 페이지에 삽입되지 않는다.
- 테마 파일을 직접 수정하지 않고 `wordpress/mu-plugins/bloguito-clarity-content-insights.php`를 추가했다. GeneratePress의 `generate_article_microdata` 필터를 사용해 단일 글의 바깥 `<article>`에만 `data-clarity-region="article"`을 추가한다.
- 아카이브/목록 article과 본문 안의 행사 카드용 `<article>`에는 이 속성을 추가하지 않는다.
- Clarity 프로젝트 연결 뒤에는 공개 글 HTML에서 `https://www.clarity.ms/tag/<project-id>?ref=wordpress` 스크립트와 `data-clarity-region="article"`을 함께 확인한다.
