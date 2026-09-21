# Bloguito · Gemini 프로젝트 지침

작업 시작 시 루트 `AGENTS.md`를 읽고 적용한다. 글 작성·주제 선정·자동화는 반드시 `docs/EDITORIAL_SYSTEM.md`와 `agent-publisher/editorial_policy.json`도 먼저 읽는다. 이 세 파일이 현재 기준이며 `PROJECT_HANDOVER.md` 등 과거 기록은 참고용이다.

기존 구현을 확인하고 재사용하며, 요구 범위에 필요한 최소 변경을 계획하고 테스트한다. 보안·입력 검증·다른 작업자의 미커밋 변경은 보존한다.

편집 시 공식 출처와 현재 글 목록·중복·유효기간을 확인하고, 구조화 원고를 `agent-publisher/editorial_cli.py` 검토·검사 경로로 처리한다. 지침·근거·검사에 접근할 수 없거나 검토가 실패하면 작업을 보류하고 이유를 내부 보고한다. WP-CLI·임시 PHP로 검사를 우회하거나, 명시적 승인 없이 기존 공개 글을 덮어쓰거나 공개하지 않는다. 기본 등록 상태는 임시글(`draft`)이다.
