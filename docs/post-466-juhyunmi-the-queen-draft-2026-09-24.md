# #466 주현미 데뷔 40주년 The Queen 용인 콘서트 임시글 작성 — 2026-09-24

## 작업 범위

- 사용자 요청: 주현미 데뷔 40주년 The Queen 콘서트를 주제로 유용한 포스트를 임시글로 작성
- 신규 WordPress ID: `466`
- 최종 상태: `draft`
- 제목: `주현미 데뷔 40주년 〈The Queen〉 용인 콘서트: 가격, 할인, 예매 안내`
- 카테고리: `공연/콘서트 예매` (`concert`, term 2)
- 공개 승격: 실행하지 않음

현재 WordPress 공개, 초안, 검토대기, 예약, 비공개 글 41개에서 `주현미`, `The Queen` 중복을 검색했으며 기존 관련 글은 없었다.

## 공식 근거

NOL 공식 개별 상품 페이지를 사용했다.

- URL: `https://nol.yanolja.com/ticket/products/26012715`
- 최종 검토 source SHA256: `86e098996363128ad1f1776450106414b19c112cedd6a56d2f33794331870add`
- 상품 페이지의 공식 공연 정보와 상품 JSON의 예매기간, 상태 필드를 함께 확인
- 예매기간: 2026-09-03 14:00부터 2026-11-07 11:00
- 상품 상태값: `Y`, 검증 시점의 예매기간 안에 있음을 확인

본문에서는 좌석 재고나 잔여석을 보장하는 표현을 사용하지 않았다.

## 최종 원고 구성

- 2026년 11월 8일 일요일 오후 6시 30분 용인포은아트홀 공연
- 공연시간 120분, 만 7세 이상
- R석 121,000원, S석 99,000원
- 장애인 본인 20% 할인
- 국가유공자 본인 20% 할인, 유족증 불가
- 할인 티켓 현장 수령과 복지카드, 국가유공자증 확인 조건
- 할인 중복 불가와 현장 사후 할인 불가
- 휠체어 이용 고객과 동반 1인 포함 총 2매 조건
- OP석 1~3열의 단차 없음, 좁은 앞 간격, OP구역 스탠딩 금지
- 10월 20일부터 22일까지 초기 예매분 일괄배송
- 일요일 공연 예매는 전일 11시까지
- 관람일 기준 취소 수수료 표
- 취소기한 경과 후 예매 시 즉시 취소와 환불 불가 조건
- FAQ 5개
- 행동 CTA 1개: NOL 공식 용인 공연 상품으로 직접 연결
- 독자 노출 문구에서 U+00B7 가운데점 미사용

## 검토

자동 의미 검토 제공자가 `editorial_model_unavailable`로 실패해 자동 서명을 강행하지 않았다. 대신 별도 독립 GPT 검토 작업자가 현재 bundle과 bound source를 읽기 전용으로 대조했다.

1차 독립 검토에서 다음 문제를 발견해 수정했다.

- `복지카드 또는 국가유공자증 등`에서 근거보다 넓어진 `등` 제거
- 취소 수수료 규정의 우선 적용을 가능성 표현이 아니라 원문과 같은 확정 조건으로 수정
- 취소기한 경과 후 예매 시 즉시 취소, 환불 불가 조건 추가
- 국가유공자 유족증 불가를 본문에 명시
- 관람일 10일 전 수수료 표기를 원문과 같은 괄호 구조로 정리

수정 후 독립 재검토 결과:

- source_support: PASS
- conditions_preserved: PASS
- question_answered: PASS
- useful_lifetime: PASS
- no_reader_deflection: PASS
- no_unsupported_claims: PASS
- issues: 없음
- evidence quote 누락: 0
- 잘못된 source ID: 0
- 미응답 reader question: 0
- 독자 노출 가운데점: 0

최종 `validate_bundle(require_review=False)`와 리뷰 서명 후 일반 `editorial_cli.py check` 모두 `ready`였다.

## WordPress 저장 검증

- ID: `466`
- 상태: `draft`
- 카테고리: `공연/콘서트 예매`
- 저장 본문 SHA256: `c97afc7521db1aa941fe096ad6bf6c186ea84c66ae325d9f75bda0e283be2e5c`
- 검토 renderer SHA256: `c97afc7521db1aa941fe096ad6bf6c186ea84c66ae325d9f75bda0e283be2e5c`
- WordPress 저장 HTML과 검토 renderer 출력 정확히 일치
- 요약 카드 1개
- 목차 1개
- 정보표 2개
- FAQ 5개
- CTA 1개
- 제목, excerpt, 본문의 가운데점 잔여 0건
- NOL 개별 상품 직접 링크 존재
- Rank Math focus keyword 저장 확인
- Rank Math description 저장 확인
- 기본 작업트리 `draft_posts.json`에 #466 reviewed manifest 병합 완료

공개 발행은 수행하지 않았다.
