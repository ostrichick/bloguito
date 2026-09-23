# Bloguito 기존 공개 글 현대화 — 최종 계획 대조·실행 검증 (2026-09-23)

## 1. 최종 판정

2026-09-22에 확정한 6단계 계획을 2026-09-23 실제 운영 상태, 독립 QA, 실제 브라우저 E2E, 로컬 코드 회귀검사와 다시 대조했다. **전체 계획은 PARTIAL**이다. 전수 재고·우선순위 장부·공통 레이아웃 기반·검증된 기존 글 갱신·반복 감사 도구는 실제 구현되었지만, 남은 구형 글 13편은 안전 게이트 때문에 아직 갱신할 수 없고, 운영 반복 감사 cron/알림·사람 검토 등록부·실제 복구 훈련·일부 외부 서비스의 최종 업무 화면 검증도 남아 있다.

이번 최종 단계에서 이전 독자 E2E가 확인한 **#81 내부 관련 글 링크 회귀는 새 현행 리뷰로 실제 복구했다.** 따라서 legacy-e2e-reader-2026-09-23.md, legacy-modernization-independent-qa-2026-09-23.md, legacy-semantic-link-audit-addendum-2026-09-23.md의 “#81 관련 #63 링크 없음” 판정은 **14:06:15 KST 수정 전의 역사적 관측**이다. 다른 실패·미검증 항목은 아래와 같이 그대로 남는다.

판정 용어는 PASS=기재한 범위에서 실제 확인, PARTIAL=필수 후속이 남음, HOLD=현행 게이트를 통과할 근거 부족, UNVERIFIED=실제 재현 증거가 없음이다.

## 2. 최초 요청·어제 확정 6단계 계획과 최종 상태

| 단계 | 원래 완료 기준 | 최종 판정 | 실제 상태 |
| --- | --- | --- | --- |
| 1. 공개·비공개 재고와 실물 전수 진단 | 실제 전체 목록·본문 구조·변경 분모 확인 | **PASS(재고/구조), 전체 사실 전수는 UNVERIFIED** | 최신 확인 분모는 공개 29, 초안 10, 휴지통 6 = 고유 45. #77은 휴지통이며 임의 복원/삭제하지 않았다. 공개 글은 새 구조 16·구형 13. |
| 2. 위험·계절·독자 가치 P0~P3 | 전체 글의 우선순위와 후속 조치 명시 | **PARTIAL** | 9/22 당시 공개 30편의 P0~P3 장부와 이후 13편 HOLD 사유가 있다. 최신 검색량·유입·수익을 다시 측정한 정량 재우선순위는 완료하지 않았다. |
| 3. 공통 레이아웃·접근성 | 목차/콜아웃/표/모바일·확대·키보드 검증 | **PARTIAL** | 운영 MU 3개는 배포본 SHA가 일치하고, 실브라우저 표본 5글에서 검색·목차 및 360/390/1280/CSS 200% 문서 폭 검사는 통과했다. 네이티브 브라우저 200%, 스크린리더, #85 표의 물리 키보드 가로 스크롤은 UNVERIFIED. |
| 4. 대표 시범 및 안전한 기존 글 갱신 | 공식 원문→독립 리뷰→CLI→백업/CAS→실반영→사후 확인 | **PASS(검증·반영한 글 한정)** | 9/22 이미 개선된 11편을 재실행하지 않았고, 9/23 #63/#81/#140을 정규 경로로 적용했다. 최종 단계에서 #81 관련 링크 회귀를 같은 게이트로 다시 검토·복구했다. |
| 5. 나머지 글 전체 근거·본문 보강 및 개별 갱신 | 남은 구형 글을 근거가 충족되는 범위에서 순차 갱신 | **PARTIAL / READY 0** | 구형 13편 #70,#85,#99,#103,#119,#125,#139,#144,#145,#163,#217,#219,#220은 현행 CLI/출처/기간/중복/의미검토 조건상 모두 HOLD. 게이트 우회나 가짜 기한·evergreen 재분류는 하지 않았다. |
| 6. 반복 감사와 수정 기록 | 변경 감지·보존·경보·운영 반복 가능 | **PARTIAL** | 감사 CLI·checkpoint·report·strict exit·보존 manifest를 E2E 검증했고, 타 폴더 삭제 결함과 동일 초 정렬 결함을 수정했다. legacy audit 운영 cron 0, 외부 경보 수신 0/미검증, 사람 review register 미구축. |

**글 길이 증가는 완료 조건으로 사용하지 않았다.** 공식 출처 충돌·기간 부족·실제 최종 행동 URL 미확인 항목은 완료로 올리지 않았다.

## 3. 최종 단계에서 실제 수정한 운영 회귀 — #81

### 원인

