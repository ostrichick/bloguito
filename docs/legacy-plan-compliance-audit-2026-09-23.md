# 6단계 구형 글 현대화 독립 계획 준수 QA — 2026-09-23

## 판정 기준·범위

**기준 시점:** 2026-09-23 KST. 계획의 출발점은 `docs/legacy-post-modernization-worklog-2026-09-22.md:3-9,53-68`, 전수 대기열은 `docs/legacy-content-priority-2026-09-22.md:1-47`, 후속 최종 실행 서술은 `docs/legacy-modernization-execution-2026-09-23.md:1-52`다. 실제 대상별 증거는 `docs/legacy-{civic,seasonal,finance,mixed}-execution-2026-09-23.md`와 해당 문서가 지정한 Git 제외 폴더를 대조했다. `AGENTS.md`, `docs/EDITORIAL_SYSTEM.md`, `agent-publisher/editorial_policy.json`도 읽었다. **PASS**는 명시한 관측 범위의 검사 완료, **PARTIAL**은 작업 일부 완료·핵심 잔여 존재, **UNVERIFIED**는 직접 성공 증거 부재다. 소스 파일의 해시 정합성과 공식 사실의 완전성·실제 독자 행동 성공을 동일시하지 않는다. 이 담당자는 오늘 운영 WordPress/서버를 새로 수정하거나 외부 등록·Git stage·commit·push를 하지 않았다.

**정확한 분모와 완료 상태:** 9/22 첫 공개 30편은 최신 저장 구조 5·구형 25(`worklog:7,15-20`). 같은 날 최신 완전 v2 기준선은 최신 13·구형 17; 9/23 08:44 #77이 공개 목록에서 제외돼 공개 **29편=최신 13+구형 16**, #77은 별도 read-only WP 조회에서 `trash`로 확인되었으나 휴지통 이동 이유·실행자 미확인(`docs/legacy-live-census-2026-09-23.md:5-18`). 이어 **오늘 공개 기존 ID #63·#81·#140의 본문 갱신 3건** 후 09:14:51 완전 공개 REST `tmp/legacy_audit_20260923/postpublish/triage.json`에서 29편·최신 **16**·구형 **13**, 변경 ID 정확히 `[63,81,140]`, 다른 26편 불변, 신규 ID/누락 ID 0을 **원자료를 다시 계산하여 확인**했다. 따라서 “3 published”는 **신규 글 3편 발행이 아니라 기존 공개 글 3편 변경**이다. #77 이탈은 현대화 성공이나 직접 삭제·복원 성과가 아니다. 9/22의 초기 정적 P0/P1 분류를 오늘의 13편 미완료 목록으로 재사용하지 않는다.

## 6단계 계획 항목별 준수 판정

