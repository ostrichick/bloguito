# Stage 5: 공개 30편 현재 레이아웃 재조사 및 단일 MU 설치·복구 절차 — 2026-09-22

## 기준과 관측 범위

- **최종 재수집 시각: 2026-09-22 16:29:36 KST.** #55·#79·#101·#218·#121·#127·#113·#105·#349의 공개 갱신을 반영해 익명 공개 WordPress REST를 다시 조회했고 `X-WP-Total`과 페이지 수·ID 중복·공개 상태를 검증한 **30/30편의 새 완전 스냅샷**을 만들었다. 현재 기준은 `tmp/legacy_audit_20260922/current-census-worker3-final/public-rest-snapshot.json`; 같은 폴더에 `triage.json`, PHP의 ID별 결과·원문 SHA256을 기록한 `php-current-census.json`, 자동 보고서 `report.md`가 있다. 이전 16:06:57·16:14:21·16:26:26 시점의 `current-census-worker3*` 결과는 변경 이력일 뿐 현재 기준으로 사용하지 않는다. 출력은 모두 Git 제외 **Windows 로컬**에만 저장했다. 수집 뒤 공개 글이 또 수정되면 이 조사 결과는 설치 직전 검증을 대신하지 못한다.
- 기준 로컬 HEAD `c58b7aa`. 시작할 때 여러 작업자의 추적·미추적 파일 변경이 있었다. 이번 작업은 이 새 문서와 Git 제외 조사·QA 산출물만 작성하고 다른 작업 파일·Git·WordPress 게시물·서버 파일·cron을 변경하지 않았다.
- 30편은 기존 전체 대상과 ID가 같지만 내용은 달라졌다. 새 렌더러 `.bloguito-article`이 **13편**(55·79·101·105·113·121·127·137·218·225·243·304·349), 구형 원고가 **17편**(63·70·77·81·85·99·103·119·125·139·140·144·145·163·217·219·220)이다. 자체 `.bloguito-toc`은 새 원고 13편 모두 한 개다. 목차 검사는 `nav` 태그만으로 한정하지 않고 `.bloguito-toc` 클래스를 기준으로 센다.
- 현재 자동 구조 후보는 `legacy_layout=17`, `missing_toc_candidate=17`, `box_paragraph_spacing_candidate=9`, `source_section_missing_candidate=9`, `reader_deflection_candidate=1`이다. `missing_toc_candidate` 17건을 목차 설치 대상 17건으로 해석하면 안 된다. 63·77·81·219 네 편은 현재 TOC 코드의 700자/유효 앵커 조건에서 변경되지 않는다. 과거 15:56 조사(구형 24·목차 후보 24·여백 후보 13), 16:06 조사(20/20/10), 16:14 조사(18/18/10) 및 최초 19편 TOC 계획은 **현재 배포 대상 수가 아니다**.

## 현행 PHP 코드 전체 30편 실행 결과

현재 소스 `wordpress/mu-plugins/bloguito-legacy-toc.php` 및 `bloguito-legacy-table-accessibility.php`를 WordPress 운영 컨테이너 **PHP 8.3 표준입력으로만** 보냈다. WordPress를 부트스트랩하거나 서버 경로에 PHP를 쓰지 않고, 최종 16:29 REST의 `content.rendered` 전체 30개를 PHP의 기존 순수 변환 함수에 공급했다. **147개 동적 검사 통과:** 목차 중복 배제, 변환 후 재호출 멱등성, 추가한 목차 안 각 `href`에 대해 결과 HTML의 해당 ID가 정확히 한 번 존재하는지, #85만 표 변환되는지를 확인했다. 다른 WordPress 필터·테마·페이지 캐시가 결합된 실제 운영 결과 검사는 **아직 미적용이므로 불가**하다.

