# Main WIP preservation — 2026-10-01

이 branch는 P1~P11 통합 직전 `main`의 미커밋 작업을 손실 없이 보존하기 위한 로컬 스냅샷이다. 정규 `main`에 자동 병합하지 않는다.

## 분류

- 파이프라인/검증/상태/metrics WIP: `edit_*`, `validation_*`, `task_state`, `workflow_metrics`, `wordpress_mutation`, 관련 tests/scripts.
- 행사·이미지 WIP: `designer.py`, `section_image.py`, `event_post_standard.py`, 이미지/폰트 관련 tests와 `agent-publisher/assets/fonts/`.
- 콘텐츠/문서 WIP: 국가건강검진, 실업급여, 대구 10월 행사, `POST_CATALOG.md`, 편집/행사 정책 문서.
- 일회성 도구/실험: `test_calc_script.py`, `test_sync_presets.js`, `test_wp_render.py`, `update_post_609_calculator.py`.

정규 `main`에는 P1~P11 단순화 구현을 우선 유지하고, 이 branch의 변경은 기능별로 다시 검토한 뒤 필요한 것만 선택적으로 이관한다.
