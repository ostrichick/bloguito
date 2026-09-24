# #227 교통민원24 이파인 전면 재작성 — 2026-09-24

## 범위

- 기존 Draft #227을 같은 제목·같은 주제로 전면 재작성했다.
- 공개 전환 요청은 없어서 상태는 draft로 유지했다.
- 직접 집필 모델은 GPT-5.6 Sol이고, Gemini 독립 의미 검토를 별도로 수행했다.

## 재작성한 독자 과제

1. 무인단속카메라에 찍힌 것 같을 때 어디를 먼저 보는지
2. 단속 직후 조회되지 않을 때 어떻게 해석해야 하는지
3. 과태료를 범칙금으로 전환하기 전에 벌점과 되돌림 불가를 어떻게 확인하는지
4. 미납·기납 과태료와 범칙금은 각각 어디서 확인하는지
5. 과태료 의견진술은 어떻게 등록·확인하는지
6. 처분벌점·누산점수·면허정지 기간은 어디서 확인하는지

## 공식 근거

경찰청 교통민원24(이파인) 공식 페이지 다섯 개를 사용했다.

- 최근단속내역 화면 이용안내
- 스마트 이파인 메뉴별 조회·납부·벌점 이용안내
- 과태료 의견진술 이용안내
- 무인카메라 단속자료 등록 시점 FAQ
- 과태료→범칙금 전환 주의사항 FAQ

핵심 근거로는 무인카메라 자료가 즉시 등록되지 않고 공식 FAQ상 보통 일주일 내외가 소요될 수 있다는 점, 최근단속 상세의 위반정보·사진, 범칙금 전환 전 벌점 표시와 전환 후 과태료로 되돌릴 수 없다는 주의, 미납/기납 조회, 의견진술, 운전면허 벌점·정지기간 메뉴를 확인했다.

## 수집기 보강

- eFine은 첫 요청에 동일 URL 307과 TMOSHCooKie를 주고 같은 세션의 두 번째 요청에서 200을 반환한다.
- 임의 리디렉션은 허용하지 않고 efine.go.kr/www.efine.go.kr의 .do 경로에서 동일 URL 307 + 해당 쿠키 조건일 때만 같은 URL을 한 번 재요청하도록 보강했다.
- 동일 도움말 응답에서 접근성용 본문 바로가기 한 줄이 나타났다 사라지는 현상을 확인했다. eFine .do source에서 정확히 그 한 줄만 제거해 source SHA를 안정화했다.

## 검토 결과

- 작성 provenance: interactive_chatgpt / GPT-5.6 Sol
- checked_at: 2026-09-24T12:00:50.207963+09:00
- source_support=true
- conditions_preserved=true
- question_answered=true
- useful_lifetime=true
- no_reader_deflection=true
- no_unsupported_claims=true
- issues=[]
- report=ready

## legacy draft 안전 교체

- #227은 reviewed manifest가 없는 기존 evergreen legacy draft였다.
- replace-legacy-draft는 명시적으로 요청된 existing evergreen draft도 원본 SHA·현재 source·검토·백업·CAS 검사를 통과할 때만 교체할 수 있게 확장했다.
- dated legacy 글은 기존 dated_post_exception 없이는 이 경로로 30일 기준을 우회할 수 없다.
- 교체 직전 기존 본문 SHA-256: fbcf7f0e9ca0b214c48c111c4b63dce08cf3e9943634089b07f53d6fdc3c0ec4
- 교체 백업:
  - /home/ubuntu/agent-publisher/data/editorial_runs/legacy-draft-227-20260924T120509586310.json
  - /home/ubuntu/agent-publisher/data/editorial_runs/legacy-draft-index-227-20260924T120509586310.json
- eFine/legacy 서버 코드 배포 백업은 /home/ubuntu/agent-publisher/data/editorial_runs/deploy-efine-legacy-${stamp} 경로에 생성됐다. 이름의 ${stamp}는 당시 배포 스크립트 이스케이프 때문에 문자 그대로 남았지만 백업 파일 자체는 정상이다.
- 정책 동기화 백업: /home/ubuntu/agent-publisher/data/editorial_runs/deploy-policy-sync-20260924T120440/

## 최종 저장 검증

- ID: 227
- 상태: draft
- 제목: 교통민원24 이파인 과태료·범칙금 조회: 최근단속과 납부 안내 구분
- 최종 본문 SHA-256: d025b8269debaf2374a24df13da401870d48bbc84cbf4ac0658d949e931501f7
- WordPress 저장 HTML은 검토된 구조화 bundle renderer 출력과 정확히 일치했다.
- 기존 bloguito-corrected legacy 마커는 남아 있지 않다.
- CTA: 이파인 최근단속내역 조회
- 하단 근거는 메뉴별 조회·납부·벌점 이용안내, 단속자료 등록 시점 FAQ, 과태료→범칙금 전환 주의사항, 과태료 의견진술 이용안내 4개로 구분했다.
- draft index에 GPT-5.6 Sol provenance와 6/6 검토 결과가 저장돼 있다.
