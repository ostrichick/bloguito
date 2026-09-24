# 인천공항 출국장 대기시간 GPT 직접 작성 임시글 — 2026-09-24

## 작업 범위

- 사용자 직접 요청에 따라 서버 예약 Gemini writer가 아니라 현재 ChatGPT의 GPT-5.6 Sol로 원고를 작성했다.
- 검색 질문은 “인천공항에 가기 전에 제1·제2여객터미널의 예상 혼잡도와 출국장 실시간 대기시간을 어디서 어떻게 확인하나요?”로 한정했다.
- 공개 전환은 요청받지 않았으므로 WordPress draft까지만 생성했다.

## 중복·공식 원문

- 작업 직전 운영 WordPress의 publish, draft, pending, future, private 전체 38건을 SSH/WP-CLI로 읽기 전용 조회했다. 인천공항·출국장·혼잡을 제목으로 하는 기존 글은 없었다.
- 인천국제공항공사 공식 자료만 사용했다: 공항 예상 혼잡도, 출국장 실시간 대기시간, 출국절차와 터미널 확인 안내.
- 예상 혼잡도는 시간대별 예측 승객 수, 실시간 대기시간은 보안검색·출국심사 소요에 따라 달라지는 별도 값으로 구분했다.
- 최초 후보에는 2026-09-25 오전 예상 승객 숫자표가 있었으나, 최종 확인에서 공식 www/business 계열 화면의 예측값이 같은 날짜에도 서로 다르게 노출되는 것을 확인했다. 인천공항도 항공편 변경 시 예측 승객 수가 달라질 수 있다고 안내하므로 고정 숫자표를 최종 원고에서 제거했다.
- 최종 글은 추석처럼 혼잡한 날에도 최신 예고 화면을 다시 보고, 공항으로 이동하는 날에는 실시간 대기시간을 새로고침하는 절차를 중심으로 구성했다.

## GPT 원고와 검토

- authoring.mode: interactive_chatgpt
- authoring.model 및 used_model: GPT-5.6 Sol
- 로컬 manual-review의 Gemini 독립 의미 검토는 source_support, conditions_preserved, question_answered, useful_lifetime, no_reader_deflection, no_unsupported_claims 6개 모두 true, issues 빈 배열이었다.
- 이어진 deterministic check는 status=ready, 사유와 상세가 모두 비어 있었다.
- 서버 editorial_cli.py publish도 자체 의미 검토와 검사를 다시 수행해 ready를 확인한 뒤 draft를 생성했다.
- 숫자표 제거 후 새 GPT 원고도 로컬 manual-review를 다시 수행했고 6개 검토 항목 모두 true, issues 빈 배열이었다. 서버에서 초안 수정 직전에도 같은 6개 항목을 다시 검토해 모두 true, report ready를 확인했다.

## WordPress 저장 결과

- Draft ID: 393
- 제목: 인천공항 출국장 대기시간 확인: T1·T2 예상 혼잡도 보는 법
- 상태: draft
- 최종 수정시각: 2026-09-24 11:08:10 KST
- 최종 저장 본문 SHA-256: 2dc8207d1e0faf6af3691538a2eff4c9292ead20876ead17682ef06966756efb
- WordPress 저장 본문은 로컬 검토 원고의 공통 renderer 출력과 문자열 기준으로 일치했다.
- 서버 draft 색인에 interactive_chatgpt / GPT-5.6 Sol 작성 provenance와 서버 재검토 6/6 true, issues 빈 배열이 보존됐다.
- 최종 본문에는 제거 대상으로 정한 과거 예측값 4557, 4157, 4128, 3946이 남아 있지 않음을 저장 후 재검사했다.

## 인천공항 공식 페이지 수집기 보완

- 인천공항의 공개 한국어 subview 페이지는 일반 브라우저에서 HTTP 200이지만 Python 기본 User-Agent에는 빈 HTTP 302를 반환하는 것을 재현했다.
- 로컬 agents/editorial_writer.py에서 www.airport.kr 및 airinfo.airport.kr의 정확한 /ap_ko/<번호>/subview.do 경로에만 브라우저 동등 User-Agent를 사용하도록 범위를 제한했다. allow_redirects=False와 비-200 차단은 유지한다.
- 신규 test_airport_official_source.py는 해당 경로에만 헤더가 적용되고 무관한 경로는 기존 빈 헤더 정책을 유지하는지 검사한다.
- 운영 서버의 editorial_writer.py는 GitHub main보다 여러 기능이 뒤처져 있어 로컬 파일 전체를 덮어쓰지 않았다. 서버 기존 SHA 1bbf100c9a4f3bce39dd6c488cfbb71f5a8e409433000a77331f5af864bc4191를 고정한 뒤 인천공항 UA 분기만 포함한 후보를 적용했다.
- 서버 원본 백업: /home/ubuntu/agent-publisher/data/editorial_runs/deploy-airport-source-20260924T102654/editorial_writer.py
- 서버 적용 SHA: c91e0788470b823d90e73fa0347feb0b7d079bf67a7081e631e9308e5a512f8c
- 적용 후 Python 문법 검사와 당시 실제 공식 출처 4개 재수집을 실행했고 저장 bundle의 source SHA와 4/4 정확히 일치했다.

