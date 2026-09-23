# 레거시 레이아웃 적용 승인 패키지 — 2026-09-22

## 현재 결정 범위

**운영 미적용·게시물 미수정.** 실제 공개 30편에 대해 레거시 목차 19편, 구형 녹색 요약 상자 24편, 게시물 #85 표 두 개의 출력을 검토했다. 이 문서는 각 변경의 원본·후보·검증·복구 경계를 제시한다. 설치·수정 승인을 대신하지 않는다. 모든 로컬 파일은 `tmp/legacy_audit_20260922/layout-worker2/`에 있으며 `docs/legacy-layout-approval-package-2026-09-22.md`만 이번 작업에서 새 문서로 만들었다. 다른 작업자의 `wordpress/mu-plugins/bloguito-legacy-callout-spacing.php`, `docs/EDITORIAL_SYSTEM.md`, `docs/INDEX.md` 및 나머지 수정 파일은 건드리지 않았다.

기준 코드는 `wordpress/mu-plugins/bloguito-legacy-toc.php`(SHA256 `6240c15ffe527665cacc7fd773944374a9cd7533f9a4c563206b99c4d2fedcdb`)이며, 다른 작업자의 별도 녹색 상자 CSS SHA256은 `c9bae087d11eeb50ece97055fca99ed315a660730757063320eda908faaeba4b`이다. 후속 변경이 있으면 이 문서의 테스트 결과를 그대로 재사용하지 않는다.

## #85: 실제 저장 HTML에 대한 원본 해시·되돌리기

공개 URL: `https://lifeinfo24.org/review-benefit-guide-20260913/`; 서버의 `wp post get 85 --format=json`을 **읽기 전용**으로 호출해 `post_status=publish`, 저장 수정시각 `2026-09-18 12:48:58`을 확인했다. 공개 REST GET도 `status=publish`, `modified=2026-09-18T12:48:58`로 일치했다. 실제 저장 `post_content`는 **7,646 UTF-8 bytes**이고 REST의 `content.rendered`는 WordPress 문단 처리로 줄바꿈·마크업이 달라진다. 두 해시를 혼용하면 안 된다.

| 확인 대상 | SHA-256 |
| --- | --- |
| 실제 저장 원본 `post_content` | `499afcf30df2cfbfdca7041e80bc139c90e1a8da5d5348837b77ee2b8e2cf065` |
| 저장본에서 표 두 개만 교체한 후보 | `9cc4d276d6dd15b8e3407a5804474687f5c628bba76db8034dc4387ddee75972` |
| 공개 REST 원본 출력 HTML | `9791443dbf4c5c9f43236c034bb4e321f8dc14cc69fed44b7710d7b98cbe644a` |
| REST 출력의 두 표만 바꾼 미리보기 후보 | `49369d8d471b5318838f7d3d4fa3acd7d2d85162d4e254ebd974bd298691bbff` |

저장 원본을 두 차례 read-only 조회해 상태·수정시각·SHA가 동일한 것을 확인했다. `fetch_post85_saved_readonly.py`는 재조회 시 기존 백업과 해시가 다르면 덮어쓰기 전에 실패한다. `prepare_post85_approval.py`도 공개 REST를 다시 GET해서 스냅샷의 본문 SHA·수정시각·상태가 모두 일치해야만 새 후보를 작성한다. 저장본 원본과 REST 원본의 `<table>` 두 개는 문자열 형식이 서로 달라 **각각 독립적으로 정확히 한 번씩** 교체한다. 3열 헤더와 2/5개 데이터 행의 전후 셀 텍스트·순서가 완전히 일치하며, 역교체 결과는 저장 HTML과 REST 출력 HTML 각각에서 원본과 바이트 단위로 일치했다.

