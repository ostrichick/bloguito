# Bloguito 14개 개선 로드맵 — 최종 운영 적용 보고 (2026-10-11)

## 결론 및 구분

- **실제 운영 적용 릴리스:** `e10a20f29473c129c1ba0410c11ab2c8fd77e5d3`, `feat/bloguito-workflow-integration-20261011` 기반의 signed 92-file archive. 이 문서 자체를 나중에 추가한 Git HEAD와 혼동하지 않는다.
- **운영 설치 확인:** 2026-10-11 약 18:09 KST, WordPress MU plugin과 Python runtime, `run_daily.sh` 적용. WordPress 게시물 신규 생성/본문 수정/공개 발행/비멱등 media import는 이번 운영 릴리스 중 **0건**.
- **운영 설치 전 상태:** runtime `9b8145c0680e1d27d9e252d7f0cfaf2c3191a8d5`, MU SHA `a77b668fd1c12c137a54ed0a14e63c3056e060f0bb43848ed5e2823b602f867f`. MU의 변경은 approval kind allowlist에 `manual_agent_delegated`를 추가하는 정확히 한 줄로 확인.
- **운영 설치 후 상태:** runtime revision `e10a20f29473c129c1ba0410c11ab2c8fd77e5d3`, inventory digest `51249534178eedbabf7fc9adf665848ee12a876a5aa0d6e3b2e7a73c44e259c6`, MU SHA `d10d4b3bff10378f965b7e9db8d6d912c3ee99fdeb833136e0774939639794fa`.

## 사전·독립 검증과 실제 운영 readback

