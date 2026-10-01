# Bloguito 운영·개발 가이드

**적용 범위:** 저장소의 코드·설정에 근거한 작업 경로를 설명한다. 이 문서 자체는 현재 서버 배포 상태나 복구 성공을 보증하지 않는다. 실서비스 수정 전에는 실제 서버 이미지/구성, 백업, 실행 프로세스, 콘텐츠 상태를 다시 조회한다. 편집 기준과 기한·검토 설정을 복제하지 않고 [EDITORIAL_SYSTEM](EDITORIAL_SYSTEM.md) / [`editorial_policy.json`](../agent-publisher/editorial_policy.json)을 따른다.

## 구조와 실행 위치

| 경로 | 역할 |
| --- | --- |
| `agent-publisher/main.py` | Radar → Curator → Editorial Writer → Designer → Publisher의 자동 **임시글 생성** 진입점 |
| `agent-publisher/editorial_cli.py` | 근거 수집, 검토, 검사, 임시글 등록/갱신, 사람 확인 후 별도 공개 |
| `agent-publisher/agents/` | 검색·검토·렌더링·WordPress 연결 로직; `copywriter.py`는 레거시이며 `main.py`는 `editorial_writer.py`를 사용 |
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

### 글쓰기·수정 시작과 묶음 처리

작업 시작 시 대상과 요청을 아래 표로 분류한다. 진행 설명은 “이번에는 [대상]의 [수정 범위]를 처리합니다. [근거 확인] → [전체/변경 부분 검토] → [임시글 저장/승인된 기존 글 수정] → 저장·화면 확인 순서로 진행합니다”처럼 1~2문장으로 한다. 대상이나 공개 의도가 실제로 불명확한 경우에만 필요한 정보를 확인하며, 이미 받은 같은 변경안의 적용 승인을 다시 묻지 않는다.

| 요청 종류 | 정규 경로 | 핵심 검사 |
| --- | --- | --- |
| 일반 신규 draft | `prepare-draft` | content/source preflight, 필요한 semantic review, 최신 inventory, draft 저장/readback, 대표이미지 |
| 기존 reviewed 글 수정 | `edit-post` | 단일 classifier가 Simple/Standard를 선택. 모든 write는 CAS/readback, 사실 변경은 source/full review 추가 |
| 대표이미지만 교체 | `replace-featured-image` | live 본문 SHA와 `_thumbnail_id`를 명령이 직접 읽고 image-only mutation/readback. article source/review는 열지 않음 |
| 공개 전환 | `promote-draft --confirm-publish` | 글별 사용자 승인, current review/source binding, draft CAS |

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

**행사 일정형 글:** 한 도시의 여러 행사·축제를 월간 가이드로 작성하거나 기존 Gemini draft를 개선할 때에는 [EVENT_POST_STANDARD.md](EVENT_POST_STANDARD.md)를 적용한다. Gemini 초안은 행사 후보·레이아웃·공식 URL·미디어 후보를 재사용할 수 있는 scaffold로 취급하고, 현재 연도 날짜·시간·비용·신청·프로그램을 공식 source로 다시 검증한 뒤 필요한 행사 section을 통째로 재작성한다. 새 표준 bundle은 `event_post_standard_version=1`, `multi_event_schedule=true`, 행사별 `event_name` binding을 사용한다. 기존 draft는 다음 Standard revision에서 이관하며, 도시별 고정 행사 수·1,200단어 기준·인터랙티브 지도·`test_<city>_festival_post.py` 같은 one-off 테스트를 새 품질 게이트로 만들지 않는다. 행사 사실·source·CTA·SEO가 바뀌는 수정은 `standard-event` 검증과 full semantic review를 거치고, actual image relevance/quality와 desktop/mobile 배치는 browser/visual QA로 확인한다.

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
  --alt-text "대전 10월 행사 일정 안내" --confirm-update

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

**신규 draft Fast 경로:** `prepare-draft`는 별도 안전장치를 없애는 명령이 아니라 기존 단계의 중복 왕복을 합친 명령이다. 구조화 원고가 완성된 뒤 먼저 WordPress inventory 없이 content/source 결정론 검사를 수행한다. 통과하면 현재 의미 검토가 없는 경우 reviewer와 `DesignerAgent` 대표 이미지 생성·비전 검수를 동시에 실행한다. current review가 bundle에 이미 결합돼 있으면 reviewer를 다시 호출하지 않는다. 이후 Publisher 잠금 안에서 최신 WordPress lightweight inventory를 한 번 조회하고 site 중복·related post·review binding을 포함한 기존 full `validate_bundle()`을 실행한 뒤에만 draft를 만든다. 따라서 별도의 `check`를 다시 실행하는 것은 실패 원인 진단이 필요한 경우에만 한다.

