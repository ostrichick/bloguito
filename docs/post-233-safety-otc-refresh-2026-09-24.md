# #233 휴일 약국, 안전상비의약품 임시글 보강 — 2026-09-24

## 작업 범위

- 대상 WordPress ID: 233
- 시작 상태: draft
- 제목: 휴일에 약국이 닫았다면: 편의점 안전상비의약품 확인과 야간 약국 찾기
- 시작 본문 SHA256: 7f79f8ca310e8e4f3249d2f088a5872bcfcfe5229ac21a661355d69dae3b7c5a
- 사용자 요청: 기존 임시글의 정보와 포맷을 보강하되 공개 발행하지 않고 임시글로 유지

기존 원고는 편의점 안전상비의약품과 휴일 약국 검색을 짧게 안내했지만, 현재 지정 품목 전체 목록, 포장단위, 판매점 등록 조건, 구매 수량과 연령 제한을 실제 의사결정에 쓸 수 있을 정도로 보여주지 못했다. 현재 공식 근거에 다시 연결한 구조화 원고로 교체하고 같은 글 ID와 제목을 유지했다.

## 공식 근거

2026-09-24에 다음 자료를 다시 수집해 원고 근거로 사용했다.

- 보건복지부 안전상비의약품 약국외 판매제도
  - https://www.mohw.go.kr/menu.es?mid=a10702040200
  - source SHA256 d1bece66399b7c2bb092ec26f0b8799e77e8206b8f36e9ec27857f8b3c463a53
  - 안전상비의약품 13개 품목과 포장단위, 판매자 등록과 24시간 연중 무휴 점포 기준 확인
- 국가법령정보센터 약사법 시행규칙 제28조
  - https://law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&lspttninfSeq=116505
  - source SHA256 fca6c4535950f1a91593ccc5dde4c424bcd4f67896c729f66bff2f038a1e06b4
  - 안전상비의약품별 1회 1개 포장단위 판매 제한, 12세 미만 아동 판매 금지, 등록증과 사용상 주의사항 게시 의무 확인
- 대한민국 정책브리핑 설 연휴 문 여는 병의원, 약국 'e-gen'에서 확인하세요
  - https://www.korea.kr/news/policyNewsView.do?newsId=148938993
  - source SHA256 6d1602782271258c912069848a833cd6a8efef0628c862489507cc2573ee0f53
  - 응급의료포털 E-Gen에서 가까운 문 연 병의원과 약국을 찾을 수 있다는 공식 안내 확인

운영 VPS는 www.e-gen.or.kr의 인증서 체인을 Python requests에서 검증하지 못해 E-Gen 페이지 자체를 source hash 재검증에 사용하는 경로가 안전하게 중단됐다. TLS 검증을 비활성화하지 않았다. 대신 서버에서 안정적으로 재검증할 수 있는 정책브리핑 원문을 근거로 사용하고, E-Gen의 약국 검색 주소는 독자가 실제 검색 화면으로 이동하는 행동 링크로 유지했다. 정책브리핑 원문은 운영 서버에서 연속 두 번 수집해 위 SHA256이 동일함을 확인했다.

## 최종 원고 구성

- 상단 핵심 답변 카드
- 본문 목차
- 안전상비의약품 13개 품목과 포장단위를 한 번에 확인하는 13행 표
- 24시간 편의점이라고 모두 판매 가능한 것은 아니라는 판매자 등록 조건
- 안전상비의약품별 1개 포장단위 판매 제한과 12세 미만 아동 판매 금지
- 12세 미만 판매 금지가 특정 제품의 복용 가능 연령을 직접 정한 규정은 아니라는 구분
- 제품별 사용상 주의사항 확인 안내
- E-Gen 문 여는 약국 검색 직접 행동 링크
- FAQ와 공식 출처 영역

독자용 문구에는 가운데점 문자를 사용하지 않았다.

## 검토와 운영 반영

- 로컬 ChatGPT 구조화 원고 작성 메타데이터: interactive_chatgpt, GPT-5.6 Sol
- 로컬 manual-review: ready
- 로컬 check: ready
- 운영 서버 현재 정책으로 독립 review: ready
- 운영 서버 적용 직전 policy fingerprint: 3e61f77a5aa15ffaef05abfcd08d5a8e1ee2f4f05d63bc768e8eefc47e45d2c5
- 검토 직후 동시 작업으로 서버 정책 파일이 한 차례 변경되어 첫 적용은 review_not_bound_to_current_content로 안전 중단됐다. 현재 정책으로 재검토한 뒤 적용했다.
- 로컬 Docker Desktop은 실행 중이 아니어서 로컬 replace-legacy-draft의 WordPress 동기화는 수행할 수 없었다. 실제 WordPress가 있는 SSH 별칭 bloguito 운영 VPS에서 동일한 편집 CLI를 실행했다.
- 기존 원본 전체 백업: /home/ubuntu/agent-publisher/data/editorial_runs/legacy-draft-233-20260924T203349962315.json
- 기존 초안 색인 백업: /home/ubuntu/agent-publisher/data/editorial_runs/legacy-draft-index-233-20260924T203349962315.json

