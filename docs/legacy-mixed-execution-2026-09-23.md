# 공개 레거시 혼합 3편 후속 실행 및 차단 증거 (2026-09-23)

## 범위·판정

- 대상은 기존 **공개** `#70` 무명전설 수원앵콜, `#99` 로이킴 서울, `#85` 복지혜택 안내다. `AGENTS.md`, `docs/EDITORIAL_SYSTEM.md`, `agent-publisher/editorial_policy.json`, 9/23 진행 문서, 전날 `full-mixed/post-{70,99,85}` 전체 후보·상태 및 9/22 운영 적용 기록을 확인했다. 원본 bundle·기존 문서·코드·WordPress·서버는 수정하지 않았다.
- **최종 판정: 세 글 모두 아직 `ready` 아님.** 독립 편집 검토 여섯 항목은 사전검사 차단 때문에 호출하지 않았으며 승인/게시 원고로 표시할 수 없다. `tmp/legacy_audit_20260923/mixed2/`의 새 전체 원고·미리보기·기존 저장본문 비교·오늘의 공식 출처 스냅샷만 준비했다. 모델 검토를 임의로 통과 처리하거나 내용 없는 공식 HTTP 200/크롤링 검색 결과를 검증된 본문 SHA로 포장하지 않았다.
- 읽기 전용 SSH `scripts/prepare_post_approval.py:live_post_and_inventory()`로 2026-09-23 09:10 KST 경 현재 WordPress 전체 5개 상태 목록 **39건(공개 29·초안 10), 자기 글 제외 각 38건** 및 대상 저장 원문을 조회했다. 원본과 그 목록의 제목·상태·본문이 일치했다. 전날 저장 `post_content` SHA와 세 ID 모두 동일했다. 외부 공개 REST `content.rendered` 해시와 저장 원본 해시를 혼용하지 않았다. 민감할 수 있는 전체 재고는 `post-{ID}-inventory-live.PRIVATE.json`에만 보관하며 여기에 본문·비공개 제목을 옮기지 않는다. 휴지통 6건은 WordPress의 이 다섯 상태 목록 범위가 아니다.

| ID | 오늘 저장 `post_content` SHA256 | 새 후보 HTML SHA256 | `validate_bundle(..., require_review=False)` | 공식 URL 재조회 가능성 |
|---|---|---|---|---|
| #70 | `fdd2ea772cac2a05a28145afa90cc28fe1754f8c09b28cd49a74dc6e43a5947c` | `adf8754bd7fa8d3cd36365a8cbbb19db3ffce98ed7de7261da61a1cfd5fe3b05` | `availability_not_verified`, `temporal_source_not_bound` | NOL 국내 상품 HTTP 403; 정식 `fetch_sources` 재현 불가 |
| #99 | `4eb6ff1d2bfa5d848030dbefb373ebe56d828cab6da08bb8619912e139a1a90d` | `fdce4a1434883317f21e7cc36225b0474c2d6179807aa2ba99cdc8706ddeba08` | `availability_not_verified`, `number_without_evidence`, `temporal_source_not_bound` | 동일 상품번호 공식 NOL World HTTP 200·본문 해시 일치 반복 |
| #85 | `499afcf30df2cfbfdca7041e80bc139c90e1a8da5d5348837b77ee2b8e2cf065` | `7db7f858cbf5fe957ae01f9334a4e040ec200e7e08e9e9af978797ea005a785c` | `dated_category_cannot_bypass_time_check`만 | 재조회 가능한 공식 정적 자료 5건 전부 원문·SHA 확보 |

위 후보 SHA는 **독립 검토 전의 `render()` 출력**이다. 원본 hash/현 재고·사전검사와 모델 검토까지 포함한 승인용 manifest가 아니며, 갱신 직전 재조회가 필요하다. `final_verify.py`의 공통 CLI 추가 실행은 도구가 안전 상태를 판별하지 못했다는 메시지로 차단되어 **실행 결과 미확보**다. 이를 테스트 통과로 간주하지 않는다. 위 사전검사는 `build_candidates.py`에서 직접 실행한 공통 `validate_bundle()` 호출의 실제 출력이다.

## #70 — 원고 자체 오류 일부 수정, 공식 NOL 403과 판매기간 차단