## 검토된 draft 본문 수정 경로

- 기존 update-draft는 이미 검토된 본문을 그대로 유지하면서 action 링크 같은 renderer 소유 요소만 갱신하도록 설계되어 있어, 독립 재검토를 마친 새 본문 전체로 교체하는 이번 작업에는 사용할 수 없었다.
- 새 agents/editorial_draft_reviser.py는 같은 draft ID에 대해 현재 저장 본문 SHA, 기존 검토 bundle, 동일 주제·제목, 자기 자신을 제외한 전체 중복 검사, 새 bundle 전체 검토, 최신 공식 source SHA, 사람 편집 여부, 발췌문 변경 여부를 확인한다.
- 모든 검사를 통과하면 WordPress 원본 전체와 draft index를 각각 백업한 뒤 본문·자동 발췌문과 저장된 editorial bundle을 함께 갱신한다. 새 editorial_cli.py 액션 이름은 revise-draft이며 --post-id, --expected-content-sha256, --confirm-update를 요구한다.
- 운영 서버는 전체 로컬 코드를 덮어쓰지 않고 새 editorial_draft_reviser.py 모듈만 추가했으며, 이후 renderer 소유 출처 footer만 달라진 경우도 본문 동일성을 검증해 허용하도록 보강했다. 현재 서버 SHA는 016d769652e066b7067dc165fe9073724c8b701c17a0e5a48ba59ab66d28cd4a이다.
- #393 최종 교체 직전 서버 자체 preflight와 Gemini 의미 검토를 다시 수행했고 모두 ready였다. 교체 중 생성한 백업은 다음 두 파일이다.
  - /home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-393-20260924T103918587753.json
  - /home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-index-393-20260924T103918587753.json
- 서버의 전체 editorial_cli.py는 현재 GitHub main보다 뒤처져 있어 새 CLI 액션 전체를 덮어쓰지 않았다. 이번 적용은 동일 검토 로직을 호출하는 제한된 Python 어댑터로 실행했고, 실제 WordPress 쓰기는 새 revise_reviewed_draft 함수 안에서만 수행했다.

## 출처 footer 중복·표시명 개선

- 사용자 확인에서 상단 CTA로 이미 제공한 예상 혼잡도와 실시간 대기시간 URL이 하단 출처에도 반복되고, 세 링크 모두 HTML title인 “인천국제공항”으로 표시돼 각 페이지의 역할을 구분할 수 없는 문제가 확인됐다.
- 공통 renderer는 evidence에 쓰인 source 중 상단 action 버튼과 URL이 완전히 같은 항목은 하단 출처 목록에서 제외한다. 행동 링크와 다른 별도 근거 페이지는 그대로 남긴다.
- 근거 페이지의 HTML title이 기관명처럼 모호할 때 선택적 citation_label을 사용하며, 4~100자 범위와 HTML/개행 금지 검사를 추가했다.
- #393의 별도 근거 페이지는 “인천국제공항 출국절차·터미널 확인 안내”로 표시한다. 최종 HTML 검증 결과 상단 CTA는 예상 혼잡도·출국장 실시간 대기시간 2개를 유지하고, 하단 source-list에는 출국절차 페이지 1개만 남는다.
- 운영 서버는 전체 editorial.py를 덮어쓰지 않고 현재 서버 파일을 기준으로 위 renderer 분기만 패치했다. 현재 서버 editorial.py SHA는 7071fbb958c00651e2751926ea7a554cb16bef67dcbb9aa06cc7e1f38f50271f이다.
- 서버 원본 백업: /home/ubuntu/agent-publisher/data/editorial_runs/deploy-source-footer-20260924T110700/
- #393 footer 교체 직전 서버 preflight와 Gemini 독립 의미 검토는 다시 6/6 true, issues 빈 배열, report ready였다.
- #393 footer 교체 백업:
  - /home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-393-20260924T110808063595.json
  - /home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-index-393-20260924T110808063595.json

## 실행 중 차단과 수정

- 첫 서버 draft 시도는 WordPress 쓰기 전에 서버의 구버전 숫자 근거 검사에서 “2026년 9월 25일”과 공식 원문의 “2026.09.25” 표기 차이를 동일 날짜로 보지 못해 차단됐다.
- 날짜는 소제목과 표 캡션에 명시되어 있어 본문 문장을 “추석 당일 공식 예고값”으로 다듬고 다시 GPT 원고 검토를 수행했다. 두 번째 서버 실행은 정상 통과했다.
- draft 생성 뒤 공식 예상 혼잡도 화면을 다시 대조하는 과정에서 공식 호스트별 예측 승객 숫자가 일치하지 않는 것을 확인했다. 변동 가능한 숫자를 독자에게 고정값처럼 남기지 않기 위해 해당 숫자표 전체를 제거하고 공식 조회 절차 중심의 새 원고로 독립 재검토·교체했다.
- 로컬 sync_wordpress_inventory.py는 Windows에서 sudo/docker subprocess 출력을 CP949로 읽는 과정의 UnicodeDecodeError로 실패했다. WordPress 쓰기는 발생하지 않았고, 최신 재고는 SSH/WP-CLI UTF-8 JSON을 별도 읽기 전용 스크립트로 받아 검증했다.
