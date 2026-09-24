# 직접 GPT 집필과 예약 Gemini 자동작성 분리 — 2026-09-24

## 사용자 결정

사용자가 직접 ChatGPT에서 새 글 작성을 명령하는 경우에는 현재 대화의 GPT 모델이 원고를 작성하고, 서버 예약 자동화는 기존 Gemini API 작성 경로를 유지한다.

## 구현

- `main.py`의 예약/자동 파이프라인은 `EditorialWriterAgent(writing_enabled=True)`를 명시해 기존 Gemini 작성 동작을 유지한다.
- `EditorialWriterAgent`에 `writing_enabled` 경계를 추가했다. `False`이면 `prepare()`가 즉시 `editorial_writer_disabled_for_manual_flow`로 중단되어 새 원고를 생성하지 않는다.
- `editorial_cli.py manual-review`를 추가했다. ChatGPT가 이미 작성한 `brief/sources/plan` bundle을 입력으로 받고 `--author-model`을 필수로 기록한 뒤 독립 의미 검토와 기존 결정론 검사를 수행한다.
- `review`, `manual-review`, `publish`에서 사용하는 모델 어댑터는 모두 review-only로 생성한다. 따라서 완성된 수동 원고를 Gemini writer가 다시 쓰는 경로가 없다.
- `publish`는 기존대로 실제 WordPress 인벤토리를 다시 조회하고 의미 검토를 다시 수행한 후 draft만 만든다. 공개 승격 절차는 변경하지 않았다.

## 사용 흐름

예약 자동화:

`cron → main.py → Gemini writer → 공통 검증/reviewer → draft`

ChatGPT 직접 작성:

`사용자 요청 → ChatGPT GPT 작성 → manual-review → 공통 검증/reviewer → publish → draft`

직접 작성 경로는 ChatGPT 제품 안에서 현재 모델을 사용하므로 OpenAI API 키를 요구하지 않는다. 서버가 GPT를 호출하도록 변경한 것이 아니다.

## 검증 범위

관련 단위 테스트에서 review-only writer가 `prepare()`를 호출할 수 없는지, 직접 작성 모델명이 최종 article metadata에 보존되는지 확인한다. 전체 WordPress 쓰기나 운영 서버 배포는 이 변경에서 수행하지 않는다.