| 단계·완료 기준 | 판정 | 실제 근거와 미완료 경계 |
|---|---|---|
| **1. 전체 상태 조사·진단**: 공개 전수/비공개 중복/구형 구조, 최신 기준선·원본 식별 | **PASS (재고·구조 한정)** | 09:14 공개 REST 완전 v2 29개 고유 ID·1페이지·변경 3개 실제 확인(`postpublish/triage.json`). 별도 9/23 정상 상태 read-only WP 39개=공개 29+초안 10, 보관 상태 6개 포함 총 45개(`legacy-live-census:5-8`; `legacy-seasonal-execution:7`). 대상 5편 DB `post_content`와 PRIVATE 원본 백업 해시도 아래 검산. 공개 REST SHA는 DB 원본 SHA가 아님. 29편 전수의 **사실/실브라우저/링크 실행** 진단 완료는 아님. |
| **2. P0~P3 위험·계절·독자 가치·작업 순서** | **PARTIAL** | `legacy-content-priority:15-46`에 **9/22 12시대 30편 전수** 우선순위와 글별 조치가 있다. 그러나 #137/#101/#55/#79는 9/22에 이미 실제 개선되었고 #77은 9/23 휴지통; 9/23 #63/#81/#140도 새 구조로 이관. 원래 P0/P1을 현재 미수정 결함/우선순위로 다시 제시하면 오판이다. 현재 13개 구형 ID·보류 사유는 `legacy-modernization-execution:35-44`로 재구성되었으나 **수치화된 새 검색 수요/유입/수익 기반 재우선순위는 수행됐다는 증거 없음**. 실제 위험과 임박 날짜로 작업을 분기한 범위만 확인. |
| **3. 공통 목차·상자·표 및 접근성** | **PARTIAL** | 9/22 최종 기록 `docs/interruption-final-2026-09-22.md:9-13,23-27`은 운영 MU 세 파일 설치, #85 표 캡션·열/행 머리글·키보드 수평 이동 실측과 26편×3 화면 **78/78 CSS 확대 근사**를 제시한다. 9/23 총괄 문서 `legacy-modernization-execution:15`은 운영 세 SHA 재확인. 단, MU가 구형 글의 **저장 본문**을 현대화하지 않고, 오늘 신형이 된 세 글에 대한 **360/390/1280 실브라우저·네이티브 200%·키보드/스크린리더 재시험은 수행되지 않음**(`legacy-modernization-execution:50`). 목차 자동 후보 표지가 실제 오류 13건 확정은 아니다. |
| **4. 대표 시범 원고·독립 6항 심사·실제 적용 검증** | **PASS (검증된 적용 3건 한정)** | #137 대표 시범은 9/22 저장 및 사후 검증 기록(`legacy-modernization-resume-execution:13-16`; `legacy-modernization-progress:49-52`). 9/23의 #63·#81은 v2에서 발견된 `65세 이상` 고위험군 범위 누락을 **v3로 정정**하고 다시 독립 6/6·정규 check·fresh preflight를 수행(`legacy-civic-execution:48-52`; `legacy-modernization-execution:23-29`). #140은 실제 다른 비공개 초안을 `온라인` 한 단어로 중복 처리한 오탐을 범위 좁힌 뒤 6/6·check·preflight(`legacy-civic-execution:32-46`). 당시 approval manifest는 `prepared_not_authorized`였지만 **그것만으로 이후의 실제 갱신이 없었다고 판단하면 오류**: 09:14 공개 REST 변경 정확히 세 ID, 09:16~09:18 독립 read-only 사후 결과에서 DB 저장 SHA·원고/메타/HTTP200 일치(`civic2/flu-postpublish-readonly-results.json`, `passport-postpublish-readonly-results.json`). 오늘 세 글 외 남은 글에 시범 PASS 전파 불가. 사용자의 포괄적 갱신 승인 범위를 개별 manifest 생성 시점의 문자열만으로 다시 판단하지 않음. |
| **5. 잔여 글 전체 근거·원고·글별 게시 적용** | **PARTIAL / 전체 완료 아님** | 적용 전 16개 구형 중 #63/#81/#140만 당일 실제 개선. 남은 13개 `#70,#85,#99,#103,#119,#125,#139,#144,#145,#163,#217,#219,#220`는 `legacy-modernization-execution:35-44`와 네 담당 문서에서 **13/13 HOLD, READY 0**으로 구분; “13편에 후보 준비”는 “13편의 공식 원문 완전성·독립 6/6·CLI ready·운영 반영”이 아니다. 계절 5편은 아래 실측대로 전부 `review/check exit 2`, 모델 호출 0. #70은 공식 NOL HTTP403, #99는 대체 운영자 상품 본문만 확보하고 판매상태/종료 근거 미확인, #85는 welfare evergreen 정책 차단(`legacy-mixed-execution:17-55`). #103 자체사업 15~65/15~64 공적 충돌, #119 단기 시효·SHA 변동(`legacy-civic-execution:13-30`). #125/#139은 중복·NTS 조회수, #220은 신청기간 공적 종료일 없음, #304는 **이미 최신형이지만** 전자레인지 수거 공식 분류 상충, #127은 정적 HTTP200과 Edge 동적 최종화면 결과가 달라 CTA 성공 미인증(`legacy-finance-execution:11-60`). 원고 길이·출처 인용 문자열 존재만으로 완료 판정 금지. |
| **6. 반복 감사·수정 기록·운영 자동화** | **PARTIAL** | `scripts/audit_legacy_posts.py`가 기준선·공개 REST 변경을 감지해 09:14 `[63,81,140]`을 표시했고, `legacy-modernization-execution:52`의 **09:16:38 수동 반복 감사 1회**는 상태/체크포인트/보고서까지 기록. 그러나 별도 **legacy 감사 cron 0**, 실제 경보 발송 0, 검토 등록부 미제공으로 공개 29편 `review_due=null`(`postpublish/triage.json:1005-1039`). 자동 재검토 주기·담당·통보/장애 모의훈련을 운영 완료로 표기 불가. |

