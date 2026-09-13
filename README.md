# 📢 [Bloguito] 대한민국 생활정보 24 - AI 멀티 에이전트 자동화 블로그

본 디렉터리는 오라클 클라우드(OCI) 인스턴스에 구축된 **워드프레스 및 5대 멀티 에이전트 자율 포스팅 시스템('생활정보 24')**의 핵심 문서 및 프로젝트 저장소입니다.

---

## 📚 프로젝트 주요 문서 안내

| 문서 파일 | 설명 및 용도 | 바로가기 |
| :--- | :--- | :---: |
| **`PROJECT_HANDOVER.md`** | **종합 프로젝트 인계서 & 아키텍처 가이드**<br>- 서버 인프라, Docker 환경, 5대 에이전트 구조, 프롬프트 규칙, 크론 스케줄, 전체 히스토리 총정리 | [열기](./PROJECT_HANDOVER.md) |
| **`implementation_plan.md`** | **시스템 지능화 및 인프라 최적화 계획서**<br>- 긴급 버그 수정, 1GB RAM 튜닝, 내부 링크(Interlinking), 타이포 배너 설계 | [열기](./implementation_plan.md) |
| **`walkthrough.md`** | **종합 개선 및 최적화 완료 결과 보고서**<br>- 캐싱 가동, 백업 스크립트, DB 메모리 캡, 크론 등록 등 실서버 검증 내역 | [열기](./walkthrough.md) |

---

## 🖥️ 서버 접속 및 기본 정보

- **서버 공용 IP**: `<YOUR_ORACLE_SERVER_IP>`
- **블로그 주소**: `http://<YOUR_ORACLE_SERVER_IP>/`
- **관리자 페이지**: `http://<YOUR_ORACLE_SERVER_IP>/wp-admin/`
- **SSH 접속 명령어 (PowerShell)**:
  ```powershell
  ssh -i "<PATH_TO_SSH_KEY>/ssh-key.key" ubuntu@<YOUR_ORACLE_SERVER_IP>
  ```

---

## 🤖 5대 멀티 에이전트 파이프라인

```text
[1. Radar Agent]      구글 뉴스 RSS 실시간 탐색 및 중복 필터링 (키워드당 2개 버퍼)
       ↓
[2. Curator Agent]    Protobuf 암호화 링크 디코딩, 본문 추출, NOL 티켓 예매처 능동 가격 발굴
       ↓
[3. Copywriter Agent] Gemini 3.6 Flash 기반 팩트 100% 원고 집필 & 내부 링크(Interlinking) 자동 주입
       ↓
[4. Designer Agent]   1번 카드뉴스 인포그래픽 / 2번 4K 실사 스톡+매거진 타이포 배너 자동 교차 생성
       ↓
[5. Publisher Agent]  워드프레스 포스팅 등록, 특성 썸네일 장착, 내부 링크 색인 자동 누적
```

---

## ⏰ 자동화 스케줄 (KST 기준)

- **매일 새벽 04:00**: MariaDB DB + WordPress 미디어 업로드 + 에이전트 설정/런타임 데이터 통합 스냅샷 자동 백업 및 7일 롤링 보관 (`backup_daily.sh`)
- **매일 아침 08:00**: 3대 카테고리 자율 발행 파이프라인 무인 가동 (`run_daily.sh`)

---

## 🔐 로컬 개발 환경 준비

실제 API 키와 데이터베이스 비밀번호는 Git에 저장하지 않습니다. 예제 파일을 복사해 각 환경의 실제 값을 입력하세요.

```bash
cp agent-publisher/.env.example agent-publisher/.env
cp wordpress/.env.example wordpress/.env
```

- `agent-publisher/.env`: Gemini API 키, 글 상태(`draft` 권장), 사이트 주소를 설정합니다.
- `wordpress/.env`: MariaDB 루트 비밀번호와 WordPress용 DB 비밀번호를 설정합니다.
- 두 `.env` 파일은 `.gitignore` 대상입니다. 실제 값이 든 파일을 커밋하지 마세요.
- `wordpress/docker-compose.yml`은 필수 DB 비밀번호가 없으면 실행을 중단합니다. 예시 비밀번호로 실수로 서버가 시작되지 않습니다.

