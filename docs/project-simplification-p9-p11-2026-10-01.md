# 프로젝트 간소화 P9~P11 및 WhatsApp 제거 — 2026-10-01

## 범위와 기준

- 기준 branch: `feat/pipeline-simplify-20261001` (`be24d9a`)에서 전용 `feat/p9-p11-project-simplify` worktree를 생성했다. dirty `main`과 다른 작업자의 미커밋 파일은 수정하지 않았다.
- 범위: P9 validation 단순화, P10 reviewed state/backup 충돌 축소, P11 SSH·section-image 왕복 축소, 사용하지 않는 WhatsApp bridge 제거.
- 유지한 안전장치: WordPress content SHA CAS, mutation 전 backup, guarded readback, 명시적 공개 승인, SSH action/ID allowlist, media import 자동 재시도 금지.

## WhatsApp 제거

- 저장소의 `agent-publisher/whatsapp-bridge/` 전체와 GitHub Actions의 Node bridge job을 제거했다. 현행 README/OPERATIONS/EDITORIAL_SYSTEM/HANDOVER의 WhatsApp 실행 안내도 제거했으며 날짜별 과거 문서는 당시 증거라 보존했다.
- 운영 서버 읽기 전용 확인에서 `whatsapp-bridge.service`는 active+enabled, WorkingDirectory는 정확히 `/home/ubuntu/agent-publisher/whatsapp-bridge`, 디렉터리는 약 65MB였다.
- 사용자 요청 범위에 따라 해당 service만 `disable --now` 후 unit 파일과 정확히 일치하는 bridge 디렉터리만 제거했다. 사후 결과: `unit=removed`, `active=inactive`, `enabled=not-found`, `dir=removed`. 다른 WordPress/백업/자동 초안 서비스는 변경하지 않았다.

## P9 — validation 단순화

- `test_groups.json`, test-group registry, post selector, 부분 suite loader를 제거했다.
- 콘텐츠/이미지 profile은 repository unit test를 실행하지 않고, 공유 repository 코드 변경에서만 `full_regression_required=true`로 전체 `test_*.py`를 한 번 실행한다.
- dirty 작업트리의 unrelated 미추적 test 파일이 runtime manifest coverage 검사를 깨뜨리던 결합도 제거했다.

## P10 — reviewed state와 lock 단순화

- `agents/post_manifest_store.py`를 추가해 legacy inline index와 새 per-post manifest 저장을 동시에 지원한다. marker가 없으면 기존 저장 형식을 유지하므로 기존 설치·fixture와 호환된다.
- marker가 활성화되면 `draft_posts.json`/`published_posts.json`에는 경량 metadata + `manifest_sha256`만 남기고 reviewed `fact_manifest`는 content-addressed `post_manifests/post-<ID>-<digest>.json`으로 분리한다. 새 manifest를 먼저 쓰고 index를 원자 교체하므로 중단 시 이전 index가 계속 유효하다.
- Fast draft/public edit, Standard draft revision/update, public manifest update, edit resume reconciliation, publisher/promote/reformat 경로를 store adapter로 연결했다. per-post 모드의 local CAS는 다른 글 변경이 아니라 대상 record에만 결합된다.
- 전체 index 사본 대신 target reviewed record snapshot을 local rollback evidence로 남기도록 Fast/Standard revision backup을 축소했다.
- 공통 editorial mutation lock acquire/release primitive를 추가하고 주요 mutator가 재사용하도록 정리했다.
- 실제 런타임 index **복사본** migration smoke test: 두 index 합계 2,436,450 bytes → 9,039 bytes의 경량 index, reviewed bundle은 별도 manifest로 분리됐다. 원본 runtime index는 이 테스트에서 변경하지 않았다.
- 실제 canonical runtime의 marker 활성화는 이 branch가 통합된 뒤 수행해야 한다. 구 코드와 compact index를 동시에 사용하지 않는다.

## P11 — SSH 및 section image 왕복 축소

