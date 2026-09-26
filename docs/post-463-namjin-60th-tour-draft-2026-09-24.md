# #463 남진 데뷔 60주년 전국투어 임시글 작성 — 2026-09-24

## 작업 범위

- 사용자 요청: 남진 데뷔 60주년 전국투어를 주제로 유용하고 알찬 정보글 작성
- 신규 WordPress ID: `463`
- 최종 상태: `draft`
- 제목: `2026 남진 데뷔 60주년 전국투어: 지역별 일정, 티켓 가격, 예매`
- 카테고리: `공연/콘서트 예매` (`concert`, term 2)
- 공개 승격: 실행하지 않음

현재 WordPress 전체 재고에서 남진 관련 기존 글이 없는 것을 확인한 뒤 신규 글로 작성했다. 독자가 실제 공연을 고를 때 먼저 필요한 지역별 일정과 공연장, 확인된 티켓 가격, 할인 조건, 직접 예매 경로를 앞쪽에 배치했다.

## 공식 근거

2026-09-24에 다음 티켓링크 공식 페이지를 수집했다.

- 남진 전국투어 지역별 일정: `https://www.ticketlink.co.kr/bridge/901`, SHA256 `af78f2dc8c0d40937f8da8ee269f2e96b6809c16f0448ac48d14ce288b75a05e`
- 원주 티켓오픈 안내: `https://facility.ticketlink.co.kr/help/notice/65731`, SHA256 `4a0f1c68a4e65641579d4cd8b469edab20eb1dbeff01901f2c5c2a34471dcd36`
- 김제 티켓오픈 안내: `https://www.ticketlink.co.kr/help/notice/65876`, SHA256 `b2a110c11d04d63cf0d77a70ce41fc127bd7eb8e0bd82139f011342e4b80d38f`

공식 전국 일정 페이지에서 2026년 9월 24일 이후 공연으로 평택 10월 11일, 원주 10월 31일, 익산 11월 7일, 음성 11월 8일, 고령 11월 15일, 김제 11월 21일을 확인했다. 각 행의 `예매하기`가 실제 지역별 상품으로 연결되는 것도 HTML 링크에서 다시 대조했다.

과거 티켓오픈 공지 중 현재 전국 일정과 날짜가 충돌하는 지역은 가격 근거로 사용하지 않았다. 지역별 가격을 하나의 전국 공통 가격으로 추정하지 않고, 현재 일정과 일치하는 공식 공지를 확보한 원주와 김제의 가격만 본문 비교표에 사용했다.

## 원고 구성

- 핵심 답변 카드
- 평택, 원주, 익산, 음성, 고령, 김제 6개 지역 일정표
- 원주와 김제의 현재 공식 티켓 가격 비교표
- 원주와 김제 할인 대상, 현장 증빙 조건
- 지역별 상품으로 이동하는 직접 예매 버튼과 전체 일정 경로
- 김제 판매 마감, 취소 마감, 매수 제한, 일괄배송일
- FAQ 3개
- 공식 출처 3개

원주 공식 공지는 VIP석 132,000원, R석 110,000원, S석 99,000원으로 안내한다. 김제 공식 공지는 VIP석 143,000원, R석 132,000원으로 안내한다. 김제는 판매 마감 2026년 11월 19일 11시, 취소 마감 공연 전일 17시, 1인 10매, 일괄배송 2026년 10월 28일 조건을 별도로 반영했다.

## 일정 검증 지원 보강

기존 일정 전용 검증은 YES24 지역별 목록만 지원하고 있었다. 티켓링크 공식 투어 브리지의 고정된 `지역/제목 → 기간 → 장소 → 예매하기` 구조에서 해당 가수의 단일 날짜 공연만 추출하는 `extract_ticketlink_bridge_schedule`을 추가했다.

