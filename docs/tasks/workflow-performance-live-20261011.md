# F1/F2 운영 데이터 관측 및 WP 읽기 전용 실측 — 2026-10-11

## 범위와 검증 시점

- `e10a20f29473c129c1ba0410c11ab2c8fd77e5d3`는 현재 운영에 설치된 상태. 이 문서의 보완 코드는 **별도 통합·릴리스 전까지 운영 미배포**이며, 이미 설치된 버전의 실측으로 혼용하지 않는다.
- 읽기 전용 SSH로 `/home/ubuntu/agent-publisher/data/editorial_runs/workflow-metrics.jsonl`을 실제 조회했다. **전체 7개 JSONL 레코드, live 성공 4개, 신 릴리스 성공 0개, 이전에 설치된 `9b8145c…` 성공 0개.** 파일 최종 데이터 행의 시각은 2026-10-11 12:04:37 KST로 18:09경 릴리스 설치 이전이다.
- 앞선 보고서에는 80건/34개 코호트라는 수치가 존재하나 현재 운영 파일은 7건뿐이고 80건의 원시 레코드 위치·해시를 독립적으로 확인하지 못했다. 이는 수집 범위가 다른 기록일 수 있으며, 누락된 73건을 임의로 보충하거나 과거 코호트의 신규 릴리스 속도 비교에 전용하지 않는다.
- 읽기 전용 `python scripts/ops/workflow_release_observer.py --ssh-host bloguito --installed-revision e10a20f29473c129c1ba0410c11ab2c8fd77e5d3 --before-revision 9b8145c0680e1d27d9e252d7f0cfaf2c3191a8d5` 결과: `performance_claim=unmeasured`, `comparable_cohort_count=0`, `installed_release_success_rows=0`. 관측 로컬 원시 사본 SHA256 `36702d67809f4de08d23cf80b6d2690f4850ee3558b8da817129bbae1202a286`. 원본/운영 WordPress 수정 없음.

## F1 신규 계측 계약

- 보고서/기존 `compare_code_versions`는 `action, route, transport, workload_signature`, 확정 `release_revision`, `code_version` 및 성공 `live` 기록만 묶는다. 어느 값이든 미분류이면 계산 금지, 양쪽 최소 **5건 이상**이어야 median/P90 비교 대상으로 인정한다. 특정 지표 SSH/WP 왕복 counter가 하나라도 빠지면 해당 지표의 개선률은 `null`; 관측되지 않은 지표는 0으로 채우지 않는다.
- `workload_signature`는 원고 내용·주소·단어·토큰·이미지 파일명을 기록하지 않고 `sources-0`부터 `sources-9`, `sources-10plus`, `sources-na` 및 `image-yes/no`만 기록한다. 정규 `prepare-draft`, `edit-post`, `replace-featured-image`가 이 차원을 남기도록 계측 코드를 추가했다. 모든 작업의 난도/인간 검수/host image_gen/브라우저 QA까지 통제한다고 주장하지 않는다.
- 현 릴리스의 과거 로그는 해당 차원이 없으므로 신뢰할 수 있는 과거 비교 결과는 계속 0개이다. 향후 실제 승인된 정상 workflow 수행으로 충분한 표본이 생기면 다시 비교하고, 인위적으로 글 생성·이미지 업로드를 반복해 표본 수를 채우지 않는다.

## F2 실제 운영 WordPress 읽기 전용 마이크로벤치

운영 서버 WordPress CLI에서 **공개 글 #641의 동일 본문 SHA** `78aa3ebed10a8eac20ae5e927f69e7a5b468b14e20b690a277e138a61aec3c17`를 검증하며, 글 전체 필드+썸네일을 두 개의 별도 PHP/WP 명령으로 읽는 기존 구성과 하나의 PHP/WP snapshot으로 읽는 통합 경로를 서로 번갈아 **각 5회** 측정했다. 실제 게시물 상태와 썸네일 결과 동일함을 검증했고 mutation 0건이었다.

| 관측 | 두 개 WordPress 읽기 | 합쳐진 WordPress 읽기 |
| --- | ---: | ---: |
| PHP/WP 명령 수 | 2회/시료 | 1회/시료 |
| 시료 수 | 5 | 5 |
| 중앙값 | **4,391.99 ms** | **2,377.42 ms** |
| P90 (nearest-rank) | **7,694.60 ms** | **3,135.60 ms** |

측정은 WordPress 호스트 **내부 CLI 실행 소요시간**만 포함한다. SSH 연결 시간, 실제 editorial full workflow, 원문 검증, 사람 작업, 이미지 생성, 브라우저 QA, 안정적인 반복 측정 표본은 **포함하지 않는다**. 특히 종전 remote SSH adapter는 이미 유사한 읽기를 합친 경로가 있으므로 이 측정값으로 실제 SSH 호출 감소나 운영 전체 속도 45% 개선을 주장하지 않는다. 읽기 경계 2→1의 비용 차이만 나타낸다.

## 운영 08:00 스케줄 검증의 다음 조건

- 현지 2026-10-11 18시 이후의 확인 시점에는 2026-10-12 08:00 KST cron이 **아직 도래하지 않았다**. 당시 `crontab`에는 `0 8 * * * .../run_daily.sh`가 있었고 잠금 디렉터리 점유는 별도로 확인해야 한다.
- **다음 예약 실행 이후에만** `cron.log`의 시작·종료·exit 코드, 동일 job 중복 실행 여부, `data/growth/.scheduler-run.lock` 커널 점유/해제, 실제 `PIPELINE_RESULT`, 신규 draft 개수와 기록된 정확한 post ID 및 readback, 수정 없는 결과라면 `no_action` 근거, workflow-metrics의 릴리스 revision을 조회한다. 수동 `run_daily.sh` 실행이나 이미지 업로드를 계측 목적으로 강행하지 않는다.