- TOC **추가 13편:** `70, 85, 99, 103, 119, 125, 139, 140, 144, 145, 163, 217, 220`.
- TOC **원문 그대로 17편:** `55, 63, 77, 79, 81, 101, 105, 113, 121, 127, 137, 218, 219, 225, 243, 304, 349`. 새 구조 13편 모두 원래 자체 목차를 보존했다. 추가된 13편 모두 두 번째 호출에서 무변경·목차 앵커 고유성을 통과했다.
- #85 전용 표 플러그인은 현재 REST 출력 단독 또는 TOC 추가 출력에서 **#85만 변경**, 다른 29편은 바이트 단위 무변경. 표의 셀 텍스트와 순서·2개 표의 헤더 6개/행 헤더 7개·캡션 2개·키보드 스크롤 영역을 확인하는 별도 현행 fixture 계약 검사 **101건 통과**.

| ID | 현재 구조 | REST `content.rendered` SHA256 | TOC 예상(링크 수) | 녹색 상자 CSS 일치 | #85 표 MU |
| ---: | --- | --- | --- | ---: | --- |
| 55 | 신규 | `fbc091e4a48ebd27a39ea67a01b6c7b7f3019eaed2c593560eeee4e33e09519f` | 유지 | 0 | 유지 |
| 63 | 구형 | `d6c376ea6c368a549bb7e82417eeb2d2e4ca456fd1901d033703dde1ece0c393` | 유지(짧음) | 1 | 유지 |
| 70 | 구형 | `4cd5e542765945a79d101446c66be500cfb09f69e3900b766334cb8a055bbe37` | 추가(4) | 1 | 유지 |
| 77 | 구형 | `90933552177d370fcaf90381a2636915cb669b841ea476f976f6e12a8e7bdca8` | 유지(짧음) | 1 | 유지 |
| 79 | 신규 | `b6500496ea0c8393a3be402897960494c0ea2b6c315970e2f14dff5a8186c91b` | 유지 | 0 | 유지 |
| 81 | 구형 | `6d978386806cbf22432673624438254c449e1c3503b140b562e8b2191d126fd0` | 유지(짧음) | 1 | 유지 |
| 85 | 구형 | `9791443dbf4c5c9f43236c034bb4e321f8dc14cc69fed44b7710d7b98cbe644a` | 추가(5) | 0 | 두 표 보정 |
| 99 | 구형 | `37c9d53d8681071592d2d00515669720354a9e0a81e56aac3f96bf0b7a21e0af` | 추가(4) | 1 | 유지 |
| 101 | 신규 | `4695d7c449089e344372520067952dc3fa0324f8111516481ffd387d413b88c1` | 유지 | 0 | 유지 |
| 103 | 구형 | `67d727bf6c02d527eea2b303d424a5e687b3f40e9c5b3db1c119f3921224a2b1` | 추가(3) | 1 | 유지 |
| 105 | 신규 | `6bc5bc1284a1cd129857cf42dd75361d814c0dfded7b4204fe893394261172c9` | 유지 | 0 | 유지 |
| 113 | 신규 | `95f8dd7133170a2de4808a6b5ce8e293462babcf14c9af26be92d642fc4d416e` | 유지 | 0 | 유지 |
| 119 | 구형 | `f706bf9b1c5a9e208751095291ae6b692ad0159dc0bf55f1c3317b77d7dbe4ba` | 추가(4) | 1 | 유지 |
| 121 | 신규 | `37b224f1e371cb63ab484742bfa67865cb1e3f13b49e3bd11ddfe3e2529c46ce` | 유지 | 0 | 유지 |
| 125 | 구형 | `3c1ba1957ce1586764d9f2f1e9d2f36fca93b760d20dfe2dcc03dedb99e1e8b2` | 추가(4) | 1 | 유지 |
| 127 | 신규 | `deec264d395c5e530f6ec7a2a30f7eafd0d16ff695f009e38e158369141bb2f2` | 유지 | 0 | 유지 |
| 137 | 신규 | `29db9533d315b7cdc47873ce75ed19b4b9fde3be342708c27d3c15e77e8b5642` | 유지 | 0 | 유지 |
| 139 | 구형 | `8d8b1b144dab3d61fa3b705b792d53063fc8b1b2e528d724f95cf8330e557244` | 추가(6) | 1 | 유지 |
| 140 | 구형 | `2715439bb4c752ad2adfbca1a332752c853f2eb074935259041292b76bab2773` | 추가(4) | 1 | 유지 |
| 144 | 구형 | `0dc64c70a43689090907714bc7c4c8d766371db6dfc0d5ce98ab0483487f9dab` | 추가(4) | 1 | 유지 |
| 145 | 구형 | `a34dfdd65b5e002895cd977695338f83f3e26f27b1759630a3877ca4eb6a31d0` | 추가(4) | 1 | 유지 |
| 163 | 구형 | `e2e589283dd5f1c8d9566e3b5518c60216712bacab6df8fcd232369e06bf9021` | 추가(4) | 1 | 유지 |
| 217 | 구형 | `a289aa7094c8c71faf0b22133ce5c304e64bceae413f7d9cc612f7e3fd233a7b` | 추가(4) | 1 | 유지 |
| 218 | 신규 | `44db4e1d2a413ce31ce4c346cf7f977955ce53c4cb9081ca3c6303c4cca7a4d8` | 유지 | 0 | 유지 |
| 219 | 구형 | `47912e9b8c6519a2ed83c007305ad9aa67f1a23802f4528cd622509de990a18a` | 유지(짧음) | 1 | 유지 |
| 220 | 구형 | `a3d2b602a2f630fc8509169eca26018a6130ff8c5ed41dbcc4c82ec40e71ccfa` | 추가(3) | 1 | 유지 |
| 225 | 신규 | `cdaaecec0d0c9cc381b7677cfaa5a49f19e71a202c6609640f596925ee6cc80d` | 유지 | 0 | 유지 |
| 243 | 신규 | `bac33da86d23c70c651d06aaeebd7204cbc2484e6d8e9c7ac7ec28dc62a553ea` | 유지 | 0 | 유지 |
| 304 | 신규 | `fbb0665d55ad20413ac4b6ee6fea2f55f9d401912d7834d469a58d69070ae566` | 유지 | 0 | 유지 |
| 349 | 신규 | `53633a680c14d6ae4918695c05c3b95e588f96e27c0e35ed516b9f01533a345a` | 유지 | 0 | 유지 |

