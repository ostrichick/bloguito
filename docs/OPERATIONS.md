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

- 문서만 수정한 경우에는 `git diff --check`와 링크/문서 구조 확인으로 충분하며 전체 Python suite를 자동으로 반복하지 않는다.
- 구조화 원고의 사실·표·문구만 수정하고 공통 코드가 그대로라면 해당 bundle의 `manual-review`/`check`와 글별 저장 검증을 수행한다. 이미 같은 digest로 독립 의미 검토를 통과한 뒤 `check`만 다시 확인하는 경우에는 원고·정책이 실제로 바뀌지 않았는지 먼저 본다.
- 특정 source parser, action-link, schedule binding처럼 범위가 좁은 코드는 관련 테스트 파일을 우선 실행한다. 공통 renderer, validator, publisher, 정책 로직을 바꾼 경우에만 표적 테스트 뒤 전체 `agent-publisher/tests`를 1회 실행한다. 전체 suite 통과 뒤 공통 코드가 바뀌지 않았다면 원고나 문서 변경 때문에 같은 suite를 다시 실행하지 않는다.
- 화면 검증은 CSS/renderer/표·목차 구조가 바뀌면 360/390px, 데스크톱, 200% 확대와 키보드 접근까지 수행한다. 구조가 그대로인 본문 데이터 수정은 대표 모바일 1개와 데스크톱 1개에서 변경 영역을 확인하고, CTA 목적지만 바뀐 경우에는 실제 도착 화면과 버튼 smoke test를 우선한다.

## 원고 경로: 기본은 draft

1. 게시물 상태(공개·임시·예약·비공개)와 출처를 조회하고, 중복·검토 만료·정책 적용 연도를 검증한다.
2. 공식 근거를 가져와 구조화 `brief`/`sources`/`plan`을 만들고 별도 의미 검토와 코드 검사를 거친다. 행동 버튼은 실제 조회·신청·예약·구매·설치 목적지를 확인한 `sources[].actions`만 사용한다.
3. `editorial_cli.py sources/review/check`의 안내에 따라 검증 원고를 구성한다. `publish bundle.json`은 **임시글 등록**이다. 검토된 임시글의 행동 링크 등 renderer 소유 요소만 바꿀 때는 `update-draft`, 이미 검토된 사실·출처·CTA·제목을 그대로 유지하면서 표 재배치·중복 삭제·표현 다듬기만 할 때는 `fast-revise-draft`, 독립 재검토를 끝낸 본문 전체를 같은 초안에 교체할 때는 원본 SHA와 `--confirm-update`를 요구하는 `revise-draft`, reviewed manifest가 없는 기존 evergreen legacy 초안을 사용자가 명시적으로 재작성 요청한 경우에는 같은 원본 SHA·현재 source·백업·검토 조건을 요구하는 `replace-legacy-draft`, 명시적 승인된 기존 공개 글은 `update-existing`으로 구분한다. `fast-revise-draft`는 `--edit-intent`에 이번 사용자 요청 범위를 명시해야 하며, 새 숫자·날짜·지역·근거·CTA·제목·고위험 상태 주장을 발견하면 `FULL_REVIEW_REQUIRED`로 중단한다. 짧은 기간의 dated legacy 글은 별도 정책 예외 없이는 `replace-legacy-draft`로 30일 기준을 우회할 수 없다.
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

- 기존 공개 글 `update-existing`은 `scripts/update_existing_via_ssh.py`를 사용한다. 이 어댑터는 정규 updater의 inventory/source/CAS/백업/저장 후 검증을 그대로 사용하며 허용된 대상 ID의 WP 명령만 원격 실행한다.
- 신규 draft 생성과 기존 reviewed draft의 `revise-draft`, `update-draft`, `replace-legacy-draft`, `promote-draft`, `reformat`, `fix-excerpt`는 `scripts/editorial_cli_via_ssh.py`를 사용한다. 예: `python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- publish bundle.json`. WSL의 Tailscale 경로가 필요한 경우 `--ssh-user ubuntu --wsl-distro Ubuntu-24.04`를 추가한다.
- 수동 편집 transport는 매 작업마다 다시 선택하지 않고 `BLOGUITO_SSH_MODE=direct|wsl|tailscale`, `BLOGUITO_SSH_HOST`, `BLOGUITO_SSH_USER`, `BLOGUITO_WSL_DISTRO` 환경설정을 기본값으로 사용한다. 명령행 `--ssh-mode`/기존 WSL·Tailscale 옵션은 일회성 override로 남긴다.
- 위 SSH 어댑터들은 정상 경로에서 `tailscale status/ping`을 먼저 실행하지 않는다. exit 255가 발생하면 transport 인스턴스당 한 번만 상태를 진단한다. 읽기 명령과 `fast-revise-draft`의 동일 본문 update처럼 재실행이 멱등적인 경우에만 1회 재시도하며, `post create`처럼 중복 생성 위험이 있는 mutation은 자동 재시도하지 않는다.
- 과거 서버에서 만든 reviewed draft의 manifest가 로컬 `agent-publisher/data/draft_posts.json`에 아직 없다면 **전환 시 1회만** `scripts/sync_editorial_state_via_ssh.py`로 기존 `draft_posts.json`/`published_posts.json`을 가져온다. 이 도구는 로컬 상태 파일이 하나라도 이미 존재하면 덮어쓰기를 거부한다. 이후 로컬 상태가 정본이므로 서버 파일을 다시 가져와 덮지 않는다.

이 구조에서 운영 서버 checkout의 버전이 로컬보다 오래됐다는 이유만으로 원고 review를 다시 수행할 필요가 없다. 반대로 실제 bundle, source, 정책 fingerprint, review 신선도가 달라졌다면 로컬 정본에서도 정상 검증이 차단되며 해당 review를 새로 해야 한다.

WordPress 전체 inventory는 schema v2에서 각 글의 `ID`, 제목, 상태, 본문 SHA256, 본문 URL signature만 수집한다. 신규 글의 URL 중복과 제목 중복은 이 경량 정보로 검사하고, 기존 글 수정에서 동일 공식 URL이 단순 출처인지 본문·CTA 중복인지 구분해야 할 때만 해당 후보 글의 본문을 단건 `post get`으로 추가 조회한다. 제한형 SSH transport는 inventory에서 관측된 후보 ID에 읽기 권한만 추가하며 mutation 대상 ID 집합은 확장하지 않는다.

내부 성능 기록은 `agent-publisher/data/editorial_runs/workflow-metrics.jsonl`에 JSONL로 쌓인다. `total_ms`, inventory/source/semantic-review 등 단계별 시간과 WordPress/source 요청 횟수만 저장하고 원고·출처 본문은 기록하지 않는다.

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
