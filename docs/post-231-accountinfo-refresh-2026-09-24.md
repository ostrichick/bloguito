# #231 어카운트인포 휴면계좌, 휴면예금 글 보강 — 2026-09-24

## 작업 범위

- 대상 WordPress ID: `231`
- 사용자 요청: 기존 글을 더 유용하게 보강하고 발전된 포맷을 적용하되 공개하지 않고 임시글로 유지
- 시작 상태: `draft`
- 제목: `어카운트인포 휴면계좌, 휴면예금 찾기: 조회와 잔고이전, 해지 조건 구분`
- 시작 본문 SHA256: `84517463b0cdfc69d9590a1bfdbc6222a3e199a36082b456df97f324966c2674`
- 시작 WordPress 분류: `정부 복지/지원금` (`welfare`, term 3)

기존 초안은 비활동성 계좌와 휴면예금을 구분하는 기본 설명은 있었지만 현재 이용시간, 온라인 잔고이전과 해지 대상, 수취계좌 조건, 수수료와 취소 불가 조건, 서비스별 휴면예금 온라인 지급 범위, 일반 미청구보험금 확인 경로가 충분히 정리되지 않았다. 공식 자료를 새로 수집해 구조화 원고로 재작성하고 같은 글 ID와 제목을 유지했다.

## 공식 근거

2026-09-24에 아래 공식 페이지를 다시 수집했고, 운영 적용 직전 한 번 더 수집해 URL과 SHA256이 모두 동일함을 확인했다.

- 금융결제원 어카운트인포 계좌해지, 잔고이전 이용안내: `https://www.payinfo.or.kr/guide/useguideAcntcb2.do`, SHA256 `bf942141a8598484a6f58246551787689ee03c4e3ce8e6cac74886fd791d6b12`
- 금융결제원 어카운트인포 FAQ: `https://payinfo.or.kr/cs/faq/qryListWebFaq.do`, SHA256 `d94107e1912e5e86084bbd9d8c4d16b3aadcaf88adca4842ef630bfc4a140f48`
- 금융결제원 어카운트인포 서비스별 이용시간: `https://payinfo.or.kr/main/main.do`, SHA256 `da61d7c72a29cb05d1c57344f196de3093c6d26e41a98b2b4944cdacad780786`
- 서민금융진흥원 휴면예금 안내: `https://www.kinfa.or.kr/cyber/appInfo/sleepMoneyInf.do`, SHA256 `fe8280ced2629b629a42aeb67e9bdac40c22075ab405deefb9ec61f7824b906c`
- 생명보험협회 내보험찾아줌 안내: `https://cont.insure.or.kr/cont_web/information/information.do`, SHA256 `540d9ef421f4cc35c2021c9602d77f37279c24946dbd1628b2f2a08365b6e41a`

## 보강한 내용과 포맷

- 첫 화면의 핵심 답변에서 일반 비활동성 계좌와 휴면예금의 차이를 바로 설명했다.
- 소액 비활동성 일반계좌, 휴면예금, 휴면보험금, 일반 미청구보험금을 한 표에서 구분했다.
- 현재 계좌 조회 시간, 잔고이전과 해지 시간, 일부 증권사와 구 개인연금저축계좌의 예외 시간을 공식 FAQ 기준으로 정리했다.
- 잔고이전 수취계좌 조건, 타 금융회사 이전 시 발생할 수 있는 수수료, 실시간 처리 후 취소 불가, 계좌를 유지하려면 별도 금융회사 채널을 이용해야 하는 조건을 추가했다.
- 어카운트인포와 서민금융진흥원 휴면예금 찾아줌의 온라인 지급 신청 범위를 구분했다.
- 휴면보험금과 내보험찾아줌의 일반 미청구보험금 범위를 분리해 설명하고, 공제상품과 미성년자, 사망자 조회 예외를 추가했다.
- 공식 행동 링크 3개를 별도 버튼 영역으로 제공했다: 어카운트인포 계좌 조회 시작, 휴면예금 지급 신청 시작, 내보험찾아줌 조회 시작.
- 핵심 답변 카드, 비교표 2개, 단계형 처리 절차, 목차, FAQ 3개, 공식 근거 영역으로 렌더링했다.
- 독자용 문구에서 가운데점 문자를 사용하지 않았다.

## 검토와 운영 반영

- 작성 provenance: `interactive_chatgpt` / `GPT-5.6 Sol`
- 로컬 구조 검사: `ready`
- 독립 의미 검토: 6개 항목 모두 `true`, `issues=[]`
- 최종 CLI `check`: `ready`
- 첫 운영 교체 시도는 운영 서버에서 서민금융진흥원 HTTPS 연결이 25초 내 성립하지 않아 출처 재수집 단계에서 중단됐다. 이 시점은 WordPress 쓰기, 원본 백업, 초안 색인 변경보다 앞선 단계였다.
- 이후 작업 PC에서 동일한 공식 5개 출처를 새로 수집하고 기존 검토 bundle의 URL, SHA256과 전부 일치함을 확인했다. 운영 서버에는 현재 작업 트리의 편집 검증 코드를 임시 실행 경로로만 전달하고, 데이터 디렉터리는 운영의 `/home/ubuntu/agent-publisher/data`를 그대로 사용했다. 운영 서버에서 접근이 막힌 출처 재수집 단계만 방금 검증한 최신 스냅샷을 전달하는 좁은 transport로 대체했으며, 원본 SHA 비교, 전체 WordPress 인벤토리, 검토 서명, 백업, 잠금, 저장 후 재조회, 초안 색인 기록은 기존 `upgrade_legacy_draft` 경로를 그대로 실행했다.
- 교체 직전 기존 본문 SHA256은 시작값과 동일했다.
- 원본 전체 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/legacy-draft-231-20260924T203107262196.json`
- 초안 색인 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/legacy-draft-index-231-20260924T203107262196.json`

## 최종 저장 검증

- 상태: `draft`
- 제목: 기존 제목 유지
- 최종 본문 SHA256: `6287719e00aedd549e339bed3778e53b60abfa64b537d3024f21532cbea27061`
- WordPress 저장 HTML과 검토된 renderer 출력: 정확히 일치
- 발췌문과 검토 원고의 lead 기반 발췌문: 정확히 일치
- 기존 `bloguito-corrected` legacy 마커: 제거됨
- 초안 색인의 reviewed manifest: 존재
- 저장된 의미 검토: `source_support`, `conditions_preserved`, `question_answered`, `useful_lifetime`, `no_reader_deflection`, `no_unsupported_claims` 모두 `true`, `issues=[]`
- 기존 WordPress 분류가 검토 분류와 달라 본문 교체 후 term 4 `생활/건강 정보` (`life-health`)로 맞췄다. 분류 변경 전후 본문 SHA와 `draft` 상태는 그대로 유지됐다.
- 공개 승격은 실행하지 않았다.
