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

- **매일 새벽 04:00**: MariaDB 데이터베이스 자동 압축 백업 및 7일 롤링 보관 (`backup_daily.sh`)
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
