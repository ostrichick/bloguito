# 2026-09-28 로컬 콘텐츠 카탈로그와 주제 백로그 갱신

## 확인된 현재 상태

- `docs/POST_CATALOG.md`, `scripts/sync_post_catalog.py`, `agent-publisher/tests/test_post_catalog.py`가 로컬 작업트리에 존재하고 `docs/INDEX.md`에도 카탈로그 진입점이 등록돼 있었다.
- 2026-09-28 12:44 카탈로그에는 WordPress 글 50편(공개 46편, draft 4편)이 반영돼 있었다.
- 새 draft `#598`의 포커스 키워드가 `임플란트 건강보험`인데도 같은 주제가 백로그 1순위에 남아 있었다. 원인은 동기화 스크립트가 백로그 5개 행을 코드에 고정해 매 실행마다 그대로 다시 생성하는 방식이었다.
- 카테고리도 WordPress의 실제 분류를 읽지 않고 제목 키워드로 추정하고 있었다.

## 이번 변경

- 주제 탐색과 1차 중복 확인은 로컬 `docs/POST_CATALOG.md`에서 시작하고, 실제 저장 직전의 최신 중복 검사는 기존 publisher/updater inventory가 담당하도록 `AGENTS.md`, `EDITORIAL_SYSTEM.md`, `OPERATIONS.md`에 흐름을 연결했다.
- 새 draft 생성, 공개 전환 또는 카탈로그 표시 메타데이터 변경 후 `python scripts/sync_post_catalog.py`를 한 번 실행하도록 운영 규칙을 추가했다.
- 동기화 스크립트는 기존 `POST_CATALOG.md`의 사람이 검토한 백로그 행을 읽어 보존하고, 현재 WordPress 글 제목·Rank Math 포커스 키워드와 중복되는 후보를 제거한 뒤 순위를 다시 매기도록 변경했다.
- WordPress 카테고리 이름을 함께 읽어 카탈로그의 카테고리 열에 실제 분류를 우선 사용하도록 변경했다. 기존 제목 기반 분류는 카테고리 데이터가 없는 입력에만 폴백으로 남겼다.
- 최초 카탈로그 생성처럼 기존 백로그가 전혀 없을 때만 기존 5개 후보를 부트스트랩 기본값으로 사용한다.
- 기존 백로그의 임플란트 항목이 #598과 중복되어 제거된 뒤, 2026-09-25 evergreen 주제 조사에서 이미 공식 근거와 경쟁 상황을 검토했던 `인감증명서 온라인 발급 가능한 용도와 본인서명사실확인서 차이`를 5순위 후보로 보충했다. 실제 원고 작성 전에는 최신 공식 원문을 다시 확인해야 한다.

## 검증 범위

이 변경은 WordPress 게시물 본문이나 공개 상태를 수정하지 않는다. `sync_post_catalog.py`는 Direct SSH로 읽기용 임시 PHP를 실행해 현재 목록과 메타데이터를 가져온 뒤 로컬 문서와 JSON inventory만 갱신한다.

- `agent-publisher/.venv/Scripts/python.exe scripts/sync_post_catalog.py`: 성공. 50편 전수 조회와 로컬 카탈로그 재생성을 확인했다.
- 첫 확인 시점인 12:44 카탈로그는 공개 46편, draft 4편이었으나 12:59 실제 재조회에서는 공개 47편, draft 3편이었다. `#598`이 그 사이 공개 상태로 바뀌어 있었다. 이번 동기화 경로는 읽기 전용이므로 이 상태 변경을 수행하지 않았다.
- 두 번째 동기화에서도 새 5순위 인감증명서 후보가 유지되고, 이미 작성된 `임플란트 건강보험` 후보가 백로그에 다시 생기지 않는 것을 확인했다.
- `python -m unittest agent-publisher/tests/test_post_catalog.py agent-publisher/tests/test_post_233_score_boost.py agent-publisher/tests/test_post_233_seo_body.py agent-publisher/tests/test_post_233_cover.py`: 18개 테스트 통과.
- `git diff --check`: 통과. 기존 작업트리의 다른 미커밋 파일은 수정하지 않았다.