기존 후보의 `required_title_terms=["2026"]`는 같은 연도를 제목에 쓴 무관한 공개 16건과 비공개 4건을 중복으로 검출했다. 전날 출처·원고를 보존한 새 사본에서 고유 제목 문자열 `무명전설 수원앵콜`로 바꾸니 전체 자기제외 재고에서 중복은 0건이다. `lead`의 떨어진 부분을 임의로 이어 붙인 인용은 실제 연속 원문으로 교체해 `quote_not_in_source`를 해소했다. 구형 수동 출처의 `fetched_at=2026-09-22T14:57:58+09:00`, hash `3097b21ed6ee5347172fcf05d8409929f30864cdd17bb6b2fe5b26cba12f4e3b`는 그대로 보존했으며 **오늘 수집본이라고 바꾸지 않았다**.

현행 `fetch_sources`의 HTTP 200 요구 아래 `https://nol.yanolja.com/ticket/products/26013136`은 9/23 두 차례 직접 GET에서 HTTP **403**·차단 응답 52,618 bytes였다. 동일 상품번호에 대한 NOL World 경로 네 형태는 **모두 404**, 옛 인터파크 경로 역시 404였다. 공식 NOL 국내 개별 상품은 별도 웹 검색에서 12/25 두 회차·좌석 등급·가격·할인·배송·예매 마감 설명이 보였지만, 이 검색 발췌는 로컬 검증기에 입력할 수 있는 재현 가능한 URL 전체 본문·SHA가 아니다. KOPIS 정보를 재게시한 제3자 일정과 공연명만 있는 MBN 과거 전국투어 공지는 수원 12/25의 공식 세부 요금·판매종료를 입증하지 못한다. 웹 열람에서 상품 정보가 보인다는 이유로 구매 가능·재고 있음·현재 판매 중을 적지 않는다.

새 전체 후보: `mixed2/post-70-repaired-source-blocked-unreviewed.json`, 동일 이름 `.html`, `.compare.html`, `.diff.txt`, `.preflight.json`. 새로운 승인에는 **동일 상품의 운영자 제공 공식 본문을 현재 재수집 가능한 출처로 확보**한 뒤 정확한 공식 판매 종료일과 상태 근거를 확보하거나 질문을 일정 소개로 제한하는 정식 검증 경로가 필요하다. 공연일 12/25를 티켓 판매 마지막 날로 바꾸거나 정해지지 않은 공연 일정 예외를 확대하면 안 된다. 별도 여건을 충족하기 전 독립 리뷰는 실행 불가다.

## #99 — 운영자 공식 World 대체 출처 확보, 확인 범위로 전체 원고 축소

원래 국내 `https://nol.yanolja.com/ticket/products/26013078`은 직접 HTTP **403**이었다. 같은 **26013078** 상품번호의 운영자 공식 영어 페이지 `https://world.nol.com/en/ticket/places/26001099/products/26013078`은 09:06·09:08·09:10·09:11에 GET HTTP **200**, 현재 표준 `fetch_sources()` 추출 텍스트 **2,020자**, 매번 동일 SHA256 `6db7501bbcdc2772a232359a0b0e90fce035b9ac5961cfae4f062785cc4b7de8`을 확인했다. 전체 원문 스냅샷 `mixed2/official-source-0.json`을 보존했다.

World 원문에는 2026년 **Nov 21–22**, **KSPO DOME**, **7세 이상**, **VIP 165,000원·R 154,000원**, **9월 16일 팬클럽 선예매**, **9월 17일 20:00 일반 예매 개시**가 실려 있다. 두 회차의 한국시간 시작시각, 회차당 매수, 국내회원 본인 인증, 휠체어석 전화번호, 무통장 납기, 배송일, 일반예매 **종료일/실시간 좌석 상태**는 이 재현 가능한 영문 텍스트에서 확인되지 않는다. 전날 국내 수동 발췌에만 있던 정보는 새 전체 원고에서 모두 제외했다. 페이지의 `General Sale Period ... ~`를 마감일이 있는 기간이나 현재 구매 확정으로 해석하지 않았다. 직접 확인한 링크는 자료 출처이며 주문 화면의 구매 동작 검증은 없어 CTA도 만들지 않았다.