이 경로는 공식 목록에 표시된 공연 날짜와 공연장, 예매 목적지의 존재만 검증한다. 잔여 좌석이나 판매 마감은 추론하지 않는다. `판매 예정`, `판매 종료` 행은 일정 전용 검증 결과에 포함하지 않도록 제한했다.

- 관련 단위 테스트: `tests.test_schedule_listing` 9개 통과
- 구조화 원고 사전 검사: `ready`
- 독립 의미 검토: 6개 항목 모두 `true`, `issues=[]`
- 최종 CLI `check`: `ready`

## 최종 저장 검증

- ID: `463`
- 상태: `draft`
- 제목: `2026 남진 데뷔 60주년 전국투어: 지역별 일정, 티켓 가격, 예매`
- 카테고리: `공연/콘서트 예매`
- 최종 본문 SHA256: `ac1acc840139549c57b4f7753d922bee2eafcdc004a11597538acb870016316c`
- 검토 renderer SHA256: `ac1acc840139549c57b4f7753d922bee2eafcdc004a11597538acb870016316c`
- WordPress 저장 HTML과 검토 renderer 출력: 정확히 일치
- draft index reviewed manifest: 존재
- 작성 provenance: `interactive_chatgpt`, `GPT-5.6 Sol`
- 저장된 독립 검토: `source_support`, `conditions_preserved`, `question_answered`, `useful_lifetime`, `no_reader_deflection`, `no_unsupported_claims` 모두 `true`, `issues=[]`

## 2026-09-26 지역별 가격·직접 예매 링크 보강 재검증

사용자 피드백에 따라 기존 6개 지역 일정에 비해 부족했던 가격과 직접 예매 경로를 다시 보강했다. 2026-09-26 09:46 KST에 티켓링크 전국투어 브리지와 평택·원주·익산·음성·고령·김제 NOL 공식 상품 페이지를 다시 수집했고, 09:54 KST 독립 의미 검토와 구조 검사를 통과한 최종 렌더를 기준으로 확인했다.

- 직접 티켓링크 상품 링크: 6/6
  - 평택 `https://www.ticketlink.co.kr/product/64896`
  - 원주 `https://www.ticketlink.co.kr/product/65198`
  - 익산 `https://www.ticketlink.co.kr/product/65074`
  - 음성 `https://www.ticketlink.co.kr/product/64244`
  - 고령 `https://www.ticketlink.co.kr/product/64316`
  - 김제 `https://www.ticketlink.co.kr/product/65605`
- 지역별 공식 상품 기본 가격: 6/6
  - 평택: VIP 143,000원 / R 121,000원 / S 99,000원 / A 77,000원
  - 원주: VIP 132,000원 / R 110,000원 / S 99,000원
  - 익산: VIP 143,000원 / R 121,000원 / S 99,000원
  - 음성: R 132,000원 / S 121,000원
  - 고령: VIP 132,000원 / R 121,000원 / S 99,000원
  - 김제: VIP 143,000원 / R 132,000원

14시대 운영 WordPress를 Tailscale 사설 관리 경로로 읽기 전용 재조회한 결과 #463은 여전히 `draft`이고 수정시각은 `2026-09-26 09:54:50`이었다. 저장 본문 SHA256은 `a33d738f0a3fc878f5d6b691cf95dcedd82112dce1f3ed5ffaeaed481e457048`이며 최종 검토 `tmp/post463-refresh-20260926/bundle.html`의 SHA256과 정확히 같다. 따라서 이 재검증 단계에서는 동일 본문을 중복 저장하지 않았다. 공개 전환도 수행하지 않았다.

오후 재검증 중 현재 편집 코드가 Ticketlink 브리지의 광역 `지역` 값(경기, 강원, 전북, 충북, 경북)과 독자 표의 실제 공연 도시명(평택, 원주, 익산, 음성, 고령, 김제)을 동일 문자열로 비교해 `schedule_listing_not_bound`를 내는 문제를 확인했다. Ticketlink 브리지에 한해 일정 결합을 정확한 날짜+공연장으로 검사하도록 좁게 수정하고, 광역지역과 도시명이 달라도 날짜+공연장이 정확하면 통과하고 공연장이 다르면 계속 차단되는 회귀 테스트를 추가했다.

