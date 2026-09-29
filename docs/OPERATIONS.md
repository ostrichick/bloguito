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
| `agent-publisher/whatsapp-bridge/` | 원격 상태·초안/공개 명령, `package-lock.json`·명령 정책 포함. 실제 systemd/env 배포와 구분 |
| `scripts/` | 반복 사용 가능한 운영·진단 도구만 유지. 게시물 한 건을 위한 임시 Python은 두지 않으며 목록은 `scripts/maintained_scripts.json`으로 검증 |
| `scratch/` | 한 작업에서만 필요한 probe, 변환 코드, 중간 JSON/HTML/이미지. Git 비추적 |
| `scripts/archive/` | 보존할 가치가 있는 과거 one-off 스크립트. 새 archive 파일은 Git 비추적이며 정규 실행 경로로 사용하지 않음 |

## 로컬 설치 및 무변경 검사

Python 3.12와 Docker/Git Bash·Node는 작업 종류에 맞춰 준비한다. Python 환경은 **로컬** `agent-publisher/.venv`, **Linux 운영 예시** `agent-publisher/venv`로 다르다. `.env.example`에는 실제 비밀번호를 쓰지 않는다.

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

P4부터 reviewed post 수정은 원고 diff와 실제 Fast/Standard route를 한 번 분석해 `validation_plan`을 만든다. 정규 `scripts/editorial_cli_via_ssh.py ... -- edit-post ...` 경로는 WordPress용 제한 transport를 설치하거나 mutation을 시작하기 **전에** 이 plan의 regression group만 로컬에서 실행한다. 테스트 실패 시 WordPress 쓰기는 시작하지 않는다. source freshness, semantic review, CAS, backup, guarded readback은 regression test 선택과 별개의 기존 안전장치이므로 profile이 좁아져도 제거되지 않는다.

| 대표 profile | 예 | regression 범위 | content/source review |
| --- | --- | --- | --- |
| `quick-text` | 오탈자, 표현 정리, 기존 사실 재배치 | 공통 safe-edit + Fast classifier | source 재사용 + changed-block delta review |
| `quick-image` | 대표이미지만 교체 | 공통 safe-edit + featured-image | 본문/source semantic review 없음; 본문 SHA/SEO/thumbnail 보존 검증 |
| `standard-fact` | 새 숫자·가격·조건·제목 | 실제 draft/public Standard mutator + validation contract + fact | Standard full semantic review + current source receipt/live 규칙 |
| `standard-source` | source snapshot/URL 변경 | Standard mutator + source | source 전체 동일성 재검증 + full semantic review |
| `standard-cta` | 조회·신청·예매 목적지 변경 | Standard mutator + CTA/navigation | 목적지/근거 확인 + full semantic review |
| `standard-layout` | 표/section/FAQ topology 변경 | Standard mutator + layout/accessibility | Standard route면 full review; Fast로 증명된 구조 재배치는 delta review |
| `standard-event` | 행사·공연의 날짜/장소/판매상태 등 도메인 사실 변경 | 위 관련 group + event, 공연이면 ticket | 변경 위험도에 따라 affected/live source + full review |
| `full-regression` | `agents/`, policy, renderer, SSH transport, test infrastructure 같은 공유 코드 변경 | 전체 `agent-publisher/tests` 1회 | 코드 변경에 맞는 기존 editorial 검증 유지 |

현재 P4 기준의 일반 draft 예시는 표현 수정 36개, 이미지 전용 17개, 사실 변경 64개, CTA 52개, 레이아웃 59개, source 변경 67개 regression test를 선택한다. 테스트 파일이 늘면 숫자는 달라질 수 있으므로 결과 보고에는 고정 수치 대신 실제 runner receipt의 profile/test count를 사용한다. 특정 과거 글은 `test_groups.json`의 post selector가 해당 글 전용 회귀만 추가한다.

문서만 수정한 경우에는 `git diff --check`와 링크/문서 구조 확인으로 충분하다. 공통 renderer, validator, publisher, 정책·transport 로직을 바꾼 경우에만 표적 테스트 뒤 전체 suite를 1회 실행하고, 이후 공통 코드가 바뀌지 않았다면 콘텐츠/문서 수정 때문에 같은 full suite를 반복하지 않는다. 화면 검증도 CSS/renderer/표·목차 구조가 바뀌면 360/390px, 데스크톱, 200% 확대와 키보드 접근까지 수행하고, 구조가 그대로인 본문 데이터 수정은 대표 모바일+데스크톱의 변경 영역, CTA-only는 실제 도착 화면과 버튼 smoke test를 우선한다.