예전 `["2026"]` 제목 필수어를 `로이킴 R:O:Y`로 좁히니 전체 재고 중복 0건이다. 영문 월 `Nov`·`September`를 독자용 한국어 숫자 **11월·9월**로 옮긴 문장에 대해 현행 수치 검증기는 인용에 문자 `11`·`9`가 없다는 `number_without_evidence`를 보고했다. 실제 의미는 공식 영문 날짜와 일치하지만 **검증기는 통과하지 않았으므로 수치 검사 합격으로 표시하지 않는다.** 이 경우만 영문 월·한국어 월의 정확 변환을 증거 단위로 허용하는 좁은 구현·회귀검사 검토를 prime에 제안한다. 판매의 최종 기한/현재 상태 증거는 별도 문제라 그 변환만으로 사전검사를 통과할 수 없다. 기간 라벨 자체가 원문에 `예매기간:` 형태로 표시되지 않아 `temporal_source_not_bound`와 `availability_not_verified`도 발생한다.

새 전체 후보: `mixed2/post-99-world-official-unreviewed.json`과 `.html`, `.compare.html`, `.diff.txt`, `.preflight.json`. 무리한 예외를 허용하지 않으려면 **운영자 원문에 판매 상태와 종료일이 제시되는 실제 상품 페이지**를 별도로 확보해야 한다. 내용 질문을 공연 일정·가격 안내로 좁힐 경우에도 기존 YES24 전용 `schedule_listing_only`를 NOL 상품에 무단 전용하지 말고, ID·URL·시간·판매 주장을 제한한 독립된 좁은 검증 구현과 테스트가 필요한지 prime이 결정해야 한다.

## #85 — 재수집 가능한 근거 5건으로 서비스별 전체 안내 재구성

어제 후보는 정부24 혜택알리미의 첫 화면과 복지로의 카카오톡 알림 변경에 비중을 두어 실제 조회·복지멤버십 가입·개별 사업 신청·접수 확인이 잘 연결되지 않았다. 오늘 공식 원문을 각각 재조회해 자료에 있는 **서로 다른 메뉴 이름**에 따라 전체 구조화 원고를 재구성했다. 공식 근거·인용·숫자·중복 검사는 사전검사에서 모두 해소했지만 서비스 정책 분류 차단은 유지된다. `source_hash_mismatch`, `quote_not_in_source`, `number_without_evidence`, `duplicate_topic`은 새 후보 사전검사에 없다.