Python 3.12 가상환경과 의존성은 다음과 같이 준비합니다.

```bash
cd agent-publisher
python3.12 -m venv venv
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements.txt
```

Windows PowerShell에서는 다음 명령을 사용합니다.

```powershell
cd agent-publisher
py -3.12 -m venv venv
./venv/Scripts/python.exe -m pip install --upgrade pip
./venv/Scripts/python.exe -m pip install -r requirements.txt
```

Python 3.12가 먼저 설치돼 있어야 합니다. 의존성 목록은 현재 서버의 직접 사용 라이브러리 버전을 고정한 것이며, 전이 의존성 전체를 고정한 잠금 파일은 아닙니다. 전체 발행 프로그램은 Linux 경로, Docker/WP-CLI, 나눔스퀘어 폰트를 사용하므로 의존성 설치만으로 Windows에서 운영 서버와 동일하게 실행되지는 않습니다.

`agent-publisher/data/`의 실행 상태 JSON은 서버마다 달라 Git에서 제외합니다. `*.example.json` 파일은 형식 참고용입니다.

## 운영 서버 적용 시 주의사항

GitHub의 템플릿을 기존 서버에 적용하기 전, 서버의 `wordpress/.env`에 **현재 DB의 실제 비밀번호**를 설정해야 합니다. 이미 초기화된 MariaDB는 Compose 환경변수를 바꿔도 기존 비밀번호가 자동 변경되지 않습니다. 이번 변경은 비밀번호 교체 작업을 포함하지 않습니다.

백업 스크립트는 같은 `.env`를 Bash로 읽으므로 공백이나 `$` 등 셸 특수문자가 있는 값은 작은따옴표로 감싸세요. Linux 서버에서는 두 `.env` 파일의 권한을 `chmod 600`으로 제한하세요. 값이나 `docker compose config`의 전체 출력에는 비밀번호가 포함될 수 있으므로 공유하지 마세요. 설정 검사에는 `docker compose config --quiet`를 사용합니다.

실행 상태 JSON은 신규 설치 시 없어도 프로그램이 생성합니다. 기존 서버를 갱신할 때는 `.env`, `data/*.json`, WordPress 볼륨을 보존해야 합니다.

## NOL 상품 일치 검증 (유지보수 2단계)

`agents/ticket_validation.py`는 Gemini와 별도로 기사와 상품의 공연명·지역·공연일을 대조합니다. 검색 순서대로 첫 상품을 선택하던 방식에서, 중복을 제거한 후보들을 검사하고 **유일하게 일치하는 상품만** 선택하는 방식으로 변경했습니다. 공연명은 기사에 등장하는 대상명과 인용된 공연 부제·앵콜 등의 구분어를 비교합니다. 지역은 상품 제목과 공연장 모두에서 확인하고, 기사에 명시된 공연장이 있으면 그것도 대조합니다.

상품의 제목과 `#details` 내 일시·장소·티켓 필드만 사용합니다. 티켓 오픈일, 소개문과 추천 상품의 날짜·가격을 공연 정보로 사용하지 않습니다. 기사에서 연도를 확인할 수 없거나 공연일·지역이 여러 개면 추측하지 않습니다. 상품 페이지 조회 실패, 후보 8개 초과, 일치 상품 없음 또는 복수 일치는 `needs_review`로 보류하며 Copywriter가 Gemini 호출 전에 집필을 중단합니다. 생성된 원고의 NOL 상품 링크도 선택한 상품과 일치해야 합니다. 명시적으로 무료인 행사에는 티켓 판매처 링크를 넣지 못하게 검사합니다.