위 SHA는 전부 **REST 출력 HTML** 해시다. 게시물 갱신 명령에 필요한 WordPress 저장 `post_content` SHA와 혼용하지 않는다. #85의 경우에는 저장본도 별도 read-only WP-CLI `wp post get 85 --format=json`으로 당일 다시 조회하여 `post_status=publish`, `post_modified=2026-09-18 12:48:58`, **7,646 UTF-8 bytes**, 저장 SHA `499afcf30df2cfbfdca7041e80bc139c90e1a8da5d5348837b77ee2b8e2cf065`, 표 2개를 확인했다. 정확한 TOC 이후 출력 SHA `0b5ae88f3a60e5a7958806f7e1861e8c8525ddbe94d47ba33d9f390118e375f3` 역시 표 MU의 기존 허용 지문과 일치했다. WordPress가 실제 페이지 필터 체인에서 전달하는 문자열은 배포 후 별도 확인해야 한다.

## 현재 CSS 선택자와 설치 상태

녹색 상자 파일 `bloguito-legacy-callout-spacing.php`의 선택자는 `.entry-content div[style*="border-left"][style*="#11775a"] > p` 및 `> p:empty`다. 공개 REST HTML을 파싱하여 정확한 좌측 테두리 스타일을 가진 `div`를 다시 셌더니 **16편의 16개 상자**만 일치한다: `63,70,77,81,99,103,119,125,139,140,144,145,163,217,219,220`. 나머지 14편은 일치 0(#85의 `#147d64` 상자 및 신규 요약 13편 포함). 그중 하단 문단 여백이 인라인으로 별도 지정되지 않은 대상 **9편**은 `70,99,119,140,144,145,163,217,220`이다. HTML 파서별 잘못된 `</p>` 복구 결과와 CSS `p:empty`의 실제 적용/화면 높이는 운영 파일을 설치한 뒤 브라우저에서 확인해야 한다. CSS는 저장된 잘못된 HTML을 수정하지 않는다.

실제 서버 `wordpress_app:/var/www/html/wp-content/mu-plugins/`에는 **`bloguito-post-id-column.php`와 `bloguito-social-share.php` 두 파일만** 있고 이번 신규 TOC·상자·표 PHP 세 파일은 모두 없다. 기존 두 파일의 운영 SHA는 각각 `6e3c383122341d37c0a1921a4c0cc62bf1d82b964775e52b459f2d478d6d47cd` 및 `5e57c16a2f47e98ca24cfba766174ea0a1429138dce92670afb610fe4aa2f00e`로 이전 조사와 같다. LuckyWP 목차는 `inactive`, WP Super Cache는 `active`이고 `advanced-cache.php` drop-in이 있다. 소스 SHA는 TOC `6240c15ffe527665cacc7fd773944374a9cd7533f9a4c563206b99c4d2fedcdb`, CSS `c9bae087d11eeb50ece97055fca99ed315a660730757063320eda908faaeba4b`, #85 표 `afe44b8ec982c8f2856506ea41d6f3edf5bd1511e9fc856aa4a85c1f0a683f5f`이다.

## 재검증

- 운영 PHP 8.3 `php -l`을 각 파일의 **표준입력**으로 3회 실행하여 모두 `No syntax errors detected in Standard input code`/종료 0.
- 소스 삽입 방식의 기존 `wordpress/tests/legacy-toc-contract-test.php`: **23건 통과**. 신규 30편 fixture로 다시 실행한 `wordpress/tests/legacy-table85-accessibility-test.php`: **101건 통과**, #85만 변경/다른 29편 그대로, #85 저장본·REST 및 TOC 전후 4개 문자열의 지문 일치, 셀/캡션/헤더/멱등성·변조 차단.
- `python -B -m unittest discover -s agent-publisher/tests -p test_legacy_post_audit.py -q`: **14건 통과, 종료 0**.
- 같은 격리 Edge 프로필/포트 `9237`을 재사용하여 최종 라이브 `node tmp/legacy_audit_20260922/liveqa-live-posts.mjs 137 55 79 101 113 121 105 218 243 127 349` 실행: **11 ID × 3화면=33/33 자동 구조 조건 통과**(360·390·1280 CSS 200% 근사). 모두 목차 하나·앵커 유효·가로 넘침/확인 대상 이미지 파손 0, #137 표 3개·#349 표 1개 구조 검사 포함. 원시 증거 `tmp/legacy_audit_20260922/liveqa-results.json`과 `live-<ID>-360.png`, `live-<ID>-390.png`. 브라우저 콘솔 자원 오류 기록은 **13건**이므로 콘솔 오류 0이라고 주장하지 않는다. 이 검사기의 PASS는 CTA 도착지 확인을 포함하지 않는다. 목차·CSS·#85 MU **실설치 이후** 브라우저 QA는 아직 시행하지 않았다.
- `live-79-360.png`, `live-101-360.png`를 실제 이미지로 추가 열어보니 양쪽 모두 대표 이미지·제목·날짜와 공유 영역이 겹치거나 잘리지 않았다. 큰 제목이 모바일 첫 화면 상당 부분을 차지해 핵심 답변은 아래로 밀리는 현상은 남는다. 이 관찰을 서식 전체 또는 본문 끝까지의 육안 통과로 확대하지 않는다.
- **별도 실제 CTA 실패:** #218의 새 CTA `내보험찾아줌 조회신청 안내·진입` URL `https://cont.insure.or.kr/cont_web/information/information.do`를 동일 격리 Edge에서 직접 열었으나, `https://cont.insure.or.kr/cont_web/common/404.jsp`로 이동하여 협회 화면에 `페이지를 찾을 수 없습니다`와 `(evfw_AD)`가 표시됐다. 인증이나 신청은 누르지 않았고 브라우저는 Bloguito QA UTM으로 돌렸다. **이 CTA는 실제 진입 경로로 합격 처리하면 안 된다.** 구조 27/27 PASS와 별도로 링크 재조사·검증 및 정상 편집 검사가 필요한 실서비스 결함이다. 앞서 확보한 HTTP GET/리디렉션 사실은 이 브라우저 404를 반박하지 않는다.
- 같은 격리 Edge에서 위 CTA의 대체 후보인 `https://cont.insure.or.kr/cont_web/` 루트와 `https://cont.insure.or.kr/cont_web/intro.do`를 실제로 별도 내비게이션했으나 **둘 다 동일 `/cont_web/common/404.jsp` 화면**이었다. 이 세 후보 중 현재 브라우저에서 검증한 정상 조회 진입 URL은 **0개**다. 이 현상은 현재 QA 브라우저 관측이며 모든 사용자 환경의 장애라고 일반화하지 않는다.
- **네이티브 확대 한계 재검증:** 라이브 #101에서 기존 Edge DevTools의 `Input.dispatchKeyEvent`로 `Ctrl`+`+`를 한 번 보내기 전후 `devicePixelRatio=1`, `innerWidth=756`, `visualViewport.width=741`, `visualViewport.scale=1`이 모두 같았다. `Ctrl`+`0` 초기화 뒤에도 동일했다. 이 입력은 실제 브라우저 확대를 발생시키지 않았으므로 **네이티브 200% 확대 통과는 미검증**이다. CSS `zoom:200%`와 혼용하지 않는다. #101 점검 뒤 QA UTM으로 탭을 되돌렸다.
- #85의 **동일한 지문으로 생성된 실제 PHP 목차+표 로컬 미리보기** `tmp/legacy_audit_20260922/layout-worker2/post85-runtime-mu-preview.html`을 기존 Edge 한 개로 다시 검사했다. `browser_table85_runtime_qa.mjs` 종료 0: 360·390·1280 CSS 200% 근사 모두 구조 PASS, 목차 5개 유효 앵커, 표 2개 각각 3개 열머리글/2·5개 행머리글, 360px에서 키보드 방향키로 수평 260px, 390px에서 230px 이동. 화면 자료는 `qa-post85-runtime-360.png`, `qa-post85-runtime-390.png`, `qa-post85-runtime-1280-200css.png`, 상세 JSON `post85-runtime-browser-results.json`이며 콘솔에 차단된 리소스 오류 1건이 있다. 실제 200% 브라우저 확대·운영 설치 후 페이지 동작·스크린리더 인증과는 별개다. 테스트 후 단일 QA 탭을 UTM 시작 주소로 복귀시켰다.

### 최종 전수 스냅샷에 반영한 게시물별 브라우저 QA와 남은 결함

아래 게시물별 재조회·실제 행동 링크 점검은 모두 위 **16:29:36 KST 최종 30편 스냅샷에 반영된 원고 버전**에서 수행했다. URL 도착 실패와 성공은 서로 구분하며, 설치 직전에는 **30편 전체**를 다시 수집하여 적용 대상과 SHA를 한 시점의 자료로 확정해야 한다.

- #218은 후속 승인된 갱신으로 2026-09-22 **16:20:23**에 다시 수정됐다. 공개 REST 재조회 시 `content.rendered` SHA는 `44db4e1d2a413ce31ce4c346cf7f977955ce53c4cb9081ca3c6303c4cca7a4d8`; 현재 격리 Edge에서 `.entry-content .bloguito-cta a` **0개**, 목차 1개, 360·390·1280 세 상태 구조 검사 모두 PASS(로그 오류 3건). 위 본문의 #218 CTA 실패는 **이전 버전**에 대한 관측이다. 다만 협회의 404 URL `https://cont.insure.or.kr/cont_web/information/information.do`가 현재 게시물의 **공식 출처 목록 `<ul class="source-list">`에 링크로 정확히 1개 남아 있음**을 같은 Edge DOM과 공개 REST에서 다시 확인했다. 행동 버튼 제거만으로 깨진 출처 링크까지 해결됐다고 주장하지 않는다. 정확한 공식 목적지의 독립 검증과 전체 승인 bundle 갱신 전까지 이 링크가 확인된 작동 링크라고 표시하지 않는다.
- #121은 2026-09-22 **16:22:22**에 후속 수정으로 실제 CTA가 들어갔다. 공개 REST 출력 SHA `37b224f1e371cb63ab484742bfa67865cb1e3f13b49e3bd11ddfe3e2529c46ce`. 같은 격리 Edge에서 `liveqa-live-posts.mjs 121`의 **360·390·1280 세 상태 모두 구조 PASS**, 현재 CTA `정부24 등본·초본 신청 안내·진입`이 정확히 하나이며 연결 URL은 `https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=13100000015`다. 실제 브라우저로 이 URL에 이동해 같은 정부24 URL의 `주민등록표 등본(초본) 발급 | 민원안내 및 신청 | 정부24` 페이지가 완전 로드됐고, 인터넷 무료·온라인 대리 신청 불가가 안내된 것을 확인했다. 인증·서류 발급·신청 제출은 하지 않았다. 마지막에 동일 QA 탭을 Bloguito UTM 시작 URL로 복귀시켰다.
- #127은 2026-09-22 **16:23:17**에 구형 원고에서 신규 구조로 갱신됐다. 현재 REST 출력 SHA `deec264d395c5e530f6ec7a2a30f7eafd0d16ff695f009e38e158369141bb2f2`. 동일 Edge에서 360·390·1280 구조 검사 **3/3 PASS**, 목차 1개·앵커 6개 모두 유효, 가로 넘침·확인 대상 이미지 파손 0, 콘솔 차단 자원 3건. CTA는 **0개**이며 본문 말미 공식 출처에 `https://mob.tbht.hometax.go.kr/jsonAction.do?actionId=UTBRDAAA03F001` 한 링크가 있다. 이 URL을 직접 열자 국세청 홈택스 `https://hometax.go.kr/websquare/websquare.html?w2xPath=/ui/pp/index_pp.xml&menuCd=index3` **메인 화면**으로 이동했고 5초 뒤 `종합소득세 기한후 환급신고` 메뉴 등은 보였으나 원고가 설명한 **국세환급금찾기 조회 입력 화면은 확인되지 않았다**. 개인 정보 입력·인증·신고는 하지 않았다. 이 주소를 확인된 직접 조회 CTA라고 표시할 수 없다.
- #105의 새 CTA는 `5개 이상 폐가전 방문수거 예약` → `https://survey.15990903.or.kr/portal/reserve/reserve.do` 한 개다. 해당 페이지를 동일 Edge에서 실제 방문했으며 URL 유지, 제목 `폐가전 무상 방문수거`, 본문 `무상방문수거신청` 메뉴 확인, 404 없음. #113의 새 CTA는 `인터넷우체국 주거이전 신청·연장` → `https://service.epost.go.kr/front.RetrieveAddressMoveInfo.postal` 한 개다. 동일 Edge 실제 도착 페이지 제목 `우편>부가서비스>주거이전서비스 신청/결제/취소`, 온라인 개인고객 신청·사업자 고객 우체국 방문 안내, 404 없음. 두 글 각각 360·390·1280 구조 검사 3/3 PASS. 신청 접수·개인정보 제출은 하지 않았다.
- #349 최종 v2는 실제 CTA `지역별 공연 일정·상품 목록` → `https://m.ticket.yes24.com/Genre/GenreBridge.aspx?genre=15456&id=1560` 한 개다. 같은 Edge에서 YES24 목록이 정상 로드되고 본문 표 **대구 10월 10일·전주 10월 31일·광주 12월 5일·고양 12월 26일**의 네 도시·날짜·공연장과 공식 목록의 네 행이 일치하며 도시별 `예매` 버튼이 보이는 것을 확인했다. 360·390·1280 구조 검사 3/3 PASS, 목차 1개·표 1개 접근성 구조 PASS. 개별 상품 상세나 잔여석·결제 가능 여부는 확인하거나 단정하지 않는다.
- 최종 11편×3화면 검사는 위 전체 재검증 항목과 `tmp/legacy_audit_20260922/liveqa-results.json`에 묶었다. 후속 개별 실행에서 동일 JSON 파일이 덮어써질 수 있으므로 **실행 시각·대상 ID 배열·검사 결과**를 함께 확인하고, 옛 파일을 최신 전수 검사 결과라고 오인하지 않는다.

## 향후 승인된 *한 개* MU만 설치하는 정확한 절차(이번에 실행하지 않음)

설치 직전 현재 30편 REST를 **다시 수집**하고 13개 TOC 변경 ID·16개 녹색 상자·#85 저장/출력 SHA·운영 MU 파일 목록·기존 두 SHA를 대조한다. 다른 작업자의 게시물 갱신이 있으면 변경 수와 대상 ID를 다시 계산하고 승인 범위와 대조한다. 승인 범위가 13편보다 좁으면 현재 TOC 소스를 그대로 설치하면 안 되며 ID 허용목록을 승인된 범위로 좁혀 재검증한다. 읽기 전용으로 백업 파일 존재와 v3 `restore_backup.sh <archive> --verify-only`의 무결성을 확인하고, 문제 발생 시 개별 파일만 되돌릴 백업·캐시 처리 담당을 확정한다. 전체 복원 스크립트·`wordpress/setup.sh`·`install_editorial_release.py`·Compose 재생성을 단일 MU 설치에 사용하지 않는다.

다음은 **TOC 파일 하나**에 대한 설치 문법 예다. 실제 설치 책임자가 승인 후 Windows PowerShell 프로젝트 루트에서 파일 SHA를 확인하고 고유한 호스트 staging 이름을 생성한다. `scp`는 서버에 파일을 쓰므로 이번 읽기 전용 단계에서는 **실행 금지**.

```powershell
$name = 'bloguito-legacy-toc.php'
$expected = '6240c15ffe527665cacc7fd773944374a9cd7533f9a4c563206b99c4d2fedcdb'
$source = (Resolve-Path "wordpress/mu-plugins/$name").Path
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Local SHA changed' }
$token = [guid]::NewGuid().ToString('N')
$stageName = "bloguito-mu-$token.stage"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes bloguito sudo docker exec wordpress_app test ! -e "/var/www/html/wp-content/mu-plugins/$name"
if ($LASTEXITCODE -ne 0) { throw 'Live target already exists or check failed' }
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes bloguito test ! -e "/home/ubuntu/$stageName"
if ($LASTEXITCODE -ne 0) { throw 'Host staging path exists or check failed' }
scp -o BatchMode=yes -o StrictHostKeyChecking=yes $source "bloguito:/home/ubuntu/$stageName"
if ($LASTEXITCODE -ne 0) { throw 'Host staging copy failed' }
Write-Host "Copy these exact values into the SSH shell: token=$token stageName=$stageName"
```

승인된 담당자가 `ssh -t bloguito`로 Ubuntu 셸에 접속해 아래 `token`을 PowerShell 출력값으로 **정확히 바꿔** 한 파일씩 실행한다. `.stage`는 `.php` 확장자로 끝나지 않아 WordPress MU 로더에 잡히지 않는다. 저장 위치는 소스 폴더 `/home/ubuntu/wordpress`가 아니라 실제 운영 named volume 안이다. 동일 대상 파일 존재·중간 파일 존재·SHA·PHP 문법 중 하나라도 불일치하면 최종 연결 전에 중단한다. 같은 디렉터리 내 `ln`은 목적지가 있으면 실패하므로 기존 MU를 덮어쓰지 않는다.

```bash
set -eu
name=bloguito-legacy-toc.php
expected=6240c15ffe527665cacc7fd773944374a9cd7533f9a4c563206b99c4d2fedcdb
token=REPLACE_WITH_POWERSHELL_TOKEN
host_stage="/home/ubuntu/bloguito-mu-${token}.stage"
mu=/var/www/html/wp-content/mu-plugins
target="$mu/$name"
hidden="$mu/.${name}.${token}.stage"
test -f "$host_stage" && test ! -L "$host_stage"
test "$(sha256sum "$host_stage" | cut -d ' ' -f1)" = "$expected"
sudo docker exec wordpress_app test ! -e "$target"
sudo docker exec wordpress_app test ! -e "$hidden"
sudo docker cp "$host_stage" "wordpress_app:$hidden"
sudo docker exec wordpress_app chmod 644 "$hidden"
sudo docker exec wordpress_app php -l "$hidden"
test "$(sudo docker exec wordpress_app sha256sum "$hidden" | cut -d ' ' -f1)" = "$expected"
sudo docker exec wordpress_app sh -c 'test ! -e "$1" && ln "$2" "$1" && rm "$2"' sh "$target" "$hidden"
sudo docker exec wordpress_app sha256sum "$target"
```

위 단계의 `ln`이 파일시스템 정책상 실패하면 대상 파일을 억지로 덮지 말고 숨김 staging 파일만 보존·상태 확인 후 대체 승인 경로를 설계한다. 설치 직후 서버의 MU 목록·파일 SHA, `wp plugin list`의 `must-use`, 캐시 상태를 확인하고 비로그인 QA UTM으로 진입하여 13편의 목차 추가/나머지 17편 무변경, 앵커 1:1, #85 표 보존 및 360/390/확대 화면을 검사한다. WP Super Cache 실제 HTML이 구버전이면 승인된 운영자의 정확한 페이지 캐시 비우기 절차를 사용하고 같은 URL을 다시 검사한다. `wp cache flush`만으로 전체 페이지 캐시가 제거된다고 가정하지 않는다. **이 단계의 공개 검증을 완료하기 전 다음 MU 파일을 연속 설치하지 않는다.**

CSS를 따로 승인받았다면 위 명령의 `$name`/`name`과 `$expected`/`expected`를 `bloguito-legacy-callout-spacing.php` 및 `c9bae087d11eeb50ece97055fca99ed315a660730757063320eda908faaeba4b`로 바꿔 **별도 한 파일**만 배포하고 녹색 16편/비대상 14편, 특히 #85·신규 요약의 선택자 미적용을 실제 HTML·브라우저로 확인한다. #85 표 MU는 `bloguito-legacy-table-accessibility.php`와 `afe44b8ec982c8f2856506ea41d6f3edf5bd1511e9fc856aa4a85c1f0a683f5f`를 사용한다. 적용 전 #85 저장/REST 지문과 TOC 유무에 따른 허용 지문을 다시 비교하고 **#85 두 표만** caption·scope·`role=region`·`tabindex=0`·키보드 수평 이동이 보이는지 확인한다. 출력 필터는 SHA가 달라지면 조용히 무변경 처리하므로 설치 파일의 존재만으로 개선 적용을 주장하지 않는다.

## 한 파일만 복구하는 정확한 절차(이번에 실행하지 않음)

문제가 생기면 해당 파일의 실제 SHA가 승인 때의 `$expected`와 일치하는지 먼저 확인하고 같은 설치 `token`으로 **WordPress MU 로더가 읽지 않는 숨김 `.disabled` 이름**에만 이동한다. 이 예는 TOC 파일 한 개만 비활성화하며 #85 표/CSS·기존 MU·DB·다른 작업자의 코드는 유지한다. SHA 불일치 또는 비활성화 목적지 존재 시 멈춰 다른 변경을 보호한다. 비활성화 후 페이지 캐시 확인과 30편에서 새 목차가 빠졌는지 검증한다.

```bash
set -eu
name=bloguito-legacy-toc.php
expected=6240c15ffe527665cacc7fd773944374a9cd7533f9a4c563206b99c4d2fedcdb
token=REPLACE_WITH_SAME_INSTALL_TOKEN
mu=/var/www/html/wp-content/mu-plugins
sudo docker exec wordpress_app sh -c '
  set -eu
  installed="$1"; disabled="$2"; expected="$3"
  test -f "$installed" && test ! -L "$installed" && test ! -e "$disabled"
  current=$(sha256sum "$installed" | cut -d " " -f1)
  test "$current" = "$expected"
  mv "$installed" "$disabled"
' sh "$mu/$name" "$mu/.${name}.${token}.disabled" "$expected"
```

문서에 적은 위 두 `bash` 명령 블록을 각각 신뢰된 SSH 별칭의 서버 `bash -n` **표준입력**으로 보내 문법 검사 2/2 통과했다. 이는 명령 본문을 실행하지 않는 문법 검사이며 설치·복구 성공 여부를 뜻하지 않는다. 이 보고서의 명령은 향후 운영 담당자의 검토용이며 이번 작업에서 `scp`·`docker cp`·`ln`·`mv`·`chmod`·캐시 삭제·WP-CLI 쓰기·cron 변경을 **어느 것도 실행하지 않았다**. 전수 실제 콘텐츠 정확성, 실사용 보조기술/네이티브 200% 확대, 신규 MU 설치 후의 테마·캐시 결합 동작은 여전히 미검증이다.