| 자료 | 파일 (모두 위 `layout-worker2/` 기준) |
| --- | --- |
| 저장 원본·후보·원복 | `post85-saved-content-original.html`, `post85-saved-content-candidate.html`, `post85-saved-content-rollback.html` |
| 저장 HTML 정확한 전방·역방향 diff | `post85-saved-forward.diff`, `post85-saved-rollback.diff` |
| 눈으로 확인하는 표별 보기 좋은 diff | `post85-table1-review.diff`, `post85-table2-review.diff` |
| REST 출력 원본·후보·원복 및 diff | `post85-original-rendered.html`, `post85-candidate-rendered.html`, `post85-rollback-rendered.html`, `post85-table-forward.diff`, `post85-table-rollback.diff` |
| 해시·원본/후보 경계 | `post85-approval-manifest.json`, `post85-saved-read-manifest.json`, 기존 `post85-table-remediation.json` |
| 전체 글 변경 전·후 시각 검토 | `post85-original-full-preview.html`, `post85-candidate-full-preview.html`, `post85-candidate-integrated-preview.html` |
| 재생성·검증 | `fetch_post85_saved_readonly.py`, `prepare_post85_approval.py`, `render_integrated_previews.py`, `verify_layout_approval.py` |

**통합 미리보기** `post85-candidate-integrated-preview.html`은 실제 소스의 `bloguito-legacy-toc.php`를 격리된 PHP 표준입력으로 실행한 결과를 넣고 다른 작업자의 녹색 박스 CSS를 별도로 시뮬레이션한다. WordPress DB, 게시물, 서버 파일은 변경하지 않았다. 렌더러/테마와 플러그인 전체를 통과한 **운영 미리보기와 동일하다고 보장하지 않는다.** 본문 기존 출처·주소·문장을 이 레이아웃 작업에서 재검토하거나 고치지 않았다.

**현재 적용 차단 조건:** `editorial_cli.py update-existing`는 `--post-id`, `--expected-content-sha256`, `--confirm-update`, 대상 ID가 맞는 최신 검토 bundle 및 공식 원문 재조회·검증을 요구한다. 실제 구현은 `render(bundle['plan'], bundle['sources'])`로 **전체 본문을 다시 렌더링**한다. 따라서 본 문서의 부분 표 치환 HTML을 임의로 `update-existing`에 넣거나 직접 WP-CLI·임시 PHP 편집으로 우회할 수 없다. #85의 공식 근거·전체 원고를 구조화 bundle로 검토하여 렌더러 출력까지 일치시키거나, 같은 안전 게이트·백업·검증을 구현한 별도 승인된 갱신 경로가 마련되기 전에는 **표 실제 적용 보류**. 최종 승인 직전 WordPress 저장 필드 SHA `499afcf…f065`와 원본 글 전체 백업을 다시 확보해야 한다. 불일치하면 이 후보는 폐기하고 다시 준비한다.

## 30편 본문 상자 교차 점검: 녹색 요약만의 문제가 아님

`audit_layout_cross_coverage.py`가 공개 REST 출력 스냅샷 30편의 배경·테두리·공통 클래스 컨테이너 **81개**를 분류하여 `cross-coverage-census.json`에 각 ID·직계 자식·빈 문단·여백·스타일을 기록했다.

| 유형 | 수량 | 확인 내용 |
| --- | ---: | --- |
| 기존 녹색 요약 | 24 | `#11775a` 직접 자식 문단만 다른 작업자 CSS가 선택. 그중 14편(70·99·105·113·119·121·127·137·140·144·145·163·217·220)은 마지막 문단의 명시적 하단 여백 지정이 없었다. 구형 박스 24편의 잘못된 `</p>`는 기존 별도 감사에 기록. |
| 신규 요약·FAQ·목차·CTA | 5·23·5·4 | 직계 빈 `<p>`·`<br>` 검출되지 않음. FAQ는 `div` 시작·끝, 신규 요약은 `div`→`p`이고 문단 하단 여백을 인라인으로 지정한다. |
| #85 별도 안내 상자 | 1 | 좌측선 `#147d64`; 자식 `h2`·`ul`, 직계 빈 문단 0. 녹색 CSS가 선택하지 않음. |
| 출처/관련 정보 등 다른 배경 상자 | 6 | #218·#225·#243·#304·#349에서 발견; 마지막 자식 `ul`이며 `margin:0` 지정, 직계 빈 문단·`br` 0. |
| 표 스크롤 영역 및 나머지 구조 | 8·5 | 신규 표 영역 8개; 나머지 5개는 공통 외부 컨테이너. 녹색 CSS와 선택자 충돌 없음. |

