# 레거시 본문 목차 및 #85 표 레이아웃: 배포 준비 기록 — 2026-09-22

## 범위 및 변경 전 상태

- 기준 로컬 HEAD: `6c38256`. 시작 시 `agent-publisher/agents/curator.py`, `publisher.py`, `agent-publisher/tests/test_article_layout_contract.py`, `test_editorial_system.py`, `test_ticket_validation.py`, `docs/EDITORIAL_SYSTEM.md`, `docs/INDEX.md` 및 기존 미추적 문서·`wordpress/mu-plugins/bloguito-legacy-callout-spacing.php`에 다른 작업자의 변경이 있었다. **이 파일들은 수정·스테이징하지 않았다.**
- `AGENTS.md`, `docs/EDITORIAL_SYSTEM.md`, `agent-publisher/editorial_policy.json`, `docs/OPERATIONS.md`, `docs/toc-duplicate-plugin-deactivation-2026-09-21.md` 및 현재 공통 렌더러의 TOC 구현을 확인했다.
- 공개 WordPress REST `GET /wp-json/wp/v2/posts?per_page=100&_fields=id,status,content,modified`로 30개 게시물의 출력 HTML을 다시 가져와 점검했다. 5편(218·225·243·304·349)은 `.bloguito-article`, `.bloguito-toc` 한 개씩이 있다. 나머지 구형 25편은 자체 목차가 없다. 24편은 본문 H2에 기존 `step-*` 또는 `guide-*` 앵커가 있으며 #85의 H2 여섯 개에만 앵커가 없다. 이미 비활성화된 LuckyWP 목차를 다시 켜면 신규 5편에서 중복 가능성이 있으므로 이 경로는 사용하지 않는다.
- 구형 25편 중 6편(55·63·77·79·81·219)은 본문 700자 기준을 충족하지 않아 자동 목차가 불필요하다. 단순한 목차 부재를 일괄 오류로 취급하지 않는다.

## 준비한 코드: 독립 MU 플러그인

**로컬 파일:** `wordpress/mu-plugins/bloguito-legacy-toc.php`. `the_content`의 우선순위 99에 등록하지만 `is_singular('post')`, 메인 쿼리·메인 루프, 해당 공개 게시물 ID 일치 조건을 만족한 경우에만 동작한다. 관리자·REST·피드·임시글은 건드리지 않는다. 2026-09-22 기준 레거시 25개 ID의 명시적 허용목록 이외에는 적용하지 않는다.

공개 출력 원고에서 네이티브 `.bloguito-article` 또는 기존 `bloguito-toc`·`bloguito-legacy-toc`·`lwptoc`·`ez-toc-container` 등을 발견하면 그대로 반환한다. 읽을 수 있는 본문 길이가 700자 미만이거나 고유한 유효 소제목 앵커가 3개 미만이어도 그대로 반환한다. 본문 H2의 기존 앵커와 제목·문단·표·출처의 원래 내용을 보존하며, 단독 `<nav aria-label="본문 목차">`를 첫 대상 소제목 앞에 삽입한다. 링크의 `href`와 라벨은 WordPress escaping 함수를 사용한다. 중복 소제목 ID를 발견하면 TOC를 만들지 않는다.

**#85 한정:** 요약 상자 속 첫 H2 `먼저 기억할 세 가지`를 목차에서 제외하고, 나머지 다섯 H2에 `bloguito-legacy-85-1`부터 `bloguito-legacy-85-5`까지의 고유 앵커를 **출력 시점에만** 부여한다. 원문 구조가 변경되어 H2 개수가 달라지거나 첫 H2가 달라지면 작업하지 않는다. 생성 ID가 다른 요소와 충돌해도 작업하지 않는다. 기존 WordPress `post_content`·DB·슬러그·제목·상태·발췌문은 변경하지 않는다. 이 플러그인은 신규 글의 `editorial_cli.py` 근거·검토 경로와 독립적인 기존 레이아웃 보정이다.

### 현재 원고 기준 적용 대상

| 분류 | 게시물 ID | 수량 |
| --- | --- | ---: |
| 목차 생성 예정 | 70, 85, 99, 101, 103, 105, 113, 119, 121, 125, 127, 137, 139, 140, 144, 145, 163, 217, 220 | 19 |
| 짧은 기존 글: 출력 유지 | 55, 63, 77, 79, 81, 219 | 6 |
| 신규 구조의 자체 목차 유지 | 218, 225, 243, 304, 349 | 5 |

이 허용목록·길이·소제목 임계값은 **현재 30편의 레이아웃 점검 범위를 제한하기 위한 구현 기준**이다. 새 글이나 구형 글 갱신 후에도 목차 필요성을 자동 판정하는 일반 정책으로 간주하지 않는다. 본문을 구조화 원고로 전면 갱신하면 별도 MU 목차는 중복 감지에 따라 작동하지 않아야 하며 배포 시 이를 재확인한다.

## #85 표 두 개의 사전 개선안

**현재 원문:** `https://lifeinfo24.org/review-benefit-guide-20260913/`, 공개 REST `modified=2026-09-18T12:48:58`, 렌더된 본문 SHA256 `9791443dbf4c5c9f43236c034bb4e321f8dc14cc69fed44b7710d7b98cbe644a`. 이 값은 REST의 **출력 HTML 해시**이며 WordPress 저장 `post_content`의 업데이트 안전 해시로 대체하지 않는다.

