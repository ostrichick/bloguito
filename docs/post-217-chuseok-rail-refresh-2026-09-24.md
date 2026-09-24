# 2026 추석 KTX 취소표 글 보강 및 포맷 현대화 — 2026-09-24

## 범위와 기준선

- 사용자 요청: 기존 공개 글 #217(`2026 추석 KTX 취소표 확인·예매: 코레일+ 통합 예매와 실시간 잔여석`)의 정보를 더 실용적으로 보강하고 Bloguito 최신 구조화 포맷을 적용한다.
- 작업 시작 Git/원격 main: `59f3f46772bf08db878816fcf42cce3d756ec972`.
- 변경 전 WordPress: `publish`, 본문 SHA256 `23191a6717c4ec73e257a324ccf720a99ce3de0dcf5c477fa03aa9c19fda1e72`, 수정시각 `2026-09-21 09:00:30`.
- 다른 작업의 `docs/INDEX.md`, WordPress 관리자 ID 열 관련 파일, 기존 미추적 문서들은 본 작업 소유가 아니므로 수정·스테이징하지 않는다.

## 공식 근거와 보강한 내용

정규 `editorial_cli.py sources` 경로로 아래 네 개의 공식 원문을 새로 수집했다.

1. 코레일 2026 추석 모바일 예매 안내 — 추석 대상기간, 잔여석 판매 시작, 결제기한·미결제 자동취소 안내.
2. 코레일 2026-09-11 보도자료 — 공급 214만석/판매 180만매/전체 84%, KTX 92.7%, 미결제 자동취소 후 예약대기 순차 배정, 잔여석 공식 구매 채널, 암표 단속.
3. 코레일 2026-08-05 고속철도 통합 안내 — 서울·수서 통합 조회, SRT 명칭의 KTX-산천 통합, 입석·자유석 확대, KTX+일반열차 환승할인.
4. 코레일 공식 승차권 예매 화면 `https://www.korail.com/ticket/main` — 실제 행동 버튼의 도착 화면.

최종 글은 특정 열차의 현재 좌석을 있다고 단정하거나 특정 시각에 취소표가 반드시 풀린다고 주장하지 않는다. 대신 독자가 실제로 할 수 있는 행동을 다음처럼 구분한다.

- 공식 잔여석/반환 승차권 확인 채널
- 미결제 자동취소와 예약대기 순차 배정의 관계
- 수서 출발편을 코레일+에서 함께 찾는 방법
- 매진 시 시간대·출발역 범위를 넓혀 재검색하는 순서
- 실제 화면에서 선택 가능한 경우에만 입석·자유석을 이용한다는 제한
- KTX+일반열차 환승 조합은 각 구간을 모두 확보한 뒤에만 이동 계획으로 확정하는 방법
- 암표·비공식 양도 대신 공식 채널을 이용해야 하는 이유

## 최신 포맷

기존 수동 HTML을 공통 renderer의 구조화 원고로 교체했다.

- 핵심 답변 요약 카드 1개
- 목차 5개
- `매진일 때 먼저 확인할 4가지` 비교표 4행
- 실제 실행 순서만 STEP 형식으로 표시
- 수서 통합 예매/입석·자유석·환승/오해 방지 절을 별도 구성
- FAQ 5개
- 공식 코레일 승차권 조회·예매 CTA 1개
- 공식 출처 목록
- 3열 표의 모바일 가로 스크롤 지원

## 짧은 유효기간 정책

추석 대상기간이 2026-09-27에 끝나 정상 30일 기준을 만족하지 않지만, 사용자가 2026-09-24에 **이미 공개된 #217 글을 직접 보강하라고 명시적으로 요청**했다. 따라서 `dated_post_exceptions.2026-chuseok-rail-post-217-refresh`를 추가했다.

예외는 다음 조건을 모두 잠근다.

- 정확한 기존 게시물 ID 217
- `useful_until=2026-09-27`
- 정확한 공식 URL 네 개의 순서
- 2026-09-11 코레일 원문 내 잔여석 공식 판매 문구와 날짜
- 2026-09-27 이후 자동 만료

다른 교통/추석/dated 글은 계속 `min_remaining_days=30`을 적용한다. 기존 #225 단일 예외도 `source_date_phrase`를 정책 필드로 명시해 동작을 유지했다.

## 검토와 운영 적용

- 새 #217 예외 테스트: **2/2 PASS**.
- 기존 #225 회귀 테스트: **3/3 PASS**.
- 구조화 bundle의 숫자/인용 바인딩 오류를 수정한 뒤 deterministic preflight 통과.
- `manual-review --author-model "GPT-5.6 Sol"`: 독립 의미 검토 후 **READY / reasons=[]**. 기본 reviewer가 quota/high-demand 오류를 만나 백업 reviewer로 정상 완료했다.
- 후속 `editorial_cli.py check`: **READY / reasons=[]**.
- `scripts/prepare_post_approval.py`: `preflight_status=ready`, `source_hashes_match_live=true`, 기존 내부 링크 누락 0, 원본 SHA 재확인.
- 검토 렌더 SHA256: `8262ade9ece2c9c7f890108fd05b5fbb3bd66a8c99e67fd0091c2ad71542a4da`.
- 로컬 직접 updater는 Windows에서 로컬 `sudo docker`를 실행하려다 WordPress write 전 실패했다. 잠금이 남지 않은 것을 확인한 뒤 기존 정규 SSH transport adapter `scripts/update_existing_via_ssh.py`를 사용했다. 이 adapter는 동일 updater의 전체 inventory 재조회, 검토, fresh source, 원본 백업, SHA CAS, 저장 후 검증을 유지한다.
- 원본 전체 백업: `agent-publisher/data/editorial_runs/public-edit-217-20260924T133122.json`; 백업 본문 SHA가 변경 전 SHA와 일치함을 확인했다.
- 실제 저장 후 WordPress: `publish`, 제목/slug 유지, 수정시각 `2026-09-24 13:31:26`, 본문 SHA256 `8262ade9ece2c9c7f890108fd05b5fbb3bd66a8c99e67fd0091c2ad71542a4da`.

## 공개 브라우저 표적 QA

별도 headless Edge 세션에서 첫 진입을 Bloguito QA UTM으로 한 뒤 실제 공개 URL을 검사했다.

- 제목 정상
- 요약 카드 1개
- 목차 5개, 첫 목차 앵커 클릭 정상
- 비교표 4행
- FAQ 5개
- 코레일 승차권 공식 CTA 1개, 목적지 `https://www.korail.com/ticket/main`
- 예약대기·입석·환승 문구 모두 실제 공개 본문에 존재
- 360px / 390px / 1280px에서 문서 전체 가로 넘침 0
- 360/390px에서 3열 표는 컨테이너 안에서만 가로 스크롤
- 구조 검증 결과 `pass=true`
- 390px 및 1280px 실제 화면 캡처를 눈으로 확인했고 제목/본문 간격, 소제목 계층 및 본문 가독성에 이상 없음

내부 QA 자료는 `tmp/post217-refresh-20260924/`에 두며 Git에 포함하지 않는다.
