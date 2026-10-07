# Bloguito 운영·개발 가이드

**적용 범위:** 저장소의 코드·설정에 근거한 작업 경로를 설명한다. 이 문서 자체는 현재 서버 배포 상태나 복구 성공을 보증하지 않는다. 실서비스 수정 전에는 실제 서버 이미지/구성, 백업, 실행 프로세스, 콘텐츠 상태를 다시 조회한다. 편집 기준과 기한·검토 설정을 복제하지 않고 [EDITORIAL_SYSTEM](EDITORIAL_SYSTEM.md) / [`editorial_policy.json`](../agent-publisher/editorial_policy.json)을 따른다.

## 코드 릴리스와 비공개 통계 전달

편집 코드 배포는 `scripts/install_editorial_release.py`에 검토한 release directory와 기존 app directory를 전달한다. release root의 `release-manifest.json`은 `schema_version=2`, Git commit SHA인 `revision`, inventory digest, 상대 경로별 SHA256인 `files`, 명시적 `retired_files`를 포함해야 한다. `files`는 release의 `agent-publisher/`·`docs/` 파일 목록과 정확히 일치해야 한다. 신규 renderer/schema/source modules 누락이나 파일 hash 불일치는 쓰기 전에 차단한다. `.env`, runtime manifest/index, source receipt는 코드 release에 넣지 않는다.

환경 설정을 `os.getenv()`로 읽는 현행 config일 때만 `main.py`·`config.py`를 함께 갱신할 수 있다. inline credentials가 있는 구 config는 먼저 별도 이관해야 하며 installer가 자동 변환하지 않는다. 기존 `data/search_briefs.json`은 덮어쓰지 않는다. 변경 파일 backup과 rollback manifest를 유지하고, 설치 뒤 editorial CLI·edit orchestration·critical-fact registry와 reviewed-content provenance registry의 전체 schema/digest 검증을 통과한 후 `data/editorial-release.json`에 실제 설치 hash와 revision을 기록한다. registry 검증 실패도 설치 실패로 처리해 같은 rollback 경로를 사용한다. obsolete 파일은 참조가 없고 retirement allowlist에 포함된 것만 명시적으로 제거한다.

비공개 Google 보고서는 GitHub Workload Identity로 읽기 전용 수집한 뒤 `https://lifeinfo24.org/_bloguito/analytics-ingest`에 전달한다. GitHub secret `BLOGUITO_ANALYTICS_TOKEN`과 서버의 root-only `/etc/bloguito-analytics.env`를 같은 token으로 설정한다. `wordpress/analytics/`의 systemd unit과 nginx snippets가 실행/HTTPS proxy의 정본이다. 수신기는 localhost에만 bind하고 POST 인증·4MiB 상한·기존 snapshot schema/freshness 검증 뒤 private analytics directory에만 저장한다. 보고서·인증 header는 응답과 access log에 노출하지 않는다. 공개 SSH allowlist는 이 전달 경로와 별개로 유지한다.

통계 전달 검증은 workflow success만으로 끝내지 않는다. 서버의 해당 날짜 JSON 생성 시각·SHA·schema validation을 확인한다. 다음 예약 실행의 실제 성공 여부는 별도로 기록한다. 기존 restricted SSH receiver는 rollback용이며 신규 workflow는 사용하지 않는다.

워크플로 metrics는 runtime code fingerprint·release revision·route·transport를 기록한다. `summarize_workflow_metrics.py --since YYYY-MM-DD --code-version <fingerprint>`로 같은 code version의 측정을 비교한다. `wp_roundtrips`는 논리적인 WP 호출, `ssh_roundtrips`는 adapter가 실제 수행한 SSH 호출이다. 없는 counter는 0으로 해석하지 않는다. image-only adapter는 바로 이어지는 post/thumbnail 조회만 한 snapshot으로 합치고, 다른 호출이 끼거나 값을 한 번 소비하면 snapshot을 재사용하지 않는다. import 전 확인과 저장 뒤 readback, media import 무재시도는 유지한다.

WordPress 호출은 `agents/wordpress_transport.py`의 실행 context로 adapter를 주입한다. 일반 subprocess 호출은 가로채지 않는다. 병렬 작업이 필요하면 기존 호출자의 `copy_context()`를 통해 해당 실행 권한을 명시적으로 전달한다.

글 목록 동기화는 본문 SHA와 검토 digest·checks·lifecycle metadata가 유효한 저장 원고에만 `(저장 원고 기준)`을 붙인다. 이는 출처의 현재 유효성을 새로 검토했다는 뜻이 아니다. 일치하는 원고가 없는 글은 제목/category slug로 분류한 `(추정)` 표시를 유지한다.

## 구조와 실행 위치

| 경로 | 역할 |
| --- | --- |
| `agent-publisher/main.py` | Radar → Curator → Editorial Writer → Designer → Publisher의 자동 **임시글 생성** 진입점 |
| `agent-publisher/editorial_cli.py` | 근거 수집, 검토, 검사, 임시글 등록/갱신, 사람 확인 후 별도 공개 |
| `agent-publisher/agents/` | 검색·검토·렌더링·WordPress 연결 로직; 자동 파이프라인과 현행 원고 경로는 `editorial_writer.py`를 사용 |
| `agent-publisher/data/` | 환경별 런타임 상태. 민감·운영 JSON 및 `.env`를 Git에 추가하지 않음 |
| `wordpress/docker-compose.yml` | WordPress·MariaDB 선언; 실행 중 서버 설정과 다를 수 있음 |
| `wordpress/mu-plugins/` | 자체 WP MU 플러그인. 관리자 글 ID 열 구현을 포함하나 운영본 설치 상태는 별도 확인 |
| `scripts/` | 반복 사용 가능한 운영·진단 도구만 유지. 게시물 한 건을 위한 임시 Python은 두지 않으며 목록은 `scripts/maintained_scripts.json`으로 검증 |
| `scratch/` | 한 작업에서만 필요한 probe, 변환 코드, 중간 JSON/HTML/이미지. Git 비추적 |
| `tmp/` | 과거 작업 증거가 연결된 legacy 임시 영역. 새 일반 작업·브라우저 프로필의 출력 위치로 사용하지 않음 |
| `scripts/archive/` | 보존할 가치가 있는 과거 one-off 스크립트. 새 archive 파일은 Git 비추적이며 정규 실행 경로로 사용하지 않음 |

## 로컬 설치 및 무변경 검사

Python 3.12와 Docker/Git Bash를 작업 종류에 맞춰 준비한다. Python 환경은 **로컬** `agent-publisher/.venv`, **Linux 운영 예시** `agent-publisher/venv`로 다르다. `.env.example`에는 실제 비밀번호를 쓰지 않는다.

```powershell
# 프로젝트 루트의 Windows PowerShell: 실제 게시물/서비스는 수정하지 않는 테스트
$env:PYTHONPATH=(Resolve-Path './agent-publisher').Path
$env:PYTHONIOENCODING='utf-8'
./agent-publisher/.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests -q

# 백업 도구 문법/명령 정책 등은 .github/workflows/test.yml을 참조
```

```bash
# Linux: 관련 도구가 준비된 환경에서만
python3 -m unittest discover -s agent-publisher/tests
bash -n agent-publisher/backup_daily.sh agent-publisher/restore_backup.sh
# Compose 검증에는 환경마다 유효한 변수 필요; 설정 전체 출력은 비밀번호를 노출할 수 있음.
MYSQL_ROOT_PASSWORD=ci-placeholder MYSQL_PASSWORD=ci-placeholder \
  docker compose -f wordpress/docker-compose.yml config --quiet
```

위 `ci-placeholder`는 **정적 설정 검증 전용**이며 컨테이너 실행이나 운영 DB에 사용하지 않는다. `wordpress/setup.sh`는 초기화 작업을 포함하므로 기존 사이트에서 재실행하지 않는다. `docker compose up`, `pull`, `down -v`, `restore_backup.sh --yes`도 이 문서의 읽기 전용 검사의 일부가 아니다.

### 작업 범위에 맞춘 검증

reviewed post 수정은 원고 diff와 실제 Fast/Standard route를 단일 classifier가 한 번 분석해 `validation_plan`을 만든다. SSH adapter는 이 결정을 mutation 단계에 그대로 전달하며 다시 분류하지 않는다. `validation_plan`의 profile은 실행 보고와 source/review 범위를 설명하지만 **콘텐츠 한 건을 수정할 때 Python unit/regression suite를 실행하지 않는다.** 콘텐츠 무결성은 bundle 검사, 필요한 source/semantic review, CAS, backup, guarded readback이 담당한다.

| 대표 profile | 예 | 콘텐츠 작업에서 실행 | content/source review |
| --- | --- | --- | --- |
| `quick-text` | 오탈자, 표현 정리, 기존 사실 재배치 | Python regression 없음, CAS/readback | source 재사용 + changed-block delta review |
| `quick-image` | 대표이미지만 교체 | Python regression/브라우저 QA 없음, attachment/ALT/thumbnail/본문 보존 readback | 본문/source semantic review 없음 |
| `standard-fact` | 새 숫자·가격·조건·제목 | Python regression 없음 | Standard full semantic review + current source receipt/live 규칙 |
| `standard-source` | source snapshot/URL 변경 | Python regression 없음 | source 동일성 재검증 + full semantic review |
| `standard-cta` | 조회·신청·예매 목적지 변경 | CTA destination browser smoke 필요 | 목적지/근거 확인 + full semantic review |
| `standard-layout` | 표/section/FAQ topology 변경 | 모바일/데스크톱·접근성 browser QA 필요 | Standard면 full review, Fast 구조 재배치는 delta review |
| `standard-event` | 행사·공연 날짜/장소/판매상태 변경 | Python regression 없음 | affected/live source + full review |
| `full-regression` | `agents/`, policy, renderer, SSH transport, test infrastructure 같은 공유 코드 변경 | 전체 `agent-publisher/tests` 1회 | 코드 변경에 맞는 기존 editorial 검증 유지 |

