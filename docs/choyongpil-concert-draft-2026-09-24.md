# 2026 조용필 콘서트 임시글 작성 기록

작성일: 2026-09-24

## WordPress 결과

- 글 ID: 465
- 제목: 2026 조용필 콘서트 예매: 서울, 부산, 대구, 대전 일정과 티켓 가격
- 상태: draft
- 카테고리: 공연/콘서트 예매
- 퍼머링크 레코드: https://lifeinfo24.org/?p=465
- 최종 본문 SHA256: 1e17de6c4ce1ef7e19ef7cee0b3b2815200bf7877835c464686f972e80f784d5
- 공개 발행은 수행하지 않았다.

## 주요 내용

- 2026년 서울, 부산, 대구, 대전 일정과 2027년 광주, 인천 후속 일정 표
- 2026년 지역별 실제 공연 시작시간
- VIP석 176,000원, R석 165,000원, S석 143,000원, A석 110,000원
- YES24 단독판매, 관람등급 8세 이상, 관람시간 약 130분
- 서울, 부산, 대구, 대전 YES24 직접 상품 링크 4개
- KSPO DOME의 올림픽공원역 3번 출구, P5 주차장 위치와 공식 주차요금
- BEXCO 공식 자가용 안내의 부산역, 김해국제공항 출발 경로 예시
- 대전컨벤션센터 제2전시장 주차 규모와 공식 주차요금
- 대구 공연장은 엑스코 서관이라는 점을 명확히 표시
- 좌석 재고나 매진 여부처럼 실시간으로 변하는 값은 확정적으로 표현하지 않음
- FAQ 5개
- 독자 노출 문구에서 가운데점 문자 미사용

## 공식 근거와 수집 방식

1. YPC 공식 홈페이지 티켓 예매 공지
   - https://choyongpil.com/43/?bmode=view&idx=173993016
   - 일반 무헤더 수집기는 403을 반환했으나 공식 페이지는 브라우저 접근이 가능했다.
   - 브라우저와 같은 User-Agent로 페이지를 받아 댓글과 변동 UI를 제외한 공식 공지 본문만 보존했다.
   - 최종 저장 직전 다시 내려받아 핵심 본문 SHA가 검토본과 동일한 것을 확인했다.

2. YES24 공식 전국투어 지역별 목록
   - https://m.ticket.yes24.com/Genre/GenreBridge.aspx?genre=15456&id=1576
   - 서울, 부산, 대구, 대전, 광주, 인천의 지역별 공연 날짜와 공연장 확인에 사용했다.
   - 일정 목록은 판매 재고나 매진 상태를 보증하지 않으므로 글에서도 이를 단정하지 않았다.

3. 올림픽공원 KSPO DOME 공식 안내
   - https://www.ksponco.or.kr/olympicpark/menu.es?mid=a20301030800

4. BEXCO 공식 교통 안내
   - https://www.bexco.co.kr/kor/CMS/Contents/Contents.do?mCode=MN083

5. 대전컨벤션센터 공식 주차 안내
   - https://www.dcckorea.or.kr/content/view.do?contentKey=70&menuKey=76
   - 로컬 requests 신뢰 저장소에서 TLS 체인 오류가 있어 TLS 검증을 끄지 않고 공식 페이지의 웹 검색 결과로 현재 안내를 재확인했다.

## 예매 직접 링크

- 서울: https://ticket.yes24.com/Perf/60153
- 부산: https://ticket.yes24.com/Perf/60154
- 대구: https://ticket.yes24.com/Perf/60208
- 대전: https://ticket.yes24.com/Perf/60209

## 검증

- manual-review: ready
- editorial_cli.py check: ready
- review.issues: []
- source support, conditions preserved, question answered, useful lifetime, no reader deflection, no unsupported claims: 전부 true
- 저장 직전 핵심 소스 해시 재확인 결과 검토본과 일치
- 원격 WordPress 본문 SHA와 로컬 검토 렌더 SHA 일치
- 원격 상태 draft
- 원격 카테고리 ID 2, 공연/콘서트 예매
- 로컬과 서버 draft_posts.json에 글 ID 465가 각각 정확히 1건 존재하며 저장된 editorial bundle이 검토본과 일치
- Rank Math focus keyword와 description 저장 확인

## 2026-09-26 예매 링크 보강

- 사용자 요청에 따라 #465의 공연 일정과 지역별 예매 경로를 다시 확인했다.
- 수정 전 운영 draft는 일정표에는 서울, 부산, 대구, 대전, 광주, 인천 6개 지역이 있었지만 CTA는 서울, 부산, 대구, 대전 4개만 존재했고, 본문에도 `상단의 네 버튼`이라고 남아 있었다.
- YES24 공식 전국투어 목록과 지역별 상품을 새로 수집해 6개 지역의 날짜, 공연장, 시작시간, 관람등급, 관람시간, 좌석 정가를 재검증했다. 새 수집본의 7개 공식 source SHA256은 직전 검토본과 모두 동일했다.
- 지역별 직접 예매 경로를 6개로 보강했다.
  - 서울: https://ticket.yes24.com/Perf/60153
  - 부산: https://ticket.yes24.com/Perf/60154
  - 대구: https://ticket.yes24.com/Perf/60208
  - 대전: https://ticket.yes24.com/Perf/60209
  - 광주: https://ticket.yes24.com/Perf/60212
  - 인천: https://ticket.yes24.com/Perf/60215