`scripts/run_validation.py`는 진단·CI용 별도 runner다. 기본 실행은 **plan 출력만** 하며 테스트를 실행하지 않는다. 실제 실행은 `--run`을 명시한다.

```powershell
# 공유 코드 변경: full-regression plan만 확인
python scripts/run_validation.py --changed-file agent-publisher/agents/editorial.py

# 두 reviewed bundle의 scope를 확인하고 선택된 regression을 실제 실행
python scripts/run_validation.py --before scratch/tasks/edit/before.json `
  --after scratch/tasks/edit/after.json --route standard --post-id 641 --run
```

## 원고 경로: 기본은 draft

### 글쓰기·수정 시작과 묶음 처리

작업 시작 시 대상과 요청을 아래 표로 분류한다. 진행 설명은 “이번에는 [대상]의 [수정 범위]를 처리합니다. [근거 확인] → [전체/변경 부분 검토] → [임시글 저장/승인된 기존 글 수정] → 저장·화면 확인 순서로 진행합니다”처럼 1~2문장으로 한다. 대상이나 공개 의도가 실제로 불명확한 경우에만 필요한 정보를 확인하며, 이미 받은 같은 변경안의 적용 승인을 다시 묻지 않는다.

| 요청 종류 | 선택할 경로 | 검토 범위 |
| --- | --- | --- |
| 일반 신규 draft (Fast) | POST_CATALOG 1차 중복 확인 → sources → 구조화 원고 → `prepare-draft` | 로컬 content/source preflight → 의미 검토와 대표 이미지 생성·검수 병렬 → Publisher의 최신 inventory 1회/full validation → draft 저장 → SSH adapter 사용 시 POST_CATALOG 자동 동기화 |
| 신규 글 진단/예외 (Strict) | POST_CATALOG → sources → 구조화 원고 → manual-review/review → 필요 시 check → publish | 정책 예외·출처 충돌·공연 공식 이미지 수동 검토·공통 코드/정책 변경 등 단계별 결과를 따로 확인해야 하는 경우 |
| 검토된 기존 글 수정 (기본) | `edit-post`, 실제 요청 범위를 `--edit-intent`로 전달 | tracked reviewed manifest로 draft/public 상태를 먼저 결정한 뒤 표현·중복·기존 사실 재배치는 Fast, 새 사실·숫자·날짜·대상·출처·제목·CTA는 상태별 Standard로 자동 전환 |
| 대표이미지만 교체 | `edit-post --image-path ...` 또는 `replace-featured-image` | 본문·slug·상태·excerpt·Rank Math를 바꾸지 않고 현재 본문 SHA와 기존 `_thumbnail_id`를 CAS로 확인한 뒤 검수한 1200×675 이미지 한 장만 교체 |
| 사실·숫자·날짜·대상·출처·제목·CTA 변경 | `edit-post`가 draft/public Standard로 분기하거나 저수준 revise-draft / update-existing / replace-legacy-draft | 새로운 근거와 전체 검토; legacy 교체는 기존 별도 진입 조건 충족 필요 |
| 검토된 임시글의 표현·중복 정리·기존 사실 재배치 (저수준 직접 호출) | `fast-revise-draft`, 실제 요청 범위를 --edit-intent로 전달 | 일반 작업에서는 `edit-draft`를 우선하고, 진단·테스트에서 Fast 경로를 명시적으로 고정할 때만 직접 호출 |
| reviewed 공개 글의 표현 정리 | `edit-post` | `published_posts.json`의 reviewed bundle이 실제 현재 본문 SHA에 정확히 결합된 경우에만 public Fast. stale/missing manifest면 Standard 또는 차단 |

**묶음 처리:** 같은 글·같은 승인 범위의 문구 다듬기, 중복 FAQ 제거, 기존 사실의 표 정리를 한 후보 bundle에 모아 검토한 뒤 한 번 저장한다. 단순 이동·삭제가 아니라 의미가 달라지는지 변경 블록을 검토한다. 저장 전에 추가 요청이 오면 범위와 경로를 다시 분류해 후보에 합치고 최종 후보로 검토한다. 저장 후 추가 요청은 새 원본과 검토 유효성을 기준으로 처리한다. P1부터 Fast 수정은 최초 full review를 trust anchor로 두고 각 delta의 `base_content_digest → result_content_digest`를 연결한 `fast_edit_chain`을 검증한다. 정책과 review 기한이 그대로이고 각 delta 검토가 모두 유효하면 최대 5개 delta까지 연속 Fast 수정이 가능하며, chain이 끊기거나 한도에 도달하면 `FULL_REVIEW_REQUIRED`로 Standard에 승격한다. 검토 digest나 timestamp를 수동으로 바꿔 통과시키지 않는다. FULL_REVIEW_REQUIRED이면 필요한 전체 검토 경로로 전환하고 사용자에게 이유를 짧게 알린다. 요청 범위 자체를 확대해야 한다면 먼저 필요한 정보를 확인한다.

**같은 작업 안의 재사용:** 다음 조건을 충족하는 자료만 재사용한다.

- 정책 문서와 설정: 같은 작업자가 이미 읽었고 이후 파일이 바뀌지 않았으면 기존 이해를 사용한다. 다른 작업이 파일을 수정했을 가능성이 있으면 변경 여부부터 확인한다.
- WordPress 목록: 같은 실행에서 확보한 목록은 읽기 전용 review/check에 재사용한다. 실제 신규 등록·일반 갱신의 최신 inventory와 저장 직전 원본 일치 확인은 정규 코드가 수행하도록 유지한다. 쓰기 이후 무효화된 목록이나 다른 작업의 오래된 목록을 재사용하지 않는다. fast 경로는 기존 구현대로 대상 한 글만 조회한다.
- 의미 검토: 원고·근거·정책과 reviewer contract의 fingerprint 및 검토 기한이 모두 같을 때 `data/editorial_runs/review-cache/`의 content-addressed review를 재사용한다. reviewer 코드를 바꾸면 contract digest가 달라져 cache가 자동 무효화된다. 변경된 원고에는 변경 범위에 맞는 새 검토가 필요하다. 모델 호출은 기본 45초 요청 timeout(`EDITORIAL_MODEL_TIMEOUT_SECONDS`, 10~120초 제한)을 사용하고 preferred model 뒤 capacity fallback 한 개까지만 시도한다. 429/503/timeout은 fallback 대상으로 취급하지만 semantic/schema 실패를 다른 모델로 우회하지 않는다.
- 공식 source 재확인: Standard revision 중 이미 같은 URL/SHA를 최근 확인한 source는 `data/editorial_runs/source-validation/`의 짧은 receipt를 재사용한다. 기본 TTL은 15분이며 `EDITORIAL_SOURCE_RECEIPT_TTL_MINUTES`로 조절하되 최대 30분이다. receipt가 없거나 만료됐거나 extractor 코드가 바뀐 source만 `fetch_sources_subset()`으로 다시 받는다. 예매·판매·신청·재고·매진 등 현재 상태를 직접 담은 source는 TTL과 무관하게 항상 live refresh한다. 새 SHA가 관측되면 `official_sources_changed_since_review`로 차단한다.
- 변경안 비교와 화면 확인: 같은 변경안 적용이 이미 승인됐으면 승인 전 비교 패키지를 다시 생성하지 않는다. CTA·레이아웃 등 검증 대상이 그대로이고 이전 확인이 현재 변경에도 유효한 범위만 재사용한다. 표 구조 변경은 전체 표 접근성 QA를 수행한다.

`edit-post`는 위 재사용 규칙을 draft/public 공통 상위 경로에서 강제한다. 기존 tracked bundle과 새 후보의 source/policy/review fingerprint를 기록하고, Fast 적합성이 확인되면 전체 inventory·전체 source 재수집·전체 semantic review 대신 기존 검증과 changed-block delta review를 사용한다. public Fast는 `published_posts.json`에 reviewed bundle이 유일하게 존재하고 그 렌더 SHA가 사용자가 넘긴 현재 본문 SHA와 일치할 때만 허용한다. Fast 조건을 벗어나면 검사를 우회하지 않고 상태별 Standard 경로로 전환한다.

수정 명령은 `agent-publisher/data/editorial_runs/task-state/post-<ID>/current.json`에 Git 비추적 작업 상태를 원자적으로 기록하고, 종료된 이전 상태는 같은 디렉터리의 `archive/`에 보존한다. v3 state는 raw `edit_intent` 대신 SHA256을 저장하고 `content_saved`, `image_saved`를 독립 phase로 기록한다. P4에서는 선택된 `validation_plan`의 profile, group, binding digest도 함께 저장해 재개/결과 보고 때 어떤 regression 범위가 선택됐는지 확인할 수 있게 했다. plan 자체에는 원고/source 본문을 복제하지 않는다. artifact는 경로와 가능한 경우 파일 SHA를 함께 기록한다. 세션 압축·연결 중단 뒤에는 candidate/policy/edit-intent/image fingerprint와 WordPress 현재 SHA를 먼저 비교하고 완료된 source/review/content/image 단계를 반복하지 않는다. WordPress 본문은 저장됐지만 local manifest 갱신 직전에 중단된 좁은 구간은 baseline/desired fingerprint가 정확히 맞을 때만 manifest를 전진시킨다. 이미지 import가 끝난 직후에는 attachment ID와 image/ALT/content SHA를 checkpoint하고, 재개 시 같은 attachment의 thumbnail/ALT/MIME/URL/본문·SEO 보존을 검증만 하며 재import하지 않는다. WordPress 저장이 끝났지만 화면 확인이 남아 있으면 `saved_pending_qa`이며, 요구된 QA scope를 모두 완료한 뒤에만 `browser_qa`를 완료 처리한다. 기존 v1/v2 state는 읽을 때 v3 형태로 호환 처리한다.

```powershell
# reviewed draft/public 공통 수정: 상태와 Fast/Standard를 먼저 자동 판정
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- edit-post tmp/article/bundle.json `
  --post-id 641 --expected-content-sha256 <현재본문SHA> --confirm-update `
  --edit-intent "표현 정리와 기존 사실의 표 재배치"