ChatGPT/CoS 로컬 환경에서는 다음 한 명령을 기본으로 사용한다. `--image-path`를 생략하면 현행 대표 이미지 정책으로 이미지를 자동 생성·검수하고, 이미 별도 검수한 이미지를 사용할 때만 경로를 전달한다.

```powershell
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- prepare-draft scratch/tasks/article/bundle.json --author-model "GPT-5.6 Sol" --output scratch/tasks/article/receipt.json
```

이 SSH adapter 경로는 draft 저장 성공 뒤 `scripts/sync_post_catalog.py`를 최대 2회까지 읽기 전용으로 시도한다. 카탈로그 동기화가 두 번 모두 실패한 경우 draft 저장 성공을 실패로 되돌리지 않는다. 이때는 출력된 post ID를 보존하고 `python scripts/sync_post_catalog.py`만 재실행한다. `prepare-draft` 자체를 재실행하면 새 draft가 중복 생성될 수 있으므로 금지한다.

**로컬 카탈로그와 주제 백로그:** 새 글 주제 탐색은 `docs/POST_CATALOG.md`에서 시작한다. 이 문서는 빠른 1차 중복 확인과 현재 포트폴리오·주제 백로그 파악용이며, 실제 저장 직전 안전 검사를 대체하지 않는다. 신규 draft 생성, 공개 전환, 제목·카테고리·Rank Math 포커스 키워드/점수처럼 카탈로그에 표시되는 정보 변경이 성공적으로 끝난 뒤 `python scripts/sync_post_catalog.py`를 한 번 실행한다. 동기화 스크립트는 기존 `POST_CATALOG.md`의 사람이 검토한 백로그 행을 보존하고, 현재 공개·임시·예약·비공개 글의 제목 또는 포커스 키워드와 겹치는 후보를 제거한 뒤 우선순위를 다시 매긴다. 백로그를 보충할 때에는 주제 탐색 단계에서 공식 출처와 유효기간을 확인한 새 후보만 추가한다.

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
- 공개 전환 `promote-draft`와 복구·진단 action은 별도 lifecycle/maintenance 명령이다. Direct SSH가 기본이며 Tailscale은 실제 비상·복구 작업에서만 명시적으로 선택한다.
- 수동 편집 transport의 기본 모드는 항상 `direct`다. `BLOGUITO_SSH_HOST`, `BLOGUITO_SSH_USER`는 Direct SSH의 기본 접속값으로 사용할 수 있지만, `BLOGUITO_SSH_MODE=tailscale` 같은 지속 환경설정이 일반 작업을 Tailscale로 자동 전환하게 두지 않는다. WSL/Tailscale은 명령행 `--ssh-mode wsl|tailscale`로만 명시적으로 선택한다.
- Direct SSH가 실패해도 공개 웹/REST 조회로 목적을 달성할 수 있으면 Tailscale로 전환하지 않는다. 서버 설정·Docker/WP-CLI·비공개 WordPress 상태처럼 SSH가 반드시 필요한 작업에서 Direct SSH가 불가능할 때만 Tailscale을 명시적으로 선택한다. Tailscale 경로를 선택한 뒤에도 `tailscale status/ping`을 선행 반복하지 않고 실제 SSH 실패 시 한 번만 진단한다. 읽기 명령은 필요할 때 1회 재시도할 수 있고, P2 guarded mutation은 서버가 전체 desired state를 확인하므로 SSH 255에서 최대 1회 replay한다. raw `post update`, `post create`, media import처럼 결과 유실 시 중복·불명확 상태를 만들 수 있는 mutation은 같은 재시도 의미론을 사용하지 않는다.
- P11부터 WSL 안의 표준 OpenSSH 경로는 한 adapter 실행 동안 `ControlMaster=auto`, `ControlPersist=30`으로 연결을 재사용한다. Windows native OpenSSH와 `tailscale ssh`에는 이 옵션을 적용하지 않는다. 연결 재사용은 transport 비용만 줄이며 action별 allowlist, target ID 제한, CAS/replay 규칙은 바꾸지 않는다.
- `import-section-image`는 고정된 read-only snapshot script로 대상 글 본문/상태, 대표이미지 ID, Rank Math 3종을 한 번에 읽고, import 뒤 attachment 메타까지 한 번에 재조회한다. 따라서 정상 경로의 WP-CLI 조회/변경은 `pre snapshot → media import → post snapshot` 3회가 기본이다. 두 snapshot은 읽기 전용이라 SSH 255에서 1회 재시도할 수 있지만 **media import는 절대 자동 재시도하지 않는다.**
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