unit/regression tests는 **공유 코드가 바뀐 작업**을 검증하는 도구다. 콘텐츠 데이터 변경과 코드 회귀 검증을 연결하지 않는다. `full-regression`은 repository change classifier가 공통 코드 변경을 감지했을 때만 선택한다.

P9부터 별도의 test-group registry나 게시물별 test selector를 유지하지 않는다. `validation_plan.full_regression_required=false`인 콘텐츠·이미지 작업은 repository unit test를 실행하지 않고, `true`인 공유 코드 변경은 `agent-publisher/tests/test_*.py` 전체를 한 번 실행한다. dirty 공유 작업트리에 임시 `test_*.py`가 생겼다는 이유만으로 unrelated 콘텐츠 mutation을 차단하지 않는다.

문서만 수정한 경우에는 `git diff --check`와 링크/문서 구조 확인으로 충분하다. 공통 renderer, validator, publisher, 정책·transport 로직을 바꾼 경우에만 표적 테스트 뒤 전체 suite를 1회 실행하고, 이후 공통 코드가 바뀌지 않았다면 콘텐츠/문서 수정 때문에 같은 full suite를 반복하지 않는다. 화면 검증도 CSS/renderer/표·목차 구조가 바뀌면 360/390px, 데스크톱, 200% 확대와 키보드 접근까지 수행하고, 구조가 그대로인 본문 데이터 수정은 대표 모바일+데스크톱의 변경 영역, CTA-only는 실제 도착 화면과 버튼 smoke test를 우선한다.

비로그인 실제 사이트 QA가 필요한 경우 첫 진입은 `https://lifeinfo24.org/?utm_source=bloguito_qa_agent&utm_medium=internal_test&utm_campaign=site_checks`로 시작해 내부 QA 세션을 식별한다. 일반 독자용 링크에 이 UTM을 전파하지 않는다.

`scripts/run_validation.py`는 진단·CI용 별도 runner다. 기본 실행은 **plan 출력만** 하며 테스트를 실행하지 않는다. 실제 실행은 `--run`을 명시한다.

```powershell
# 공유 코드 변경: full-regression plan만 확인
python scripts/run_validation.py --changed-file agent-publisher/agents/editorial.py

# 두 reviewed bundle의 콘텐츠 profile만 확인; 콘텐츠 작업은 테스트를 실행하지 않음
python scripts/run_validation.py --before scratch/tasks/edit/before.json `
  --after scratch/tasks/edit/after.json --route standard --post-id 641
```

## 원고 경로: 기본은 draft

### 카테고리 taxonomy 운영

현행 신규 분류는 `events`, `concert`, `welfare`, `tax`, `health`, `transport`, `life-admin`, `finance` 8개다. 표시명·WordPress term ID·slug의 코드 정본은 `agent-publisher/config.py`의 `CATEGORIES`이며, 신규 파이프라인은 이 목록 밖의 값을 자동 생활 카테고리로 폴백하지 않는다.

운영 WordPress에서 카테고리를 추가·이동할 때에는 먼저 category term, primary menu, 대상 post의 status/title/post_name/content SHA/category/get_permalink를 스냅샷하고, 여러 글을 옮길 때에는 `post_id → target term` 명시적 매핑을 사용한다. 각 글은 `wp post term set ... category ... --by=id`처럼 기존 카테고리를 교체하고 즉시 정확히 한 category만 남았는지 readback한다. 완료 뒤에는 title, slug, status, 본문 SHA와 permalink가 작업 전과 같은지 전수 비교하고 `wp term recount category`, cache flush, category archive/menu 확인 후 `python scripts/sync_post_catalog.py`를 실행한다.

과거 `life-health` term은 서로 다른 새 카테고리로 분할되므로 하나의 alias나 새 term으로 일괄 치환하지 않는다. 글 수가 0이 되고 메뉴·신규 코드에서 제거된 뒤에도 초기 cutover/rollback 기간에는 term을 바로 삭제하지 않는다. 삭제 전에는 기존 `/category/life-health/` archive의 처리 방침과 rollback 필요성을 별도로 확인한다.

### 글쓰기·수정 시작과 묶음 처리

작업 시작 시 대상과 요청을 아래 표로 분류한다. 진행 설명은 “이번에는 [대상]의 [수정 범위]를 처리합니다. [근거 확인] → [전체/변경 부분 검토] → [임시글 저장/승인된 기존 글 수정] → 저장·화면 확인 순서로 진행합니다”처럼 1~2문장으로 한다. 대상이나 공개 의도가 실제로 불명확한 경우에만 필요한 정보를 확인하며, 이미 받은 같은 변경안의 적용 승인을 다시 묻지 않는다.

| 요청 종류 | 정규 경로 | 핵심 검사 |
| --- | --- | --- |
| 일반 신규 draft | `prepare-draft` | content/source preflight, 필요한 semantic review, 최신 inventory, draft 저장/readback. 대표이미지는 사용자 선택 전까지 미부착 허용 |
| 기존 reviewed 글 수정 | `edit-post` | 단일 classifier가 Simple/Standard를 선택. 모든 write는 CAS/readback, 사실 변경은 source/full review 추가 |
| 대표이미지만 교체 | `replace-featured-image` | live 본문 SHA와 `_thumbnail_id`를 명령이 직접 읽고 image-only mutation/readback. article source/review는 열지 않음 |
| 공개 전환 | `promote-draft --confirm-publish` | 글별 사용자 승인, current review/source binding, 승인된 대표이미지 attestation, draft CAS |

과거 `publish`, `edit-draft`, `revise-draft`, `fast-revise-draft`, `update-existing`, `update-draft`, `quick-image-replace`, `replace-legacy-draft` 공개 action은 제거했다. P10 reviewed state가 없는 legacy draft도 별도 호환 mutation 경로로 즉시 이관하지 않는다. 사용자가 해당 글을 수정할 때 현행 편집 지침과 source/review 절차를 적용하며, HTML이나 과거 작업 기록만으로 reviewed provenance를 합성하지 않는다.

### Simple Task Fast Path와 이미지 연속 실행 규칙

작은 요청이 시스템 개선 작업으로 커지지 않도록 아래 요청은 우선 **Simple Task**로 분류한다.

- 대표이미지 한 장 교체
- 문구·오탈자·짧은 문단 한정 수정
- 검증된 링크 목적지 한정 교체
- 기존 사실을 바꾸지 않는 표/목록 정리

Simple Task는 `baseline 확인 → mutation 1회 → readback → 종료`가 전부다. 코드의 단일 classifier가 Fast/Standard, QA 필요 여부와 validation metadata를 한 번 계산하며, SSH adapter와 mutator가 같은 결정을 재사용한다. 문구·중복·기존 사실 재배치는 기존 source와 full review를 재사용하고 changed-block delta review만 수행한다. Simple 작업은 긴 task-state를 만들지 않는다.

**실패 예산:** 같은 방법으로 같은 오류가 연속 두 번 발생하면 그 접근은 중단한다. 세 번째 동일 재시도 대신 다른 transport/provider/도구 경로를 선택한다. 새로운 접근에서도 진전이 없으면 이미 확보한 state·attachment ID·본문 SHA·산출물을 보존하고 blocker를 보고한다. 장시간 sleep, 무한 polling, 같은 명령 반복으로 해결을 기대하지 않는다.

**바이너리 전달:** 이미지·PDF·ZIP 같은 파일은 실제 파일 경로, mount, connector, provider output file, 정식 upload API 중 가능한 경로를 사용한다. Base64 문자열을 터미널 stdout으로 수만 자 출력하거나 stdin에 chunk 단위로 밀어 넣는 방식은 일반 경로로 사용하지 않는다. 파일 handoff가 되지 않으면 동일 Base64 방식을 반복하지 말고 다른 전달 수단이나 생성 provider로 전환한다.

대표이미지 전용 교체의 완료 조건은 아래 순서로 고정한다.

1. 대상 post의 현재 status, 본문 SHA, `_thumbnail_id`를 읽는다.
2. 새 이미지 파일이 실제 CoS/작업공간 경로에 있고 규격·ALT가 준비됐는지 확인한다.
3. `replace-featured-image`를 한 번 실행한다. 이 명령이 현재 본문 SHA와 `_thumbnail_id`를 직접 읽고 image-only CAS 경로에 전달한다.
4. 새 attachment ID를 확보하고 WordPress `_thumbnail_id`가 그 ID인지 readback한다.
5. image-only 작업이면 본문 SHA, title, slug, status, excerpt가 그대로인지 확인한다. 제한 transport가 SEO meta mutation을 허용하지 않으므로 image-only 경로에서 Rank Math meta를 반복 조회하지 않는다.

위 작업에서 본문 source/review pipeline을 다시 열지 않는다. 관련 없는 regression 실패나 다른 파일의 dirty 상태가 image-only mutation을 막지 않는다면 그 문제를 같은 작업에 끼워 넣지 않는다.

**이미지 생성이 포함된 복합 작업:** 사용자가 “이미지를 만들고 업로드”, “대표이미지를 만들고 본문도 수정”, “여러 포스트에 이미지를 적용”처럼 이미지 생성 뒤 후속 작업을 함께 요청한 경우 이미지 생성은 중간 단계다. Prime은 이미지 생성 자체를 완료로 보고 final하지 않는다. 가능하면 이미지 생성은 후속 실행이 가능한 worker/API/provider에 맡기고 Prime은 파일 handoff 뒤 mutation과 검증을 계속한다.

ChatGPT native image generation처럼 도구 특성상 이미지 생성 호출이 현재 turn의 종료점이 되는 경로를 반드시 써야 한다면, 생성 호출 직전에 task-state 또는 `scratch/tasks/<작업명>/`의 안정된 state 파일에 `AFTER_IMAGE` 체크포인트를 남긴다. 최소 필드는 `post_id`, `remaining_steps`, `expected_content_sha256`, `expected_thumbnail_id`, `target_image_path_or_handle`, `completion_requirements`다. 다음 turn에서는 정책·source·본문을 처음부터 다시 조사하지 않고 이 checkpoint와 live WordPress state만 비교해 후속 단계부터 바로 재개한다.

실제 체크포인트는 `checkpoint-after-image`로 기록하고 이미지 생성 뒤 `update-after-image-checkpoint`로 진행 상태를 갱신한다. `complete-task-qa`는 현재 작업의 필수 phase뿐 아니라 같은 본문 SHA에 결합된 `AFTER_IMAGE` 완료 조건도 확인하므로, 업로드·대표이미지 지정·요청된 후속 수정·readback 중 필요한 항목이 남아 있으면 `complete`로 닫히지 않는다.

**Completion Guard:** final 완료 보고 전에 사용자 요청을 단계 목록으로 다시 확인한다. 다음 중 요청에 해당하는 항목이 하나라도 false면 완료가 아니다.

- `image_generated`
- `image_saved_or_handed_off`
- `uploaded`
- `featured_image_set`
- `requested_content_or_meta_edits_done`
- `readback_verified`
- `content_sha_preserved` (image-only 등 본문 불변이 필요한 경우)

이미지 생성만을 명시적으로 요청한 경우에만 `image_generated`와 필요한 파일 전달이 완료 조건의 끝이 될 수 있다.

**묶음 처리:** 같은 글·같은 승인 범위의 문구·중복 제거·기존 사실 재배치는 한 후보 bundle에 모아 한 번 저장한다. Fast 수정은 최초 full review를 trust anchor로 두고 `fast_edit_chain`을 검증하며 최대 5개 delta까지만 이어간다. 새 사실·근거·제목·CTA 또는 chain 단절은 Standard로 올린다.

**행사 일정형 글:** [EVENT_POST_STANDARD.md](EVENT_POST_STANDARD.md)를 적용하는 bundle은 `event_post_standard_version=1`, `multi_event_schedule=true`, 행사별 `event_name` binding을 사용한다. 행사 사실·source·CTA·SEO가 바뀌는 수정은 `standard-event` 검증과 full semantic review를 거치고, 이미지 적합성·화질과 desktop/mobile 배치는 browser/visual QA로 확인한다. 행사 선정·본문 구조·지도·이미지·대표이미지의 편집 규칙은 이 운영 문서에 복제하지 않고 행사 전용 표준을 따른다.

**재사용과 task-state:** 같은 bundle/source/policy/reviewer fingerprint의 current review와 짧은 source receipt는 재사용한다. 예매·판매·신청·재고처럼 상태가 빠르게 변하는 source는 live refresh한다. Standard·복합 이미지·중단 가능 작업만 `task-state`를 사용하고, Simple one-shot은 state machine 없이 CAS/readback으로 끝낸다. media import 결과가 불명확한 경우 attachment checkpoint가 있을 때만 reconcile하며 자동 재import하지 않는다.

```powershell
# reviewed draft/public 공통 수정: 상태와 Fast/Standard를 먼저 자동 판정
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- edit-post scratch/tasks/article/bundle.json `
  --post-id 641 --expected-content-sha256 <현재본문SHA> --confirm-update `
  --edit-intent "표현 정리와 기존 사실의 표 재배치"