개정 전 #81에는 어린이·임신부의 종합 일정을 #63으로 연결하는 https://lifeinfo24.org/?p=63 내부 링크가 있었으나, 9/23 v3 구조화 원고에는 관련 글을 표현하는 필드가 없어 링크가 사라졌다. 공식 질병청 지정기관 CTA는 의료기관 검색 기능이고, #63 종합 일정 글은 접종군별 일정·횟수의 보충 읽을거리라 서로 대체하지 못한다.

### 코드 근본 조치

- agent-publisher/agents/related_links.py: 동일 사이트의 명시적 ?p=ID 내부 글 이동을 보수적으로 식별하고 기존→제안에서 누락된 대상 ID를 계산.
- agent-publisher/agents/editorial.py: plan.related_posts를 최대 2개까지 검증하고, 대상이 현재 공개 글인지·자기 자신이 아닌지·정확한 내부 URL인지 확인하며 검토된 관련 글 카드로 렌더링.
- agent-publisher/agents/editorial_writer.py: 구조화 Plan에 related_posts를 추가하고 독립 의미 검토에서 공개 상태·관련성·도착 주제·기존 링크 보존을 확인하도록 연결.
- scripts/prepare_post_approval.py, agent-publisher/agents/editorial_updater.py: 기존 공개 본문의 명시적 내부 글 링크가 제안본에서 사라지면 승인 준비와 실제 갱신 양쪽에서 fail-closed.
- agent-publisher/tests/test_related_post_navigation.py: 정상 렌더, 미공개/자기링크/잘못된 URL/리뷰 결속, 기존 링크 누락, 읽기 전용 preflight 차단을 검증.

### 새 리뷰→실반영→사후 확인

1. 기존 검토본을 그대로 재사용하지 않고 #81 v3 원고에 **개정 전 실제 앵커 문구를 원본 PRIVATE 백업에서 다시 추출**해 관련 글 #63 한 건을 구조화 필드로 추가했다.
2. 현 운영 목록에서 자기 #81을 제외한 38건을 다시 읽어 #63이 현재 publish임을 확인했다.
3. 새 editorial_cli.py review는 1차에 로컬 삽입 문자열 인코딩 문제를 의미 검토가 거부해 semantic_review_failed로 중단했다. 원본 백업에서 UTF-8 앵커 문구를 재추출해 후보를 다시 만들었고, 재검토는 **ready / exit 0**. 기본 Gemini 3.5 Flash는 무료 티어 429에 걸렸으나 기존 모델 cascade가 다음 모델로 전환해 정상 검토를 완료했다.
4. 동일 후보 editorial_cli.py check **ready / exit 0**.
5. scripts/prepare_post_approval.py 실제 운영 읽기 전용 사전검사: **ready / exit 0**, 공식 출처 SHA 재조회 일치, 현재 저장 SHA 959d932c…71c3f, 제안 SHA eb166ae5…52af7.
6. 기존 사용자가 승인한 “검증이 끝난 기존 공개 글은 승인 대기 없이 즉시 반영” 범위와 현행 게이트를 모두 만족해 정규 scripts/update_existing_via_ssh.py의 ID 81 한정 갱신을 실행. **exit 0**, 새 저장 SHA eb166ae519293560ce06d8a16f15992c545d3fb4adeb92258074463dc5252af7.
7. 사후 읽기: DB 저장본문에 관련 링크 1개, 공개 #81 HTTP 200과 공개 HTML 관련 링크 1개, ?p=63 HTTP 200 및 최종 host lifeinfo24.org. 제목·slug·상태·게시일 등 비교 메타 변경 0, excerpt 변경 없음, modified만 정상 갱신.
8. 이전 09:14 사후 공개 REST 기준선과 최종 새 REST 29편을 비교하면 ID 집합은 동일하고 **추가 변경은 #81의 content, modified 두 필드만**이다.

따라서 #81 관련 글 회귀는 **최종 상태에서 FIXED/PASS**다. WP에 다른 글을 다시 적용하지 않았다.

## 4. 현재 남은 콘텐츠·독자 흐름 문제

### 남은 구형 13편 — HOLD

- #103: 목포시 자체사업 공식 자료가 15~65세와 15~64세로 충돌. 신규 critical_facts 가드는 실제 자체사업 질문에서 양 공식 페이지가 일치하지 않으면 mokpo_city_program_age_conflict_unresolved로 차단한다. HWP 원자료도 현 fetch_sources 재수집 계약이 미완성.
- #70: NOL 국내 공식 상품 원문 HTTP 403. 현재 판매기간·좌석/판매 상태를 확정할 수 없음.
- #99: 동일 공식 상품 원문은 재조회되지만 영문 월 표기→숫자 월의 보수적 근거 검사와 실제 판매기간/상태가 별도 문제.
- #85: welfare를 evergreen으로 우회할 수 없고, 원본의 사업별 확인표·방문 대안 손실 위험이 있다.
- #125/#139: 국세청 적용 코호트/중복/변동 출처와 #139 제목·내부 링크 문제가 남음.
- #119/#144/#145/#163/#217/#219: 9/27 또는 9/30 종료로 현 30일 최소 유효기간을 충족하지 못함.
- #220: 신청 종료일·기간 라벨의 공식 증거 부족.