1. GitHub Actions [실제 CAS/InnoDB CI](https://github.com/ostrichick/bloguito/actions/runs/38125050282) 4 job PASS. [COMMIT 응답 유실·v3 백업 전체 복원·런타임 rollback CI](https://github.com/ostrichick/bloguito/actions/runs/38125946395) 5 job PASS. 모두 운영 서버·프로덕션 DB와 분리된 WordPress/MariaDB/볼륨 사용. COMMIT 응답 유실은 PHP 출력 누락 시뮬레이션이지 실제 TCP 끊김/DB crash는 아님. 가상 사이트 백업은 별도 DB와 uploads/plugins/themes/MU/configs/secrets를 복원했고, host 서비스 설정을 자동 재설치하거나 실제 운영 RTO/RPO를 증명하지 않음.
2. 로컬 통합 코드 repository route Python **1,335 tests / failures 0 / errors 0 / skipped 4 / exit 0**. 최초 한 번 Windows analytics localhost 소켓 중단으로 오류가 발생했으나 해당 test_analytics_http_receiver 4건 독립 PASS 후 전체 재실행이 PASS. PHP MU·실 WordPress policy/metadata 테스트와 Linux cron-vs-direct/SIGKILL 8건은 CI PASS.
3. **사전 독립 백업:** 정규 운영 `/home/ubuntu/agent-publisher/backup_daily.sh` 실행 결과 `/home/ubuntu/backups/bloguito_backup_20261011_175028.tar.gz` (약 114MB), SHA256 `8f5729c0d4bfbbba85c04a71e516cd863f576fcbe1b4449ccb14830d3e206611`. 운영 `restore_backup.sh --verify-only`로 version 3.0 archive의 components/SHA/gzip/nested path 검사 exit 0. 실제 이 운영 아카이브의 destructive restore는 수행하지 않음.
4. **MU 운영 업데이트:** 현재 운영 MU의 SHA 정확한 매치, 원본 바이트 별도 백업, `.php`로 끝나지 않는 비활성 staged 파일 SHA/권한 및 `php -l` 확인, editor+growth 공유 lock 획득, 원자 rename, 새 live SHA, `php -l`, WordPress `wp eval` 게이트 로드 확인, lock 해제 모두 PASS. 사전·사후 source SHA를 독립 조회. 원본 MU는 `/home/ubuntu/agent-publisher/backups/mu-pre-e10a20f-20261011.bin` (mode 600, SHA `a77b668f…`)에 보존.
5. **Python + cron 운영 업데이트:** `/tmp/bloguito-release-e10a20f-20261011/release`에 stage한 아카이브의 local/remote tar SHA 동일, `--preflight-only`가 MU 전에는 정확히 차단되고 MU 설치 후 PASS. 정규 `install_editorial_release.py` 실행 중 imports/publish gate/provenance registries smoke PASS, 정확한 설치 receipt와 자동 이전 파일 백업 생성. 후속 독립 read-only verifier는 **signed 92개 파일 중 92개 SHA 일치**, 불일치 0, `run_daily.sh` mode 775 실행 가능, `data/.editorial-publish.lock` 해제 확인. `/home/ubuntu/agent-publisher/backups/editorial-20261011T090921Z-415ca8a41e07/manifest.json`은 이전 파일별 rollback 자료.
6. `crontab`의 **`0 8 * * * /home/ubuntu/agent-publisher/run_daily.sh`가 유지**됨을 재확인. 실제 다음 08:00 예약 실행은 아직 관측하지 않음. 수동으로 `run_daily.sh`를 실행하면 콘텐츠 생성 가능성이 있으므로 이번 smoke에서 실행하지 않음.
7. WP-CLI read-only 공개 post **#641**: 상태 `publish` 그대로, 저장 본문 SHA256 `78aa3ebed10a8eac20ae5e927f69e7a5b468b14e20b690a277e138a61aec3c17` 설치 전과 일치. 공개 페이지 `https://lifeinfo24.org/?p=641` → canonical redirect 후 HTTP 200.

## F1·F2·Q1·Q3·R1·R2 잔여 범위

| 항목 | 현재 성과와 확인 증거 | 한계 |
| --- | --- | --- |
| F1 | 같은 action/route/transport/확정 release로 median/P90/SSH/WP roundtrip을 구분하는 진단 구현·운영 코드 적용 | 이전 로컬 80개 성공·34 cohorts는 코드/릴리스 혼합이며 신규 릴리스 비교 표본 0건. 실측 개선률 **미측정** |
| F2 | 같은 시점의 WP post/thumbnail 논리 조회를 2→1, image attestation pre/post 총 4→2로 줄이는 mock/fault 테스트 및 운영 코드 적용 | 실제 원격 latency·median/P90/SSH 횟수 개선률 미측정; CAS/readback 생략 없음 |
| Q1 | 공개 #641 실제 Edge 390x844, 1280x900 첫 viewport PNG와 JSON evidence, 각 TOC 12, table 4, overflow 없음, `browser_pass`. `<worktree>/scratch/tasks/live-qa-641/evidence/` 원본과 통합 `scratch/tasks/roadmap-final-live-qa-641/` 사본 보존 | 브라우저 200% 확대 실제 적용·target=_blank CTA 클릭·인증된 draft Preview·페이지 전체 스크롤 구간 QA 미확인 |
| Q3 | task-state 최신 WP SHA/thumbnail read-only 검사, 이미지 import 불명확 상태 attachment SHA 후보 분류, `creating/created/complete` 신규 draft journal 정확한 reviewed bundle 대조 및 정규 resume 안내 구현·운영 적용 | ID가 없는 `creating`은 소유권 입증 없이 안전하게 자동 복구 불가. 이미지 import 후보도 원본 host provenance와 readback 전에는 채택/재업로드 금지 |
| R1 | 순수 image baseline, task reconciliation, draft-create reconciliation, SSH CLI request parse를 독립 내부 모듈로 추출, 기존 CLI/저장 schema·allowlist·CAS를 유지 | 나머지 `featured_image.py`/`edit_router`/SSH transport를 무리하게 전면 재구성하지 않아 구조 개선은 부분 |
| R2 | 사용자/에이전트 선택, staged receipt 경로·actor/SHA/승인 일치, null thumbnail, PNG 지원, 새 MU policy의 실제 SHA 배포 및 원복 훈련 | `origin_claim`은 image_gen 호스트 호출의 서명 증거가 아니며 독립 host attestation은 미확인 |

## 14개 항목 최종 기능 판정

| 판정 | 항목 | 근거 범위 |
| --- | --- | --- |
| **완료 (8)** | S1, S2, S3, T1, T2, T3, T4, Q2 | 코드·회귀 통과, signed runtime 운영 적용. 실제 기사별 공식 검토/개별 콘텐츠 작업은 별도 승인 계약 |
| **부분 완료 (6)** | F1, F2, Q1, Q3, R1, R2 | 추가 기능과 주요 실환경 검증은 완료했지만 위 표의 실측·브라우저·원본성·자동 복구/구조 범위가 잔존 |
| **미착수 (0)** | 없음 | 부분 개선의 남은 수용 기준을 무시하거나 완료 처리하지 않음 |

## 남은 운영 관찰·복구 위험

- **다음 cron:** 실제 08:00 실행 결과, `cron.log` 종료 코드, 성장 plan/draft 중복 여부와 lock 동작을 별도 read-only 확인해야 함. 기존 예정 실행을 강제 시뮬레이션하지 않았다.
- **성능:** 신규 릴리스에서 같은 동질 작업 성공 표본이 양쪽 최소 5건 이상 누적되면 F1 median/P90를 비교한다. 콘텐츠 성과/GSC 증가나 속도 개선률을 현재 사실로 단정하지 않는다.
- **복구:** runtime error-time rollback은 실제 detached CI에 성공했다. 운영 **post-success** 수동 rollback은 위 per-file 백업과 원본 MU·v3 snapshot을 사용해야 하며, 자동 완료나 실제 운영 사이트 전역 복원으로 주장하지 않는다. DB와 미디어 v3 백업이 전역 원자 snapshot은 아니므로 복구 중 서비스 중단·정합성 재검증과 운영 변경 창이 필요하다.
- **정책:** 원본 이미지 생성 host 증빙, 실제 게시물 발행/미디어 업로드의 실패 시 재시도, semantic review·공식 출처의 신선도는 이번 소프트웨어 릴리스로 면제되지 않는다. 공개 발행·비멱등 mutation 수행 0건.
- 원본 `main`의 미커밋 문서·계획서를 변경하지 않았으며 통합 worktree에서 코드를 배포했다. 통합 브랜치를 dirty `main`에 강제 병합하거나 다른 세션의 worktree를 삭제하지 않았다.