replace-legacy-draft는 현재 WordPress 원본 SHA가 시작값과 동일한지 다시 확인한 뒤 본문과 발췌문을 교체하고, 저장 결과가 검토 HTML과 일치하는지 자체 검사했다.

## 최종 저장 상태

- 상태: draft
- 제목: 기존 제목 유지
- 슬러그: 기존 빈 값 유지
- 카테고리: 생활/건강 정보 (life-health, term 4)
- 최종 수정시각: 2026-09-24 20:33:51
- 최종 본문 SHA256: 6ff0389080d5f274bb018d04e6def80493408412df75434f52bd23320e566b66
- 저장 본문 길이: 15,351자
- 발췌문 길이: 169자
- 저장 HTML 실측: 핵심 답변 카드 1개, 목차 1개, 표 1개, 표 본문 13행, FAQ 영역 존재, E-Gen 행동 링크 1개, 공식 출처 목록 1개, 가운데점 0개

promote-draft나 그 밖의 공개 전환 명령은 실행하지 않았다. 임시글이므로 비로그인 공개 페이지 QA는 수행하지 않았고, WordPress 저장 원문과 구조를 직접 검증했다.

## 2차 보강: 대표 이미지 교체와 가격 중심 표 — 2026-09-24 22시대

사용자 피드백에 따라 첫 표의 `포장단위`를 독자의 실제 구매 판단에 더 유용한 `대략적인 가격`으로 교체했다. 가격은 정부가 정한 정가가 아니므로 공식 정책 근거와 분리한 `reference` 자료로 검증하고, 표와 본문에 점포·지역·시점에 따라 실제 결제가격이 달라질 수 있음을 명시했다.

현재 판매 여부는 보건복지부의 지정 13종과 2026년 연합뉴스의 유통 현황을 함께 대조했다. 타이레놀정 160mg과 어린이용 타이레놀정 80mg은 생산 중단으로 실제 구입 가능한 품목에서 제외된다는 최신 보도에 따라 가격을 표시하지 않고 `생산 중단, 가격 비교 제외`로 표시했다. 나머지 11개는 CU, GS25, 세븐일레븐의 공개 가격 비교 사례를 참고했다. 해당 가격 비교 페이지는 Naver의 변동 UI를 제외하고 작성 본문 컨테이너만 해시해 두 번 연속 동일한 원문 SHA를 확인한다.

최종 첫 표의 가격 참고값은 타이레놀정 500mg 약 3,600원, 어린이타이레놀현탁액 약 7,400원, 어린이부루펜시럽 약 8,000원, 베아제정 약 2,200원, 닥터베아제정 약 2,400원, 훼스탈골드정 약 2,700원, 훼스탈플러스정 약 2,500원, 판콜에이내복액 약 3,000원, 판피린티정 약 2,000원, 제일쿨파프 약 3,000~3,500원, 신신파스아렉스 약 3,300~3,900원이다. 이 값은 정가가 아니라 비교 당시 매장 가격의 참고값이다.

가격처럼 공식 정액이 없는 보조 정보를 공식 정책·법적 조건과 혼동하지 않도록 편집 시스템에 선택적 `brief.reference_urls` / `source_type=reference`를 추가했다. reference 자료에는 행동 버튼을 허용하지 않고, 공식 URL과 reference URL의 중복을 차단하며, 공식 정책·자격·판매 규정은 계속 `official` 자료로만 검증한다. #233 가격 비교 Naver 페이지는 작성 본문만 추출해 조회·추천 등 변동 UI가 source hash를 흔들지 않도록 범위를 고정했다. 운영 서버 적용 전 기존 `editorial.py`, `editorial_writer.py`, `EDITORIAL_SYSTEM.md`의 SHA를 고정 확인했고, 원본은 `/home/ubuntu/agent-publisher/data/editorial_runs/post233-price-refresh-20260924/server-code-backups/20260924T220458/`에 백업했다.

