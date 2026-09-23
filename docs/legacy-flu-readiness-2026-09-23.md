# #63·#81 독감 기존 글 재작성 후보 재검증 및 사전검토 인계 — 2026-09-23

## 범위와 판정

`#63`(어린이·임신부·65세 이상 종합)과 `#81`(어르신 연령별 시작일)의 2026-09-22 전체 교체 번들을 **격리 복사**하고, 오늘 질병관리청 공식 문서 재조회, 실제 운영 WordPress 전체 재고 읽기, 현재 공통 사전검사 및 근거 결속을 재검증했다. 기존 번들·코드·WordPress를 이 담당자가 수정하지 않았고, 공개 적용·독립 모델 검토·Git 커밋/푸시는 실행하지 않았다. 다른 작업자가 작업 중인 파일은 보존했다.

**최신 결과(2026-09-23 08:54:09 KST):** 아래 두 `*-season-unreviewed.json`을 당일 전체 운영 재고 39건과 함께 `validate_bundle(..., require_review=False)`에 넣었을 때 모두 `ready`, 사유 `[]`, 세부 오류 `[]`. 이 판정은 **독립 모델 검토를 시작할 수 있는 사전검사 통과**이며 최종 편집 승인 또는 사용자 승인·운영 반영을 뜻하지 않는다. 번들에는 `review`가 없고 `brief.reviewed_at=2026-09-22`, `brief.review_until=2026-09-23`은 연장하지 않았다.

| 게시물 | 9/23 재조회 후 시즌 근거 추가 번들 | 기존 WP 저장 본문 SHA-256 | 현재 제안 HTML SHA-256 |
| --- | --- | --- | --- |
| #63 | `tmp/legacy_audit_20260923/worker-flu/post-63-season-unreviewed.json` | `b1d573c15629315caa470d7dde855c39b67cbc571e7d405121c36583f447fc21` | `5bab1acb8071ce568d299334bf7e5066bfdd3cbba6191c50341d4df0a22b3154` |
| #81 | `tmp/legacy_audit_20260923/worker-flu/post-81-season-unreviewed.json` | `999f28c919dbd9f51cf9869cdb47a909aaa6fa69728bb23bab0e953d1d0ed3e2` | `ac38e8ee1fa52406eecda5f593de6551f83b51f9562fd53b745f8f55c458d317` |

원본 WP 본문 해시는 9/22 비공개 백업과 **9/23 08:52 직접 읽기 전용 `wp post get`** 결과 모두 동일했다. 제목도 각 기존 기록과 일치했다. HTML SHA는 오늘 현재 `render()`의 미검토 제안값이므로 모델 검토 뒤 변경되면 다시 계산해야 한다.

## 공식 자료와 안전한 편집 근거

- 공식 s0: 질병관리청 **2026-09-16 일정 변경 보도자료 PDF**, `https://www.kdca.go.kr/bbs/kdca/42/309764/download.do`. 9/23 08:51:43 KST 현행 `fetch_sources()`로 PDF를 다시 요청하고 페이지 구분을 유지하여 텍스트를 추출했다. 본문 SHA-256 `78458521307aee8c6bc87549963e7588d9f8e909d53a2b884b57c34ac32f9325`: 9/22 번들과 **텍스트까지 동일**. 어린이 1회 대상 9/28→9/21, 모든 어린이·임신부 9/21 시작, 어르신 75세 이상 10/6·70~74세 10/12·65~69세 10/15, 해당 어르신 고위험군 의료진 상담 후 10/6 예외를 설명한다. 이 PDF 추출 본문은 **전체 사업 종료일 2027-04-30을 명시하지 않는다**.
- 공식 s1: 질병관리청 **2026-08-25 원 발표**, `https://www.kdca.go.kr/bbs/kdca/42/312308/artclView.do`. 9/23 08:51:44 KST 직접 재조회 결과 SHA-256 `8c161eafdeac8ca62a7f31fab6344adec1623e1149dc2954fe38fb873988d4ae`: 9/22 번들과 텍스트 동일. 본문에는 국가 접종사업이 **2026-09-21부터 2027-04-30까지**라는 연속 문장이 있다. 어린이 지원 출생 범위·2회 대상·백신 3가 등 s0과 충돌하지 않는 정보에만 사용한다. s1에 있는 어린이 1회 9/28, 어르신 구 시작일은 **s0에 의해 변경된 과거 일정이므로 인용해 현재 일정으로 사용하지 않는다**.
- 재조회한 s1의 HTML `<title>`이 일반 문구 `검색관련문의`인 문제를 확인하고, 동일 공식 HTML 본문에 실제로 존재하는 기사 표제를 `sources[1].title`에만 반영했다. 다른 문장·원고·`reviewed_at`·공식 출처 URL·SHA는 건드리지 않았다. 제목 교정은 출처 본문 해시 변경이 아니다.
- 질병관리청 `https://cert.kdca.go.kr/irhp/infm/goVcntInfo.do?menuCd=134&menuLv=1`에서 웹으로 각 접종군의 종료일까지 포함한 표가 보였지만, 현 프로젝트의 `fetch_sources()`로 9/23 직접 요청 시 `SSLError: UNSAFE_LEGACY_RENEGOTIATION_DISABLED`가 발생했다. 사이트 머리말 최종검토일도 8/25이며 과거 절기 자료가 같은 페이지 아래에 혼재한다. 따라서 이를 새 번들 증거로 추가하지 않았다. `nip.kdca.go.kr` 직접 행동 링크도 앞선 동일 TLS 실패가 있으므로 확인되지 않은 CTA를 만들지 않았다.