실제 콘텐츠 E2E에서는 13/13 review·check가 exit 2로 중단됐고, 승인 준비 manifest도 13/13 blocked였다. **오늘 추가 승인 가능한 잔여 구형 글은 0편**이다.

### 최신/기존 글의 남은 실제 링크·행동 문제

- **#85:** 실제 클릭한 ‘보조금24 원클릭 조회’는 일반 plus.gov.kr 홈, ‘복지멤버십 온라인 신청 바로가기’는 복지로 일반 홈으로 도착해 레이블이 약속하는 구체 흐름과 불일치. #85 전체 원고가 HOLD라서 raw WP 링크만 바꾸지 않는다.
- **#127:** 현재 홈택스 문헌 링크는 홈택스 일반 WebSquare 화면으로 리디렉션되고 직접 미수령 환급 조회 폼까지 검증되지 않았다. 현재 CTA 버튼은 아님.
- **#140:** 본문은 정부24 검색/상태조회 메뉴를 설명하지만 현재 gov.kr 앵커/CTA는 0. 실브라우저에서 정부24 ‘여권 재발급’ 서비스 안내 …/126200000030, 상태 조회 …/126200000038까지는 확인했으나 실제 ‘신청하기’ 이후 최종 인증/제출 목적지는 확인하지 않아 행동 버튼으로 자동 승격하지 않았다. 옛 gov.kr 루트는 정확한 최종 업무 URL이 아니므로 단순 복원하지 않는다.

## 5. 코드·데이터 변경과 차이점

### 편집·출처·기존 글 안전 경로

주요 추적 변경: agent-publisher/agents/critical_facts.py, curator.py, editorial.py, editorial_updater.py, editorial_writer.py, publisher.py, search_intent.py, temporal_validation.py, docs/EDITORIAL_SYSTEM.md.

주요 신규 파일: agent-publisher/agents/related_links.py, scripts/prepare_post_approval.py, scripts/update_existing_via_ssh.py, scripts/build_legacy_approval_dashboard.py, scripts/build_legacy_current_dashboard.py, scripts/build_legacy_full_approval_index.py.

핵심 차이는 공식 출처 본문 범위/변동 메타데이터 처리, 중복·기간·공연/복지/독감 특수 조건, 구조화 표·CTA·관련 글 렌더, 현 운영 inventory·원본 SHA·PRIVATE 백업·CAS·사후 저장 확인을 공통 경로에서 fail-closed하는 것이다.

### 반복 감사

scripts/audit_legacy_posts.py와 agent-publisher/tests/test_legacy_post_audit.py는 공개 REST 전수 수집·변경감지·checkpoint/report/strict exit와 함께 다음 두 실제 결함을 수정했다.

1. 정규 이름+snapshot 파일 존재만으로 타/위조 폴더를 삭제할 수 있던 보존 결함 → run-manifest 소유/구조/해시 검증, 링크 경계, 모르는 실행 하나라도 있으면 삭제 0.
2. 같은 초에 생성한 무작위 suffix run을 이름순으로 정리해 진짜 오래된 run이 아닌 것을 삭제할 수 있던 결함 → microsecond audited_at과 검증된 manifest 시각 순 정리, 경계 동률은 fail-closed.

기존 실제 4파일짜리 pre-manifest 수동 실행은 소급 소유를 꾸며내지 않고 그대로 보존한다.

### 회귀 테스트/도구

신규·수정 테스트에는 test_related_post_navigation.py, test_legacy_mokpo_conflict.py, test_legacy_reference_period.py, test_post_approval_preflight.py, test_update_existing_via_ssh.py, test_legacy_current_dashboard.py, test_legacy_full_approval_index.py, test_duplicate_citation_scope.py, test_legacy_source_citation_scope.py, test_koreakr_briefing_source.py, test_mohw_attachment_counters.py, test_national_flu_reference.py 및 기존 편집/출처/레이아웃/티켓/감사 테스트 보강이 포함된다.

작업 이력 문서는 legacy-*, resume-*, interruption-*, callout-spacing-audit-2026-09-22.md에 단계별로 분리했다. PRIVATE 원본·초안 전체 목록·API 비밀·브라우저 증거 원자료는 tmp/ Git 제외 경로에 유지한다.

## 6. 최종 테스트와 실제 동작 검증