### 횡단 완료 기준과 분명한 제한

| 기준 | 판정·증거 |
|---|---|
| 기존 공개 글 무관한 ID·메타 보호 | **PASS (오늘 세 편의 문서화된 관측):** 정규 단일 ID updater의 결과를 `legacy-modernization-execution:19-29`에서 확인; 사후 read-only 저장 SHA는 #63 `128f680d…`, #81 `959d932c…`, #140 `9a0d8c8b…`, 제목·slug·발행일·상태 보존 및 공개 HTTP200(`civic2/*postpublish*results.json`). 모든 WordPress 글과 전체 서버 자산의 불변성까지 독립 전수 해시한 것은 아님. |
| 출처·기간·독립 검토 차단 준수 | **PASS (보류 결정):** 계절 5/5, 교통 #119 등 기간 30일/유일 예외 #225의 범위를 임의 완화하지 않음. 원문 충돌 #103/#304 및 실제 판매상태·재고 미확인 건은 HOLD. 9/22 오래된 리뷰 서명은 오늘 새 공식 source 결합에 재사용 금지. |
| 당일 공식 사실 완전 검증·실행 링크/개인 결과 | **UNVERIFIED**: 13 보류 원고 전부 6/6 불가 또는 미호출, 공개 29편 자동 상태 `fact_review_status`/`link_behavior_review_status`는 `unverified`. 특정 CTA HTTP200·정적 HTML만으로 로그인 후 조회·예약·실시간 재고 검증 불가; 특히 #127/#304의 남은 공식 충돌 별도 필요. |
| 회귀 검증과 배포 분리 | **PARTIAL:** 9/23 저장 로그 `tmp/legacy_audit_20260923/prime/regression-test.log:13-16`에는 **292 tests, OK (skipped=1)**. 시작부 `FAILED ... simulated transfer interruption`은 실패를 기대한 테스트 중 stdout/stderr이고 최종 unittest 실패 수는 0; 이를 운영 백업 실제 전송 실패로 재해석 금지. 이 독립 QA는 동시 변경 중인 전체 테스트를 새로 재실행하지 않았으므로 최신 작업 트리에 대한 새 292 PASS 선언도 아님. `legacy-modernization-execution:17`의 당일 v3 백업 verify-only 0은 **전체 복원/격리 재해복구 성공이 아님**. |
| 라이브 UI·검토 레지스터·자동 운영 | **UNVERIFIED 또는 미완료:** 오늘 새 3편 실브라우저 크기·200%/스크린리더, 외부 링크의 실제 개인 동작, 사람 검토 만료 등록, 신규 legacy cron 및 알림 전송, 격리 전체 복원은 완료 기록 없음(`legacy-modernization-execution:46-52`). 9/22의 78/78 근사 CSS 관측을 오늘 새 세 편의 실브라우저 통과로 옮겨 쓰지 않음. |

## 계절성 5개 bundle 직접 재계산: ID·출처 SHA/크기·원본 백업