적용기간 검사는 `agent-publisher/agents/temporal_validation.py`의 기존 게시물 ID #63·#81 전용 `national_flu_season` 분기를 사용한다. 실제 8/25 원문의 전체 기간 **연속 인용**과 9/16 PDF의 어린이 변경 표제·어르신 세 연령대 **정확한 연속 인용**을 다른 출처 ID로 연결했다. 날짜는 `start_date=2026-09-21`, `end_date=useful_until=2027-04-30`으로 원문 범위와 일치한다. 상용 예약·실시간 백신 보유량·모든 연령대의 현재 접종 가능을 증명한다는 의미는 없다. 기본 `extract_evidence()`는 행사·신청·판매 기간을 식별하지만 국가 접종 절기 전체를 다루지 않으므로, 원래 두 번들의 `availability_not_verified`·`temporal_source_not_bound`는 그 일반 경로로는 해결할 수 없었다.

## 중복 원인과 오늘 실제 재검사

9/22 공개 29건 자기 제외 스냅샷으로 처음 복구한 기존 중복 결과는 `#63 → #81,#103`, `#81 → #63,#103`였다. 세 구형 게시물 모두 제목 필수어의 동일성은 **불충족**, 겹친 URL은 `https://www.kdca.go.kr/bbs/kdca/42/309764/download.do` 하나다. 실제 링크는 각 게시물의 `<h2>공식 근거 및 확인 경로</h2>` **바로 다음** 클래스 없는 `<ul>`의 직접 `<li><a>`에 있다. #63/#81 각각 2개, #103 3개 출처 링크이며, 행동 CTA 안의 링크가 아니다. `search_intent.py`의 기존 `h2#sources + ul.source-list` 식별만으로는 이 구형 출처 목록을 인식하지 못했다.

이후 다른 담당자가 구형의 위 **정확한 표제·인접 UL·질병관리청 PDF 링크**만 인용으로 취급하도록 추가한 현재 코드가 있는 상태에서 9/23 **08:52:27** SSH 읽기 전용 WP-CLI로 전체 `publish,draft,pending,future,private` 재고를 재수집했다. 합계 **39건: 공개 29, 초안 10, ID 중복 없음**이다. 비공개 게시물 제목과 본문은 일반 보고서·채팅에 출력하지 않았다. 독립 모델 검토용 CLI가 최신 전체 재고를 요구하여 **08:56:33 읽기 전용 재조회**로 각 자기 ID만 제외한 38건을 별도의 Git 무시되는 접근 제한 `PRIVATE` JSON 두 개에 저장했다. 이 비공개 파일은 일반 문서·HTML·대시보드에서 링크하거나 원고를 인용하지 않는다. 08:56 새 재고에서도 두 후보의 사전검사가 `ready`였다. 이 새 전체 재고에서 양쪽 **공개 중복 ID `[]`, 비공개 중복 건수 0**을 확인했다. 종전 문서의 40건이라는 과거 수치와 현재 39건 차이는 사실이나 어떤 개별 게시물이 왜 빠졌는지는 조사하지 않았고 원인을 추정하지 않는다. 해당 시점 현재 중복 해소는 공식 출처 URL 재사용을 허용하는 범위에 한정된다. 두 글의 독자 질문과 대상이 실제로 충분히 구분되는지는 독립 편집 검토에서 별도로 확인한다.

## 사전검사 결과 및 반례

기존 9/22 자료를 당시 15:00 시각으로 다시 돌리면 #63/#81 모두 세 사유 `availability_not_verified`, `duplicate_topic`, `temporal_source_not_bound`가 재현됐다. 9/23 새 출처 시각과 출처 제목만 적용한 `*-fresh-unreviewed.json`은 같은 날 새 인벤토리에서 `availability_not_verified`, `temporal_source_not_bound`가 남았다. 마지막으로 **공식 원문에서 직접 복사한 시즌·수정 인용을 결합한** `*-season-unreviewed.json`은 08:54:09 전체 live 목록과 `validate_bundle(..., require_review=False)`에서 양쪽 사유가 0개였다.