| 공식 원자료 | 오늘 `fetch_sources` SHA256 및 근거 범위 |
|---|---|
| [정부24 혜택알리미 홈](https://plus.gov.kr/portal/benefitV2/) | `e173e85e576f0094f6f38dd993dd0bbb41c0eb122d7b5dfb51095b249f510853`; 혜택알리미 및 맞춤/가족 설정·일부 앱 전용 표시 |
| [정부24 나의 혜택](https://plus.gov.kr/portal/benefitV2/myBenefit/) | `74603ec07fd7ae1d49c2f7fe9f0522f737477349533c1e7e8083475490801ac2`; 별도 메뉴의 실제 공개 URL·제목. 로그인 뒤 개인 결과 미검증 |
| [복지로 공식 모바일 사이트맵](https://m.bokjiro.go.kr/ssis-tem/cms/mob/customer/sitemap/index.html) | `ec438f7257b6f19deac22aaaa1e3318df7d7d2a72db3be21705f8e5a55231953`; `복지서비스→서비스 찾기`, `맞춤형급여안내(복지멤버십)`, `서비스 신청→복지급여 신청`, `나의 복지지갑→서비스 신청 현황` **서로 다른 경로** |
| [복지멤버십 2026.4.24 알림 변경 공지](https://m.bokjiro.go.kr/ssis-tem/cms/mob/customer/notice/1309681_1155.html) | `01cd3213fd8fc59b8934a1ba5cf9396e7af7a2a7b6b8e1c9cf48a32f68265c54`; 가입자 대상으로 카카오톡·문자·이메일 및 변경 신청의 정확한 메뉴 |
| [복지로 공식 홍보자료](https://www.bokjiro.go.kr/ssis-tbu/cms/pc/news/promotion/1304825_1118.html) | `d803eaa65aad42596b53b0e5c6bd1534e2676d052a1e067ec10d342899ad17e2`; 가입 신청과 받을 가능성이 있는 서비스 안내를 구분. **게시일 2023년**이므로 현재 동작/UI 세부 기준으로 단독 사용 금지 |

추가로 실제 메뉴 링크의 동작을 검사했다. 복지로 사이트맵 내 `복지서비스 신청`·`복지급여 신청`·`서비스 신청 현황` 링크는 구형 `/ssis-tbm/`에서 `/ssis-tem/`으로 **HTTP 302**, 이동한 대상은 HTTP 200이어도 공통 껍데기 약 2,491 bytes만 보여 `fetch_sources()`가 핵심 내용을 추출하지 못했다. 안내 홍보자료의 “신청 바로가기” 링크도 `href="#"`이다. 이것은 **실제 제출 가능한 최종 신청 URL이 아님**을 확인했으므로 둘을 `sources[].actions`에 억지로 등록하지 않았다. 정부24 개별 서비스 홈페이지는 200이어도 앱 전용 표지가 있어 온라인 개인별 조회·혜택 신청 성공을 주장할 수 없다. 따라서 독자에게 사이트맵에 적힌 *공식 메뉴 경로*와 조회/신청/신청내역의 분기만 설명하고, 미확인 최종 앱 동작·수급 판정을 설명하지 않는다.

참고로 복지로의 [2026-09-21 서비스 중단 공지](https://www.bokjiro.go.kr/ssis-tbu/cms/pc/customer/notice/1310378_1141.html)를 현재 정적 원문 `mixed2/official-source-8.json` 및 SHA `fcb1ea79c40c37b08310500b68694808ebe69f8ab0ddb1bbe26a4c424347b87d`로 별도 확인했다. 이 공지는 **9/27 13:00~9/30 15:00 온라인 신청서의 관할 지자체 전송 중단**, 9/27 및 9/30 로그인 중단 시간과 9/30 15:00 이후 순차 전송을 구별한다. #85의 상시 안내에 이 며칠짜리 운영 제한을 영구 절차나 즉시 제출 완료로 편입하지 않았다. 해당 기간 안에 글을 실제 수정할 경우 별도의 최신 공지·버튼 작동 상태 대조가 필요하다.

새 전체 후보: `mixed2/post-85-service-guide-unreviewed.json`과 `.html`, `.compare.html`, `.diff.txt`, `.preflight.json`. 현행 정책은 `category_key=welfare`와 `content_type=evergreen`의 결합을 일괄 차단한다. 이 글은 특정 지원금의 지급액·신청기간을 안내하는 글이 아니라 반복 가능한 **서비스 탐색 절차**이지만, 단지 통과하려고 다른 카테고리로 위장하거나 `useful_until`을 만들면 안 된다. prime에는 필요한 경우 **기존 공개 #85 단일 ID, `welfare_service_navigation` 상시 절차, 금액·지원대상 확정·접수 중 주장 없음, 자료 최신성·기존 중복·독립 검토 필수**라는 실물 원고 조건에 묶어 분류 정책의 명시적 개정과 테스트를 제안한다. 현행 `update-existing`는 기존 게시물 제목과 검토 계획 제목이 같아야 하므로 원제의 구형 ‘보조금24’ 표현을 현행 ‘혜택알리미’로 바꾸는 제목 정정도 별도 안전한 승인·경쟁검사 경로를 검토해야 한다. 이 작업에서는 제목·slug를 바꾸지 않았다.

## 남은 검토·적용 승인 요건

세 새 bundle을 오늘 실제 자기제외 전체 인벤토리로 `validate_bundle(..., require_review=False)` 실행한 결과는 표에 표시했다. 각 원고의 모든 본문·표 행과 FAQ 인용을 정규 검증기가 검사했지만 **독립 모델 6항목은 세 건 모두 실행 전**이다. 규칙을 우회하지 않는 출처/기간/정책 경로를 해결한 뒤에만 `editorial_cli.py review <scoped bundle> --inventory <private file>`, `check`, 공식 source 즉시 재다운로드 해시 및 실제 WP 원본 `post_content`·제목·상태·전체 재고 새 read-only 사전검사로 승인 패키지를 생성한다. 적용한다면 각 글별 명시 승인 범위에 맞춰 기존 `update-existing`의 전체 백업, 예상 SHA 동시수정 가드, 저장 후 SHA 및 공개 브라우저(비로그인 최초 QA UTM) 검사를 통과해야 한다. 공개 이력·미리보기·로컬 HTML은 실제 운영 반영을 뜻하지 않는다. 이번 담당자는 **WordPress/서버 쓰기, 게시물 상태 변경, Git 커밋/푸시를 실행하지 않았다.**