**검산 방식:** Git 제외 `tmp/legacy_audit_20260923/seasonal2/post-{ID}/candidate.unreviewed.json`을 5개 각각 실제 읽고 `brief.existing_post_id`, `original.PRIVATE.json`의 원래 `ID`, source `id/url/text/fetched_at/sha256`, 별개 `official-s*.json`, `official-recheck-status.json`의 글자 수, 정책의 ID별 예외를 서로 비교했다. `SHA256(UTF-8(source.text))`를 **10개 모두 독립 재계산**하여 각 candidate source·원출처 snapshot·직전 재조회 장부의 최초 SHA와 정확히 일치했다. 다음의 `글자`는 추출 `text`의 길이, `UTF-8 B`는 그 **추출 텍스트만의 실제 바이트 크기**, `snapshot B`는 별도 JSON 파일 전체 크기로 **세 가지가 서로 다르다**. PDF 원본 다운로드의 바이너리 SHA/크기로 텍스트 SHA를 대체하지 않는다. 소스 파일 수 10/10, 해당 글의 후보 내 source 개수 1/1/1/2/5 일치. 후보 HTML 자체 SHA 5/5 `candidate-status.json`과 일치, 5개 후보 모두 새로운 `review` 없음. PRIVATE 백업 파일 실제 전체 SHA와 그 안의 `post_content` UTF-8 SHA도 `live-stored-provenance.json`의 각 5개 기록에 일치. 이는 **09:07 당시 원본 검산**이지 미래 동시편집 방지/갱신 승인 아님.

| 글·출처 ID | 원출처 snapshot | 글자 | UTF-8 B | snapshot B | 검산된 추출 text SHA256 |
|---|---|---:|---:|---:|---|
| #144 `s0` 서초구 9월 재산세 | `post-144/official-s0.json` | 1,269 | 2,638 | 3,305 | `5f97241462c1a93a9aeaeeec6b165a1eb6441654f4487040b97b97c9f8b09917` |
| #145 `s0` 국토부 확정 PDF | `post-145/official-s0.json` | 3,630 | 6,392 | 6,868 | `3e4e650f66d15256889bd6b829b82062a00daa65ad8af55d76da202f47e2cfeb` |
| #163 `s0` 복지부 운영 계획 | `post-163/official-s0.json` | 6,328 | 14,091 | 14,941 | `d020109be43812d45582bbeb1b78e10fc7c728f4638e565f5bcc3572f8c5052f` |
| #217 `s0` 코레일 8/14 보도자료 | `post-217/official-s0.json` | 2,954 | 6,883 | 7,390 | `ad3cb0f3e74df2ac683a1d3fbe1074ab9d9f316a21b1be4a195ed84490991ffa` |
| #217 `s1` 코레일 모바일 공지 | `post-217/official-s1.json` | 2,004 | 4,251 | 4,660 | `2db355e5cca3834ad137e599ec5e15611a7dffd0552f3596f71099baa974934d` |
| #219 `s0` 오피넷 동적 가격 | `post-219/official-s0.json` | 4,059 | 9,001 | 9,910 | `53ee196e6db925e818828657dd5c9ea1b210fbec0b96a08e2af0e1d6219d1f2e` |
| #219 `s1` 한국환경공단 웹진 | `post-219/official-s1.json` | 1,071 | 2,503 | 2,868 | `38598853b73bbec5a070ab9700905b2b98838e637c7d0e615877307e7b769a9b` |
| #219 `s2` 정부 교통대책 | `post-219/official-s2.json` | 2,344 | 5,386 | 5,987 | `31d69aada9149085a843944682c945f678a9c24855cc162069cc9b41ddbc966b` |
| #219 `s3` 공공 EV 할인 | `post-219/official-s3.json` | 2,195 | 5,107 | 5,542 | `24d38cd2ab8c4185838f9849d3910c26d6f6a7131812ac73049d2d5120a9adff` |
| #219 `s4` 통행료·유류 할인 | `post-219/official-s4.json` | 4,298 | 10,023 | 10,499 | `441bb1bf1a9f6b83bd1dad8aaea82ffcb5812355d5328db23aa77f089c1bdea7` |