시즌 후보 각각의 복사본에 시행한 네 가지 부정 검사도 올바르게 차단됐다. 종료일을 근거 없이 2027-05-01로 늘리면 `legacy_national_flu_season_not_officially_bound`; s1 전체기간 인용에 원문에 없는 말을 붙이면 `legacy_reference_period_dates_or_source_unverified`; s0 어린이 변경 인용을 지우고 임의 문구로 대체하면 `legacy_national_flu_season_not_officially_bound`; 리드에 “현재 모든 대상 접종 가능합니다”를 붙이면 `legacy_reference_period_misleading_current_status`가 각각 발생했다. 이 네 가지는 일부 회귀 확인이며 독립 사실검증이나 전체 정책 테스트 완료를 뜻하지 않는다.

## 실제 검토 자료와 다음 수락 조건

두 게시물마다 `tmp/legacy_audit_20260923/worker-flu/` 아래 다음 파일이 있다.

| 파일 패턴 (`post-63`과 `post-81` 각각) | 용도 |
| --- | --- |
| `post-{ID}-fresh-unreviewed.json` | 공식 s0/s1을 오늘 다시 수집하고 s1 제목을 바로잡은 기초 번들. 기간 결속 이전 상태. |
| `post-{ID}-season-unreviewed.json` | ID·공식 출처·날짜·원문 인용에 제한된 시즌 근거 추가, 오늘 사전검사 통과. **독립 리뷰 미실행**. |
| `post-{ID}-proposed-unreviewed.html` | `render()`가 오늘 생성한 전체 교체안 HTML, 실제 사이트에 미적용. 기간 결속은 렌더되는 글 문장을 바꾸지 않아 두 번들의 본문 미리보기가 같다. |
| `post-{ID}-compare-unreviewed.html` | 어제 백업한 실제 WordPress 저장 본문과 오늘 전체 새 HTML을 sandbox iframe으로 나란히 비교하는 페이지. |
| `post-{ID}-content-diff.txt` | 원본과 교체안의 가시 텍스트 변경. |
| `post-{ID}-fresh-status.json`, `post-{ID}-season-status.json` | 사전검사 차단·해소 증거와 부정 검사. |
| `live-inventory-readonly-summary.json` | 9/23 최신 재고 총수/공개·비공개 중복 건수/본 게시물 SHA만 포함. 다른 비공개 게시물 본문과 제목 없음. |

독립 검토에 넘길 번들은 반드시 **`post-{ID}-season-unreviewed.json`**이다. 각각 공식 출처의 교체 전후 일정 충돌, 연령대별 실제 접종 자격과 10/6 고위험군 예외의 적용 범위, 영아의 생후 6개월 도달 조건, 3가 백신, 2027-04-30 종료일, 문단별 근거와 중복 글 사이 독자 질문의 구분을 확인한다. 특히 #63의 고위험군 문구를 모든 연령층의 무료 접종 확대라고 읽히지 않게 검토하고 #81에는 어르신 중심 범위를 보존한다. 질병관리청 8/25 최초 자료의 구 일정이 최신 일정으로 노출되는지 다시 찾는다.

독립 모델의 여섯 의미 검사 모두 `true`, 문제 `[]`를 확보한 뒤, **독립 검토자가 작성한 `review`가 현재 본문·근거·정책 digest에 결속**되었는지 `editorial_cli.py review`/`check`로 검증한다. 반드시 이 새 격리 사본만 검토에 사용하고 원본 full-civic 번들을 덮어쓰지 않는다. 검토가 끝나면 본문 렌더 SHA를 다시 계산하여 read-only `scripts/prepare_post_approval.py`로 최신 WP 전체 재고·원본 내용·제목·상태·공식 자료 SHA 및 비교 파일을 다시 준비한다. 편집 검토 유효기간 24시간과 주제 승인 종료일 **9/23 당일**을 넘기면 새 근거를 토대로 재승인해야 하며 날짜만 임의로 변경하지 않는다. 사용자 승인과 운영 쓰기·실사이트 QA는 후속 단계다.

**잔여 미검증:** 실제 개별 의료기관 백신 재고·예약·홈페이지 로그인 뒤 기능, 실사이트 새 렌더링의 브라우저/모바일 화면, 전체 문장에 대한 별도 인간 검토, 새 버전 게시 및 복구 실행은 검증하지 않았다.