# 중단된 같은 작업 재개: task-state fingerprint와 live SHA가 맞아야만 이어감
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- edit-post tmp/article/bundle.json `
  --post-id 641 --expected-content-sha256 <작업시작본문SHA> --confirm-update --resume `
  --edit-intent "표현 정리와 기존 사실의 표 재배치"

# 대표이미지만 교체: 본문/source/review pipeline을 열지 않음
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- replace-featured-image `
  --post-id 641 --expected-content-sha256 <현재본문SHA> --expected-thumbnail-id <현재이미지ID> `
  --image-path tmp/article/cover.jpg --alt-text "대전 10월 행사 일정 안내" --confirm-update

# 실제 브라우저 QA가 끝난 뒤 로컬 task-state 종료
python agent-publisher/editorial_cli.py complete-task-qa `
  --post-id 641 --expected-content-sha256 <저장후본문SHA> `
  --qa-scope content-mobile-desktop
```

`replace-featured-image`의 media import는 응답 유실 시 중복 attachment를 만들 수 있어 SSH 255 자동 재시도를 하지 않는다. import 응답으로 attachment ID를 확보한 뒤 중단된 경우에는 state의 `image_outcome` checkpoint로 해당 attachment를 검증만 한다. attachment ID를 확보하지 못한 채 결과가 불명확하면 새 media import를 자동 반복하지 않는다. `edit-post --resume`은 live 본문 SHA가 작업 시작 SHA 또는 저장 예정 SHA 중 하나일 때만 이어가며 제3의 SHA가 관측되면 동시 변경으로 차단한다. featured-image QA를 완료할 때는 `--qa-scope featured-image --observed-thumbnail-id <저장된attachmentID>`를 함께 전달한다.

**Standard P1/P2 preflight와 mutation:** `revise-draft`와 public Standard는 inventory sync, 대상 글의 초기 baseline read, 공식 source 동일성 recheck처럼 서로 독립적인 읽기 작업을 병렬화한다. P2부터 저장 직전 CAS → `wp_update_post()` → 저장 후 readback은 고정된 server-side guarded mutation 한 번으로 합친다. reviewed HTML은 JSON stdin으로 전달하며 임의 PHP/명령은 허용하지 않는다. guarded protocol은 status/title/slug/excerpt/content SHA의 전체 expected state를 확인하고, 저장 후 전체 desired state를 다시 검증한다. 따라서 Fast draft의 기본 target 왕복은 `get + guarded mutation` 2회, Standard draft는 경량 inventory + 초기 target read + guarded mutation의 약 3회 수준이 된다. SSH 255에서 guarded request는 desired-state 일치 검사를 전제로 최대 1회만 replay하며, raw `post update`와 media import는 이 재시도 의미론을 공유하지 않는다.

**신규 draft Fast 경로:** `prepare-draft`는 별도 안전장치를 없애는 명령이 아니라 기존 단계의 중복 왕복을 합친 명령이다. 구조화 원고가 완성된 뒤 먼저 WordPress inventory 없이 content/source 결정론 검사를 수행한다. 통과하면 현재 의미 검토가 없는 경우 reviewer와 `DesignerAgent` 대표 이미지 생성·비전 검수를 동시에 실행한다. current review가 bundle에 이미 결합돼 있으면 reviewer를 다시 호출하지 않는다. 이후 Publisher 잠금 안에서 최신 WordPress lightweight inventory를 한 번 조회하고 site 중복·related post·review binding을 포함한 기존 full `validate_bundle()`을 실행한 뒤에만 draft를 만든다. 따라서 별도의 `check`를 다시 실행하는 것은 실패 원인 진단이 필요한 경우에만 한다.

ChatGPT/CoS 로컬 환경에서는 다음 한 명령을 기본으로 사용한다. `--image-path`를 생략하면 현행 대표 이미지 정책으로 이미지를 자동 생성·검수하고, 이미 별도 검수한 이미지를 사용할 때만 경로를 전달한다.

```powershell
python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- prepare-draft tmp/article/bundle.json --author-model "GPT-5.6 Sol" --output tmp/article/receipt.json
```

이 SSH adapter 경로는 draft 저장 성공 뒤 `scripts/sync_post_catalog.py`를 최대 2회까지 읽기 전용으로 시도한다. 카탈로그 동기화가 두 번 모두 실패한 경우 draft 저장 성공을 실패로 되돌리지 않는다. 이때는 출력된 post ID를 보존하고 `python scripts/sync_post_catalog.py`만 재실행한다. `prepare-draft` 자체를 재실행하면 새 draft가 중복 생성될 수 있으므로 금지한다.

**로컬 카탈로그와 주제 백로그:** 새 글 주제 탐색은 `docs/POST_CATALOG.md`에서 시작한다. 이 문서는 빠른 1차 중복 확인과 현재 포트폴리오·주제 백로그 파악용이며, 실제 저장 직전 안전 검사를 대체하지 않는다. 신규 draft 생성, 공개 전환, 제목·카테고리·Rank Math 포커스 키워드/점수처럼 카탈로그에 표시되는 정보 변경이 성공적으로 끝난 뒤 `python scripts/sync_post_catalog.py`를 한 번 실행한다. 동기화 스크립트는 기존 `POST_CATALOG.md`의 사람이 검토한 백로그 행을 보존하고, 현재 공개·임시·예약·비공개 글의 제목 또는 포커스 키워드와 겹치는 후보를 제거한 뒤 우선순위를 다시 매긴다. 백로그를 보충할 때에는 주제 탐색 단계에서 공식 출처와 유효기간을 확인한 새 후보만 추가한다.

최종 보고는 대상 글·변경 내용·임시글/공개 상태·통과한 검증·미검증/보류 사항을 짧게 전달하고 같은 주제의 기존 날짜별 MD에 이력을 추가한다. P4 이후에는 `Validation: <profile>`, `관련 regression: N/N PASS`, source refresh/reuse, semantic review 범위, WP CAS/readback, browser QA scope를 구분해 적는다. 공유 코드를 실제로 바꿔 full suite를 실행한 경우에만 `Full regression: N/N PASS`를 추가하며, 콘텐츠 한 건을 수정했다는 이유만으로 전체 테스트 수를 결과 보고의 기본 지표로 쓰지 않는다. 이 절은 작업 실행 규칙이며 편집 검증 임계값이나 공개 승인 조건을 변경하지 않는다.

1. 게시물 상태(공개·임시·예약·비공개)와 출처를 조회하고, 중복·검토 만료·정책 적용 연도를 검증한다.
2. 공식 근거를 가져와 구조화 `brief`/`sources`/`plan`을 만들고 별도 의미 검토와 코드 검사를 거친다. 행동 버튼은 실제 조회·신청·예약·구매·설치 목적지를 확인한 `sources[].actions`만 사용한다.
3. 일반 신규 draft는 `sources` 뒤 구조화 원고가 완성되면 `prepare-draft`를 사용한다. 단계별 원인 진단이 필요한 Strict 작업만 `review/check/publish`를 분리한다. `publish bundle.json`은 **임시글 등록**이다. reviewed draft/public의 일반 수정은 `edit-post`를 기본으로 사용하며 이 상위 라우터가 대상 상태와 Fast/Standard를 자동 선택한다. `edit-draft`, `revise-draft`, `fast-revise-draft`, `update-existing`, `replace-featured-image`는 특정 경로를 진단하거나 레거시 호출을 유지할 때만 쓰는 저수준 호환 진입점이다. reviewed manifest가 없는 기존 evergreen legacy 초안을 사용자가 명시적으로 재작성 요청한 경우에는 같은 원본 SHA·현재 source·백업·검토 조건을 요구하는 `replace-legacy-draft`를 사용한다. Fast 경로는 `--edit-intent`에 이번 사용자 요청 범위를 명시해야 하며 새 숫자·날짜·지역·근거·CTA·제목·고위험 상태 주장을 발견하면 Standard 전체 검토로 전환한다. 짧은 기간의 dated legacy 글은 별도 정책 예외 없이는 `replace-legacy-draft`로 30일 기준을 우회할 수 없다.
4. **공개 전환은 사람의 글별 확인 후** `promote-draft <ID> --confirm-publish`만 사용한다. 명령어가 있어도 현재 공식 원문/원고 해시 및 검토가 불일치하면 차단된다. 보류한 글을 위해 WP-CLI 직접 편집이나 임시 PHP로 검사를 우회하지 않는다.

`scripts/prepare_post_approval.py`는 사용자가 아직 현재 변경안을 적용할지 검토하는 단계에서 변경 전후 비교 패키지를 만들기 위한 도구다. 같은 변경안의 실제 적용이 이미 명시적으로 승인된 뒤에는 이 패키지를 다시 만들지 않는다. 정규 `update-existing`/`revise-draft`/관련 updater가 자체적으로 최신 전체 inventory, 대상 글 CAS, 공식 source 재조회, 원본 백업, 저장 직전·직후 검증을 수행하므로 그 경로를 바로 사용한다. 승인 대상이나 변경안이 달라졌다면 새 승인으로 취급한다.

### 작성 모델 경로

- **서버 예약/자동 실행:** `main.py`가 `EditorialWriterAgent(writing_enabled=True)`를 사용한다. `editorial_policy.json`의 `writer_model` 및 `EDITORIAL_WRITER_MODEL`은 이 자동 작성 경로의 Gemini 모델 선택에 사용한다.
- **ChatGPT에서 사용자가 직접 집필을 요청한 경우:** 현재 ChatGPT 모델이 `sources` 이후의 구조화 `plan`을 작성한다. 별도 OpenAI API 호출은 필요하지 않는다. 완성한 bundle은 `manual-review`로 넘기며, 이 경로의 모델 어댑터는 `writing_enabled=False`라 Gemini 작성기가 원고를 다시 생성할 수 없다.
- 직접 작성 예: `python agent-publisher/editorial_cli.py manual-review bundle.json --author-model "GPT-5.6 Sol" --inventory inventory.json --output report.json`. 이후 필요하면 `check`로 결정론 검사를 확인하고 `publish`를 사용한다. `publish`는 **이미 bundle에 결합된 현재 독립 의미 검토가 있어야 하며**, Publisher 잠금 안에서 WordPress 전체 목록을 한 번 새로 동기화하고 현재 policy/content/review 결합을 다시 검사한 뒤 draft를 만든다. 같은 원고와 정책에 대해 AI 의미 검토를 다시 호출하지 않는다. 원고·정책·검토 신선도가 달라졌다면 publish가 차단되며 먼저 `manual-review`/`review`를 다시 수행한다.
- `manual-review`의 `--author-model`은 실제 대화에서 사용한 모델명을 기록하기 위한 필수 값이다. 이 값은 게시물의 `used_model` 메타데이터로 이어져 자동 Gemini 작성물과 직접 GPT 작성물을 구분한다.

한 세션에서 `EDITORIAL_SYSTEM.md`와 `editorial_policy.json`을 이미 읽었고 두 파일이 변경되지 않았다면 같은 작업자가 후속 문구·표·링크 수정 때 전체 문서를 다시 읽지 않는다. 새 worker는 자신의 최초 콘텐츠 작업에서 읽는다. 공통 정책 파일을 바꾼 작업과 콘텐츠 적용은 분리하고, 동시 작업이 공통 파일을 수정할 가능성이 있으면 전용 worktree에서 정책/코드를 먼저 안정화한 뒤 그 버전으로 review를 수행한다.

### 로컬 편집 코드 + 원격 WordPress 실행

운영 서버의 `editorial.py`, `editorial_cli.py`, 정책 문서를 매 작업마다 복사·교체한 뒤 서버에서 다시 review하는 방식을 기본 경로로 사용하지 않는다. 현재 로컬 checkout을 편집 코드의 정본으로 사용하고, 실제 WordPress 명령만 제한된 SSH transport로 전달한다.

- 신규 draft와 reviewed draft/public 수정은 모두 `scripts/editorial_cli_via_ssh.py`를 정규 원격 adapter로 사용한다. 기존 공개 글도 기본은 `-- edit-post ...`이며, 과거 `scripts/update_existing_via_ssh.py`는 예전 명령행 모양을 unified adapter의 `update-existing` 저수준 action으로 전달하는 호환 shim일 뿐 별도 transport를 유지하지 않는다.
- `revise-draft`, `fast-revise-draft`, `update-existing`, `replace-featured-image`, `update-draft`, `replace-legacy-draft`, `promote-draft`, `reformat`, `fix-excerpt`는 호환·진단용으로 계속 지원하지만 일반 작업에서는 상위 `prepare-draft`/`edit-post`를 우선한다. Direct SSH가 기본이며 Tailscale이 실제로 필요한 비상·복구 작업에서만 `--ssh-mode tailscale --ssh-host <private-host> --ssh-user ubuntu --wsl-distro Ubuntu-24.04`처럼 명시적으로 선택한다.
- 수동 편집 transport의 기본 모드는 항상 `direct`다. `BLOGUITO_SSH_HOST`, `BLOGUITO_SSH_USER`는 Direct SSH의 기본 접속값으로 사용할 수 있지만, `BLOGUITO_SSH_MODE=tailscale` 같은 지속 환경설정이 일반 작업을 Tailscale로 자동 전환하게 두지 않는다. WSL/Tailscale은 명령행 `--ssh-mode` 또는 기존 일회성 옵션으로만 선택한다.
- Direct SSH가 실패해도 공개 웹/REST 조회로 목적을 달성할 수 있으면 Tailscale로 전환하지 않는다. 서버 설정·Docker/WP-CLI·비공개 WordPress 상태처럼 SSH가 반드시 필요한 작업에서 Direct SSH가 불가능할 때만 Tailscale을 명시적으로 선택한다. Tailscale 경로를 선택한 뒤에도 `tailscale status/ping`을 선행 반복하지 않고 실제 SSH 실패 시 한 번만 진단한다. 읽기 명령은 필요할 때 1회 재시도할 수 있고, P2 guarded mutation은 서버가 전체 desired state를 확인하므로 SSH 255에서 최대 1회 replay한다. raw `post update`, `post create`, media import처럼 결과 유실 시 중복·불명확 상태를 만들 수 있는 mutation은 같은 재시도 의미론을 사용하지 않는다.
- 과거 서버에서 만든 reviewed draft의 manifest가 로컬 `agent-publisher/data/draft_posts.json`에 아직 없다면 **전환 시 1회만** `scripts/sync_editorial_state_via_ssh.py`로 기존 `draft_posts.json`/`published_posts.json`을 가져온다. 이 도구는 로컬 상태 파일이 하나라도 이미 존재하면 덮어쓰기를 거부한다. 이후 로컬 상태가 정본이므로 서버 파일을 다시 가져와 덮지 않는다.

이 구조에서 운영 서버 checkout의 버전이 로컬보다 오래됐다는 이유만으로 원고 review를 다시 수행할 필요가 없다. 반대로 실제 bundle, source, 정책 fingerprint, review 신선도가 달라졌다면 로컬 정본에서도 정상 검증이 차단되며 해당 review를 새로 해야 한다.

WordPress 전체 inventory는 schema v2에서 각 글의 `ID`, 제목, 상태, 본문 SHA256, 본문 URL signature만 수집한다. 신규 글의 URL 중복과 제목 중복은 이 경량 정보로 검사하고, 기존 글 수정에서 동일 공식 URL이 단순 출처인지 본문·CTA 중복인지 구분해야 할 때만 해당 후보 글의 본문을 단건 `post get`으로 추가 조회한다. 제한형 SSH transport는 inventory에서 관측된 후보 ID에 읽기 권한만 추가하며 mutation 대상 ID 집합은 확장하지 않는다.

내부 실사용 성능 기록은 `agent-publisher/data/editorial_runs/workflow-metrics.jsonl`에 JSONL로 쌓인다. unit test는 기본적으로 `workflow-metrics-test.jsonl`로 분리되며 각 행의 `run_context`가 `live`/`test`를 표시한다. `total_ms`, inventory/source/semantic-review 등 단계별 시간과 WordPress/source 요청 횟수, cache hit/fallback 같은 운영 카운터만 저장하고 원고·출처 본문은 기록하지 않는다. P4의 선택 regression 실행은 별도 `run-validation` action으로 profile/group/file/test 수와 `validation_tests` 시간·실패 수를 기록하므로 edit-post mutation latency와 섞지 않는다. 경로를 명시적으로 바꿀 때는 `EDITORIAL_METRICS_FILE`, context를 바꿀 때는 `EDITORIAL_METRICS_CONTEXT`를 사용한다.

반복 성능 분석을 위해 별도 임시 Python을 만들지 않는다. `python scripts/summarize_workflow_metrics.py --context live --status ok`를 사용하면 action별 실행 건수, median/P90 `total_ms`, 평균 WordPress 왕복, 단계별 평균 시간을 JSON으로 확인할 수 있다. 특정 action만 보려면 `--action edit-post`처럼 반복 지정한다.

### 일회성 작업 파일 정리

- 게시물 한 건의 HTML 조각을 넣거나 바꾸기 위해 `patch_post_<ID>_*.py`를 만들지 않고 `scripts/patch_post_component.py`를 사용한다. 이 도구는 로컬 파일 한 곳만 수정하며 target regex가 0건 또는 2건 이상이면 fail closed한다. WordPress 쓰기는 수행하지 않는다.
- 한 번만 필요한 조사·변환·검증 Python, 다운로드한 원문, 중간 bundle/HTML/이미지는 `scratch/tasks/<작업명>/`에 둔다. `scratch/`는 Git에 포함하지 않는다.
- 재현·사고 분석을 위해 one-off 코드를 보존해야 하면 작업 종료 후 `scripts/archive/<날짜 또는 작업명>/`로 이동한다. 새 archive 산출물은 Git에 넣지 않고 정규 도구처럼 호출하지 않는다.
- `scripts/` 루트의 Python 파일은 `scripts/maintained_scripts.json`과 정확히 일치해야 하며 unit test가 이를 검사한다. 두 번째 독립 사용 사례가 생긴 임시 도구만 명시적 인터페이스와 테스트를 갖춘 뒤 루트 도구로 승격한다.
- 자세한 규칙과 예시는 `scripts/README.md`를 따른다.

상세 인자와 제한은 [편집 규약](EDITORIAL_SYSTEM.md) 및 코드 [`editorial_cli.py`](../agent-publisher/editorial_cli.py)를 우선 확인한다. 과거 작업 기록의 '발행'은 draft 생성과 공개 승격을 혼용했으므로 명시적으로 구분한다.

## 백업·복구 및 운영 배포

- `backup_daily.sh`: v3 **코드**는 DB, uploads, plugins/themes/MU 플러그인, 설정, 별도 비밀 구성요소, manifest를 다룬다. 운영에서 v3가 정기 생성되는지, Nginx/TLS까지 복구 가능한지는 별도 확인한다.
- `restore_backup.sh <archive> --verify-only`: **데이터를 변경하지 않는** 해시·구조 확인. 구형 v2는 검증만 지원하고 전체 복원을 거부한다.
- `scripts/sync_backups.py`: 신뢰된 SSH 별칭/호스트키, 전후 해시, 임시 파일 검증 후 로컬 확정. 기존 백업을 건드리지 않는 다운로드라도 저장 경로의 권한과 여유 공간을 확인한다.
- v3의 `secrets.tar.gz`는 일반 압축이며 **암호화된 금고가 아니다**. 접근권한, 오프사이트 암호화·키 보관·독립 복구 계획 없이 완전 백업이라고 표현하지 않는다. 실제 격리 복원 범위와 호스트 단위 미검증 항목은 [2026-09-25 애플리케이션/데이터 복구 훈련](backup-restore-drill-2026-09-25.md)과 [2026-09-26 호스트 단위 DR 확장 훈련](host-disaster-recovery-drill-2026-09-26.md)의 PASS/PARTIAL/NOT TESTED 판정을 따른다.
- 운영 서버는 로컬 Compose와 `.env` 구성·systemd 설정이 다를 수 있다. **이미지 digest가 같다는 이유만으로 재생성할 필요는 없다.** 사전 해시·백업·비밀값 비노출 설정 확인, 스테이징 테스트, 서비스별 롤백 계획을 마련한 뒤 변경한다. WhatsApp 명령 검사에서 **유효한 `/publish`를 스모크 테스트로 보내지 않는다.**

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
- 플러그인 활성화, GA4/Site Kit, 공개/임시글 수, WhatsApp 실사용, 서치콘솔 지표는 저장소 문서만 보고 현재 상태·성능으로 단정하지 않는다.
- 작업마다 **기준 commit, 사전 변경 파일, 실제 변경/배포 범위, 테스트 결과, 서버 검증 여부, 미검증/롤백 지점**을 날짜별 기록에 남기고 [문서 안내](INDEX.md)에 편입한다. 개인식별자·API 키·DB 암호는 출력·Git·보고서에 기록하지 않는다.
- 같은 게시물이나 같은 기능의 후속 수정은 기존 작업 기록 MD의 새 날짜/절에 이어서 기록한다. 새 MD는 새로운 기능, 독립 장애, 배포, 아키텍처 변경처럼 별도 이력으로 찾을 가치가 있는 경우에만 만든다.
