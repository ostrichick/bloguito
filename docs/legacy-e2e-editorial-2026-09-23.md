# 레거시 13편 원문→검토→검사→승인 준비 E2E 게이트 — 2026-09-23

## 실행 범위와 최종 판정

**13/13 모두 보류(HOLD), 새 게시·수정 0건.** 2026-09-23 10:50~10:58 KST에 기존 13편의 *실제 번들·정규 CLI 입력*, 같은 날 읽기 전용 SSH의 활성 WordPress 전체 재고 39건(공개 29·초안 10), 실제 공식 GET 및 정규 `scripts/prepare_post_approval.py`를 이용했다. `sources` 13회, `review` 13회, `check` 13회, 승인 준비 `prepare` 13회를 실행했다. **정규 `review` 및 `check` 26회 전부 종료 코드 2; 승인 준비 manifest 13개 전부 `blocked`, 승인 `prepared_not_authorized`.** 독립 모델 호출은 전 단계의 결정론적 실패로 일어나지 않았다. 타인의 검토 기록을 복제하거나 모델 서명/digest를 가짜 생성하지 않았다. 실제 `publish`·`update-existing`·`promote`는 실행하지 않았다.

공통 규범은 `AGENTS.md`, `docs/EDITORIAL_SYSTEM.md`, 실제 `agent-publisher/editorial_policy.json`이다. 이 작업은 #103에 대한 **좁은 내용 오류 예방 코드**만 prime에게 사전 소유권을 확인한 뒤 `agent-publisher/agents/critical_facts.py`에 추가했으며 신규 테스트 파일 `agent-publisher/tests/test_legacy_mokpo_conflict.py`를 작성했다. 기존 테스트·작업자 문서·번들·정책 수치·기한 예외·서버·WordPress·Git stage/commit/push는 변경하지 않았다. 그 외 산출물은 Git 제외 `tmp/legacy_audit_20260923/editorial-e2e/`에만 위치한다. 전체 WordPress 재고·비공개 원본·사본은 `*.PRIVATE.json` 및 전용 승인 준비 디렉터리에서만 보관하고 보고서에 비공개 제목·본문을 인용하지 않는다.

검사 계약: `editorial_cli.py sources <brief> --output ...`는 먼저 `topic_reasons()`를 검사하고 통과해야 공식 GET을 수행한다. `review <bundle> --inventory ...`는 `validate_bundle(require_review=False)`가 `ready`일 때만 모델을 호출하며, 그렇지 않으면 이유를 출력하고 **즉시 종료 코드 2**로 중단한다. `check`는 별도로 실제 소스 SHA, 문단별 연속 인용·수치, 중복, 30일, 검토 본문/정책 digest·6/6·기한을 평가한다. `prepare_post_approval.prepare()`는 게시물별 실제 저장본·자기 제외한 전체 재고, 공식 원문 재다운로드 SHA, 제목 보존, 읽기 전용 백업/diff를 검사하고 승인 manifest만 **로컬에** 만든다. `prepared_not_authorized`는 게시나 승인 명령이 아니다.

## 13개 실제 명령의 증거 및 결과

