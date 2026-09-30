# 2026-09-30 Simple Task / 이미지 연속 실행 구현 기록

## 목적

대표이미지 한 장 교체 같은 저위험 작업이 전체 편집 파이프라인으로 확대되거나, ChatGPT 이미지 생성 뒤 남은 업로드·대표이미지 지정·본문 수정·readback 단계가 누락되는 문제를 줄이기 위해 실행 코드에 Fast Path와 Completion Guard를 추가했다.

## 구현

- `quick-image-replace`를 추가했다. 대상 post의 현재 본문 SHA와 `_thumbnail_id`를 명령이 직접 읽어 기존 `replace_featured_image()` CAS 경로에 전달한다. 사용자는 이미지 경로, ALT, post ID만 제공하면 된다.
- 동일 post/content/image/ALT 조합의 안전한 실패는 최대 2회까지만 허용한다. media import가 시작됐지만 attachment ID를 확보하지 못한 모호한 실패는 새 import를 자동 반복하지 않는다.
- task-state schema를 v4로 올리고 `completion_requirements`를 추가했다. 실제 edit/image 작업은 필요한 phase가 모두 끝나기 전 `complete`로 닫을 수 없다.
- `AFTER_IMAGE` 체크포인트를 `task-state/post-<ID>/after-image.json`에 별도로 저장한다. 이미지 생성 전 남은 단계, 예상 본문 SHA/thumbnail, 이미지 handle, 완료 요구사항을 남기고 다음 turn에서 이어갈 수 있다.
- `checkpoint-after-image`, `update-after-image-checkpoint` CLI를 추가했다. `complete-task-qa`는 같은 본문 SHA에 결합된 AFTER_IMAGE 요구사항도 확인한다.
- `quick-image-replace` 성공 시 matching AFTER_IMAGE 체크포인트의 이미지 생성/파일 handoff/업로드/대표이미지 지정/readback/본문 SHA 보존 상태를 자동 전진시킨다. 본문·메타 후속 수정 요구사항은 별도로 완료해야 한다.

## 검증

- 표적 회귀: task-state, featured-image, QA scope, SSH transport, edit-router/edit-post, validation router/runner **84 tests PASS**.
- `py_compile` 및 `git diff --check` 통과.
- 전체 suite: 745 tests 실행, 이번 변경과 무관한 기존 `test_designer_safety.py` 계열 8개 오류로 전체 결과는 FAIL. 오류는 저품질 fallback 제거 이후 기대값이 갱신되지 않은 designer safety 테스트와 temp cover 생성 테스트이며 이번 변경 파일에는 `designer.py`/`test_designer_safety.py`가 포함되지 않는다.

## 운영 사용

대표이미지 전용 교체는 다음 경로를 기본으로 사용한다.

```powershell
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- quick-image-replace `
  --post-id 724 --image-path scratch/tasks/post-724/cover.jpg `
  --alt-text "국민연금 수령 시기 안내" --confirm-update
```

ChatGPT native 이미지 생성처럼 turn이 끊길 수 있는 복합 작업은 생성 직전 `checkpoint-after-image`를 기록하고, 다음 turn에서 `update-after-image-checkpoint`와 실제 mutation을 이어간다.