현재 확인된 상자 외부 여백 이상은 **다른 작업자가 소유한 `#11775a` 구형 요약의 CSS 범위 안**에 있다. #85 `#147d64`, 신규 `.bloguito-summary`·`.bloguito-faq`, 출처/관련 글에 적용하는 포괄적인 새 CSS는 필요하다는 증거가 없으므로 추가하지 않았다. 잠재적인 테마·모바일 상태는 운영 적용 후 다시 확인해야 한다. CSS는 DOM에서 빈 문단을 숨기지만 WordPress가 출력하는 잘못된 HTML을 저장 원고에서 제거하지는 않는다.

## 목차 적용 단위·전수 PHP 검사

독립 MU 플러그인 `wordpress/mu-plugins/bloguito-legacy-toc.php`는 기존 25편 ID 명시 허용목록, 메인 게시물/공개 조건, 저장 본문 무변경을 갖는다. 700자 미만 6편(55·63·77·79·81·219)은 그대로 두고 **19편(70·85·99·101·103·105·113·119·121·125·127·137·139·140·144·145·163·217·220)**에만 출력 목차 1개를 추가한다. 신규 자체 목차 5편(218·225·243·304·349)은 그대로 둔다. #85 요약 내부 H2는 제외하고 나머지 H2에만 출력 시점 ID 5개를 만든다. 불명확한 구조·ID 충돌 시 작업을 중단하는 가드와 HTML 이스케이프를 포함한다. 원래 FAQ/출처 등 앵커 없는 H2는 기존 검토 범위에서 자동으로 새 ID를 생성하지 않아 목차에 없는 경우가 있다. 전수 테스트가 검증한 **현재 30편에만** 결과를 일반화한다.

`verify_layout_approval.py`를 실제 PHP 8.3.33 표준입력으로 실행한 결과: 공개 스냅샷 30편에 대한 **144개 검사 통과**, 변경 대상 정확히 19편, 나머지 11편 무변경, 목차 중복·깨진 링크 없음. 추가로 기존 `wordpress/tests/legacy-toc-contract-test.php`의 합성 **23개 검사 통과**(짧은 글·중복 호출·HTML escaping·구형 구조 변경·초안 제외 등). 모두 원격 PHP **stdin-only**, 서버 소스 파일 생성·WordPress 갱신 없음. 서버에 설치된 환경의 실제 WordPress hook·테마·캐시와 결합한 검증은 아직 하지 않았다.

**게시물별 승인 조건:** 플러그인을 그대로 설치하면 위 19편의 공개 화면이 한꺼번에 달라진다. 19편의 레이아웃 일괄 변경을 명시적으로 승인받지 못하면 **설치하지 않는다**. 일부 ID만 승인되면 플러그인의 ID 허용목록을 승인된 게시물만으로 좁히고 전수 PHP 및 브라우저 검사를 다시 통과시킨 뒤 적용한다. 다른 작업자 CSS도 구형 24편에 동시 적용되므로 별도 일괄 레이아웃 승인 또는 동일한 승인 범위 축소가 필요하다. 게시물 내용·공식 사실의 최신성 승인을 목차/간격 검사로 대체하지 않는다.

## 실제 로컬 브라우저 미리보기 (운영 미적용)

비로그인 QA 초기 URL은 `https://lifeinfo24.org/?utm_source=bloguito_qa_agent&utm_medium=internal_test&utm_campaign=site_checks`로 열었다. 연결된 Desktop에는 직접적인 브라우저 탭 함수가 노출되지 않아, 이전 작업 종료 후 **격리 Edge 하나만 시작**하고 동일 인스턴스를 모든 미리보기에 재사용해 CDP로 실제 렌더링·키 입력·스크린샷·콘솔을 검사했다. Windows 사용자 Chrome 세션에 접속하거나 로그인하지 않았다. 검증은 **360×800 / 390×800 CSS px, 1280×900의 CSS `zoom:200%` 근사**로 구성했다. 마지막 항목은 브라우저 네이티브 Ctrl+ 200% 확대가 아니며 실기기 터치·스크린리더 확인도 아니다. 총 **5개 HTML 미리보기 × 3개 화면 = 15개 화면 상태**, 스크린샷 **17개** 및 기록 `browser-layout-qa-results.json`, `browser-qa-console.log`.

