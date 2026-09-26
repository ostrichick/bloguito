# #463 남진 60주년 전국투어 예매·가격 보강 — 2026-09-26

## 요청과 결과

- 사용자 확인: #463에는 남은 공연 일정이 평택, 원주, 익산, 음성, 고령, 김제 6곳인데 직접 예매 링크는 4곳, 티켓 가격은 2곳만 있어 의사결정 정보가 불완전했다.
- 대상: WordPress draft **#463**, `2026 남진 데뷔 60주년 전국투어: 지역별 일정, 티켓 가격, 예매`.
- 결과: 글 ID, 제목, `draft` 상태, 카테고리 `공연/콘서트 예매`(term 2)를 유지하면서 본문과 검토 bundle을 보강했다. 공개 전환은 하지 않았다.

## 새로 확인한 공식 근거

2026-09-26에 티켓링크 공식 투어 브리지와 현재 NOL 지역별 상품 페이지를 다시 수집했다.

- 투어 일정: `https://www.ticketlink.co.kr/bridge/901`
- 평택: `https://nol.yanolja.com/ticket/products/26011784`
- 원주: `https://nol.yanolja.com/ticket/products/26012537`
- 익산: `https://nol.yanolja.com/ticket/products/26012157`
- 음성: `https://nol.yanolja.com/ticket/products/26009734`
- 고령: `https://nol.yanolja.com/ticket/products/26009970`
- 김제: `https://nol.yanolja.com/ticket/products/26013305`

현재 상품 페이지 기준 좌석 가격은 다음과 같다.

| 지역 | 가격 |
| --- | --- |
| 평택 | VIP 143,000원, R 121,000원, S 99,000원, A 77,000원 |
| 원주 | VIP 132,000원, R 110,000원, S 99,000원 |
| 익산 | VIP 143,000원, R 121,000원, S 99,000원 |
| 음성 | R 132,000원, S 121,000원 |
| 고령 | VIP 132,000원, R 121,000원, S 99,000원 |
| 김제 | VIP 143,000원, R 132,000원 |

공연 시작 시간도 공식 상품 페이지에 맞춰 평택 오후 5시, 원주 오후 2시, 익산 오후 5시, 음성 오후 5시, 고령 오후 6시, 김제 오후 1시를 별도 표로 추가했다.

## 예매 링크 보강

렌더러의 직접 행동 버튼에 아래 지역별 티켓링크 상품 6개를 모두 연결했다.

- 평택 `https://www.ticketlink.co.kr/product/64896`
- 원주 `https://www.ticketlink.co.kr/product/65198`
- 익산 `https://www.ticketlink.co.kr/product/65074`
- 음성 `https://www.ticketlink.co.kr/product/64244`
- 고령 `https://www.ticketlink.co.kr/product/64316`
- 김제 `https://www.ticketlink.co.kr/product/65605`

투어 브리지의 `예매하기`는 일정과 지역별 예매 목적지가 존재한다는 근거로만 사용했다. 특정 좌석의 잔여 수량, 매진 여부 또는 실시간 판매 가능 상태는 단정하지 않았다.

## 할인 조건 보강

- 평택, 원주, 익산, 음성, 고령, 김제 상품에서 중증장애인 20%(동반 1인까지), 경증장애인 20%(본인), 국가유공자 20%(본인) 안내를 확인했다.
- 음성은 음성군민 20%, 고령은 고령군민 20%, 김제는 김제시민 20% 할인도 본인 기준으로 안내한다.
- 휠체어석은 공식 상품 페이지가 전화예매만 가능하다고 안내하므로 이 조건을 본문에 보존했다.

## 편집 시스템 지원 보강

이번처럼 지역별 공식 가격 근거와 직접 예매 경로가 여러 개인 투어 글을 검증 경로 안에서 처리하기 위해 다음 범위를 정식 지원했다.

- 공식 근거 최대 7개까지 수집·재검증.
- 직접 행동 링크 최대 6개까지 검증·렌더링.
- 티켓링크 투어 브리지의 `지역/제목 → 기간 → 장소 → 예매하기` 행을 검증 가능한 일정 원문으로 파싱.
- 독자용 지역은 티켓 제목의 실제 개최지(`- 평택`, `- 원주` 등)에 결합해 일정표와 원문을 정확히 대조.

관련 코드 커밋:

- `cb27a76 Support regional concert tour links`
- `b611d00 Bind Ticketlink tours to city names`

일정, CTA, 출처 상한 관련 표적 테스트 20건을 실행해 모두 통과했다.

## 독립 검토와 적용

- 첫 의미 검토에서 지역별 공연 시간과 김제 할인 조건 누락을 지적받아 보강했다.
- 최종 `manual-review` 결과: `source_support`, `conditions_preserved`, `question_answered`, `useful_lifetime`, `no_reader_deflection`, `no_unsupported_claims` 모두 `true`, `issues=[]`.
- 최종 review digest: `c2e35d02ea172998f937fec13d36a80630e624b933e5819bca84d8a8289e4da0`.
- 검토 시각: `2026-09-26T09:54:04.953774+09:00`.
- 7개 공식 원문을 검토 직후 다시 읽어 URL별 SHA가 bundle과 전부 일치함을 확인했다.
- 수정 직전 저장 본문 SHA256: `ac1acc840139549c57b4f7753d922bee2eafcdc004a11597538acb870016316c`.
- 서버에는 검토에 사용한 동일 코드·정책을 `/tmp` 격리 runner로 전달하고, 기존 `.env`와 `data`만 연결해 정규 `revise-draft --post-id 463 --confirm-update`를 실행했다.
- 원본 게시물 백업: `data/editorial_runs/draft-revision-463-20260926T095446864658.json`.
- draft index 백업: `data/editorial_runs/draft-revision-index-463-20260926T095446864658.json`.
- 수정 후 저장 본문 SHA256: `a33d738f0a3fc878f5d6b691cf95dcedd82112dce1f3ed5ffaeaed481e457048`.

## 사후 검증

- WordPress 저장 본문은 검토 renderer 출력과 **정확히 일치**했다.
- `draft` 상태와 기존 제목을 유지했다.
- 카테고리는 term 2 `공연/콘서트 예매` 그대로다.
- 실제 저장 HTML의 `.bloguito-cta a`는 정확히 6개이며 각 지역 상품 URL과 일치한다.
- 저장 본문에는 `2026 남진 60주년 전국투어 남은 일정`, `지역별 공연 시작 시간`, `지역별 좌석 가격` 3개 표가 존재한다.
- 수정 후 명시적 발췌문도 새 검토 lead로 갱신됐다.
