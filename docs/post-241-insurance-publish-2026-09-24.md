# #241 교대운전 보험 가이드 보강, 발행 — 2026-09-24

## 작업 범위

- 대상 WordPress ID: 241
- 시작 상태: `draft`
- 제목: `명절 교대운전 보험 확인: 단기운전자확대특약과 원데이보험의 효력 시작 시점`
- 시작 본문 SHA256: `4bcd53b84f8fa511ba65971ce5ed65d0c2454a126bfc10319c90bbe4563bb0f4`
- 시작 WordPress 카테고리: `생활 세금/절세 정보` (`tax`, term 102)
- 사용자 요청: 기존 초안을 더 유용하고 읽기 좋은 형식으로 전면 보강한 뒤 공개 발행

기존 초안은 단기운전자 확대특약과 원데이 자동차보험의 구조 차이만 짧게 설명해 실제 출발 전 판단에 필요한 가입 주체, 효력 시작 시점, 가입 제한, 확인 순서가 부족했다. 현행 source-bound editorial bundle로 재구성하고 검토한 뒤 같은 글 ID를 유지해 공개했다.

## 공식 근거

2026-09-24에 아래 공식 상품, 계약변경 페이지를 다시 수집했다.

- 삼성화재 다이렉트 원데이 애니카 자동차보험: `https://direct.samsungfire.com/m/fp/oneday.html`, SHA256 `e84719ccba00b9a0437eea84d5f5e286cc819b31642b920efcb14ba3f2076c79`
- 하나손해보험 원데이자동차보험: `https://www.hanainsure.co.kr/w/product/carDriver/hanaOnedayCarIntro`, SHA256 `2b0e9f6dd1f2449b298020ad185c0d5048a4d53b1dac6c9cc5912c6efc76a446`
- 현대해상 다이렉트 자동차보험 계약 변경: `https://platform.hi.co.kr/service.do?m=d0ea897ef2`, SHA256 `f953cb7275818e600ae2b31d97caaa903c09ad1826ad497a85d40dc8a8d1feef`

초기 후보였던 KB손해보험 인사이트 페이지는 실제 본문 조건은 같았지만 하단 해시태그 순서가 조회마다 달라져 독립 source hash 재검사에서 차단됐다. 해시 검사를 우회하거나 동적 부분을 임의로 제외하지 않고 해당 출처와 그 출처에만 의존하던 수치를 최종 원고에서 제거했다.

## 최종 원고 구성

- 핵심 답변 카드 1개
- 목차 5개
- 내 차를 다른 사람이 운전하는 경우와 내가 다른 사람 차를 운전하는 경우의 비교표
- 현대해상 단기운전자 확대특약의 현재 신청 시점, 계약자, 신청 기간 안내
- 삼성화재, 하나손해보험 원데이 상품의 현재 효력 시작 시점, 보험기간, 연령과 차량 제한 비교표
- 원데이보험의 보상 범위와 렌터카, 카셰어링 조건 예외
- 출발 전 보험 범위 확인, 신청, 결제와 전자서명, 최종 보험증권 확인 순서
- FAQ 4개
- 공식 출처 3개

특정 보험사의 조건을 전체 보험사 공통 규칙처럼 일반화하지 않고, 각 보험사의 현재 공식 페이지에서 확인된 조건을 해당 상품에만 연결했다. 특정 명절 날짜의 한시 행사 대신 반복되는 교대운전 판단 절차를 다루므로 `evergreen`으로 검토했다.

## 검토와 반영

- 로컬 `manual-review`, `check`: `ready`
- 운영 서버 현재 정책으로 공식 출처 재수집, 독립 `review`, `check`: `ready`
- 최종 의미 검토 6항: `source_support`, `conditions_preserved`, `question_answered`, `useful_lifetime`, `no_reader_deflection`, `no_unsupported_claims` 모두 `true`
- 검토 issues: `[]`
- 최종 review digest: `e76e91e782e0b3d9fe73cea164e23c2a913d57734a50fdeccbdda7e011b06d0a`
- 작성 메타데이터: `interactive_chatgpt`, `GPT-5.6 Sol`

기존 글은 reviewed manifest가 없는 legacy draft였으므로 `replace-legacy-draft`로 같은 ID의 초안을 검토 원고로 교체하고 manifest를 등록했다. 교체 전에 WordPress 원본 SHA가 시작값과 동일함을 재확인했다.

- 원본 전체 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/legacy-draft-241-20260924T144922569734.json`
- 초안 색인 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/legacy-draft-index-241-20260924T144922569734.json`
- 검토 원고 저장 후 본문 SHA256: `bf3b5c48205a7b20a741f02d6d366c42d5b1cf41cf7078a8ce649985211a0559`

기존 WordPress 분류가 보험 글과 무관한 `tax`였기 때문에 본문 교체 후 #241의 카테고리만 term 4 `생활/건강 정보`로 변경했다. 카테고리 변경 전후 본문 SHA는 유지됐다. 이후 reviewed bundle을 `promote-draft 241 --confirm-publish`로 공개 전환했다.

## 최종 상태와 공개 QA

- 최종 상태: `publish`
- 최종 본문 SHA256: `bf3b5c48205a7b20a741f02d6d366c42d5b1cf41cf7078a8ce649985211a0559`
- 최종 WordPress 카테고리: `생활/건강 정보` (`life-health`, term 4)
- 최종 수정시각: `2026-09-24 14:50:26`
- 공개 URL: `https://lifeinfo24.org/?p=241`에서 canonical 공개 주소로 정상 이동

비로그인 QA는 먼저 전용 UTM 세션으로 진입한 뒤 실제 공개 글을 확인했다. 공개 HTML에서 요약 카드 1개, 목차 링크 5개, 표 2개, FAQ 4개, 공식 출처 영역 1개가 렌더링됐고 `최소 1일 전`, `가입 완료 직후부터 바로 보장`, `만 21세 미만`, `만 20세 이상`, `최종 보험증권` 핵심 문구가 모두 존재했다.

Headless Edge 실측에서 390px 뷰포트의 본문 폭은 315px, document scroll width는 375px로 페이지 전체 가로 넘침이 없었다. 표는 본문 내부의 별도 가로 스크롤 영역에 들어가 페이지 폭을 확장하지 않았다. 1280px에서도 전체 가로 넘침이 없었다. 390px 실제 화면 캡처도 `tmp/post241-20260924/mobile.png`에서 확인했다.

최종 bundle, server review, check 결과와 QA 산출물은 Git 제외 `tmp/post241-20260924/`에 보관했다. 운영 서버의 임시 검토 디렉터리와 임시 SHA 확인 파일은 검증 후 정리했고, 위 원본 백업은 롤백 근거로 보존했다.