| 화면 | 검증 결과 |
| --- | --- |
| #85 변경 전 | 목차 0·표 두 개 모두 caption/열·행 `scope` 없음. 360px 캡처에서 서비스명 열이 한 글자씩 극단적으로 줄바꿈됨. |
| #85 개선 후 통합 미리보기 | 목차 1개·유효 앵커 5개; 표 2개 모두 caption·열머리글 3개 및 행머리글 2/5개, 모바일 힌트 2개, `role=region`·`tabindex=0`; 표 폭 580px, 360/390에서 스크롤 영역의 폭 320/350px. **실제 브라우저 방향키 입력**으로 첫 표 `scrollLeft 0→260px`(360), `0→230px`(390) 확인. 문서 전체 가로 넘침·깨진 이미지 0. |
| #137 새 검토 정적 원고 | `pilot137/bundle.reviewed.html` SHA256 `19654865151823398b1dcd3a7661a5e1b3016ee5964048b76494c114d96da6df`를 변경 없이 포장. 목차 1개/유효 앵커 6개, 표 3개 모두 caption·머리글 scope, FAQ 3개, 공식 CTA 1개. CTA에 프로그램 초점 이동 성공하며 주소는 이전 공개 브라우저에서 HTML GET 및 로그인 안내를 관측한 홈택스 상세 조회 경로. 실제 인증·조회·신청 수행하지 않음. 가로 넘침·깨진 이미지 0. |
| #137 구형 상자 CSS 전·후 | 동일 공개 REST 글의 360px 높이 **335→292px**, 390px **303→260px**; 빈 `<p>`는 DOM에 1개 남지만 `display:none`으로 감춤, 문단 하단 여백 **25.5px→0px**. 변경 전후 이미지로 상자 아래 여백 감소 확인. |
| 전체 15개 상태 | `documentElement.scrollWidth`는 각 시각 뷰포트 폭 이내; 외부로 튀어나온 비표 요소/이미지 실패 없음. 로컬 미리보기 콘솔 오류 0. 최초 실제 QA 홈에서는 WP Statistics `tracker.js`가 클라이언트 차단된 로그가 1건 있었으나 이번 로컬 코드 오류로 판단할 근거는 없음. |

확인용 이미지 파일은 모두 `layout-worker2/qa-*.png` 17개이며 예시는 `qa-post85_before-360-table1.png`, `qa-post85_after-360-table1.png`, `qa-post85_after-360-table2.png`, `qa-post137_legacy_before-360-card.png`, `qa-post137_spacing_after-360-card.png`, `qa-post137_reviewed-390-top.png`, `qa-post85_after-200css-desktop-top.png`이다. 실제 존재·파일 크기를 확인했고 UI 화면도 직접 살폈다. 파일은 Git에 넣지 않은 로컬 검토 자료다.

## 승인 후 실행·롤백 시 확인할 사항

1. 먼저 사용자에게 **대상 ID별 또는 명시된 범위의 공유 레이아웃 승인**과 #85의 별도 본문 승인 여부를 확인한다. 일부 ID만 승인되면 목차/CSS 적용 집합을 줄이고 테스트를 재실행한다. 승인되지 않은 본문에는 WordPress 쓰기나 MU 파일 설치를 하지 않는다.
2. 배포 담당자는 설치 직전 실제 서버의 동일 이름 MU 파일 존재·해시, 플러그인 활성 설정(LuckyWP 등), 게시물 상태·해시와 복구 파일을 별도 점검한다. CSS 소유자가 소스와 승인 범위를 검토한다. 검토 완료 후 승인된 파일만 스테이징→적용하고 홈·#85·#137·#225·신규 5편과 목차 대상 19편을 다시 QA한다. 여기서 기록한 PHP stdin 검사는 운영 hook·실제 브라우저 배포 검사를 대체하지 않는다.
3. 목차에 문제가 있으면 이번에 **새로 설치한 목차 MU 파일 하나만 제거**하여 렌더 시점 변경을 되돌린다. 다른 작업자 CSS·게시물 본문·기존 MU 파일은 유지한다. CSS 문제는 담당 소유자의 승인·백업에 맞춰 해당 CSS 파일만 되돌린다. 목차 설치 자체는 DB 원고를 변경하지 않는다.
4. #85는 최신 공식 근거와 전체 구조화 원고의 **정상 `update-existing` 검증** 또는 동등한 사전 승인된 안전 경로가 갖추어지기 전까지 변경 금지다. 실변경 전 저장 원본 SHA와 상태를 다시 대조하고 원본 **전체 post JSON**을 백업하며 실제 검토 HTML과 원고/출처 해시를 검사한다. 실변경 후 저장 필드가 승인 후보와 일치하는지 확인한다. 복구 필요 시 현 저장 본문이 승인 후보 SHA와 일치하는지 확인하고, 이 패키지의 실제 저장 원본·역방향 diff와 전체 백업을 사용한 **승인된 복구 경로**로 복원한다. 상태가 달라졌으면 강제 덮어쓰기 대신 중단한다.