# 중단된 같은 작업 재개: task-state fingerprint와 live SHA가 맞아야만 이어감
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- edit-post scratch/tasks/article/bundle.json `
  --post-id 641 --expected-content-sha256 <작업시작본문SHA> --confirm-update --resume `
  --edit-intent "표현 정리와 기존 사실의 표 재배치"

# 대표이미지만 교체: live SHA/thumbnail baseline을 명령이 직접 읽고 image-only CAS 실행
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- replace-featured-image `
  --post-id 641 --image-path scratch/tasks/article/cover.jpg `
  --alt-text "대전 10월 행사 일정 안내" --confirm-update --confirm-image-selection

# ChatGPT native 이미지 생성처럼 turn이 끊길 수 있는 복합 작업: 생성 전에 AFTER_IMAGE 기록
python agent-publisher/editorial_cli.py checkpoint-after-image `
  --post-id 641 --expected-content-sha256 <현재본문SHA> --expected-thumbnail-id <현재이미지ID> `
  --image-handle "chatgpt-native:pending" `
  --remaining-step "새 이미지 업로드" --remaining-step "대표이미지 지정" --remaining-step "본문 수정" `
  --completion-requirement image_generated --completion-requirement image_saved_or_handed_off `
  --completion-requirement uploaded --completion-requirement featured_image_set `
  --completion-requirement requested_content_or_meta_edits_done --completion-requirement readback_verified

# 실제 브라우저 QA가 끝난 뒤 로컬 task-state 종료
python agent-publisher/editorial_cli.py complete-task-qa `
  --post-id 641 --expected-content-sha256 <저장후본문SHA> `
  --qa-scope content-mobile-desktop
```

`replace-featured-image`의 media import는 응답 유실 시 중복 attachment를 만들 수 있어 SSH 255 자동 재시도를 하지 않는다. import 시작 직후 결과가 불명확해 attachment ID를 확보하지 못한 상태는 `featured_image_import_outcome_ambiguous`로 차단하고 자동 재import하지 않는다. attachment ID가 checkpoint에 남아 있으면 다음 실행은 새 import 대신 해당 attachment를 reconcile한다. 동일 이미지+ALT의 안전한 실패는 최대 2회까지만 허용한다. `edit-post --resume`은 live 본문 SHA가 작업 시작 SHA 또는 저장 예정 SHA 중 하나일 때만 이어가며 제3의 SHA가 관측되면 동시 변경으로 차단한다.

**Standard P1/P2 preflight와 mutation:** `edit-post`가 선택한 draft Standard route와 public Standard route는 inventory sync, 대상 글의 초기 baseline read, 공식 source 동일성 recheck처럼 서로 독립적인 읽기 작업을 병렬화한다. P2부터 저장 직전 CAS → `wp_update_post()` → 저장 후 readback은 고정된 server-side guarded mutation 한 번으로 합친다. reviewed HTML은 JSON stdin으로 전달하며 임의 PHP/명령은 허용하지 않는다. guarded protocol은 status/title/slug/excerpt/content SHA의 전체 expected state를 확인하고, 저장 후 전체 desired state를 다시 검증한다. 따라서 Fast draft의 기본 target 왕복은 `get + guarded mutation` 2회, Standard draft는 경량 inventory + 초기 target read + guarded mutation의 약 3회 수준이 된다. SSH 255에서 guarded request는 desired-state 일치 검사를 전제로 최대 1회만 replay하며, raw `post update`와 media import는 이 재시도 의미론을 공유하지 않는다.

**신규 draft Fast 경로:** `prepare-draft`는 별도 안전장치를 없애는 명령이 아니라 기존 단계의 중복 왕복을 합친 명령이다. 구조화 원고가 완성된 뒤 먼저 WordPress inventory 없이 content/source 결정론 검사를 수행한다. 수동 ChatGPT/CoS 경로에서 대표이미지 생성은 Gemini를 호출하지 않으며, 아직 후보를 고르지 않았다면 image 없이 draft를 저장할 수 있다. current review가 bundle에 이미 결합돼 있으면 reviewer를 다시 호출하지 않는다. 이후 Publisher 잠금 안에서 최신 WordPress lightweight inventory를 한 번 조회하고 site 중복·related post·review binding을 포함한 기존 full `validate_bundle()`을 실행한 뒤에만 draft를 만든다. 따라서 별도의 `check`를 다시 실행하는 것은 실패 원인 진단이 필요한 경우에만 한다. Gemini 커버 생성은 `main.py`의 scheduler context에서만 허용된다.

ChatGPT/CoS 로컬 환경에서는 본문 검토가 끝난 시점에 먼저 draft를 저장할 수 있다. 이미지까지 함께 적용할 때에는 이미 사용자에게 보여 주고 선택된 1200×675 jpg/jpeg/png/webp 파일과 ALT, `--confirm-image-selection`을 전달한다. 수동 작성에서 Gemini 자동 생성을 켜는 fallback은 없다.

```powershell
# 이미지 선택 전: reviewed draft만 저장
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- prepare-draft scratch/tasks/article/bundle.json --author-model "GPT-5.6 Sol" --output scratch/tasks/article/receipt.json

