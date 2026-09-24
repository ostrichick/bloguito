# 인천공항 출국장 대기시간 GPT 직접 작성 임시글 — 2026-09-24

## 작업 범위

- 사용자 직접 요청에 따라 서버 예약 Gemini writer가 아니라 현재 ChatGPT의 GPT-5.6 Sol로 원고를 작성했다.
- 검색 질문은 “인천공항에 가기 전에 제1·제2여객터미널의 예상 혼잡도와 출국장 실시간 대기시간을 어디서 어떻게 확인하나요?”로 한정했다.
- 공개 전환은 요청받지 않았으므로 WordPress draft까지만 생성했다.

## 중복·공식 원문

- 작업 직전 운영 WordPress의 publish, draft, pending, future, private 전체 38건을 SSH/WP-CLI로 읽기 전용 조회했다. 인천공항·출국장·혼잡을 제목으로 하는 기존 글은 없었다.
- 인천국제공항공사 공식 자료만 사용했다: 2026-09-25 제1여객터미널 예상 혼잡도, 같은 날 제2여객터미널 예상 혼잡도, 출국장 실시간 대기시간, 출국절차와 터미널 확인 안내.
- 예상 혼잡도는 시간대별 예측 승객 수, 실시간 대기시간은 보안검색·출국심사 소요에 따라 달라지는 별도 값으로 구분했다.
- 2026-09-25 오전 참고표는 날짜가 붙은 시의성 스냅샷으로만 두고, 글의 핵심은 특정 명절 이후에도 이용할 수 있는 공식 조회 절차로 구성했다.

## GPT 원고와 검토

- authoring.mode: interactive_chatgpt
- authoring.model 및 used_model: GPT-5.6 Sol
- 로컬 manual-review의 Gemini 독립 의미 검토는 source_support, conditions_preserved, question_answered, useful_lifetime, no_reader_deflection, no_unsupported_claims 6개 모두 true, issues 빈 배열이었다.
- 이어진 deterministic check는 status=ready, 사유와 상세가 모두 비어 있었다.
- 서버 editorial_cli.py publish도 자체 의미 검토와 검사를 다시 수행해 ready를 확인한 뒤 draft를 생성했다.

## WordPress 저장 결과

- Draft ID: 393
- 제목: 인천공항 출국장 대기시간 확인: T1·T2 예상 혼잡도 보는 법
- 상태: draft
- 저장시각: 2026-09-24 10:21:53 KST
- 저장 본문 SHA-256: aca34cdfd1cb21b4246ff0e87fd69dbaf4b3769e0d9686591af6108a8ded233c
- WordPress 저장 본문은 로컬 검토 원고의 공통 renderer 출력과 문자열 기준으로 일치했다.
- 서버 draft 색인에 interactive_chatgpt / GPT-5.6 Sol 작성 provenance와 서버 재검토 6/6 true, issues 빈 배열이 보존됐다.

## 인천공항 공식 페이지 수집기 보완

- 인천공항의 공개 한국어 subview 페이지는 일반 브라우저에서 HTTP 200이지만 Python 기본 User-Agent에는 빈 HTTP 302를 반환하는 것을 재현했다.
- 로컬 agents/editorial_writer.py에서 www.airport.kr 및 airinfo.airport.kr의 정확한 /ap_ko/<번호>/subview.do 경로에만 브라우저 동등 User-Agent를 사용하도록 범위를 제한했다. allow_redirects=False와 비-200 차단은 유지한다.
- 신규 test_airport_official_source.py는 해당 경로에만 헤더가 적용되고 무관한 경로는 기존 빈 헤더 정책을 유지하는지 검사한다.
- 운영 서버의 editorial_writer.py는 GitHub main보다 여러 기능이 뒤처져 있어 로컬 파일 전체를 덮어쓰지 않았다. 서버 기존 SHA 1bbf100c9a4f3bce39dd6c488cfbb71f5a8e409433000a77331f5af864bc4191를 고정한 뒤 인천공항 UA 분기만 포함한 후보를 적용했다.
- 서버 원본 백업: /home/ubuntu/agent-publisher/data/editorial_runs/deploy-airport-source-20260924T102654/editorial_writer.py
- 서버 적용 SHA: c91e0788470b823d90e73fa0347feb0b7d079bf67a7081e631e9308e5a512f8c
- 적용 후 Python 문법 검사와 실제 공식 출처 4개 재수집을 실행했고 저장 bundle의 source SHA와 4/4 정확히 일치했다.

## 실행 중 차단과 수정

- 첫 서버 draft 시도는 WordPress 쓰기 전에 서버의 구버전 숫자 근거 검사에서 “2026년 9월 25일”과 공식 원문의 “2026.09.25” 표기 차이를 동일 날짜로 보지 못해 차단됐다.
- 날짜는 소제목과 표 캡션에 명시되어 있어 본문 문장을 “추석 당일 공식 예고값”으로 다듬고 다시 GPT 원고 검토를 수행했다. 두 번째 서버 실행은 정상 통과했다.
- 로컬 sync_wordpress_inventory.py는 Windows에서 sudo/docker subprocess 출력을 CP949로 읽는 과정의 UnicodeDecodeError로 실패했다. WordPress 쓰기는 발생하지 않았고, 최신 재고는 SSH/WP-CLI UTF-8 JSON을 별도 읽기 전용 스크립트로 받아 검증했다.