**실제 작업 범위:** 작업자가 소유한 `tmp/legacy_audit_20260922/layout-worker2/`의 준비 스크립트·HTML·diff·검증 자료와 본 문서만 생성/수정했다. 다른 작업자의 CSS·편집 정책·테스트·문서는 수정하지 않았으며 Git stage/commit/push, 서버 파일 설치/교체, 운영 WordPress 게시물 업데이트·공개·스케줄 변경은 하지 않았다.

## 추가 검증: #85만의 출력 단계 표 접근성 보정 — 승인 전 준비

이 절은 앞의 **WordPress 저장 원고를 직접 교체하려면 전체 구조화 원고 검토가 필요하다**는 경계를 유지하면서, 표 *서식만* 개선하는 독립 대안을 검증한 결과다. `wordpress/mu-plugins/bloguito-legacy-table-accessibility.php`를 신규 작성했다. 파일 SHA-256은 `afe44b8ec982c8f2856506ea41d6f3edf5bd1511e9fc856aa4a85c1f0a683f5f`이다. **서버에는 설치하지 않았다.** 다른 작업자 소유의 `bloguito-legacy-callout-spacing.php`와 기존 `bloguito-legacy-toc.php`, 편집 시스템 코드/문서 및 WordPress DB는 수정하지 않았다.

### 정확한 대상 및 변경 조건

- WordPress `the_content` 우선순위 **100**, 기존 목차의 우선순위 99 이후에 적용한다. 공개 상태의 **ID #85** 단일 글, 메인 쿼리·메인 루프만 통과하며 관리자·REST·피드·초안·다른 글은 그대로 반환한다. TOC 플러그인을 설치하지 않았을 때도 #85 원본 출력 해시와 일치하면 표 보정만 독립 실행할 수 있다.
- 저장 HTML(`499afcf3…e2cf065`) 또는 공개 REST 출력 HTML(`9791443d…be644a`)과, 각각에 기존 목차 코드가 추가된 HTML(`e0ad7f77…b277f` 또는 `0b5ae88f…e375f3`)의 **SHA-256 네 가지 전체 본문 지문 중 정확히 하나와 일치**해야 한다. 이 값들은 `post85-render-only-manifest.json`과 실제 PHP 검증에 원문 전체로 기록했다. 두 원본의 정확한 표 SHA도 각각 **두 개가 올바른 순서·동일 버전의 쌍**으로 맞아야 한다. 본문 문장 하나, 표 하나, H2 개수/요약 표식, 다른 플러그인의 출력 변경 등이 있으면 조용히 기존 출력을 유지한다. 승인 후에는 이 조건 때문에 적용이 자동 중단됐는지 실제 공개 페이지에서 재확인해야 한다.
- 원래의 표 셀 텍스트와 순서를 그대로 유지하면서 두 표에 `caption`, 열 헤더 3개씩 `scope="col"`, 행 헤더 2개·5개 `scope="row"`, 좌우 스크롤 안내 문장, `role="region"`, `tabindex="0"`, `overflow-x:auto`, 최소 폭 580px를 **HTML 출력에만** 추가한다. 제목·날짜·본문·출처·저장된 `post_content`·발췌문·DB는 전혀 변경하지 않는다. 두 표 치환 결과를 완성한 뒤 문자열 전체를 반환하며, 재호출은 원문을 그대로 반환한다.

### 독립 검증 및 산출물

