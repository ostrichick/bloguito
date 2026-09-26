# #239 2026 추석 궁궐, 종묘, 왕릉 임시글 보강 기록

작업일: 2026-09-24

## 요청과 수정 전 상태

- 기존 WordPress #239를 더 유용한 정보글로 보강하고 공통 편집 시스템의 발전된 포맷을 적용했다.
- 공개 상태로 전환하지 않고 draft를 유지했다.
- 제목은 2026 추석 궁궐, 종묘, 왕릉 무료개방: 후원 제외와 미술관 휴관일 그대로 유지했다.
- 수정 전 본문 SHA256: 3fe0eb4d9df7cd05a690917466ae9673334f5dc3faf3af558b699b30714850d4
- 기존 draft index에는 검토된 editorial bundle이 없었다.
- WordPress 실제 카테고리는 기존부터 공연/콘서트 예매로 잘못 지정돼 있었다.

## 공식 근거와 보강 범위

편집 시스템이 다음 공식 자료를 직접 수집해 근거 snapshot으로 고정했다.

- 정책브리핑 국가유산청 발표: https://www.korea.kr/briefing/pressReleaseView.do?newsId=156782379
- 궁능유적본부 통합 관람시간: https://royal.khs.go.kr/ROYAL/contents/R702000000.do
- 창덕궁 추석 관람 안내: https://royal.khs.go.kr/ROYAL/contents/R403000000.do?id=20260921134912308090&schBcid=notice01&schM=view
- 종묘 추석 관람 안내: https://royal.khs.go.kr/ROYAL/contents/R403000000.do?id=20260916111620269300&schBcid=notice01&schM=view
- 국립현대미술관 추석 운영 안내: https://m.mmca.go.kr/pr/newsDetail.do?bdCId=202609080010583

본문에는 4대궁, 종묘, 조선왕릉의 무료개방 범위와 장소별 관람시간 비교표, 경복궁 수문장 행사 시간, 창덕궁 후원 제외와 해설, 덕수궁 석조전 예약, 종묘 자유관람과 날짜별 해설, 조선왕릉별 시간 차이와 영월 장릉 예외, 국립현대미술관 연휴 운영, 무료 티켓 발권, 아트셔틀 중단, 공식 왕릉 위치 조회와 창덕궁 후원 예약 행동 링크, FAQ를 추가했다.

## 출처 해시 안정화

첫 교체 시도는 official_source_changed_since_review에서 안전하게 중단됐으며 WordPress 본문 쓰기는 발생하지 않았다. 두 snapshot을 비교해 사실 본문이 아니라 정책브리핑의 실시간 인기뉴스 회전 영역, 창덕궁과 종묘 공지의 조회수, 국립현대미술관 공지의 조회수가 해시를 바꾸는 원인임을 확인했다.

agents/editorial_writer.py에 #239의 정확한 URL에만 적용되는 정규화를 추가했다. 사실 본문, 날짜, 운영시간, 제외 조건은 보존하고 위 동적 표시만 제거하며 예상 구조가 달라지면 예외로 중단한다. 운영 서버에서 공식 URL 5개를 연속 두 번 조회해 아래 SHA256이 전부 동일함을 확인했다.

- s0: aa85a94ddd1587f976dba2e15b0aaf30279f81970649299d840fee8d5f7e1bc2
- s1: 2faf27e6f6499f7d2fd1171380a65b45aa88580fd58627cb9ce15574313a330b
- s2: d4d43d7faf646fb6c470ed6f0ca04754dc4e6d75eec7efae47c0bf2fffed3ffa
- s3: c9c0eaf9c2a420a0b2d2e52d362cf7744a784d846d3747ddbc2cb47cf10afbe2
- s4: 3a3e5c96480fb8abbd2b86c2bd3bac8f8c7b82ca0de647efd9cea9d4c90b8793

## 검토와 저장

운영 서버가 직접 수집한 최종 snapshot으로 독립 의미 검토를 다시 실행했다. 기본 reviewer의 일시적인 503 뒤 백업 reviewer로 자동 전환됐으며 최종 결과는 ready, reasons와 issues는 빈 배열이었다.

- 검토 시각: 2026-09-24T20:29:19.666801+09:00
- 본문 digest: 26dd45133ceb8f66fc088838ac91a9d012e63abee523e529ef938128724f2511
- source support, conditions preserved, question answered, useful lifetime, no reader deflection, no unsupported claims: 모두 true
- 원본 백업: /home/ubuntu/agent-publisher/data/editorial_runs/legacy-draft-239-20260924T202939282108.json
- index 백업: /home/ubuntu/agent-publisher/data/editorial_runs/legacy-draft-index-239-20260924T202939282108.json

기존 카테고리 오분류는 검토 manifest, 현재 본문 SHA, 공식출처 해시를 다시 검사하는 repair-draft-category 경로를 추가해 생활/건강 정보로 교정했다. 본문 SHA는 교정 전후 동일하다.

- 카테고리 백업: /home/ubuntu/agent-publisher/data/editorial_runs/draft-category-239-20260924T203648775747.json

## 최종 운영 확인

- 상태: draft
- 제목: 변경 없음
- 최종 본문 SHA256: 19086dedb1b590882e305fb0c604592f0c1f14c9db20aaf7fddf878a4dbdfe9b
- 명시적 excerpt: 139자
- 공통 레이아웃 래퍼: 존재
- 비교표: 2개
- FAQ: 존재
- 창덕궁 후원 예외, 영월 장릉 예외, 국립현대미술관 추석 당일 휴관 정보: 모두 존재
- 조선왕릉 위치 조회 링크, 창덕궁 후원 예약 링크: 모두 존재
- 독자 노출 가운데점 문자: 없음
- draft index reviewed manifest: 존재
- WordPress 카테고리: 생활/건강 정보, ID 4

공개 전환은 수행하지 않았다.

## 후속 수정: 한눈에 보기 표 무료관람 기간 명시

사용자 피드백에 따라 첫 번째 요약표만 봐도 무료관람 기간을 바로 알 수 있도록 표를 다시 수정했다.

- 표 제목: 2026 추석 무료개방 기간과 관람시간 한눈에 보기
- 열 구성: 장소 / 무료관람 기간 / 무료 범위와 예외 / 관람시간
- 경복궁, 창덕궁, 덕수궁, 창경궁, 종묘: 9월 24일(목)~9월 27일(일)을 각 행에 직접 표시
- 조선왕릉: 9월 24일(목)~9월 27일(일)과 함께 영월 장릉은 9.25.(금) 추석 당일 휴일을 같은 기간 셀에 표시
- 창덕궁 후원 특별관람 제외, 종묘 자유관람, 왕릉별 관람시간 차이 등 기존 예외는 별도 열에 유지

수정 원고는 운영 서버의 동일 편집 검토를 다시 거쳐 ready 판정을 받은 뒤 reviewed draft 전용 수정 경로로 적용했다.

- 수정 전 본문 SHA256: 19086dedb1b590882e305fb0c604592f0c1f14c9db20aaf7fddf878a4dbdfe9b
- 수정 후 본문 SHA256: 0f24d6aa43457bf42be047b0785347efc2816d5c69e1b682aa8b55e0e1c9dc69
- 게시물 상태: draft
- 수정 백업: /home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-239-20260924T210044366633.json
- index 백업: /home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-index-239-20260924T210044366633.json