독립 의미 검토는 로컬 Gemini 검토 모델의 429/503 때문에 완료되지 않았지만 운영 서버의 별도 검토 환경에서 최종적으로 `ready`, 6개 의미 검토 항목 모두 `true`, issues `[]`를 받았다. 적용 직전 서버 `check`도 `ready`였고 policy fingerprint와 bundle `policy_digest`는 `340354e4e23d349e041394d5c79097ba1a0c5ea13d90aa7259ad30c432f653e6`로 일치했다. `revise-draft`가 현재 본문 SHA `6ff0389080d5f274bb018d04e6def80493408412df75434f52bd23320e566b66`를 compare-and-swap 조건으로 확인한 뒤 같은 ID 233을 갱신했다.

- 본문 원본 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-233-20260924T221502070044.json`
- 초안 색인 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-index-233-20260924T221502070044.json`
- 최종 본문 SHA256: `df90068f75ce462b9f5985b605f6efaee58b470eb30302f002d730dc0a5661c2`
- 최종 상태: `draft`
- 최종 첫 표: `구분 / 품목명 / 대략적인 가격`, 13행
- E-Gen 행동 링크 1개, 출처 영역 1개, 독자용 가운데점 0개

대표 이미지는 한글 글리프 깨짐을 피하기 위해 Windows 맑은 고딕 계열 글꼴로 1200×675 WebP를 결정적으로 다시 렌더링했다. 로컬 결과 `tmp/post233-price-refresh-20260924/post233-cover.webp`의 SHA256은 `ca3eda182d2d41b8c99041a4e2ca7888c40b4148660d7dfe1908297763a06358`, 크기는 35,246바이트다. WordPress에 새 미디어 ID 461로 업로드했고 #233의 대표 이미지를 기존 ID 234에서 461로 교체했다. 이전 미디어 234는 롤백을 위해 삭제하지 않았다. WordPress 저장 파일 SHA가 로컬 원본과 정확히 일치하고, 메타데이터는 1200×675, `image/webp`, alt 텍스트 `추석 연휴 편의점 안전상비의약품 13종 가격과 문 여는 약국 안내`로 확인했다. 이미지 교체 전 WordPress 원본 JSON과 기존 대표 이미지 ID는 `/home/ubuntu/agent-publisher/data/editorial_runs/post233-price-refresh-20260924/media-backup/`에 보관한다.

검증에서는 reference source 기능과 Naver 본문 고정 추출 신규 테스트 4건, 기존 편집/PDF 관련 테스트를 합친 42건이 모두 통과했다. 전체 `agent-publisher/tests`는 400건 중 다른 동시 작업의 `test_post144_property_tax_refresh` import 오류 1건과 `test_legacy_85_welfare_navigation` 기대값 불일치 1건으로 종료 1이었다. 두 실패는 이번 reference source 변경 경로와 무관하며, 이번에 추가·수정한 집중 회귀 테스트는 모두 통과했다. 공개 전환 명령은 실행하지 않았다.

## 3차 보강: 실제 유통 11종만 노출 — 2026-09-24 23시대

사용자 후속 지시에 따라 지정 목록 13종과 생산 중단 2종을 독자에게 별도로 설명하는 방식은 제거했다. 실제 구매 의사결정에 필요한 현재 유통 11종만 표와 본문에 노출하도록 다시 수정했다. 최종 독자 표시 영역에서 `13` 표기 0건, 생산 중단 제품명 `타이레놀정 160mg`과 `어린이용 타이레놀정 80mg` 노출 0건, 가운데점 문자 0건을 확인했다. 생산 중단 사실은 현재 유통 11종을 검증하기 위한 내부 source/evidence에만 남아 있다.

최종 가격표는 다음 11종만 포함한다.

- 타이레놀정 500mg: 약 3,600원
- 어린이타이레놀현탁액: 약 7,400원
- 어린이부루펜시럽: 약 8,000원
- 베아제정: 약 2,200원
- 닥터베아제정: 약 2,400원
- 훼스탈골드정: 약 2,700원
- 훼스탈플러스정: 약 2,500원
- 판콜에이내복액: 약 3,000원
- 판피린티정: 약 2,000원
- 제일쿨파프: 약 3,000~3,500원
- 신신파스아렉스: 약 3,300~3,900원

가격은 CU, GS25, 세븐일레븐 매장 비교 사례를 `reference` 자료로 사용했으며 정부가 정한 공식 정가가 아니라 지역·점포·시점에 따라 달라질 수 있는 대략적인 예산 참고값임을 표 직전 본문에 명시했다.