현재는 날짜가 명확한 단일 공연을 대상으로 하는 보수적인 검증입니다. 지역 목록에 없는 도시, 여러 날 공연, 투어 기사, 표기 차이가 큰 공연장은 검토가 필요할 수 있습니다. 대상명·일부 부제 비교는 모든 공연명을 완전히 식별하는 방법은 아닙니다. **판매 상태와 신청 기간을 독립적으로 확인하는 작업은 다음 3단계**이며, 검색의 판매중 필터만으로 실제 구매 가능성을 보장하지 않습니다.

프로젝트 루트의 Windows PowerShell에서 외부 API 호출 없이 회귀 테스트를 실행합니다. 현재 PC의 가상환경 이름은 `.venv`입니다.

```powershell
$env:PYTHONIOENCODING='utf-8'
./agent-publisher/.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests -v
```

테스트 HTML은 가상 데이터입니다. 2026-09-13에 31개 단위/회귀 테스트(NOL 티켓 28개 + 백업 3개)를 전수 통과했고 실제 NOL 페이지에 대한 읽기 전용 대조도 성공했습니다. 실제 뉴스 수집부터 Gemini 원고 생성·WordPress 발행까지의 전체 검증은 수행하지 않았습니다. 이 변경은 로컬 코드에 적용했으며 운영 서버 배포는 별도로 진행해야 합니다.
 
## 통합 백업 및 원클릭 복구 시스템 (유지보수 7단계)
 
`agent-publisher/backup_daily.sh`는 데이터베이스 단독 백업에서 **3대 핵심 자산 통합 스냅샷 백업**으로 전면 확대되었습니다:
1. **MariaDB 데이터베이스 (`db.sql.gz`)**: 워드프레스 전체 테이블 및 데이터 덤프.
2. **워드프레스 미디어 업로드 (`uploads.tar.gz`)**: 카드뉴스 썸네일, 타이포 배너, 본문 첨부 이미지.
3. **에이전트 설정 및 런타임 데이터 (`configs.tar.gz`)**: `config.py`, `data/*.json` (기사 중복 방지 이력 및 내부 링크 색인), Docker 설정 파일.
4. **체크섬 및 메타데이터 (`manifest.json`)**: SHA256 체크섬과 생성 시각, 컴포넌트별 바이트 크기 명세.
 
모든 컴포넌트는 단일 통합 아카이브 `bloguito_backup_YYYYMMDD_HHMMSS.tar.gz`로 원자적(Atomic) 묶음 압축되어 7일간 롤링 보관됩니다.
 
### 1) 수동 백업 실행
```bash
./agent-publisher/backup_daily.sh
```
 
### 2) 원클릭 복구(Restore) 실행
```bash
# 아카이브 체크섬 검증 및 대화형 복원
./agent-publisher/restore_backup.sh /home/ubuntu/backups/bloguito_backup_20260913_040001.tar.gz
 
# 프롬프트 없이 즉시 복원 (--yes)
./agent-publisher/restore_backup.sh /home/ubuntu/backups/bloguito_backup_20260913_040001.tar.gz --yes
```
복구 시 `manifest.json`의 SHA256 체크섬을 사전 대조하여 파일 변조나 손상이 감지되면 작업을 즉시 중단합니다.

## 기간·판매 상태 독립 검사 (유지보수 3단계)

`agents/temporal_validation.py`가 출처 텍스트의 명시적 필드(예: `신청기간: 2026.09.01 ~ 09.30`, `공연일시: 2026.12.25`, `판매상태: 판매중`)를 추출하고 코드로 검사합니다. `active`만 집필·발행을 허용하며 `closed`와 `needs_review`는 보류합니다. 시작 전 신청/판매, 지난 마감, 매진·취소·종료, 불명확한 연도, 잘못된 날짜, 상충하는 기간·상태는 통과시키지 않습니다. 날짜만 있는 마감은 한국시간 당일 끝까지 유효하고 시간이 명시되면 해당 시각을 적용합니다.

