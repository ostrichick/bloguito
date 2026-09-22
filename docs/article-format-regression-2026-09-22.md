# 게시물 #225 서식 회귀 점검 및 공통 렌더러 수정 — 2026-09-22

## 사용자 제보와 실제 원인

- 사용자 제공 공개 글 스크린샷과 WordPress #225 본문 HTML, 공통 `agents/editorial.py` 렌더러를 대조했다. 문제가 된 글은 이미 `publish`였으며, 시작 본문 SHA-256은 `c3a4ccdd5d1d5b8fb5453f7cb5fcc29aa09ce10cfec441abd3d33d48ac47c2d1`이다.
- 모든 본문 `h2`는 크기·여백·선만 지정하고 `font-weight`와 글꼴을 테마 상속에 맡겼다. 결과적으로 스크린샷에서 소제목이 본문과 비슷한 무게로 보였다. 일반 문단·요약·FAQ는 서로 다른 크기·행간을 사용해 글 흐름도 일관되지 않았다.
- 전체 원고에서 `kind=procedure`가 한 번만 나와도 코드가 기계적으로 `STEP 1`을 붙였다. 이 글의 단일 '큰돈 이체·해외송금' 절과 목차에 의미 없는 번호가 나타났다.
- 목차는 본문과 FAQ뿐 아니라 하단 출처까지 기본 포함했다. 한눈에 보기 표와 목차가 이미 상단 공간을 쓰는 구성에서 목록을 불필요하게 길게 했다.
- 기존 검사는 원고의 근거·날짜·HTML 구조는 확인했지만 실제 WordPress 테마의 글꼴 상속, 단일 STEP 표시 및 브라우저 반응형 화면까지 자동으로 판정하지 않았다. 이전의 `ready`는 시각적 합격 판정이 아니다.

## 수정 범위와 예방 장치

- 공통 `agent-publisher/agents/editorial.py`에 한글 글꼴 스택·통일된 문단 크기와 간격을 명시했다. 각 `h2`·FAQ 제목·하단 출처 제목의 굵기·글꼴·자간을 직접 정했다. 원고의 문장·근거·날짜·수치·표·FAQ·이미지와 공식 URL은 수정하지 않았다.
- `STEP` 배지는 복수의 절차형 절이 있는 경우에만 표시하며 목차 번호도 같은 조건으로 생성한다. 목차에서 하단 출처 항목을 제외하되 출처 본문과 `id=sources`는 그대로 유지했다.
- `agent-publisher/tests/test_article_layout_contract.py`에 제목 글꼴/굵기, 단일·복수 STEP, 목차 단일성·앵커, 요약·표·FAQ 보존을 점검하는 테스트 3개를 추가했다. 기존 렌더 테스트의 단일 STEP 기대값도 변경했다. `docs/EDITORIAL_SYSTEM.md`에 공통 서식과 실제 브라우저 검증 기준을 기록했다.
- 독립적인 모델 재검토가 `ready`/이슈 0건으로 끝난 원고(`tmp/post225_work/post225_layout_review.json`)만 사용했다. 검토 원고의 `brief`·`sources`·`plan`·`temporal_source`는 이전 원고와 완전 일치했다. 원고 내용 변경이 아닌 HTML 서식 변경이다.

## 실제 운영 적용과 검증

- 서버에서 편집 잠금이 없고 해당 코드·문서가 로컬 기준 버전과 일치하는지 확인한 뒤, 코드와 편집 문서만 SHA-256 검증·원본 백업 후 반영했다. 백업은 서버 `/home/ubuntu/agent-publisher/data/editorial_runs/post225-layout-20260922/backups/`에 있다. 서버 `py_compile` 성공.
- 운영 WordPress #225의 ID·공개 상태·원문 SHA를 변경 직전 비교한 후 표준 `editorial_cli.py update-existing`로 갱신했다. 이전 게시물 전체 백업은 서버 `/home/ubuntu/agent-publisher/data/editorial_runs/public-edit-225-20260922T092907.json`이다. 검토 본문·공식 원문 재조회·쓰기 전 해시·쓰기 후 필드 보존 검사를 통과했다.
- 새 본문 SHA-256: `62eb3b53459c42ed07148b3d8eca33a2c67cebeb25aab6fbd9040591fe4c6826`. WordPress 상태 `publish`, 제목·슬러그·발췌문·게시일·대표 이미지 ID `362` 보존.
- 공개 URL `https://lifeinfo24.org/?p=225` HTTP 200, 본문 제목 8개에 동일한 글꼴·굵기 지정 확인. 요약 1개·목차 1개·표 1개·FAQ 5개, 목차 내부 링크 전부 실제 앵커와 일치, 단독 `STEP 1`과 출처 목차 항목 제거 확인.
- 기존 서식 회귀 테스트 33개, 신규 레이아웃 테스트 3개 통과. 브라우저 실제 렌더링도 **Chromium 1280×960 데스크톱 / 390×844 모바일**에서 각각 확인: `h2` computed font-weight `700`, 자간 `normal`, 화면 전체 가로 넘침 0. 작업용 스크린샷 `tmp/post225_work/layout-after-desktop.png`, `layout-after-mobile.png`를 시각적으로 확인했다. 별도 360px·200% 확대·보조기술 검사는 수행하지 않았다.
- Google Analytics QA 방문은 `utm_source=bloguito_qa_agent&utm_medium=internal_test&utm_campaign=site_checks`로 식별했다. 리포트의 저장된 사진과 HTML 검사는 검색 순위·유입·전체 기기 성능의 증명이 아니다.

## 범위와 후속 주의

- 본 작업은 요청된 #225와 공통 렌더러·회귀 검사·편집 문서만 수정했다. 다른 공개 글은 WordPress에서 변경하지 않았다. 이미 공개된 과거 게시물의 HTML은 서버 렌더러만 변경해도 일괄 재생성되지 않으므로, 해당 글에 동일 문제가 보이면 글별 원본 백업·검토·비교 갱신이 필요하다.
- 이 글은 2026년 추석의 한시적 일정이므로 연휴 종료 이후 별도 시의성 재검토가 필요하다. 이번 서식 수정은 2027년 일정의 유효성을 뜻하지 않는다.