독립 의미검토에서 기존 보건복지부 요약 인용만으로는 `안전상비의약품별 1개 포장단위`의 법적 문구와 `개봉 판매 금지`가 충분히 직접 뒷받침되지 않는다는 이슈 2건이 발견됐다. 이를 해결하기 위해 현행 국가법령정보센터 `약사법 시행규칙 제28조`를 다섯 번째 출처로 추가했다. 해당 원문에서 1회 판매 수량의 안전상비의약품별 1개 포장단위 제한, 12세 미만 아동 판매 금지, 등록증 및 사용상 주의사항 게시, 개봉 판매 금지의무를 직접 인용했다. 수정 후 별도 ChatGPT 작업 에이전트의 재검토 결과 `source_support`, `conditions_preserved`, `question_answered`, `useful_lifetime`, `no_reader_deflection`, `no_unsupported_claims` 6개 항목 모두 `true`, issues `[]`였다. 서버 자동 Gemini 리뷰는 당일 API 429와 503 때문에 재호출이 불가능하여 이 독립 검토 결과를 현재 bundle digest와 policy fingerprint에 결합한 뒤 공통 `editorial_cli.py check`를 실행했고 최종 `ready`를 확인했다.

연합뉴스 현재 유통 11종 근거 페이지는 기사 본문 밖 실시간 추천 영역 때문에 전체 페이지 해시가 바뀌어 `revise-draft`의 source recheck가 한 번 안전 중단됐다. 정확한 해당 기사 URL에만 `div.story-news.article` 본문을 추출하는 안정화 처리를 추가했다. 이 추출기는 현재 판매 허용 13종과 실제 구입 가능 11종 문구가 모두 존재할 때만 동작한다. 운영 서버 연속 두 번 조회에서 연합뉴스 source SHA256 `ee1161e5f76ecc8c2524814771b99d291748045415f7ff3b34eddaa512e55944`가 동일함을 확인했다. 관련 신규 테스트와 기존 reference source 테스트를 포함한 로컬 집중 테스트 5건은 모두 통과했고, 운영 서버에 배포한 신규 연합뉴스 추출 테스트도 단독 통과했다. 서버 원본 `editorial_writer.py`는 `/home/ubuntu/agent-publisher/data/editorial_runs/post233-price-refresh-20260924/server-code-backups/yna-20260924T225523/`에 백업했다.

최종 `revise-draft`는 직전 본문 SHA `df90068f75ce462b9f5985b605f6efaee58b470eb30302f002d730dc0a5661c2`를 compare-and-swap 조건으로 확인하고 성공했다.

- 본문 원본 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-233-20260924T230743059372.json`
- 초안 색인 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/draft-revision-index-233-20260924T230743059372.json`
- 최종 본문 SHA256: `3a4a49005c6613809367a74f45ee9b8e03a516c55cff1eebfc42d208bffdaa84`
- 최종 상태: `draft`
- 최종 첫 표: `구분 / 품목명 / 대략적인 가격`, 11행
- E-Gen 행동 링크 1개, 국가법령정보센터 출처 링크 1개, 독자용 가운데점 0개

대표 이미지도 본문과 맞춰 `11종`으로 다시 제작했다. 이미지 안의 가운데점은 제거했고 상단 문구를 `보건복지부 기준 품목`, 제목을 `추석 연휴 편의점 상비약 / 소화제, 해열진통제 11종`, 하단을 `판매 품목 확인 | 구매 수량 제한 | 문 여는 약국은 E-Gen 검색`으로 구성했다. 1200×675 WebP 파일 SHA256은 `e1fff73a965fd802187b197d787e4d26ddf1dc4817d1a9db59f61c75c46c2112`다. WordPress 미디어 ID 468로 업로드해 #233 대표 이미지로 연결했고, alt는 `편의점에서 실제 구입 가능한 안전상비의약품 11종 가격과 문 여는 약국 안내`로 저장했다. 이미지 교체 직전 WordPress 원본과 기존 대표 이미지 ID 461은 `/home/ubuntu/agent-publisher/data/editorial_runs/post233-price-refresh-20260924/post-233-before-cover-11.PRIVATE.json`에 백업했다. 이전 미디어는 삭제하지 않았다.

최종 WordPress 실측은 `draft`, 본문 15,462자, 가격표 11행, 대표 이미지 ID 468, 1200×675, 저장 이미지 SHA와 로컬 SHA 일치다. 공개 전환 명령은 실행하지 않았다.