유료 NOL 공연은 선택된 상품 URL에서 가져온 판매 기간과 판매 상태를 모두 요구합니다. 검색 필터나 기사에만 적힌 판매중 문구는 근거로 인정하지 않습니다. 현재 파서는 상세정보의 명시적 필드를 읽으므로 판매 상태를 다른 방식으로 제공하는 페이지는 보류됩니다. 자연어만 있는 일정, 상시·예산 소진 시 종료, 복수 회차 등은 별도 파서 개선이 필요합니다. `active`는 수집 정보의 기간 검사 통과를 뜻하며 실시간 좌석 재고 보장은 아닙니다.

Curator가 출처 URL을 포함한 `temporal_source`를 전달하고 Copywriter가 집필 전에 재검사합니다. Publisher도 쓰기 직전에 현재 시간으로 다시 검사하며 계산된 `expires_at`을 기존 색인에 전달합니다. 발행 직전 재검사는 보관된 근거를 사용하며 웹페이지를 다시 조회하지 않습니다. Gemini의 적합 판정은 이 검사를 우회할 수 없고 JSON 응답에 적합 판정이 없으면 보류합니다.

프로젝트 루트에서 전체 회귀 테스트를 실행합니다. 현재 PC의 가상환경은 `.venv`입니다.

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH=(Resolve-Path './agent-publisher').Path
./agent-publisher/.venv/Scripts/python.exe -m unittest discover -s agent-publisher/tests
```

2026-09-13 전체 50개 테스트 통과. 외부 API 호출·운영 글 발행 없이 검사했으며 OCI 배포는 별도 작업입니다.

## 핵심 사실·출처와 원고 대조 (유지보수 4단계)

`agents/fact_validation.py`가 수집한 기사와 선택된 상품 상세정보를 `fact_manifest`로 구조화합니다. 출처 URL·유형·수집 시각·수집 텍스트의 SHA256, 사실별 ID·종류·값·발췌·문자 위치를 기록합니다. 수집 텍스트는 웹페이지 전체 HTML이 아닌 추출 본문/상품 상세정보이며 해시는 기록 무결성 검사이지 출처 진위 인증이 아닙니다.

명시적 필드의 일정·상태·장소·가격·지원금액·신청대상·조건·제외대상·방법·문의 등을 지원합니다. 공연은 일정·장소·가격, 다른 카테고리는 신청기간·대상·방법을 필수로 요구합니다. 다른 값의 핵심 사실이 함께 나오면 자동으로 하나를 선택하지 않고 보류합니다. 자연어에만 있는 사실은 현재 구조화 범위 밖이며 원문의 모든 사실을 자동 추출했다고 간주하지 않습니다.

자동 발행 원고는 **출처 제목 + 고정 안내문 + 모든 추출 사실과 출처 링크를 담은 표**로 제한합니다. 기존 장문·FAQ·STEP 생성 프롬프트를 제거했고 새 사실을 생성할 수 있는 태그는 빈 배열로 제한합니다. Gemini가 반환한 HTML의 구조·텍스트·행·링크가 검증 템플릿과 같아야 하며 가격/날짜/조건 변경, 사실 누락, 추가 문장, 허위 링크는 보류합니다. 통과 후에도 모델 HTML 대신 코드가 이스케이프한 표준 HTML을 발행합니다. 이 경로에서는 기존 내부 추천 삽입 함수를 호출하지 않으며 색인/추천 함수는 유지됩니다. 자유로운 장문 설명을 재개하려면 별도의 의미 검증과 검토 절차가 필요합니다.

Copywriter와 Publisher 양쪽에서 원문 기록으로 manifest를 재생성해 대조하고 기간 검사 근거도 같은 출처 기록 전체와 일치해야 합니다. 발행 색인의 `fact_manifest`에 근거를 보관합니다. 출처 자체의 오류·본문 추출 누락·실시간 정보 변경까지 보장하는 검사는 아닙니다.

2026-09-13 전체 회귀 테스트 61개 통과. 외부 API 호출 없이 Gemini의 구조화 응답과 JSON 응답 경로를 모의 검증했습니다. 운영 서버 배포 및 실제 뉴스부터 발행까지의 검증은 별도로 필요합니다.