| 대상 | 현재 구조 | 검토용 변경 |
| --- | --- | --- |
| 표 1: 두 서비스 활용 | 3열, 데이터 2행; caption·scope·가로 스크롤 없음 | `복지멤버십과 보조금24의 역할 및 활용 방법` caption, 열 `scope="col"`, 2개 행 제목 `scope="row"`, 최소 폭 580px 및 스크롤 컨테이너 |
| 표 2: 처음 조회할 때의 점검표 | 3열, 데이터 5행; caption·scope·가로 스크롤 없음 | `혜택 신청 전 확인 항목` caption, 열 `scope="col"`, 5개 행 제목 `scope="row"`, 동일한 스크롤 컨테이너 |

검토용 산출물은 다음 세 개이며 **운영 본문에 적용하지 않았다**.

- `tmp/legacy_audit_20260922/layout-worker2/post85-table-remediation.json`: 교체 전·후 **각 표의 HTML 전체**, 원본 표 해시, 3열 모든 행의 전후 셀 텍스트 목록, 공개 글 ID·수정시각·출력 본문 해시. 원본 두 표만 교체하는 실제 후보다.
- `tmp/legacy_audit_20260922/layout-worker2/post85-table-remediation-preview.html`: 두 교체용 표의 독립적인 로컬 미리보기. 360/390px 및 200% 확대 브라우저 QA는 아직 수행하지 않았다.
- `tmp/legacy_audit_20260922/layout-worker2/build_post85_tables.py`: 공개 REST를 재조회하고 예상 구조(표 2개·3열·각각 2행/5행)를 먼저 검사한 후 검토 파일을 생성하는 읽기 전용 스크립트. 테이블 셀의 전후 텍스트가 일치하지 않으면 중단한다.

교체 후보의 각 표에는 사전에 모바일 좌우 스크롤 힌트, `<div role="region" aria-label="표 제목" tabindex="0">`, `overflow-x:auto`, `<caption>`, 열과 행의 `scope`를 추가했다. 모든 표 행·셀 내용과 순서를 보존하며 `CELL_TEXT_INTACT True`를 확인했다. 표를 새로 해석하거나 복지 자격·금액·신청 가능 여부를 추가하지 않았다. 실게시를 결정할 때는 현재 WordPress 저장 원고 해시·전체 원문 백업·공식 근거와 조건·독립 검토를 다시 확인하고 기존 공개 글의 정상 `update-existing` 절차를 따른다. 표만 바꿀 목적의 직접 WP-CLI 또는 임시 PHP 편집은 사용하지 않는다.

## 검증 결과

1. 로컬 신규 MU 플러그인을 신뢰된 SSH 별칭의 **운영 Docker PHP 8.3.33 표준입력**으로만 보내 `php -l`을 실행했다: `No syntax errors detected in Standard input code`. 서버에 PHP 파일을 생성하거나 설치하지 않았다.
2. 신규 `wordpress/tests/legacy-toc-contract-test.php`를 PHP 표준입력으로 실행해 합성 예제 23개 검사 **통과**. 중복 호출, 기존 TOC 배제, 새 글 배제, 짧은 글 배제, 기존 앵커 보존, HTML 탈출, 중복 ID 차단, #85 요약 제외·5개 앵커·원표 보존, 초안 배제를 포함한다.
3. 공개 REST 실제 30개 본문을 스냅샷으로 저장해 같은 PHP 실행에 입력했다. 실제 30편에 대한 검사까지 합계 **207개 검사 통과**. 정확히 위 19편에 목차 1개가 추가되고, 나머지 11편은 원문과 바이트 단위로 일치했다. 19편 모두 목차 링크가 실제 앵커를 가리키고 반복 렌더링 때 중복되지 않았다. 새 목차를 제거하고 #85에 일시적으로 부여한 ID를 제거하면 19편의 나머지 출력 HTML이 원본과 바이트 단위로 일치한다.
4. #85 표 변경안은 읽기 전용 REST 데이터를 사용하며 표 1의 데이터 2행, 표 2의 데이터 5행, 모든 셀 텍스트가 전후 완전 일치하는 것을 생성 스크립트에서 확인했다.

**미검증:** 운영에 파일을 실제 설치한 뒤의 GeneratePress/플러그인 필터 조합, 360px/390px 화면·200% 확대·키보드 및 보조기술을 이용한 시각/접근성 QA, #85 전체 원고의 공식 출처 최신성 검토. PHP 표준입력 검사만으로 이 항목을 통과했다고 말하지 않는다. 사이트 전체의 정확성·검색 유입·사용자 성과를 보증하지 않는다.

## 이후 설치와 복구 경계

이 단계는 **배포 준비만 완료**했다. 운영 서버 MU 디렉터리의 파일 존재·해시 및 활성 플러그인/테마·현재 공개 30편·원고 해시를 배포 직전에 다시 점검한다. 충돌하는 동일 이름 MU 파일이 있다면 덮어쓰지 않는다. 설치 전 백업·별도 스테이징 검증 후 이 단일 `bloguito-legacy-toc.php` 파일만 전송하고 PHP 문법 검사를 다시 한다. 라이브 신규 5편의 기존 목차 1개 유지, 대상 19편의 새 목차·링크 1:1 관계, 나머지 6편의 무변경, #85 요약·표·모바일 간격을 샘플 및 전수 점검한다. 문제 발생 시 이번에 추가한 TOC MU 파일 **한 개만 제거**하고 기존 녹색 박스 CSS·다른 MU 파일·게시물 데이터·테마 설정은 보존한다. 실행 명령과 전후 관측 결과는 실제 배포 담당자가 날짜별 운영 기록에 추가해야 한다.

**현 상태:** 새 코드·계약 테스트·#85 사본·이 문서만 준비했다. WordPress 게시물 수정/공개, 서버 MU 설치, Git stage/commit/push, 원격 배포는 수행하지 않았다.