- 현재 정책 `manual-review`: `ready`, reasons `[]`
- 현재 정책 최종 CLI `check`: `ready`, reasons `[]`
- 일정/NOL 관련 집중 회귀 테스트: 30건 전부 통과
- `git diff --check` 대상 변경 파일: 통과
- 최종 렌더 SHA256: `a33d738f0a3fc878f5d6b691cf95dcedd82112dce1f3ed5ffaeaed481e457048`
- 최종 운영 WordPress 재조회: `draft`, 수정시각 `2026-09-26 09:54:50`, 본문 SHA256 위 렌더와 정확히 일치, Ticketlink 직접 상품 링크 6개 확인

최종 재조회 직전 Tailscale SSH 한 번이 종료 코드 255로 실패했으나, 즉시 `tailscale status`와 1회 ping에서 서버가 active/direct이고 응답하는 것을 확인한 뒤 같은 읽기 전용 WordPress 조회를 재실행해 정상 성공했다. 이 연결 오류 동안 WordPress 쓰기는 수행하지 않았다.

## 2026-09-26 일정표와 공연시간표 통합

사용자 미리보기 피드백에 따라 같은 6개 지역을 반복하던 `남은 지역 일정` 표와 `지역별 공연 시작 시간` 표를 하나로 합쳤다. 최종 첫 표는 `지역 / 날짜 / 공연시간 / 공연장` 4열, 6행이며 평택, 원주, 익산, 음성, 고령, 김제의 날짜와 시작 시각, 공연장을 한 행에서 바로 비교할 수 있다. 별도 `지역별 공연 시간도 함께 확인하세요` 절과 두 번째 시간표는 제거했다. 가격표는 정보 성격이 달라 별도 비교표로 유지했다.

각 통합 일정 행에는 Ticketlink 전국투어 일정 근거와 해당 지역 NOL 상품의 운영 시간 근거를 함께 연결했다. Ticketlink 브리지의 광역지역 값과 독자용 도시명이 다르면서 4열 표에서 공연장 열 위치도 달라지는 경우를 안전하게 검증하기 위해 일정 결합 검사는 Ticketlink에 한해 정확한 날짜와 공연장 값이 같은 행에 존재하는지 확인하도록 보완했다. 4열 `지역 / 날짜 / 공연시간 / 공연장` 회귀 테스트를 추가했으며 일정 검증 테스트 12건이 모두 통과했다.

- 구조화 원고 `manual-review`: `ready`, reasons `[]`
- 최종 CLI `check`: `ready`, reasons `[]`
- 저장 전 원본 본문 SHA256: `a33d738f0a3fc878f5d6b691cf95dcedd82112dce1f3ed5ffaeaed481e457048`
- 정규 `revise-draft` 원본 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-463-20260926T145550871384.json`
- 정규 `revise-draft` 인덱스 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-index-463-20260926T145550871384.json`
- 최종 WordPress 상태: `draft`
- 최종 수정시각: `2026-09-26 14:55:53`
- 최종 본문 SHA256: `dd835acc3cfd8884a6d618a3e5b805e3f17924c1f0c4cde82b0ca4640f22fe40`
- 검토 렌더 SHA256: `dd835acc3cfd8884a6d618a3e5b805e3f17924c1f0c4cde82b0ca4640f22fe40`, WordPress 저장본과 정확히 일치
- 최종 HTML 표: 통합 일정표 1개 + 지역별 좌석 가격표 1개
- 제거된 별도 시간표 소제목: 0건
- Ticketlink 지역별 직접 예매 링크: 6개 유지
- 공개 승격: 실행하지 않음