- WSL 표준 OpenSSH 경로만 `ControlMaster=auto`, `ControlPersist=30`, process-scoped ControlPath를 사용해 한 adapter 실행 안에서 연결을 재사용한다. Windows native OpenSSH와 Tailscale transport에는 적용하지 않는다.
- `import-section-image`는 고정 read-only snapshot protocol을 사용한다. 정상 WP-CLI 경로는 `pre snapshot → media import → post snapshot` 3회로 축소됐다. 이전에는 post/meta/attachment 개별 조회 때문에 약 13회였다.
- snapshot payload는 target post와 media import 후 학습된 attachment ID만 허용한다. snapshot은 읽기 전용이라 SSH 255에서 1회 재시도하지만 media import는 non-idempotent이므로 자동 재시도하지 않는다.

## 검증

- P9 표적: 32 tests PASS.
- P10/P11 및 관련 편집 경로 표적: 159 tests PASS, 별도 section-image/transport 39 tests PASS.
- 최종 전체 Python suite: **764 tests 실행, 763 PASS + 1 SKIP, 실패 0**.
- `git diff --check`: exit 0.
- P10 migration은 운영 원본이 아닌 복사본으로만 수행했다. P11 변경 후 실제 운영 이미지 mutation/latency benchmark는 이 코드 작업에서 실행하지 않았다.

## 배포 경계

- WhatsApp 서비스 제거는 운영 서버에 실제 적용 완료했다.
- P9~P11 코드와 문서는 feature worktree/branch에 구현했으며, dirty/diverged `main`을 강제로 덮어쓰거나 기존 미커밋 작업을 재배치하지 않았다.

## main 통합 및 실제 P10 runtime 전환

- 2026-10-01 14시대 통합 전에 기존 `main`의 미커밋 64개 파일을 `stash@{0}`과 `C:\Dev\Bloguito-preservation-20261001-1434`에 이중 보존하고, 기준 HEAD는 `backup/main-pre-p1-p11-20261001`로 고정했다.
- 해당 WIP는 `preserve/main-wip-20261001` 로컬 branch/worktree에 그대로 재적용한 뒤 commit `fa748fa`로 보존했다. 내용은 파이프라인/검증 WIP, 행사·이미지 WIP, 콘텐츠 문서, 일회성 실험 도구로 분류했다. 이 branch는 정규 `main`에 자동 병합하지 않는다.
- `origin/main`의 원격 전용 변경을 먼저 병합했고, 국민연금 계산 예시와 실업급여 월 예상액 계산 검증 충돌은 두 기능을 모두 유지하도록 합쳤다. 이후 P1~P11 연속 branch를 `main`에 병합했다.
- 통합 전체 suite는 767 tests 중 `test_designer_safety` 계열 8건만 오류였고 1건 skip이었다. 같은 8건을 현재 `origin/main` 기준 worktree에서도 그대로 재현해 P1~P11 통합 회귀가 아니라 원격 main의 기존 대표이미지 정책/테스트 불일치임을 확인했다.
- 실제 runtime 전환 전 `draft_posts.json`/`published_posts.json`을 `C:\Dev\Bloguito-p10-state-backup-20261001-144052`에 복사하고 SHA-256을 기록했다. 당시 editorial lock과 기존 schema marker는 없었다.
- `migrate_data_dir()`로 실제 canonical data를 전환했다. 결과는 draft reviewed 15건, published reviewed 2건, 총 per-post manifest 17개다.
- 전환 전후 전체 record canonical SHA-256은 draft `3c9899149a60f261a8fc23a911fa57ca2285eae490bcadea51166cfac003331c`, published `ed1a128122655d87b414b4a9047ecf0e584586d6e7db4c4012f37a4d9110193e`로 각각 완전히 동일했다.
- index 크기는 `draft_posts.json` 2,314,471 bytes → 6,368 bytes, `published_posts.json` 121,979 bytes → 2,671 bytes로 줄었다. schema marker와 17개 content-addressed manifest를 `load_records()`로 다시 읽어 ID 목록과 reviewed record 내용을 검증했다.