`editorial-e2e/run_gates.py`가 모든 번들의 원본 바이트를 독립 사본으로 보존하고, 매 글별 자기 ID만 제외한 새 38건 재고를 주어 실제 CLI 세 명령을 수행했다. **13/13 원본·사본 SHA 변경 0**, pre-review HOLD 13/13, review HOLD 13/13, check HOLD 13/13. `e2e-13.json`은 글별 `source` exit code, 실제 CLI 사유, 사전검사, 코드 2 및 소스 해시 차이를 기록한다. `approval_gate_readonly.py`는 실제 `prepare()`에서 새 live `post list/get`을 글별 다시 수행하며 승인 준비 13개와 모두 PRIVATE 전체 원본 백업, diff/비교 HTML을 `approval-readonly/post-{ID}/`에 작성했다. `approval-13.json`의 최종 manifest 집계는 **공식 재조회 SHA 동일 3건(#85·#99·#145), 변경 8건(#119·#125·#139·#144·#163·#217·#219·#220), 재조회 실패 2건(#70·#103)**이다. 8건의 해시 변동이 모두 실질 정책 개정이라는 뜻은 아니나 지금의 승인 해시 일치 요건을 충족하지 않는다.

| 글 | 정규 `sources` 단계 | `review` 사전검사에서 실제 발생한 HOLD | `check`·읽기 전용 승인 준비 |
|---|---|---|---|
| **#103 목포 독감** | **실패**: 원본 5개 URL 중 국가 위탁기관 HWP가 현행 HTML/PDF 수집기의 텍스트 범위를 충족하지 못함 | **신규 `mokpo_city_program_age_conflict_unresolved`**; 기존에는 잘못 `ready` | check 2, 승인 준비 차단: 공식 HWP 재조회 실패+신규 충돌·리뷰 부재 |
| **#70 공연** | **실패**: 정확 NOL 상품 URL HTTP 403 | `availability_not_verified`, `temporal_source_not_bound` | check 2, 승인 준비 403+리뷰 부재; 저장 원본 유지 |
| **#99 공연** | **성공**: 동일 상품 NOL World 수집 SHA=후보 SHA | `availability_not_verified`, `number_without_evidence`, `temporal_source_not_bound` | check 2, 승인 준비 SHA 동일이어도 현재 판매 기한/상태·영문 월 숫자 근거 등 미해결 |
| **#85 복지 절차** | **실패**: `welfare/evergreen`에서 정책 단계 선차단(HTTP 실패로 오인 금지) | `dated_category_cannot_bypass_time_check` | check 2. 승인 준비 직접 GET 5개 SHA 전부 같아도 분류 정책·리뷰 부재로 차단 |
| **#125 세금포인트** | **성공**, 국세청 페이지의 시시각각 바뀌는 메타로 SHA 다름 | `duplicate_topic`, `tax_points_2026_authoritative_version_missing`, `tax_points_2026_expiry_cohort_missing` | check 2, 승인 준비 source drift+중복·코호트 차단 |
| #139 네 기관 환급 | 성공, 동적 원문으로 SHA 달라짐 | `duplicate_topic` | check 2, 승인 준비 source drift+현재 게시물과 제안 제목 불일치+기존 내부 이동 링크 소실도 새 검사에서 차단 |
| #220 본인부담상한 | 성공, MOHW 출처 SHA 달라짐 | `availability_not_verified`, `temporal_source_not_bound` | check 2, 승인 준비 source drift 및 신청 종료 기한 불명 |
| #119 기후동행패스 | **실패**: 9/30 종료로 승인 topic gate 7일 | `insufficient_useful_lifetime`, `availability_not_verified`, `temporal_source_not_bound` | check 2, 승인 준비 서울 기사 source drift |
| #144 재산세 | **실패**: 9/30 종료 7일 | 위 3개 | check 2, 승인 준비 source drift |
| #145 통행료 | **실패**: 9/27 종료 4일 | 위 3개 | check 2, 승인 준비 PDF 동일해도 날짜 게이트 유지 |
| #163 병원·약국 | **실패**: 9/27 종료 4일 | 위 3개 | check 2, 승인 준비 공식 기사 source drift |
| #217 열차 취소표 | **실패**: 9/27 종료 4일 | 위 3개 | check 2, 승인 준비 공식 기사 source drift |
| #219 충전·주유 | **실패**: 9/27 종료 4일 | 위 3개 | check 2, 승인 준비 실제 주유 자료 포함 source drift |

위 13건의 정규 `check`에는 모두 별도의 `review_not_bound_to_current_content`, `review_stale`, `semantic_review_failed`도 포함된다. **이는 모델 검토를 생성하지 않은 올바른 차단**이고 원문 SHA 또는 정책을 우회해 리뷰만 붙이면 풀리는 상태가 아니다. 성공한 `sources` 4건도 그 출처로 작성된 후보의 의미·기간·정책 통과를 뜻하지 않는다. 실패한 9건은 #70 HTTP403, #103 HWP 파서, #85 정책 분류, #119/#144/#145/#163/#217/#219 최소 30일 부족으로 각각 구별했다.

## 우선 #103: 거짓 사전 준비 판정의 원인과 최소한의 수정

동일 시점 실제 공식 GET을 `editorial-e2e/inspect_103.py`로 **세 URL**에 실행했다. 목포 보건소 공지 `https://www.mokpo.go.kr/health/citizen_participation/notice?idx=548678&mode=view`는 **자체사업 15세~65세**, 목포시 보도자료 `https://www.mokpo.go.kr/www/mokpo_news/press_release/report_material?idx=548751&mode=view`는 **자체사업 15~64세**로 계속 서로 다르다. 보도자료의 공식 다른 호스트 `seafountain.mokpo.go.kr/...idx=548751...`도 후자와 같은 text SHA였으며 전자는 `14220931...`, 후자는 `ea22e429...`이다. 전체 내용 유실 방지를 위해 본문 전체 대신 URL·SHA·대상 연령을 보여주는 짧은 발췌만 `official-conflict-public.json`에 기록했다. 이 불일치 중 어느 쪽이 맞는지 추정하지 않고, 대상자에게 적용할 **공식 정정/최종 기준을 미확인**으로 남긴다.

기존 `full-mixed/post-103/full-candidate.json`의 `brief.official_urls`에는 보건소 공지가 있지만 **시 보도자료 자체가 빠져 있다.** 기존 숫자 검사·인용 검사·`legacy_reference_period`는 자신에게 전달된 보건소 공지의 텍스트와 시즌 기간만 검사하므로 `validate_bundle(require_review=False)`에서 **잘못된 `ready`**를 내었다. 독립 리뷰/원문 재다운로드는 여전히 다른 사유로 중단했으나, 작업자가 이 형식상 ready를 공식 연령 사실 검증 완료로 오인할 위험이 있었다. 81개 목록의 HWP는 **국가사업 위탁기관 자료**이고 두 시 문서의 서로 다른 자체사업 상한을 해결하지 않는다.

prime의 사전 코드 소유권 허가를 받은 뒤 `critical_facts.py`에 정확히 다음 조건의 **한정 사실 차단기**를 구현했다: 기존 게시글 ID 103, 카테고리 `life-health`, 글의 계획/독자 질문에서 *목포시 자체사업*을 실제 다룰 때에 한하여, 명시적으로 알려진 보건소 공지와 시 보도자료 **양쪽**이 `official_urls`와 `sources`의 실제 공식 출처로 있어야 하며, 각각의 시 자체사업 연령 표기가 단일 15~64 또는 15~65 형태로 추출되고 양쪽이 일치해야 한다. 누락·중복·상충·다중 수치를 `mokpo_city_program_age_conflict_unresolved`로 막는다. 전국 국가접종의 `65세 이상` 언급을 시 자체사업 연령 범위로 오인하지 않는다. 시민 글 103의 **전국 무료접종 기간만 설명하는 합성 사례**는 기존 정상 `ready`를 보존하되, 실제 자체사업을 설명하는 전체 후보는 HOLD한다. 이것이 언젠가 두 공식 웹페이지에서 같은 연령으로 확인되더라도 **그 자체로 승인 자동 진행은 아니며**, HWP 파서/자료 최신성/인용·모든 81행/독립 의미 검토/원본 대비 손상/실제 게시 승인 절차는 별도 필수다.

코드 변경 후 실제 원고에 대해 다시 `validate_bundle(require_review=False)` 및 **실제** `editorial_cli.py review <격리 원고103> --inventory ...`를 실행하여 각각 `needs_review`와 동일한 신규 사유, CLI **종료 2**를 확인했다. 모델은 preflight에서 중단되어 호출되지 않았고 원본 후보·WordPress·서버에 손대지 않았다. 새 회귀테스트 9개는 실제 충돌/press 누락/양쪽 동일 연령/잘못된 호스트·비공식 소스/양쪽 수치 혼재/국가 나이 언급/다른 글/국가 일정 전용 사례/preflight 실제 결합을 테스트한다.

**남은 #103 복구 조건:** 목포시가 동일 대상 65세 상한을 직접 정정하거나 두 출처가 현행 일치하는 공식 자료를 확보하고, 5개 URL 제한에 걸린 두 공지+국가 근거+HWP 원자료를 잃지 않는 정식 수집·검증 구조를 검토해야 한다. HWP 226,816바이트 원본 검증·파일 SHA는 이전 기록에 있으나 현재 `fetch_sources()`는 PDF/HTML만 읽어 이 HWP를 재수집·재검증 가능한 완전 번들로 만들 수 없다. 정정 전 연령 64/65 어느 쪽도 독자에게 단정하거나 HWP의 81개를 자체사업 병원으로 둔갑시키지 않는다. 별도 사용자·서비스 공식 확인이 필요한 경우 완료로 보고하지 않는다.

## 다른 우선 글의 독립 차단·정밀 후속 작업

- **#70:** 국내 NOL 공식 개별 상품 재조회는 이번 `sources`에서도 `official_source_http_403`, 승인 준비에서도 공식 재수집 실패. 9/22 수동 복사 스냅샷의 해시 존재는 9/23 공식 자동 조회가 아니다. 같은 상품의 운영자 공개 원문과 판매 종료일·상태를 확보할 때까지 예매 가능, 현재 잔여석, 마감 추정 및 공연일=판매종료일 판단 모두 금지. #99 World의 다른 상품 번호를 재사용해서는 안 된다.
- **#99:** 같은 상품번호 NOL World URL은 현행 CLI 소스·승인 준비에서 원문 SHA 모두 일치했지만, 영문 November/September를 숫자 `11월`/`9월`로 표현한 세 블록이 보수 숫자 인용 검사를 통과하지 못한다. 숫자 표기 번역은 향후 공식 월 토큰과 대응하는 한국어 숫자만 정확히 변환하는 독립 정밀 테스트로 풀 수 있으나, 그 개선은 실제 판매기간·상태 증빙을 만들지 않는다. YES24 목록만 허용하는 `schedule_listing_only`를 NOL에 확대 사용하지 않는다. 상품에 없는 회차별 시각·휠체어/배송·실시간 구매 여부를 기존 글에서 근거 없이 복원하지 않는다.
- **#85:** 정규 `sources`는 공식 사이트 장애가 아니라 **정책상 welfare evergreen 분류 차단**이다. 별도 정규 `prepare`에서는 실제 공식 다섯 출처 SHA 전부 일치. 그러나 조회·복지멤버십 가입·개별 급여 신청·신청 현황은 다른 서비스이며, 최종 제출 가능한 동적 양식/앱 이동은 검증되지 않았다. 임의로 `content_type=dated`+가짜 마감일 또는 카테고리 재라벨을 하는 대신, 소유자가 1건짜리 절차성 글 분류를 정확한 범위·정책 변경으로 결정하거나 명확히 HOLD. 원본의 사업별 확인표·방문 대안·접수번호를 없앤 손상 위험도 재검토한다.
- **#125:** 실제 국세청 `’25년에 부여`와 현 `critical_facts.py`의 `2025` 정수 문자열 강제는 좁은 버전인식 충돌이며, 이 담당자 할당 범위가 아닌 세금포인트 코드·중복 정책은 수정하지 않았다. 공식 원문 고유 문맥에서만 **연도 2025 부여 코호트 + 개인 5년/법인 다른 소멸기간 + 연간 1천포인트**를 검증하는 별도 수정·부정 테스트를 prime에 권고한다. #139와 비공개 다른 초안의 실중복을 독립 해결하기 전에는 단순 guard 조정만으로 승인될 수 없다. 이번 실 CLI `sources`에서 국세청 수집 성공하였으나 기존 후보 SHA와 다르며, `prepare`가 실제 이를 추가 차단했다.
- **#139/#220 및 짧은 시효 6건:** #139은 출처/중복·제목 보존·기존 내부 링크 보존의 독립 장애가 있다. #220은 진료 연도와 신청 종료일이 다르며 공식 신청 유효기간 미확인. #119/#144/#145/#163/#217/#219의 실제 마지막 날은 9/27 또는 9/30으로 최소 30일을 어긴다. 사후 조회·기한 정보와 실제 현재 신청/표 구매/기관 운영 상태를 섞지 않는다. 모든 변경 후보는 새 근거 확보 후 전체 정규 재검토 필요.

## 회귀 테스트와 미검증 경계

1. 신규 전용 테스트 `test_legacy_mokpo_conflict.py`: **9/9 PASS**. 기존 `test_legacy_reference_period.py`: **7/7 PASS**. 첫 전체 테스트는 기존 **전국 절기만 다루는 #103 합성 fixture**에도 ID만으로 신규 guard가 걸려 1건 실패했고, 다른 작업자의 테스트는 건드리지 않고 **실제 자체사업 관련 글/독자 질문에만 적용**하도록 guard 자체를 고친 후 두 targeted test를 다시 통과시켰다.
2. 최종 `./agent-publisher/.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests -q`: **311개 중 310개 통과, 1개 skipped, 실패 0**. 테스트의 외부 모형 출력·썸네일 로그는 실제 WordPress 수정이나 네트워크 신청 성공을 뜻하지 않는다. `git diff --check`의 신규 차단기 diff는 공백 오류 0.
3. `tmp/legacy_audit_20260923/editorial-e2e/e2e-13.json`, `approval-13.json`, `official-conflict-public.json`, 13개 개인별 CLI source JSON·PRIVATE 재고, 13개 PRIVATE 원본·manifest·diff가 재현 근거다. 당일 내부 시각 이후 다른 사람이 WordPress를 수정하거나 공식 원문이 바뀌었을 수 있으므로 새 적용 직전 재고/CAS/SHA/서명 재검사가 필요하다. 네이티브 200%·모바일/스크린리더, 개인정보를 입력한 신청·결제·접종 예약, 실제 publish/update와 배포·복구는 이번 범위에서 **실행하지 않았으며 성공으로 표시하지 않는다**.

**prime 후속 실행 순서:** #103 공식 서면 상충 해결→안전한 HWP 및 6개 이상 원자료 수집 계약 검토→행별 적용사업/연령·전화·주소 전수 의미 재검사. 각 글에서 현행 공식 원문 SHA와 30일/중복/원고 조건을 충족한 뒤에만 진짜 독립 검토 6/6→정규 `check ready`→전후 FULL diff·현재 저장 SHA/제목·slug·출처 재조회가 포함된 읽기 전용 승인 패키지→게시글별 사용자 승인→정규 updater와 공개 브라우저 QA. **오늘 승인 가능 글은 0/13.**