- 최종 관련 핵심 회귀: related-post + 목포 충돌 + recurring audit **33/33 PASS**.
- 최종 전체 Python unittest: **311 실행 / 310 PASS / 1 SKIP / 실패 0 / exit 0**.
- 최종 현재 트리 재확인 기준 활성 Python **91개 compile / 오류 0**, git diff --cached --check exit 0. 이전 중간 검사에서는 파일 분모가 87개·88개이던 시점에도 모두 compile 통과했고, Bash backup/restore bash -n, Node bridge 구문/정책 테스트, Compose config도 통과했다. PHP CLI·ShellCheck는 해당 Windows PATH에 없어 UNVERIFIED.
- 공개 독자 E2E(수정 전 독립 실행): 첫 UTM 진입, 검색→결과→실제 클릭 **5/5 PASS**, 목차 키보드 Enter **5/5 PASS**, 360/390/1280/CSS200 표본에서 문서 전체 가로 overflow 없음. #63/#81 KDCA 실제 CTA는 2026~2027 인플루엔자 지정의료기관 검색 UI까지 도착.
- 최종 #81 수정 후 별도 실상태 검사: 저장 SHA/내부 링크/공개 HTML/대상 #63 HTTP와 메타 보존을 모두 재확인.
- 최종 공개 REST: **29편, 1페이지, 이전 postpublish ID 집합과 동일**, 최종 수정으로 추가 변경된 ID는 #81 하나뿐.

테스트 성공을 실제 로그인 신청·결제·접종 예약, 네이티브 200%·스크린리더, 관리자 인증 UI, 재해복구 성공으로 확대하지 않는다.

## 7. 미완료·UNVERIFIED

1. 구형 13편의 공식 근거/기간/중복/독립 의미 검토 해결과 실제 현대화.
2. #85/#127/#140의 검증된 최종 행동 목적지와 새 전체 리뷰.
3. 네이티브 브라우저 200%, 스크린리더, #85 표의 물리 키보드/터치 가로 스크롤.
4. 인증된 WordPress 관리자 UI의 글 목록/ID 열/편집 화면 읽기 전용 E2E.
5. 실제 로그인 후 정부/기관 신청·조회·예약·결제 완료.
6. legacy audit 운영 cron, 외부 알림 수신자/전달, 사람 review register.
7. 실제 격리 restore/DR, 오프사이트 암호화·키 보관.
8. Linux 실제 symlink/junction·경쟁 상태 보존 공격 검증.
9. #77 휴지통 이동 이유 확인 및 복원 여부 결정.

## 8. 승인·배포 경계

이미 존재하는 공개 글은 **공식 출처 재조회→현행 독립 검토→CLI check→전체 WP inventory→원본 백업/SHA→CAS→정규 ID 한정 updater→사후 확인**을 모두 통과하면 사용자의 기존 승인 범위에서 즉시 갱신할 수 있다. 이번 최종 #81 복구가 이 경로의 실제 사례다.

다음은 **추가 승인/결정이 필요**하다: legacy-audit cron 설치, 외부 알림 수신자 설정, #77 복원/상태 변경, 30일 정책 예외 신설, 신규 draft 공개 승격, 전면 디자인/서버 런타임 재배포, 실제 restore/DR 훈련, 오프사이트 암호화·키 운영.

기존에 배포된 레이아웃/접근성 MU 및 백업 관련 운영 자산은 후속 SHA 검증이 끝났고 **재배포하지 않는다**. 현재 로컬 editorial/audit 소스 전체를 서버에 복사하거나 서비스 재시작하는 blanket 배포 승인도 없다.

Git은 프로젝트 지침에 따라 **검증된 현대화 관련 파일만 선택적으로 stage/commit/push**한다. git add -A는 사용하지 않으며, 별도 작업인 콘서트 커버·플러그인 소유권 복구·프로젝트 최적화 문서는 이 계획의 커밋에서 제외한다.

## 9. 최종 결론

- **완료:** 현재 재고 기준선, 6단계 장부, 운영 레이아웃 기반, 검증된 기존 글 갱신, #81 회귀 복구, 공식 충돌/기간/중복 fail-closed 게이트, 반복 감사의 두 데이터 보존 결함 수정, 실제 E2E 및 전체 회귀검사.
- **미완료:** 남은 구형 13편의 실제 현대화, 세 개 주요 행동 링크(#85/#127/#140), 접근성/관리자/실업무의 미검증 구간, 운영 cron/알림/사람 검토 등록부, 실제 DR.
- 따라서 **“전체 기존 글 현대화 완료”라고 보고하지 않는다.** 안전하게 완료된 부분은 운영 반영·테스트 증거와 함께 확정하고, 근거 부족 항목은 HOLD/UNVERIFIED 상태를 유지한다.
