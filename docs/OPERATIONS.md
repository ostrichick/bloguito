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

## 원고 경로: 기본은 draft

1. 게시물 상태(공개·임시·예약·비공개)와 출처를 조회하고, 중복·검토 만료·정책 적용 연도를 검증한다.
2. 공식 근거를 가져와 구조화 `brief`/`sources`/`plan`을 만들고 별도 의미 검토와 코드 검사를 거친다. 행동 버튼은 실제 조회·신청·예약·구매·설치 목적지를 확인한 `sources[].actions`만 사용한다.
3. `editorial_cli.py sources/review/check`의 안내에 따라 검증 원고를 구성한다. `publish bundle.json`은 **임시글 등록**이다. 기존 원고 갱신은 `update-draft`(검토된 임시글), `update-existing`(명시적 승인된 기존 공개 글)로 구분한다.
4. **공개 전환은 사람의 글별 확인 후** `promote-draft <ID> --confirm-publish`만 사용한다. 명령어가 있어도 현재 공식 원문/원고 해시 및 검토가 불일치하면 차단된다. 보류한 글을 위해 WP-CLI 직접 편집이나 임시 PHP로 검사를 우회하지 않는다.

### 작성 모델 경로

- **서버 예약/자동 실행:** `main.py`가 `EditorialWriterAgent(writing_enabled=True)`를 사용한다. `editorial_policy.json`의 `writer_model` 및 `EDITORIAL_WRITER_MODEL`은 이 자동 작성 경로의 Gemini 모델 선택에 사용한다.
- **ChatGPT에서 사용자가 직접 집필을 요청한 경우:** 현재 ChatGPT 모델이 `sources` 이후의 구조화 `plan`을 작성한다. 별도 OpenAI API 호출은 필요하지 않는다. 완성한 bundle은 `manual-review`로 넘기며, 이 경로의 모델 어댑터는 `writing_enabled=False`라 Gemini 작성기가 원고를 다시 생성할 수 없다.
- 직접 작성 예: `python agent-publisher/editorial_cli.py manual-review bundle.json --author-model "GPT-5.6 Sol" --inventory inventory.json --output report.json`. 이후 `check`와 `publish`를 사용한다. `publish`는 현재 공식 원문과 WordPress 목록을 다시 검사하고 독립 의미 검토를 새로 수행하지만 원고 작성기를 호출하지 않으며, 등록 상태는 draft다.
- `manual-review`의 `--author-model`은 실제 대화에서 사용한 모델명을 기록하기 위한 필수 값이다. 이 값은 게시물의 `used_model` 메타데이터로 이어져 자동 Gemini 작성물과 직접 GPT 작성물을 구분한다.

상세 인자와 제한은 [편집 규약](EDITORIAL_SYSTEM.md) 및 코드 [`editorial_cli.py`](../agent-publisher/editorial_cli.py)를 우선 확인한다. 과거 작업 기록의 '발행'은 draft 생성과 공개 승격을 혼용했으므로 명시적으로 구분한다.

## 백업·복구 및 운영 배포

- `backup_daily.sh`: v3 **코드**는 DB, uploads, plugins/themes/MU 플러그인, 설정, 별도 비밀 구성요소, manifest를 다룬다. 운영에서 v3가 정기 생성되는지, Nginx/TLS까지 복구 가능한지는 별도 확인한다.
- `restore_backup.sh <archive> --verify-only`: **데이터를 변경하지 않는** 해시·구조 확인. 구형 v2는 검증만 지원하고 전체 복원을 거부한다.
- `scripts/sync_backups.py`: 신뢰된 SSH 별칭/호스트키, 전후 해시, 임시 파일 검증 후 로컬 확정. 기존 백업을 건드리지 않는 다운로드라도 저장 경로의 권한과 여유 공간을 확인한다.
- v3의 `secrets.tar.gz`는 일반 압축이며 **암호화된 금고가 아니다**. 접근권한, 오프사이트 암호화·키 보관·독립 복구 계획 없이 완전 백업이라고 표현하지 않는다. 새 v3 전체 격리 복구·로그인·글·미디어·플러그인/테마·사이트맵은 마지막 작업 기록에서 미검증으로 남았다.
- 운영 서버는 로컬 Compose와 `.env` 구성·systemd 설정이 다를 수 있다. **이미지 digest가 같다는 이유만으로 재생성할 필요는 없다.** 사전 해시·백업·비밀값 비노출 설정 확인, 스테이징 테스트, 서비스별 롤백 계획을 마련한 뒤 변경한다. WhatsApp 명령 검사에서 **유효한 `/publish`를 스모크 테스트로 보내지 않는다.**

세부 구현·명령·검증 근거는 [백업 기록](backup-recovery-2026-09-20.md)과 [배포 준비 기록](implementation-execution-2026-09-20.md) 참고. 두 문서의 '당시 미배포'는 이후 배포 여부를 증명하지 않으므로 현재 상태를 다시 관측한다.

## 운영 확인과 이력 남기기

- WordPress 관리 글 목록의 ID 열은 [2026-09-21 적용 기록](admin-post-id-column-2026-09-21.md)에 서버 반영과 WP 후크 검사 결과가 있다. 로그인 브라우저 UI 검사는 당시 수행하지 않았다.
- 백업 크론 `04:00`, 초안 생성 `08:00`(KST)은 2026-09-20에 관측된 기록이며 현재 스케줄은 서버 `crontab -l`로 재확인한다.
- 플러그인 활성화, GA4/Site Kit, 공개/임시글 수, WhatsApp 실사용, 서치콘솔 지표는 저장소 문서만 보고 현재 상태·성능으로 단정하지 않는다.
- 작업마다 **기준 commit, 사전 변경 파일, 실제 변경/배포 범위, 테스트 결과, 서버 검증 여부, 미검증/롤백 지점**을 날짜별 기록에 남기고 [문서 안내](INDEX.md)에 편입한다. 개인식별자·API 키·DB 암호는 출력·Git·보고서에 기록하지 않는다.