**특별 식별 주의:** #219의 `brief.id`는 `legacy-sourcebound-219-20260922`로 전일 값을 유지하나 **실제 대상 `existing_post_id=219` 및 원본 ID=219는 동일**하고 9/23 새 `sources`·fetched_at·새 후보에서 옛 모델 `review`는 삭제돼 있다. 이를 글 ID 불일치나 9/23 신규 출처 미수집으로 오진하지 않는다. #145의 오늘 **텍스트** SHA `3e4e...`와 `docs/legacy-seasonal-primary-pdf-evidence-2026-09-22.md:9-11`에 기록된 어제 실제 PDF **바이너리** SHA `3d456...`·304,670 B는 해시 대상이 다르므로 모순이 아니다. 이번 QA는 오늘 PDF HTTP 바이트를 새로 다운로드하거나 독립 렌더하지 않았고, 오늘 보관된 추출 출처 및 앞선 다운로드 기록을 교차 검산한 범위만 주장한다.

**당일 재조회 드리프트는 별도 실패:** 위 10개는 **보관 후보 내부의 서명 일치**이며, 직후 두 번째 공식 fetch의 현재 SHA까지 10개 동일하다는 뜻이 아니다. `official-recheck-drift.json` 실물에서 **5개 불일치**: #144 서초구 조회수 627→628, #163 정부 사이트 실시간 뉴스, #217 코레일 조회수 37,759→37,761, #219 `s0` 오피넷 주유소·가격 목록 **570줄 diff**, #219 `s2` 뉴스 영역. 나머지 #145 PDF, #217 모바일, #219 `s1/s3/s4` **5개 동일**. 앞선 기록의 본문 변경 여부를 다시 증명한 것이 아니며, #219 실가격 변화는 메타데이터로 제거해서는 안 된다. 따라서 글별 실 WP 최종 출처 SHA 재검사가 필요한 approval 패키지는 **5편 모두 없음**.

### 정확한 기간 게이트 및 CLI 재확인

현재 `editorial_policy.json:3-12`에는 `min_remaining_days=30`, 특정 key `2026-chuseok-bank-post-225` / `existing_post_id=225` / `useful_until=2026-09-27` / **두 고정 금융위 URL**만 있는 단독 예외가 명시돼 있다. `agents/editorial.py:54-97`의 `dated_post_exception`은 brief ID·게시물 ID·종료일·정확한 공식 URL 목록까지 모두 일치해야 참이다. 검산 기준일 **2026-09-23**에서 30일 기준을 달력으로 적용하면 최소 `useful_until=2026-10-23`이 필요하다. `review_until`을 연장해도 유효기간 결손이 해결되지 않는다.

| ID | 저장 원문/brief ID 일치 | 명시된 `useful_until` | 정확 잔여일 | 30일 충족 | #225 예외 | 실제 `topic_reasons` 및 정규 게이트 |
|---:|---|---|---:|---|---|---|
| 144 | PASS | 2026-09-30 | **7** | NO | NO | `insufficient_useful_lifetime`; review/check 각 exit **2** |
| 145 | PASS | 2026-09-27 | **4** | NO | NO | 동일; review/check 각 exit **2** |
| 163 | PASS | 2026-09-27 | **4** | NO | NO | 동일; review/check 각 exit **2** |
| 217 | PASS | 2026-09-27 | **4** | NO | NO | 동일; review/check 각 exit **2** |
| 219 | PASS | 2026-09-27 | **4** | NO | NO | 동일; review/check 각 exit **2** |

`seasonal2/official-recheck-status.json`, `candidate-status.json`, `cli-gate-summary.json`와 각각 `post-ID/{deterministic-prereview,cli-review,cli-check}.json` 직접 대조 결과: 모든 후보의 최신 전 검토 검사 세 이유 **정확히** `availability_not_verified`, `insufficient_useful_lifetime`, `temporal_source_not_bound` (그 외 문단별 인용·숫자 차단은 당시 0); 실제 `editorial_cli.py review`는 다섯 모두 선행 검사에서 종료 2, **독립 모델 호출 0**, `check`도 다섯 모두 종료 2 및 위 세 항목 + `review_not_bound_to_current_content`, `review_stale`, `semantic_review_failed`. 미리보기가 있는 것은 승인된 reviewed HTML이 아니다. #217 공식 모바일 공지의 요일/특설 페이지 관련 표기 이상은 후보가 해당 값을 사용하지 않아도 원출처 완전 신뢰로 간주 불가. #144 공식 예시의 `7월/10월`을 9월 고지의 2차 납기로 전용하지 않았고, #163 전국 운영 계획·#219 실시간 유가를 개별 이용 보장으로 바꾸지 않았다. 날짜형을 가짜 evergreen으로 바꾸거나 공식 마감일 없이 종료일을 늘려 통과시키는 수정은 현재 허가 범위가 아니다.

