# Bloguito scripts policy

`scripts/` 루트에는 **여러 게시물·여러 작업에서 반복 사용할 유지보수 도구만** 둔다.
게시물 한 건을 위해 만든 임시 Python 파일을 이 디렉터리에 새로 추가하지 않는다.

## 기본 경로

콘텐츠 작업은 새 스크립트를 만들기 전에 기존 정규 진입점을 먼저 사용한다.

- 신규 reviewed draft: `editorial_cli.py prepare-draft`
- reviewed draft/public 수정: `editorial_cli.py edit-post`
- 대표이미지 전용 교체: `replace-featured-image` (현재 SHA/thumbnail baseline 자동 수집)
- 로컬 HTML의 한 컴포넌트 삽입·교체·삭제: `patch_post_component.py`
- workflow 병목 확인: `summarize_workflow_metrics.py`
- 검색 성장 기회 갱신: `build_growth_queue.py`
- 신규 주제 demand gate 점수화: `score_topic_candidates.py`
- 일일 성장 작업 결정: `build_daily_growth_plan.py`
- 기존 글 성장 개선 완료 기록: `record_growth_work.py`
- 변경 범위별 regression plan/실행: `run_validation.py` (기본 plan-only, 실제 실행은 `--run`)

직접 WP-CLI나 임시 PHP로 편집 검증을 우회하지 않는다.

## 파일 수명주기

1. **재사용 가능**: 두 개 이상의 독립 작업에서 쓸 명확한 인터페이스가 있고 테스트를 둘 수 있으면 `scripts/` 루트에 둔다. `maintained_scripts.json`에도 등록한다.
2. **작업 중 임시**: 한 글, 한 이미지, 한 조사에만 필요한 코드는 `scratch/tasks/<작업명>/` 아래에 둔다. `scratch/`는 Git 비추적 영역이다.
3. **기록 보존 필요**: 일회성 스크립트를 나중에 참고할 필요가 있으면 `scripts/archive/<날짜 또는 작업명>/`로 옮긴다. 새 archive 파일은 Git에 추가하지 않는다. 이미 과거에 추적된 archive 파일은 역사 기록으로 유지한다.
4. **게시물 전용 테스트/하네스**: 공통 동작을 검증하는 테스트가 아니면 `agent-publisher/tests/`에 두지 않는다. 작업 중 검증 코드는 `scratch/tasks/`에, 설명 기록은 필요할 때 기존 작업 MD에 남긴다.
5. **브라우저 QA 프로필**: repo의 `tmp/`/`scratch/`에 Edge/Chrome user-data-dir를 만들지 않는다. 기존 브라우저 세션을 재사용하거나 OS 임시 디렉터리를 사용하고, 성공한 QA 뒤 프로필/cache는 삭제한다. 저장소에는 최종 screenshot/JSON 증거만 남긴다.
6. **재시도 산출물**: 같은 작업의 retry마다 timestamp 폴더를 추가하지 않고 동일 task workspace의 안정된 파일명(`candidate.json`, `qa.json`, `mobile.png` 등)을 갱신한다. 별도 보존이 필요한 실패본만 명시적으로 `failed/`에 남긴다.
7. **관리형 task workspace**: 새 disposable 작업은 `python scripts/task_workspace.py open <task>`로 `scratch/tasks/<task>/`를 생성·재사용한다. 완료는 `mark <task> completed`, 실패 후 재개용은 `failed`, 장기 보존은 `preserved --reason ...`로 표시한다. manifest가 없는 기존 scratch 파일은 자동 TTL 정리 대상으로 소급 해석하지 않는다.
8. **TTL**: 관리형 `completed` workspace는 기본 72시간, `failed` workspace는 기본 168시간 뒤 `cleanup_workspaces.py` 후보가 된다. `active`, `preserved`, manifest가 없거나 손상된 workspace는 자동 삭제하지 않는다. 브라우저 프로필은 가능하면 `agents.workspace_lifecycle.temporary_browser_profile()`로 OS temp에서 한 QA batch 동안만 사용한다.

## 왜 이 규칙이 필요한가

과거에는 행사 글 하나를 만들거나 수정할 때 `build_*`, `create_*`, `patch_post_<ID>_*`, `test_*` 형태의 Python 파일을 빠르게 생성했다. 작업 자체는 끝나도 파일이 `scripts/`와 `agent-publisher/tests/`에 남아 Git 상태를 오염시키고, 다음 작업자가 그 파일을 정식 도구인지 일회성 산출물인지 다시 판단해야 했다.

P3부터는 **데이터는 bundle/JSON/HTML에 두고 동작은 공통 CLI에 둔다.** 새 Python 파일이 정말 필요한 경우에도 먼저 `scratch/`에서 검증하고, 두 번째 독립 사용 사례가 생겨야 재사용 도구로 승격한다. 과거 `tmp/`는 날짜별 작업 증거가 다수 연결된 legacy 영역으로 취급하며 새 일반 작업의 기본 출력 위치로 사용하지 않는다.