- 현재 정책으로 `manual-review`와 `check`를 다시 실행해 모두 `ready`를 확인했다. 독립 의미 검토의 모든 check가 true이고 issues는 없다.
- 관련 회귀 테스트 29개(`test_action_destinations`, `test_reference_sources`, `test_schedule_listing`, `test_editorial_draft_reviser`)가 통과했다.
- canonical `revise-draft` 경로로 원본 SHA256 `1e17de6c4ce1ef7e19ef7cee0b3b2815200bf7877835c464686f972e80f784d5`를 CAS 조건으로 사용해 #465만 갱신했다.
- 자동 백업:
  - `agent-publisher/data/editorial_runs/draft-revision-465-20260926T164749292454.json`
  - `agent-publisher/data/editorial_runs/draft-revision-index-465-20260926T164749292454.json`
- 저장 후 운영 WordPress를 다시 읽어 상태가 `draft`로 유지되고 6개 YES24 상품 URL이 각각 정확히 1회 존재함을 확인했다.
- 저장된 본문 SHA256은 `52a448222984d8cedd49391fc4488107f827941058ab7fa51ab5082747989480`이며 현재 reviewed render SHA256과 정확히 일치한다.
- 6개 직접 예매 URL은 모두 HTTP 200으로 확인했다. 서울, 부산, 대구는 YES24 Special 상품 화면으로 정상 이동하고 대전, 광주, 인천은 해당 Perf 상품 화면으로 열린다.
- 공개 전환은 수행하지 않았다.

## 2026-09-26 일정표 통합, 문구·FAQ 정리

- 사용자 요청에 따라 공연 일정 표와 공연 시작시간 표를 하나로 합쳤다. 최종 표는 `지역, 공연 날짜, 공연장, 공연 시작시간` 네 열로 6개 지역을 한 번에 비교한다.
- 기존 별도 `지역별 공연 시작시간` 표는 제거했다.
- 확정된 관람 정보는 출처를 앞세우는 표현을 줄이고 `관람등급은 8세 이상이며, 관람시간은 총 130분입니다.`처럼 직접 답하는 문장으로 정리했다.
- `광주와 인천도 직접 예매 링크가 있나요?` FAQ는 본문 상단에 6개 지역별 직접 예매 버튼이 이미 노출되므로 중복 질문으로 판단해 제거했다.
- 독립 의미 검토에서 기존 제목이 2027년 광주, 인천까지 포함하는 실제 본문 범위와 맞지 않는다는 지적이 반복되어 제목을 `2026~2027 조용필 콘서트 예매: 전국투어 6개 지역 일정, 티켓 가격`으로 정리했다.
- YES24 일정 검증기가 기존 3열 표만 인정하던 제약을 수정해 `지역, 날짜, 공연장` 세 핵심 값이 앞의 세 열에서 정확히 일치하면 그 뒤의 `공연 시작시간` 같은 검증된 추가 열을 허용하도록 했다.
- reviewed draft의 제목 변경은 별도 `--confirm-title-change`가 있을 때만 canonical `revise-draft`가 본문, 발췌문과 함께 적용하고 저장 후 제목, 슬러그, 본문 일치를 검사하도록 보강했다.
- 일반 SSH 22번 포트가 타임아웃되는 동안 Tailscale ping과 `tailscale ssh`는 정상인 상황을 확인해 제한형 SSH 어댑터에 명시적인 `--tailscale-ssh` 전송 옵션을 추가했다.
- 표적 테스트: schedule listing 13개, draft reviser 4개, SSH transport 9개가 통과했다.
- 공통 변경 후 전체 `agent-publisher/tests` 454개가 통과했고 1개가 skip됐다. `git diff --check`도 통과했다.
- 수정 원고는 최종 `manual-review=ready`, `check=ready`, `review.issues=[]` 상태다.
- canonical `revise-draft`에 수정 전 본문 SHA256 `52a448222984d8cedd49391fc4488107f827941058ab7fa51ab5082747989480`을 CAS 조건으로 지정해 #465만 갱신했다.
- 자동 백업:
  - `agent-publisher/data/editorial_runs/draft-revision-465-20260926T172427130467.json`
  - `agent-publisher/data/editorial_runs/draft-revision-index-465-20260926T172427130467.json`
- 저장 직후 canonical reviser가 draft 상태, 새 제목, 기존 슬러그, 새 본문, 새 발췌문 일치를 모두 검증했다.
- 최종 reviewed render의 원문 SHA256은 `bb10dce4c4c4068fb6506991360d3d7aff4afb0dce4824b9d41077180e912e9f`이다. 원격 `wp post get --field=post_content` 출력의 개행을 포함한 SHA256 `d2a0b6626118ccdcb25b50b2b0128fc8966c6b89619256f83b4cad012e39b92d`가 로컬 reviewed render에 개행 하나를 붙인 SHA256과 일치했다.
- 저장 후 독립 SSH 재조회는 연결이 간헐적으로 255 종료되는 현상이 있었지만, canonical 저장 후 검증과 별도 원격 본문 SHA 대조는 모두 통과했다.
- 공개 전환은 수행하지 않았다.