## 발견된 생략·표현 교정 필요와 총괄 인계

1. **`완료`의 단위:** 계획의 최종 전체 현대화 **미완료**. 완료 판정은 기존 공개 3개 ID의 **글별 저장 갱신과 제한 사후 QA** 및 재고/정책 차단 경로에 국한한다. 현대화 잔여 공개 13개와 아직 최신형 구조지만 공식 사실/행동 문제가 남은 #127/#304를 숨기지 않는다. `3 published`를 새 글 발행 건수로 쓰거나 과거 #77 휴지통을 개선 실적으로 합치지 않는다.
2. **중간 보고서의 시점:** `legacy-modernization-progress:18-39,56-63`의 #63/#81 승인 대기·#140 중복 보류는 09:02경의 진짜 과거 중간 상태이나 09:12~09:14 실제 적용 후 현황으로 재사용하면 거짓이다. `legacy-civic-execution:7-12,38-46`의 #140 `prepared_not_authorized`도 사전 준비 시점 상태이고, 총괄의 사후 업데이트 및 검증 기록과 병기해야 한다. `legacy-content-priority`의 #225·#137·#101 과거 결손도 오늘 현재 미수정 결함이 아니다.
3. **사실 충돌·규칙 제한:** #103 공식 두 대상 연령 상충, #304 공식 수거품목 분류 상충, #220 공식 실제 신청 종료일 부재, #70/#99 실판매 미확인, #119/#144·추석 글의 30일 시효를 보류 근거로 유지. 특히 #144와 #145는 공식 날짜·절차를 잘 정리했어도 30일 정책 밖이라 `READY`가 아니다. #219 동적 오피넷 데이터는 새 조회에서도 달라져 출처 SHA 정합성을 별도 해결해야 하며, 소스 URL을 삭제하거나 `source_hashes_match_live=true`로 조작하면 안 된다.
4. **누락된 마지막 QA:** 오늘 새 3편의 실제 브라우저 360/390/1280·네이티브 200%·키보드/보조기술·CTA 실제 목표 화면; `review_due` 등록 책임과 스케줄·알림 운영; v3 오프사이트 암호화/격리 복구는 **추가 검증 및 별도 운영 결정을 필요로 하는 항목**이다. 코딩 테스트 292 OK와 백업 verify-only는 이들을 대체하지 않는다.
5. **안전한 실행 순서:** 13개 글 각각의 현재 검색 질문·공식 원문 적용 연도/기간/부속 자료 및 충돌부터 해결 → 전체 정상 WP inventory/자기 제외·실 DB SHA/백업 → 수정한 정확한 원고의 source SHA 재수집 동일성·독립 의미 6/6·CLI ready → 글별 diff/미리보기·사용자가 이미 부여한 승인 범위에 대한 운영 책임자 판정 → 정상 단일 ID updater CAS·read-after-write → 실제 브라우저/행동/재검토 등록. 정책 변경·추가 예외·제목 전환·전면 배포·휴지통 복구는 이 보고서가 자동 승인하지 않는다.

**변경 범위/독립성:** 이번 QA 결과는 신규 문서 `docs/legacy-plan-compliance-audit-2026-09-23.md`에만 작성했다. 본인 기존 계절 실행 문서·prime 총괄 문서·다른 작업자 파일·비공개 원고·WordPress·운영 서버·Git 인덱스는 변경하지 않았다. 자료의 존재·해시·크기·ID·기간은 실제 파일을 직접 계산했고, 모든 외부 자료의 내용 정확성과 라이브 상태는 이번 QA에서 다시 독립 방문·원문 전 페이지 대조하지 않았으므로 증명 범위에 포함하지 않는다.