| 검증 | 관측 결과 |
| --- | --- |
| 독립 PHP 문법·계약 | 실제 PHP 8.3 표준입력 `php -l` 통과; **101건 검사 통과**. 30개 공개 REST 스냅샷에서 #85만 변경, 나머지 29편 바이트 단위 무변경. 원본 저장/REST 및 TOC 조합 네 가지 처리, 두 표 외 모든 출력 원문 보존, 셀 텍스트·순서 보존, 멱등성, 새 렌더러 배제, 초안·관리자·REST·피드·쿼리 ID 불일치 배제. 표 또는 본문 다른 문장 변조·서로 다른 버전 지문 혼합 모두 적용 중단. PHP는 원격 컨테이너 **stdin으로만 실행**했으며 서버 파일/DB 쓰기는 없었다. |
| 실제 출력 미리보기 구조 | `post85-runtime-mu-rendered.html`은 **실제 새 표 플러그인 + 기존 목차 코드**를 실행한 HTML. 목차 1개·연결되는 링크 5개, 표 2개·caption 2개·열 헤더 6개·행 헤더 7개, 원래 모든 데이터 셀 일치. 로컬 HTML 미리보기는 `post85-runtime-mu-preview.html`; WordPress 운영 출력과 같다는 주장은 아니다. |
| 모바일 브라우저 | 같은 단일 격리 Edge 세션에서 해당 실제 PHP 결과를 360×800·390×800으로 렌더링. 두 표 각각 `scrollWidth=580px`, 스크롤 영역 `clientWidth=320px / 350px`, 문서 전체 폭은 각각 360px / 390px. 첫 표에 키보드 초점 후 방향키로 `scrollLeft 0→260px / 0→230px`. 목차 5개 앵커 모두 존재, 깨진 이미지 0. |
| 확대 | 1280×900에서 **CSS zoom 200% 근사**로 검사; 시각·문서 폭 1265px, 가로 넘침 0. OS/브라우저의 실제 200% 확대·스크린리더·실기기 터치는 이 결과로 인증하지 않는다. |
| 콘솔 | 최종 로컬 미리보기 3개 화면 검사에서 오류 **0건**. 최초 공개 QA 사이트의 WP Statistics `tracker.js`는 격리 브라우저에서 `ERR_BLOCKED_BY_CLIENT`가 발생한 별도 현상으로, 로컬 미리보기에는 나타나지 않았다. |

새 검증 소스는 `wordpress/tests/legacy-table85-accessibility-test.php`, 로컬 실행기는 `tmp/legacy_audit_20260922/layout-worker2/verify_post85_render_only.py`이다. 화면 검사 코드는 같은 폴더의 `browser_table85_runtime_qa.mjs`, 측정 증거는 `post85-runtime-browser-results.json`, 화면 캡처는 `qa-post85-runtime-360.png`, `qa-post85-runtime-390.png`, `qa-post85-runtime-1280-200css.png`(3개 모두 실제 파일 크기 확인). 적용 기준 SHA와 결과는 `post85-render-only-manifest.json`에 기록했다. 새 코드와 파일은 이 작업자의 소유 범위 안에만 있다.

### 승인·운영·원복의 최소 단위

이 대안을 사용하면 **#85의 표 두 개에 대한 서식 승인만으로** 신규 MU 파일 **하나**의 설치를 별도로 검토할 수 있다. #85 전체 원고의 내용/최신성 검토 및 `update-existing`를 이 서식 변경으로 대체하지 않는다. 배포 담당자는 승인 직전에 운영 파일 존재·해시 및 게시물 저장/공개 출력 지문을 다시 대조하고, 운영 훅의 실제 `$content` 지문이 위 허용 값 중 하나인지 확인한다. 불일치하면 플러그인은 동작하지 않으므로 현재 HTML에 맞춘 증거와 검증부터 다시 준비한다. 설치 후 #85 두 표의 caption·scope·스크롤·키보드 이동, 목차 중복 여부, 나머지 29편 무변경을 실제 공개 브라우저로 확인한다. **이 작업에서는 설치·게시물 쓰기·Git 작업을 수행하지 않았다.** 문제가 발생하면 이번 표 전용 MU 파일 **하나만 제거**하고 출력 캐시를 별도로 확인하면 원래 저장 HTML이 그대로 남아 출력 단계 변경을 되돌릴 수 있다. TOC 및 다른 작업자 CSS 파일은 그대로 보존한다.
