---
trigger: always_on
---

Bloguito 글 작성·주제 선정·자동화에서는 루트 AGENTS.md, docs/EDITORIAL_SYSTEM.md, agent-publisher/editorial_policy.json을 읽고 적용한다. 사용자가 매번 긴 조건을 반복할 필요가 없게 한다. 공식 출처를 실제로 조회하고 공개·임시글 중복과 정보 유효 수명을 검사한다. 수동 글도 editorial_cli.py의 검토/검사/등록 절차를 이용한다. 기본 임시글, 검토 실패 시 보류. 확인을 독자에게 떠넘기거나 미확인 내용을 FAQ로 만들지 않는다. 사실과 실제 조건을 보존하고 작업 이력을 MD에 남긴다.