# 사용자가 후보를 선택한 경우: 선택 이미지까지 적용하고 공개용 attestation 생성
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- prepare-draft scratch/tasks/article/bundle.json --author-model "GPT-5.6 Sol" --image-path scratch/tasks/article/cover.jpg --alt-text "대표 이미지 설명" --confirm-image-selection --output scratch/tasks/article/receipt.json
```

**Publication gate:** 대표이미지 mutation 자체의 완료 기록은 공개 승인 증거가 아니다. 수동 경로는 `--confirm-image-selection`, 스케줄러는 실제 자동 비전 검수 PASS evidence가 있어야 `_bloguito_publish_gate_v1` attestation을 기록한다. attestation은 reviewed content/title, thumbnail attachment, 파일 SHA, ALT SHA, review digest, freshness deadline을 묶는다. WordPress MU plugin은 목록/미리보기 버튼뿐 아니라 모든 비공개→공개 상태전환을 같은 값으로 검사하고 성공 공개 시 attestation을 소비한다. attestation이 없는 legacy draft는 자동 backfill하지 않으며 현행 review/image 절차를 거쳐야 한다.

이 SSH adapter 경로는 draft 저장 성공 뒤 `scripts/sync_post_catalog.py`를 최대 2회까지 읽기 전용으로 시도한다. 카탈로그 동기화가 두 번 모두 실패한 경우 draft 저장 성공을 실패로 되돌리지 않는다. 이때는 출력된 post ID를 보존하고 `python scripts/sync_post_catalog.py`만 재실행한다. `prepare-draft` 자체를 재실행하면 새 draft가 중복 생성될 수 있으므로 금지한다.

**로컬 카탈로그와 주제 백로그:** 새 글 주제 탐색은 `docs/POST_CATALOG.md`에서 시작한다. 이 문서는 빠른 1차 중복 확인과 현재 포트폴리오·주제 백로그 파악용이며, 실제 저장 직전 안전 검사를 대체하지 않는다. 신규 draft 생성, 공개 전환, 제목·카테고리·Rank Math 포커스 키워드/점수처럼 카탈로그에 표시되는 정보 변경이 성공적으로 끝난 뒤 `python scripts/sync_post_catalog.py`를 한 번 실행한다. 동기화 스크립트는 기존 `POST_CATALOG.md`의 사람이 검토한 백로그 행을 보존하고, 현재 공개·임시·예약·비공개 글의 제목 또는 포커스 키워드와 겹치는 후보를 제거한 뒤 우선순위를 다시 매긴다. 백로그를 보충할 때에는 주제 탐색 단계에서 공식 출처와 유효기간을 확인한 새 후보만 추가한다.

WordPress UI에서 reviewed draft의 status만 직접 `publish` 또는 다시 `draft`로 바꾼 경우 카탈로그 동기화는 로컬 reviewed index의 상태도 함께 점검한다. live 제목과 본문 SHA가 저장 editorial bundle의 제목·renderer SHA와 **모두 정확히 일치할 때만** `draft_posts.json`과 `published_posts.json` 사이에서 해당 reviewed record를 이동한다. live 본문/제목이 조금이라도 다르거나 양쪽 index에 동시에 존재하는 등 provenance가 모호하면 자동 채택하지 않고 경고만 남긴다. 이 보정은 로컬 reviewed state만 다루며 WordPress 글 자체를 수정하지 않는다.

known historical renderer도 fuzzy 비교가 아니라 byte-for-byte provenance로만 인정한다. `agent-publisher/data/renderer_provenance.json`의 항목은 post ID, 현재 reviewed renderer SHA, historical live SHA, renderer revision을 함께 묶는다. 현재 bundle의 renderer SHA가 registry의 current SHA와 정확히 일치할 때만 historical SHA를 같은 reviewed provenance로 사용할 수 있다. HTML/text 유사도나 DOM 유사도는 승인 근거로 사용하지 않는다.

renderer와 별개로, 과거 Standard/full-review 저장 트랜잭션이 저장 bundle의 semantic review digest와 실제 저장 SHA를 이미 정확히 결합한 경우에는 `agent-publisher/data/reviewed_content_provenance.json`에 그 결합을 명시적으로 보존할 수 있다. registry 적용 전에 현재 bundle의 review digest/checks/issues를 다시 검증하며, bundle 전체 digest까지 registry와 일치해야 한다. full-review 직후 본문에서 CAS로 이미지 URL만 1:1 교체한 경우도 review task-state, pre/post SHA, before snapshot, mutation payload/script, 업로드 receipts, old/new URL과 각 asset SHA가 모두 남아 있을 때만 같은 registry의 별도 `post-review-image-url-substitution` lineage로 기록한다. 이미지 변환 필드는 deterministic transformation digest로 다시 묶는다. 가능하면 당시 **reviewed public HTML exact bytes만** `data/provenance_attestations/`에 immutable attestation으로 보존하고, installer/registry validator가 `SHA(attestation)==reviewed_content_sha` 및 선언된 old→new URL 치환을 실제로 재실행해 `SHA(transformed)==live_content_sha`를 독립 검증한다. 이 attestation은 scratch task-state·payload·script·receipt 원본을 release에 복제하지 않으며, 해당 원본이 사라진 뒤에는 registry에 기록된 그 artifact hash 자체의 원본성까지 새로 증명할 수는 없다. 따라서 같은 digest를 별도 ledger에 한 번 더 저장하는 방식은 독립 검증으로 간주하지 않는다. exact reviewed bytes가 별도 신뢰 가능한 artifact에서 확인되지 않는 lineage에는 live HTML에서 attestation을 역합성하지 않는다. 이 registry는 fuzzy 비교나 live HTML 역추론을 허용하지 않는다. 이 provenance는 reviewed index/status와 catalog binding에만 사용할 수 있고 historical renderer 출력으로 간주하거나 renderer migration을 승인하는 근거로 사용하지 않는다.

historical renderer migration은 candidate bundle이 저장 reviewed bundle과 동일하고 live 본문 SHA가 위 provenance에 정확히 결합될 때만 실행한다. 이 경로는 source나 semantic review를 새로 승인하지 않으며 WordPress `post_content`만 current renderer 출력으로 CAS/backup/readback한다. 제목, slug, excerpt, status, 사실, source, CTA, SEO metadata는 보존한다. current renderer와 reader/metadata 내용이 동일한 no-op migration의 validation profile은 source `not-applicable`, semantic review `none`이다.

카탈로그 동기화는 live 제목과 본문이 exact reviewed provenance로 결합된 경우 outer reviewed record의 `title`, `url`, `category_id`, `category_name` 같은 기술 metadata를 현재 WordPress 값으로 정리할 수 있다. 이 보정은 editorial bundle 내부의 brief, source, review digest, 사실을 수정하지 않는다. same-status 글이 exact provenance를 만족하지 않으면 자동 metadata 채택이나 새로운 경고를 만들지 않는다.

운영 editorial release는 `python scripts/build_editorial_release.py <새 출력폴더> --archive`로 매번 현재 HEAD에서 새로 만든다. 이전 scratch release의 파일 inventory를 복사해 재사용하지 않는다. manifest의 `revision`은 반드시 builder를 실행한 checkout의 HEAD와 같아야 하며, 다른 revision을 배포하려면 그 revision을 별도 worktree에 checkout한 뒤 그 worktree에서 빌드한다. canonical builder는 전체 `agent-publisher/agents/*.py`, top-level runtime Python, 정책·growth·cluster·renderer/reviewed provenance, 독립 검증 가능한 reviewed-content attestation, critical fact·policy exception JSON과 4개 정책 문서를 포함하고 tests, `.env`, example/private runtime data는 제외한다. provenance attestation은 `data/provenance_attestations/*.html`만 허용하며 scratch/task-state/private artifact를 release inventory에 넣지 않는다. installer는 `editorial.py`, `public_fast_edit.py`, `publish_gate.py`, `validation_router.py`, `wordpress_mutation.py`, `renderer_provenance.json` 등 핵심 runtime 파일이 빠진 manifest를 설치 전에 거부한다.

**검색 성장 Opportunity Queue:** `python scripts/build_growth_queue.py`는 `agent-publisher/data/analytics/`의 최신 GSC/GA4 JSON과 비공개 `catalog_inventory.json`을 읽어 `agent-publisher/data/growth/latest-opportunities.json`을 생성한다. 이 결과는 WordPress를 수정하지 않는 private triage 자료다. GSC page URL은 WordPress가 반환한 실제 permalink와 post ID alias에만 결합하며 매칭되지 않는 legacy/alternate URL은 별도로 남겨 추정 연결하지 않는다. GA4 page 수치는 채널 전체 값이므로 organic traffic으로 취급하지 않는다. 표본이 작은 페이지는 `low` confidence로 남기며 이 분류 자체가 검색 순위 예측이나 자동 수정 승인으로 사용되지는 않는다.

정규 scheduler는 최신 analytics가 도착한 뒤 구형 derived input을 계속 소비하지 않는다. `main.py`의 scheduled planner 진입점은 **가장 최신 이름의 analytics snapshot 하나를 먼저 선택한 뒤 canonical receiver 계약으로 그 파일 자체를 검증**한다. 최신 파일이 malformed/stale이면 이전 파일로 후퇴하지 않고 `no_action`으로 fail closed한다. 검증된 snapshot을 사용할 때는 현재 WordPress post 목록을 매 실행 **읽기 전용**으로 다시 조회해 Opportunity를 재계산하므로, 이전 Opportunity body가 손상됐거나 live catalog가 바뀐 상태를 재사용하지 않는다. exact reviewed title/content SHA/category를 만족하는 저장 bundle만 기존 글 개선 후보의 reviewed provenance로 인정하며, draft/publish index status drift는 관측 정보로 남기되 그 자체만으로 exact review를 무효화하지 않는다. Topic score도 매 실행일 다시 계산해 evidence age를 갱신하고, Opportunity payload digest·analytics period·shared `refresh_id`가 일치하지 않으면 `no_action`으로 fail closed한다. 이 JIT 갱신은 공개 글을 수정하지 않고 Naver DataLab을 자동 호출하지 않으며, 수동 editorial CLI의 growth gate 비적용 계약도 바꾸지 않는다.

**P2 신규 주제 demand gate:** 자동 스케줄러에 넣을 신규 아이디어는 tracked `search_briefs.json`에 먼저 추가하지 않는다. `agent-publisher/data/topic_candidates.example.json`을 형식 참고용으로만 사용하고 실제 후보와 측정값은 Git 비추적 `agent-publisher/data/growth/topic_candidates.json`에 둔다. `demand_evidence`에는 실제로 조회한 `keyword_planner`, `google_trends`, `naver_datalab` 값만 `measured: true`로 기록한다. Search Console 연관성은 후보가 명시한 `gsc_terms`와 P1의 실제 query 행이 문자 단위로 맞는 경우만 계산하며 의미 유사도를 추정하지 않는다.

**P9 외부 measured-demand 수집:** `python scripts/collect_topic_demand.py`는 이미 사람이 검토해 `topic_candidates.json`에 넣은 후보만 보강한다. 후보 주제나 category/value metadata를 자동 생성하지 않는다. 기본 provider는 NAVER API HUB의 공식 Naver DataLab 검색어 트렌드 API이며, `NAVER_API_HUB_CLIENT_ID`와 `NAVER_API_HUB_CLIENT_SECRET`이 필요하다. collector는 기본 애플리케이션 환경과 동일하게 Git 비추적 `agent-publisher/.env`를 먼저 읽으며, `https://naverapihub.apigw.ntruss.com/search-trend/v1/search`에 `X-NCP-APIGW-API-KEY-ID`/`X-NCP-APIGW-API-KEY` 헤더로 요청한다. 이전 로컬 설정과의 호환을 위해 `NAVER_DATALAB_CLIENT_ID`/`NAVER_DATALAB_CLIENT_SECRET`도 fallback으로 읽지만 새 설정은 API HUB 이름을 사용한다. 기본값에서는 최신 P1 `top_queries_global`과 후보의 `gsc_terms`가 문자 정규화 기준으로 실제 매칭된 후보만 측정한다. 외부 API로 먼저 새 아이디어를 확장하지 않고 Google이 이미 사이트와 관련 있다고 본 query를 우선하는 경계다. `--include-unseeded`는 운영자가 별도로 검토한 후보를 의도적으로 측정할 때만 사용한다.

Naver DataLab의 `ratio`는 **절대 검색량이 아니라 조회 묶음/기간 안의 상대 검색 추이**다. collector는 최근 90일의 완료된 날짜(기본 주간)를 조회해 반환된 ratio의 기간 평균을 `source=naver_datalab`, `metric=relative_interest`로만 기록하고, 기간/검색어/aggregation을 함께 보존한다. API HUB가 `week`/`month` 구간 경계에 맞춰 시작·종료일을 넓혀 반환할 수 있으므로 collector는 time unit별 제한된 boundary expansion만 허용하고 `requested_period_*`와 실제 provider `period_*`를 둘 다 기록한다. 응답에 data point가 없으면 `0`으로 추정하지 않고 evidence를 쓰지 않는다. P2도 source별 metric을 고정해 Keyword Planner만 `avg_monthly_searches`, Google Trends와 Naver DataLab은 `relative_interest`만 허용한다. Google Trends API는 alpha 접근, Google Ads Keyword Planner는 별도 Ads developer token/OAuth/customer ID가 필요한 동안 추정치나 비공식 값을 대신 넣지 않는다.

duplicate/source 검토에서 기존 글이 같은 검색 의도를 이미 해결한다고 확인된 private candidate는 삭제해 측정 이력을 잃지 않고 `review_disposition="duplicate_existing"`, `duplicate_post_id`, `reviewed_at`을 기록한다. 이 candidate는 이후 DataLab 재측정에서 제외되며 P2 score에는 기존 measured evidence와 점수를 남기되 `duplicate_existing_post` reason으로 `eligible_for_automation=false`가 된다. 따라서 P3가 같은 후보를 반복해서 `new_draft`로 고르지 않는다. 신규 brief 승격 여부가 아직 검토 전인 candidate는 필드를 생략하거나 `review_disposition="active"`로 둔다.

```powershell
# 자격증명이 있고 GSC-seeded reviewed candidate가 있을 때만 실제 측정
python scripts/collect_topic_demand.py

# API 응답과 검증까지만 수행하고 private candidate 파일은 변경하지 않음
python scripts/collect_topic_demand.py --dry-run
```

```powershell
# P1 queue를 최신화한 뒤, 최초 private candidate 파일만 빈 문서로 초기화할 때
python scripts/score_topic_candidates.py --init-empty

# topic_candidates.json에 실제 측정 evidence를 기록한 뒤 재점수화
python scripts/score_topic_candidates.py
```

결과는 Git 비추적 `agent-publisher/data/growth/topic-candidate-scores.json`이다. 기본 gate는 100점 중 70점 이상, `medium` 이상 confidence, 최근 측정 demand evidence 존재, 최소 30일 useful lifetime, 명시적 added value를 요구한다. 이 값은 `growth_policy.json`의 운영 heuristic이며 검색 순위·유입·수익 예측값이 아니다. `RadarAgent`가 호출하는 scheduled discovery만 이 score report를 필수로 요구한다. 사용자가 직접 지시한 수동 집필과 기존 editorial CLI는 growth score가 없다는 이유만으로 차단하지 않는다. score가 통과해도 기존 duplicate/source/lifecycle/semantic review/draft-only 계약은 모두 별도로 통과해야 한다.

**Reviewed brief narrow merge:** 자동 후보가 실제 duplicate/source/lifecycle 검토까지 통과해 `search_briefs.json` 승격 대상이 된 경우 운영 파일 전체를 release로 교체하지 않는다. `agent-publisher/merge_search_brief.py`는 한 번에 reviewed brief ID 하나만 다루며 기본은 dry-run이다. `--confirm-merge`에서 target의 pre-SHA를 다시 확인하고, 기존 bytes를 `agent-publisher/backups/search-briefs-<UTC>/`에 보존한 뒤 같은 디렉터리 임시 파일을 `os.replace()`로 교체한다. readback에서는 target ID와 비대상 `ID → row` mapping이 그대로인지 확인하고 실패 시 원본 bytes로 rollback한다. 기존 ID를 다른 내용으로 바꾸려면 `--replace-existing`을 별도로 지정해야 하며 동일 row 재적용은 no-op다. loader도 malformed/중복 brief ID storage를 fail-closed한다. 운영 `scripts/install_editorial_release.py`의 기존 `data/search_briefs.json` skip 계약은 그대로 유지한다.

```bash
# 먼저 dry-run. production target을 수정하지 않는다.
python /home/ubuntu/agent-publisher/merge_search_brief.py /path/to/reviewed-brief.json \
  --expected-sha256 <현재-search_briefs-sha256>

# 검토된 동일 payload만 명시적으로 narrow merge
python /home/ubuntu/agent-publisher/merge_search_brief.py /path/to/reviewed-brief.json \
  --expected-sha256 <현재-search_briefs-sha256> --confirm-merge
```

**P3 Daily Growth Planner:** 정규 자동 작성은 P1/P2 결과를 바로 소비하지 않고 하루 작업 1개를 먼저 결정한다. `python scripts/build_daily_growth_plan.py`는 private `latest-opportunities.json`과 `topic-candidate-scores.json`을 읽어 `daily-growth-plan.json`을 만든다. 결정은 `existing_improvement`, `new_draft`, `no_action` 중 하나다. P3의 초기 기본값은 actionable 기존 글 개선 우선이었고, 현재는 아래 P5 work-mix 정책이 existing/new가 동시에 eligible인 경우의 최종 우선순위를 결정한다. existing을 선택한 경우 공개 글은 자동 수정하지 않고 해당 run의 신규 draft를 보류하며 운영 요약에 post ID를 남긴다. `new_draft`를 선택한 경우 P2에서 `eligible_for_automation=true`인 최고점 brief 하나만 Radar에 전달한다. stale/malformed/private state 누락은 `no_action`으로 fail closed하며 WordPress inventory refresh도 실행하지 않는다.

```powershell
python scripts/build_daily_growth_plan.py
```

정규 `main.py`도 같은 planner 계약을 사용한다. `new_draft`일 때만 WordPress inventory를 갱신하고 Curator/Writer/Designer/Publisher를 생성하며, planner가 선택한 `brief_id` 하나만 scheduled Radar가 소비한다. `existing_improvement` 또는 `no_action`은 정상 성공 결과이며 "오늘 글을 쓰지 않음" 자체가 오류로 처리되지 않는다. 수동 ChatGPT/CoS 집필과 `editorial_cli.py`는 이 scheduled planner의 자동 작성 차단 대상이 아니다.

**P4 Growth Work Log:** planner가 기존 글을 추천했다는 사실만으로 완료 처리하지 않는다. 실제 `edit-post` 작업과 CAS/readback 검증이 끝난 뒤에만 `record_growth_work.py complete-existing`으로 private `growth-work-log.json`에 완료 기록을 남긴다. 기록은 **완료 당일** planner의 `post_id`, planner policy digest, 해당 Opportunity report 종료일에 결합되므로 다른 글, 전날 plan, 정책 변경 후의 오래된 plan으로 완료를 기록하지 못한다.

```powershell
# 예: planner가 Post #345를 기존 글 개선 대상으로 선택했고 실제 edit-post/readback까지 끝난 뒤
python scripts/record_growth_work.py complete-existing --post-id 345 `
  --note "edit-post 저장 및 readback 검증 완료"

# 완료 기록을 반영해 다음 일일 결정을 다시 확인
python scripts/build_daily_growth_plan.py
```

기본 `existing_recheck_days`는 14일이다. 완료된 post는 **완료일에서 14일 뒤까지의 데이터가 포함된 새 Opportunity report**가 나오기 전에는 같은 과거 GSC 신호로 다시 `existing_improvement`에 올라오지 않는다. `as_of` 날짜만 14일이 지났다고 재활성화하지 않으며, Search Console 관측기간 종료일이 실제 recheck 날짜에 도달해야 한다. 따라서 수정 직후의 옛 28일 표본이 같은 글을 매일 반복 차단하는 일을 피하면서도, 충분한 새 데이터가 쌓였는데 동일 문제가 지속되면 다시 개선 후보가 될 수 있다. work log가 없으면 빈 기록으로 보수적으로 시작하고, 파일이 존재하지만 스키마가 깨졌다면 planner는 `no_action`으로 fail closed한다.

**P5 Work Mix / Rotation:** 같은 private `growth-work-log.json`은 scheduler가 실제 WordPress draft를 생성한 `new_draft` 완료도 기록한다. 신규 draft는 저장 성공 후 `main.py`가 자동으로 `brief_id`, post ID, 완료일을 기록하며, 한 번 성공한 `brief_id`는 같은 P2 score report에 남아 있어도 다시 선택하지 않는다. 기록 실패는 이미 생성된 WordPress draft를 실패로 되돌리거나 재생성하지 않고 `growth_log_errors`로 별도 보고한다.

기존 글 개선과 신규 draft가 **둘 다 eligible**일 때만 최근 `work_mix_lookback_actions`(기본 8개) 완료 이력을 보고 다음 작업을 선택한다. 목표 existing 비율은 `target_existing_ratio=0.5`다. 다음 action 하나를 추가했을 때 50:50에 더 가까워지는 쪽을 고르고, 수학적으로 동률이면 직전 완료 action의 반대쪽으로 회전한다. 이력이 전혀 없을 때만 `prefer_existing_improvement=true`가 tie-breaker다. 이 비율은 quota가 아니므로 P2를 통과한 신규 후보가 없으면 비율을 맞추기 위해 새 글을 만들지 않고, actionable existing 후보가 없으면 불필요한 기존 글 수정도 만들지 않는다.

**P6 Content Cluster / Internal Links:** 추적 파일 `agent-publisher/data/content_clusters.json`은 사람이 검토한 cluster ID와 post ID 목록만 보존한다. 자동 writer brief에 `cluster_id`가 있으면 현재 WordPress inventory에서 **실제로 공개 상태인** 같은 cluster 글을 순서대로 최대 2개 골라 기존 `plan.related_posts` 형식(`https://lifeinfo24.org/?p=ID`)으로 결합한 뒤 semantic review를 수행한다. 모델이 cluster 밖의 내부 링크를 임의로 만든 경우에는 이 deterministic 후보로 대체된다. `cluster_id`가 없는 기존 brief/bundle은 영향을 받지 않는다.

`python scripts/build_content_cluster_report.py`는 canonical `wordpress_inventory.json`의 `content_urls`를 우선 사용하는 read-only 점검이다. canonical snapshot이 없을 때는 최신 catalog sync가 만든 `catalog_inventory.json`을 fallback으로 사용할 수 있지만, 이 fallback은 모든 row에 `content_urls`가 있는 URL-complete snapshot일 때만 허용된다. 명시적으로 `--inventory`를 지정한 경우에는 다른 inventory로 자동 대체하지 않는다. cluster 구성원이면서 명시적 `?p=ID` incoming link가 0이고 같은 cluster로 나가는 명시적 링크도 0인 공개 글만 `orphan_candidate=true`로 추천한다. URL state가 없거나 불완전한 fallback은 fail closed하며 orphan으로 추정하지 않는다. 이 보고서는 기존 공개글을 자동 수정하거나 hub page를 자동 생성하지 않는다.

**P7 Value-first / AI-answerability:** scheduler가 소비할 reviewed brief에는 `intent_type`, `ai_answerability`, `added_value`를 명시한다. `intent_type`은 `guide`, `lookup`, `application`, `calculator`, `comparison`, `decision`, `troubleshooting` 중 하나다. `ai_answerability`는 `low/medium/high`, `added_value`는 P2와 같은 허용값(`calculator`, `decision_support`, `comparison`, `official_action`, `troubleshooting`, `multi_source_synthesis`, `lookup`)만 사용한다.

scheduled `load_briefs(..., require_growth_gate=True)`는 P2 score gate를 통과한 뒤 이 metadata도 검증한다. 특히 `ai_answerability=high`인데 `added_value=[]`이면 `high_ai_answerability_without_added_value`로 자동 작성을 보류한다. metadata 자체가 빠졌거나 허용되지 않은 값이면 scheduler에서 fail closed한다. 반대로 사용자가 ChatGPT/CoS에서 직접 지시한 글과 일반 editorial CLI/manual `load_briefs()`에는 이 value gate를 적용하지 않는다. P7은 기존 semantic-review checks/signature를 늘리지 않고 **brief 선택 단계**에서만 동작한다.

**P8 Interactive Reader Tool Pilot:** `plan.reader_tools`는 모델이 임의 HTML/JavaScript를 넘기는 통로가 아니다. 현재 allowlist는 `kind=minimum_wage_monthly`, `formula_version=moel_weekly_holiday_v1` 한 종류뿐이며 `agents/reader_tools.py`가 고정 HTML/JS 템플릿을 렌더한다. 입력은 시급, 주 소정근로시간(0~40시간), 주휴 적용 여부이고 출력은 세전 단순 월 환산 예상액이다. 주휴를 적용하더라도 주 15시간 미만이면 주휴시간을 0으로 처리하며, 40시간/주휴 8시간은 월 환산 209시간이 되도록 공식 안내와 같은 환산 경계를 사용한다.

Reader tool은 `intent_type=calculator`, `added_value`에 `calculator` 포함, brief entity/primary keyword에 `최저임금`이 있는 경우에만 허용한다. 계산식 evidence는 **official source**의 실제 인용문과 exact binding되어야 한다. tool당 임의 `script`, 다른 formula version, 40시간 초과 기본값, 비공식/불일치 evidence는 `invalid_reader_tools` 또는 `reader_tool_outside_brief_scope`로 보류한다. renderer는 native number/checkbox input, `aria-live`, responsive grid, `<noscript>` 안내를 제공하며 연장/야간/휴일 가산수당·세금/공제는 계산하지 않는다고 명시한다. 실제 최저임금 글을 자동 생성하는 것은 P2 측정 수요 gate를 별도로 통과해야 하며, P8 기능 추가 자체가 신규 글 생성 승인이 아니다.

최종 보고는 대상 글·변경 내용·임시글/공개 상태·source refresh/reuse·semantic review 범위·WP CAS/readback·필요한 browser QA만 짧게 전달한다. 공유 코드를 실제로 바꿔 테스트를 실행한 경우에만 표적/full regression 결과를 추가한다. 콘텐츠 한 건의 결과 보고에 저장소 전체 테스트 수를 붙이지 않는다.

1. 게시물 상태(공개·임시·예약·비공개)와 출처를 조회하고, 중복·검토 만료·정책 적용 연도를 검증한다.
2. 공식 근거를 가져와 구조화 `brief`/`sources`/`plan`을 만들고 별도 의미 검토와 코드 검사를 거친다. 행동 버튼은 실제 조회·신청·예약·구매·설치 목적지를 확인한 `sources[].actions`만 사용한다.
3. 일반 신규 draft는 `prepare-draft`, reviewed 기존 글은 `edit-post`, 대표이미지 전용은 `replace-featured-image`를 사용한다. Fast 경로는 `--edit-intent` 범위 안에서 기존 사실만 다루며 새 숫자·날짜·지역·근거·CTA·제목·고위험 상태 주장은 Standard 전체 검토로 전환한다.
4. **공개 전환은 사람의 글별 확인 후** `promote-draft <ID> --confirm-publish`만 사용한다. 명령어가 있어도 현재 공식 원문/원고 해시 및 검토가 불일치하면 차단된다. 보류한 글을 위해 WP-CLI 직접 편집이나 임시 PHP로 검사를 우회하지 않는다.

`scripts/prepare_post_approval.py`는 아직 변경안 자체를 승인받아야 하는 경우에만 사용한다. 이미 승인된 변경안은 `edit-post`의 현재 inventory/source/CAS/backup/readback 경로로 바로 적용한다.

승인 비교 패키지와 일반 one-off 산출물의 기본 위치는 `scratch/tasks/<작업명>/`이다. 같은 작업의 retry는 새 timestamp 디렉터리를 계속 추가하지 않고 동일 workspace의 안정된 파일명을 재사용한다. 새 disposable 작업은 `scripts/task_workspace.py`로 ownership manifest를 만든다. 관리형 workspace의 기본 TTL은 완료 72시간, 실패/재개 대기 168시간이며 `active`, `preserved`, manifest가 없거나 손상된 기존 workspace는 자동 삭제하지 않는다. 승인 비교 패키지처럼 사람이 검토·승인에 사용할 증거는 필요 기간 동안 `preserved`로 취급한다. 브라우저 QA는 가능한 한 이미 열린 세션을 재사용한다. 독립 user-data-dir가 필요한 경우 repo 밖 OS temp에 만들고 한 QA batch에서 재사용한 뒤 성공 시 즉시 삭제하며, 최종 screenshot/결과 JSON만 task workspace에 남긴다. 과거 `tmp/`에는 문서에서 참조하는 legacy 증거가 있으므로 전체 자동 삭제하지 않고 `scripts/cleanup_workspaces.py`의 보수적 profile/생성물/명시적 관리형 workspace 정리만 사용한다.

### 작성 모델 경로

- **서버 예약/자동 실행:** `main.py`가 `EditorialWriterAgent(writing_enabled=True)`를 사용한다. `editorial_policy.json`의 `writer_model` 및 `EDITORIAL_WRITER_MODEL`은 이 자동 작성 경로의 Gemini 모델 선택에 사용한다.
- **ChatGPT에서 사용자가 직접 집필을 요청한 경우:** 현재 ChatGPT 모델이 `sources` 이후의 구조화 `plan`을 작성한다. 별도 OpenAI API 호출은 필요하지 않는다. 완성한 bundle은 `manual-review`로 넘기며, 이 경로의 모델 어댑터는 `writing_enabled=False`라 Gemini 작성기가 원고를 다시 생성할 수 없다.
- 직접 작성 예: `python agent-publisher/editorial_cli.py manual-review bundle.json --author-model "GPT-5.6 Sol" --inventory inventory.json --output report.json`. 이후 필요하면 `check`로 결정론 검사를 확인하고 실제 draft 저장은 `scripts/editorial_cli_via_ssh.py ... -- prepare-draft bundle.json`을 사용한다. bundle에 current 독립 의미 검토가 결합돼 있으면 재사용하고, Publisher 잠금 안에서 최신 WordPress inventory와 policy/content/review 결합을 다시 확인한 뒤 draft만 만든다. 원고·정책·검토 신선도가 달라졌다면 저장이 차단되며 먼저 `manual-review`/`review`를 다시 수행한다.
- `manual-review`의 `--author-model`은 실제 대화에서 사용한 모델명을 기록하기 위한 필수 값이다. 이 값은 게시물의 `used_model` 메타데이터로 이어져 자동 Gemini 작성물과 직접 GPT 작성물을 구분한다.

한 세션에서 `EDITORIAL_SYSTEM.md`와 `editorial_policy.json`을 이미 읽었고 두 파일이 변경되지 않았다면 같은 작업자가 후속 문구·표·링크 수정 때 전체 문서를 다시 읽지 않는다. 새 worker는 자신의 최초 콘텐츠 작업에서 읽는다. 공통 정책 파일을 바꾼 작업과 콘텐츠 적용은 분리하고, 동시 작업이 공통 파일을 수정할 가능성이 있으면 전용 worktree에서 정책/코드를 먼저 안정화한 뒤 그 버전으로 review를 수행한다.

### 로컬 편집 코드 + 원격 WordPress 실행

운영 서버의 `editorial.py`, `editorial_cli.py`, 정책 문서를 매 작업마다 복사·교체한 뒤 서버에서 다시 review하는 방식을 기본 경로로 사용하지 않는다. 현재 로컬 checkout을 편집 코드의 정본으로 사용하고, 실제 WordPress 명령만 제한된 SSH transport로 전달한다.

- 신규 draft와 reviewed draft/public 수정, 대표이미지 교체는 모두 `scripts/editorial_cli_via_ssh.py`를 정규 원격 adapter로 사용한다. 정상 콘텐츠 mutation은 `prepare-draft` / `edit-post` / `replace-featured-image` 세 경로만 선택하며 P12 이후 과거 wrapper/action은 공개 CLI 표면에서 제거됐다.
- reviewed manifest가 없는 레거시 **공개글**은 `brief.existing_post_id`가 요청 `--post-id`와 정확히 일치하는 full-reviewed bundle에 한해서만 `edit-post` Standard 경로로 1회 편입한다. 이 경우 Fast/delta review는 금지하고 현재 공개 상태·본문 SHA CAS, full source/site/semantic validation, 원문 backup, guarded mutation/readback을 모두 통과한 뒤에만 `published_posts.json`/per-post manifest에 reviewed provenance를 새로 기록한다. ID 불일치, draft 상태, stale SHA, review/source 검증 실패는 manifest 생성과 WordPress mutation 전에 차단한다.
- 기존 글의 본문·제목·excerpt·status, category, Rank Math reviewed meta, 대표이미지 연결은 `wp post update` 같은 pre-read→write 우회로 저장하지 않는다. 정규 helper는 `docker exec -i`로 JSON payload를 전달하고 WordPress DB transaction 안에서 대상 post row(필요하면 taxonomy/postmeta row도)를 `FOR UPDATE`로 잠근 뒤 expected status/title/slug/excerpt/content SHA 및 해당 metadata baseline을 검사한다. mutation 뒤 같은 transaction에서 readback 검증이 통과해야 commit한다. featured-image 교체는 attachment import 자체는 비재시도 단계로 먼저 수행하되 기존 글의 `_thumbnail_id` 변경은 별도 guarded thumbnail CAS로만 수행하며, 경쟁 변경이 있으면 새 attachment가 orphan으로 남을 수는 있어도 기존 글이나 대표이미지를 덮지 않는다.
- 공개 전환 `promote-draft`와 복구·진단 action은 별도 lifecycle/maintenance 명령이다. Direct SSH가 기본이며 Tailscale은 실제 비상·복구 작업에서만 명시적으로 선택한다.
- 수동 편집 transport의 기본 모드는 항상 `direct`다. `BLOGUITO_SSH_HOST`, `BLOGUITO_SSH_USER`는 Direct SSH의 기본 접속값으로 사용할 수 있지만, `BLOGUITO_SSH_MODE=tailscale` 같은 지속 환경설정이 일반 작업을 Tailscale로 자동 전환하게 두지 않는다. WSL/Tailscale은 명령행 `--ssh-mode wsl|tailscale`로만 명시적으로 선택한다.
- Direct SSH가 실패해도 공개 웹/REST 조회로 목적을 달성할 수 있으면 Tailscale로 전환하지 않는다. 서버 설정·Docker/WP-CLI·비공개 WordPress 상태처럼 SSH가 반드시 필요한 작업에서 Direct SSH가 불가능할 때만 Tailscale을 명시적으로 선택한다. Tailscale 경로를 선택한 뒤에도 `tailscale status/ping`을 선행 반복하지 않고 실제 SSH 실패 시 한 번만 진단한다. 읽기 명령은 필요할 때 1회 재시도할 수 있고, P2 guarded mutation은 서버가 전체 desired state를 확인하므로 SSH 255에서 최대 1회 replay한다. raw `post update`, `post create`, media import처럼 결과 유실 시 중복·불명확 상태를 만들 수 있는 mutation은 같은 재시도 의미론을 사용하지 않는다.
- 운영 서버의 OpenSSH는 2026-10-06 실제 재부팅 검증 후 **상시 `ssh.service` 모드**가 정본이다. `ssh.service`는 enabled/active, `ssh.socket`은 disabled여야 한다. Ubuntu socket activation 구성에서는 `ssh.socket`이 enabled인데도 부팅 시 `ConditionResult=no`로 남아 listener가 생기지 않는 현상을 두 차례 재현했기 때문에 다시 socket activation으로 되돌리지 않는다. Direct SSH 장애 시 공개 HTTP가 정상이고 `BLOGUITO_SSH` allowlist도 맞는데 22번 listener가 없으면 Tailscale SSH로 들어가 `systemctl is-active/is-enabled ssh.service`와 `ss -lntp`를 먼저 확인한다.
- P11부터 WSL 안의 표준 OpenSSH 경로는 한 adapter 실행 동안 `ControlMaster=auto`, `ControlPersist=30`으로 연결을 재사용한다. Windows native OpenSSH와 `tailscale ssh`에는 이 옵션을 적용하지 않는다. 연결 재사용은 transport 비용만 줄이며 action별 allowlist, target ID 제한, CAS/replay 규칙은 바꾸지 않는다.
- `import-section-image`는 고정된 read-only snapshot script로 대상 글 본문/상태, 대표이미지 ID, Rank Math 3종을 한 번에 읽고, import 뒤 attachment 메타까지 한 번에 재조회한다. 따라서 정상 경로의 WP-CLI 조회/변경은 `pre snapshot → media import → post snapshot` 3회가 기본이다. 두 snapshot은 읽기 전용이라 SSH 255에서 1회 재시도할 수 있지만 **media import는 절대 자동 재시도하지 않는다.**
- 한글 등 비 ASCII attachment 제목/ALT는 명령행 인코딩 계층에서 `?`로 치환되는 일을 피하기 위해 UTF-8 JSON 파일 사용을 권장한다. JSON은 정확히 `{"media_title":"…","alt_text":"…"}` 두 필드만 가지며 `import-section-image ... --media-metadata-file <파일>`로 전달한다. 직접 `--media-title`/`--alt-text`를 사용하더라도 연속 `???` 또는 Unicode replacement character가 감지되면 import 전에 중단해 손상된 메타데이터를 저장하지 않는다.
- 과거 서버 reviewed state의 1회 동기화는 완료됐고 P10 per-post manifest 전환도 2026-10-01에 끝났다. 따라서 `sync_editorial_state_via_ssh.py`는 P12에서 제거했으며 로컬 `agent-publisher/data`가 정본이다. 새 환경 복구는 검증된 백업/restore 절차를 사용하고 오래된 서버 index를 다시 가져와 덮지 않는다.

### reviewed state 저장 구조

P10부터 대형 reviewed bundle을 `draft_posts.json`/`published_posts.json` 한 파일 안에 반복 저장하지 않아도 된다. `agent-publisher/data/post_manifests/schema.json` marker가 없는 기존 설치는 예전 inline index를 그대로 읽고 쓰며, marker가 활성화된 설치는 index에는 ID·제목·상태·URL·카테고리 같은 경량 metadata와 `manifest_sha256`만 남기고 실제 `fact_manifest`는 `post_manifests/post-<ID>-<digest>.json`에 불변 파일로 저장한다.

전환은 **새 코드를 먼저 배치한 뒤** `python agent-publisher/agents/post_manifest_store.py --data-dir agent-publisher/data`로 수행한다. 이전 코드가 실행 중인 상태에서는 compact index를 이해하지 못하므로 marker를 먼저 만들지 않는다.

전환기는 두 index를 먼저 검증한 뒤 marker를 만들고 reviewed record만 sidecar로 분리한다. unreviewed legacy row는 inline으로 남긴다. per-post 모드의 local CAS는 대상 manifest와 대상 index projection에만 결합하므로 다른 글의 병렬 수정 때문에 실패하지 않는다. manifest는 content-addressed 불변 파일을 먼저 쓴 뒤 index pointer를 원자 교체하므로 index 교체 전 중단돼도 기존 record가 깨지지 않는다. WordPress의 content SHA CAS, 원문 backup, guarded readback과 전역 editorial mutation lock은 그대로 유지한다.

이 구조에서 운영 서버 checkout의 버전이 로컬보다 오래됐다는 이유만으로 원고 review를 다시 수행할 필요가 없다. 반대로 실제 bundle, source, 정책 fingerprint, review 신선도가 달라졌다면 로컬 정본에서도 정상 검증이 차단되며 해당 review를 새로 해야 한다.

WordPress 전체 inventory는 schema v2에서 각 글의 `ID`, 제목, 상태, 본문 SHA256, 본문 URL signature만 수집한다. 신규 글의 URL 중복과 제목 중복은 이 경량 정보로 검사하고, 기존 글 수정에서 동일 공식 URL이 단순 출처인지 본문·CTA 중복인지 구분해야 할 때만 해당 후보 글의 본문을 단건 `post get`으로 추가 조회한다. 제한형 SSH transport는 inventory에서 관측된 후보 ID에 읽기 권한만 추가하며 mutation 대상 ID 집합은 확장하지 않는다.

내부 실사용 성능 기록은 `agent-publisher/data/editorial_runs/workflow-metrics.jsonl`에 JSONL로 쌓인다. SSH adapter가 바깥 실행 receipt 하나를 소유하고 내부 CLI/source/review/image/WP 단계의 timing과 counter를 같은 receipt에 합친다. 주요 필드는 `total_ms`, `source_fetch`, `semantic_review`/`delta_semantic_review`, `cover_generation`, `image_upload`, `wp_target_read`, `wp_meta_read`, `wp_guarded_mutation`, `catalog_sync`, WordPress/source 요청 횟수다. 원고·출처 본문은 기록하지 않는다. unit test는 별도 test metrics 파일을 사용한다.

반복 성능 분석을 위해 별도 임시 Python을 만들지 않는다. `python scripts/summarize_workflow_metrics.py --context live --status ok`를 사용하면 action별 실행 건수, median/P90 `total_ms`, 평균 WordPress 왕복, 단계별 평균 시간을 JSON으로 확인할 수 있다. 특정 action만 보려면 `--action edit-post`처럼 반복 지정한다.

### 일회성 작업 파일 정리

- 게시물 한 건의 HTML 조각을 넣거나 바꾸기 위해 `patch_post_<ID>_*.py`를 만들지 않고 `scripts/patch_post_component.py`를 사용한다. 이 도구는 로컬 파일 한 곳만 수정하며 target regex가 0건 또는 2건 이상이면 fail closed한다. WordPress 쓰기는 수행하지 않는다.
- 한 번만 필요한 조사·변환·검증 Python, 다운로드한 원문, 중간 bundle/HTML/이미지는 `scratch/tasks/<작업명>/`에 둔다. `scratch/`는 Git에 포함하지 않는다.
- `DesignerAgent`가 자동 생성한 대표이미지는 `%TEMP%/bloguito/covers/`에만 만들고 WordPress 저장 성공·실패 뒤 즉시 삭제한다. 사용자가 `--image-path`로 지정한 파일은 자동 삭제하지 않는다. 프로세스 강제 종료로 남은 24시간 이상 된 generated cover와 과거 `tmp/`의 browser user-data profile만 `python scripts/cleanup_workspaces.py`로 dry-run 확인한 뒤 `--apply`로 정리한다.
- 재현·사고 분석을 위해 one-off 코드를 보존해야 하면 작업 종료 후 `scripts/archive/<날짜 또는 작업명>/`로 이동한다. 새 archive 산출물은 Git에 넣지 않고 정규 도구처럼 호출하지 않는다.
- `scripts/` 루트의 Python 파일은 `scripts/maintained_scripts.json`과 정확히 일치해야 하며 unit test가 이를 검사한다. 두 번째 독립 사용 사례가 생긴 임시 도구만 명시적 인터페이스와 테스트를 갖춘 뒤 루트 도구로 승격한다.
- 자세한 규칙과 예시는 `scripts/README.md`를 따른다.

상세 인자와 제한은 [편집 규약](EDITORIAL_SYSTEM.md) 및 코드 [`editorial_cli.py`](../agent-publisher/editorial_cli.py)를 우선 확인한다. 과거 작업 기록의 '발행'은 draft 생성과 공개 승격을 혼용했으므로 명시적으로 구분한다.

## 백업·복구 및 운영 배포

- `backup_daily.sh`: v3 **코드**는 DB, uploads, plugins/themes/MU 플러그인, 설정, 별도 비밀 구성요소, manifest를 다룬다. 운영에서 v3가 정기 생성되는지, Nginx/TLS까지 복구 가능한지는 별도 확인한다.
- `restore_backup.sh <archive> --verify-only`: **데이터를 변경하지 않는** 해시·구조 확인. 구형 v2는 검증만 지원하고 전체 복원을 거부한다.
- `scripts/sync_backups.py`: Direct SSH와 명시적 Tailscale SSH가 **같은 검증/atomic sync engine**을 사용한다. 기본은 Direct이며 비상 경로는 `BLOGUITO_BACKUP_TRANSPORT=tailscale`로만 선택한다. 두 transport 모두 전후 SHA, 임시 파일, v2/v3 manifest와 nested archive/path 검증 후 `os.replace`로 확정한다. 기존 백업을 건드리지 않는 다운로드라도 저장 경로의 권한과 여유 공간을 확인한다.
- WordPress PHP 검증은 `.github/workflows/test.yml`에서 파일을 수동 나열하지 않고 `php wordpress/tests/run.php` 한 진입점으로 실행한다. 이 runner는 모든 MU plugin과 test PHP를 syntax-check하고 standalone `*-test.php`를 자동 실행한다. 실제 WordPress나 보존 fixture가 필요한 `wp-post-id-column-smoke.php`, `legacy-table85-accessibility-test.php`는 syntax-check만 하고 전용 환경에서 별도 실행한다.
- 호스트 DR의 nginx/TLS/sshd/fail2ban/systemd 검증 정본은 `scripts/host_dr_validate.sh` 하나다. `host_dr_config_drill.sh`는 읽기 전용 repo mount를 만든 disposable Ubuntu container에서 이 validator를 `--with-wp-cli`로 호출해 pinned WP-CLI의 정상/오류 경로까지 추가 검증한다.
- v3의 `secrets.tar.gz`는 일반 압축이며 **암호화된 금고가 아니다**. 접근권한, 오프사이트 암호화·키 보관·독립 복구 계획 없이 완전 백업이라고 표현하지 않는다. 실제 격리 복원 범위와 호스트 단위 미검증 항목은 [2026-09-25 애플리케이션/데이터 복구 훈련](backup-restore-drill-2026-09-25.md)과 [2026-09-26 호스트 단위 DR 확장 훈련](host-disaster-recovery-drill-2026-09-26.md)의 PASS/PARTIAL/NOT TESTED 판정을 따른다.

**Windows 암호화 오프호스트 사본:** `scripts/sync_backups_encrypted.py`는 Direct SSH로 서버 snapshot의 원격 SHA를 두 번 확인하고 기존 `sync_backups.verify_archive()`의 v3 component/gzip/nested-path 검증을 통과한 임시 평문만 AES-256-GCM으로 암호화한다. 저장 파일은 `*.tar.gz.blgenc`이며 원본 filename/size/SHA를 인증된 header에 포함한다. `scripts/sync_backups_encrypted_scheduled.ps1`은 기본적으로 `%USERPROFILE%\BloguitoBackupsEncrypted`에 암호화본만 30일 보존하고 recovery key는 `%USERPROFILE%\Documents\Secure\Bloguito-Backup-Recovery.key`에서 읽는다. 평문 임시 파일은 성공/실패 후 삭제한다. recovery key는 Git, 서버, 암호화 backup directory에 복사하지 않는다. 암호화 backup 자체의 검증은 `backup_encryption.verify_or_decrypt()`로 GCM tag와 원본 SHA/size를 함께 검사한다. 이 구조도 같은 노트북 하나에 backup과 key가 함께 존재하면 장비 전체 분실에는 충분하지 않으므로 recovery key의 별도 오프라인 수탁은 운영자 책임으로 남는다.
- 운영 서버는 로컬 Compose와 `.env` 구성·systemd 설정이 다를 수 있다. **이미지 digest가 같다는 이유만으로 재생성할 필요는 없다.** 사전 해시·백업·비밀값 비노출 설정 확인, 스테이징 테스트, 서비스별 롤백 계획을 마련한 뒤 변경한다.

### WP-CLI 재구축

`wordpress/docker-compose.yml`은 호스트의 `wordpress/wp-cli.phar`를 컨테이너 `/usr/local/bin/wp`에 읽기 전용으로 마운트한다. 새 서버에서는 수동으로 임의 PHAR를 내려받지 말고 `wordpress/provision-wp-cli.sh`를 먼저 실행한다.

```bash
cd /home/ubuntu/wordpress
./provision-wp-cli.sh
docker compose up -d
sudo docker exec wordpress_app wp --info --allow-root
sudo docker exec wordpress_app wp core version --allow-root
sudo docker exec wordpress_app wp option get home --allow-root
```

provisioner는 WP-CLI `2.12.0`의 버전 지정 release URL과 SHA-256 `ce34ddd838f7351d6759068d09793f26755463b4a4610a5a5c0a97b68220d85c`를 고정한다. 기존 파일이 같은 해시이면 다운로드 없이 성공하고, 새 다운로드가 해시와 다르면 기존 파일을 교체하지 않는다. 이 해시는 2026-09-26 운영 컨테이너의 `/usr/local/bin/wp`와 동일 버전 공식 release PHAR를 서로 대조해 확인한 값이다. 버전을 올릴 때는 새 release 자산을 별도 검증하고 버전과 해시를 함께 변경한 뒤 격리 복구 훈련을 다시 수행한다.

세부 구현·명령·검증 근거는 [백업 기록](backup-recovery-2026-09-20.md)과 [배포 준비 기록](implementation-execution-2026-09-20.md) 참고. 두 문서의 '당시 미배포'는 이후 배포 여부를 증명하지 않으므로 현재 상태를 다시 관측한다.

## 운영 확인과 이력 남기기

- WordPress 관리 글 목록의 ID 열은 [2026-09-21 적용 기록](admin-post-id-column-2026-09-21.md)에 서버 반영과 WP 후크 검사 결과가 있다. 로그인 브라우저 UI 검사는 당시 수행하지 않았다.
- 백업 크론 `04:00`, 초안 생성 `08:00`(KST)은 2026-09-20에 관측된 기록이며 현재 스케줄은 서버 `crontab -l`로 재확인한다.
- 플러그인 활성화, GA4/Site Kit, 공개/임시글 수, 서치콘솔 지표는 저장소 문서만 보고 현재 상태·성능으로 단정하지 않는다.
- 작업마다 **기준 commit, 사전 변경 파일, 실제 변경/배포 범위, 테스트 결과, 서버 검증 여부, 미검증/롤백 지점**을 날짜별 기록에 남기고 [문서 안내](INDEX.md)에 편입한다. 개인식별자·API 키·DB 암호는 출력·Git·보고서에 기록하지 않는다.
- 같은 게시물이나 같은 기능의 후속 수정은 기존 작업 기록 MD의 새 날짜/절에 이어서 기록한다. 새 MD는 새로운 기능, 독립 장애, 배포, 아키텍처 변경처럼 별도 이력으로 찾을 가치가 있는 경우에만 만든다.
