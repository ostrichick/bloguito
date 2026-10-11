# T1 검색 의도 분리 검토 기록 — 운영 미적용

## 변경 범위 및 안전 조건

- **기본값:** 신규 글의 공식 URL 공유는 계속 중복으로 차단한다. 제목·검색 의도상 명백한 동일성, 본문/신청·조회·구매 CTA 공유는 영수증으로도 예외 처리하지 않는다.
- **명시적 수동 예외:** 사용자가 실제 기존 글의 질문·답변 범위와 신규 글의 독자 질문, 신청 행동, 대상/지역/시기를 대조한 후 별도의 JSON 영수증을 승인한 경우에만 현행 renderer의 **마지막 공식 출처 목록**에 있는 동일 URL을 허용한다.
- 영수증은 reviewed bundle 바깥에 보존한다. 정확한 brief JSON SHA, 비교한 모든 WordPress post ID·본문 SHA·제목·상태, 신규/기존 질문과 분리 근거, 사용자 검토일 및 최대 7일의 만료일을 검증한다. 하나라도 불일치하거나 unhydrated inventory/legacy HTML이면 fail closed한다.
- 현재 source freshness, 6항목 semantic review, signed bundle digest, draft-only, 저장 직전 WordPress 재확인, S3 post-create 복구 fence는 그대로다. unattended scheduler는 영수증을 자동 제공하지 않는다. 분류 함수의 출력은 승인 기록이 아닌 **진단**이다.

## 영수증 JSON 필드

최상위 필드: schema_version=1, brief_sha256 (agents.search_intent.intent_brief_digest(brief) 결과), reviewer="user", approved=true, reviewed_on (YYYY-MM-DD), valid_until (YYYY-MM-DD), comparisons 배열.

comparisons의 각 행은 post_id (정수), post_content_sha256 (현재 WordPress 본문 SHA), post_title (정확한 제목), post_status (현재 상태), new_reader_question (brief.question 원문), existing_reader_question (기존 답변이 해결하는 질문), existing_answer_scope (기존 답변/행동/대상/시기의 구체적 범위), differentiation_reason (왜 독립적인 독자 질문인지 구체적 설명), decision="distinct_reader_question", shared_action_or_answer=false를 모두 포함한다. 추가·누락 필드는 허용하지 않는다.

승인은 사용자의 수동 결정을 기록하는 것이며 서명된 신원 증명은 아니다. 검토자 항목만 임의로 기입하는 것으로 실제 사용자 검토를 대체할 수 없다.

## 수동 실행 경로

~~~powershell
python scripts/editorial_cli_via_ssh.py -- prepare-draft scratch/tasks/article/bundle.json --topic-intent-receipt scratch/tasks/article/intent-receipt.json --confirm-intent-differentiation --output scratch/tasks/article/draft-result.json
~~~

작성 모델·대표 이미지 인자는 기존 prepare-draft 계약에 따라 별도 추가한다. 영수증 없는 일반 명령과 scheduled planner에는 **동작 변경 없음**. WordPress 상태 불일치라면 게시물 생성 전에 멈추며, 부분 생성 후 재시도 정책을 우회하지 않는다.

#928 대 #139/#926 테스트는 구체적인 운영 WordPress 페이지를 검증한 결과가 아닌 **합성 충돌 fixture**이다. 실제 예외 적용 전에 원문과 독립된 질문/CTA를 다시 확인해야 한다. 본 변경에서는 WordPress, 실제 글, 운영 설정을 수정하지 않았다. 카탈로그 T2 동기화와 충돌하지 않도록 백로그 자동 삭제 휴리스틱은 건드리지 않았다.
