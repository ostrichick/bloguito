# 검토용 임시글 2건 (2026-09-13)

사용자가 고품질 검토용 포스트 두 건의 임시글 등록을 요청하여 공식 자료를 확인하고 수동 편집한 원고를 WordPress에 등록했다. 자동 파이프라인 성능 검증 결과가 아니며 4단계의 제한된 표 형식과 별개인 사용자 검토용 장문 샘플이다. 자동 검증 코드를 완화하거나 공개 발행 설정을 변경하지 않았다.

| 글 ID | 제목 | 카테고리 | 상태 | 대표 이미지 ID |
| --- | --- | --- | --- | --- |
| 85 | 놓친 복지혜택 찾는 순서: 복지멤버십·보조금24 조회부터 실제 신청까지 | 정부 복지/지원금 | draft | 87 |
| 86 | 공연 티켓 결제 전 꼭 확인할 것: 날짜·총비용·취소 마감 체크리스트 | 공연/콘서트 예매 | draft | 88 |

각 글에 핵심 요약, 비교/점검 표, 실천 순서, 복사 가능한 메모 양식, 관련 공식 링크와 확인일을 넣었다. 자체 제작한 1200×630 한국어 타이포그래피 대표 이미지를 연결했다. 특정 지원금 지급액·선정 여부와 개별 공연의 환불액은 단정하지 않았다. 공식 정보와 편집부의 체크리스트 제안을 구분했다.

근거:
- 복지로 복지멤버십 이용 방법: https://www.bokjiro.go.kr/ssis-tbu/twatza/wmAplyMng/selectWmJoinProcGdnc.do
- 복지로 소개: https://www.bokjiro.go.kr/ssis-tbu/cms/pc/intro/intro/info/01/index.html
- 복지로 모의계산: https://www.bokjiro.go.kr/ssis-tbu/twatbz/mkclAsis/mkclPage.do
- 행정안전부 보조금24 안내: https://www.mois.go.kr/frt/bbs/type002/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000205&nttId=97408
- NOL 티켓 이용정책: https://policy.yanolja.com/pf/policy/nol-ticket-service
- 한국소비자원 분쟁조정 사례: https://www.kca.go.kr/odr/bj/br/osBjDecisionExamDetW.do?brdId=00000007&dataStts=Y&seq=1003639728

검증: WP-CLI에서 두 글의 draft 상태와 제목을 재조회했고 저장된 본문 SHA256가 준비한 HTML과 동일함을 확인했다. 대표 이미지 등록 ID를 확인했다. 기존 임시글은 수정하지 않았다. 실제 관리자 로그인 미리보기의 브라우저 렌더링 검증은 수행하지 않았다. 원고와 제작/등록 임시 파일은 Git 제외 tmp/review-posts에 보관하며 공개 저장소에는 서버 주소를 기록하지 않는다.

사용자 검토 후 문체·길이·표·실용성 의견을 바탕으로 자동 생성 원고의 목표 형식을 재설계할 수 있다. 이번 두 글만으로 자동 파이프라인이 같은 품질을 재현한다고 주장하지 않는다.
