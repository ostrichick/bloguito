# Bloguito 우선순위 1–5 개선 실행 결과 (2026-09-20)

## 작업 기준과 변경 범위

- 기준: `main` / `ddd86c7`. 작업 시작 당시부터 수정되어 있던 `agent-publisher/agents/curator.py`, `agents/publisher.py`, `tests/test_editorial_system.py`, `tests/test_ticket_validation.py`와 미추적 `docs/project-optimization-audit-2026-09-20.md`는 이번 단계의 별도 작업으로 취급하고 변경 내용을 덮어쓰거나 이번 커밋 대상으로 섞지 않는다.
- 본 단계는 로컬 코드·문서·검증 및 운영 서버에 대한 **읽기 전용** 상태 조회와 기존 백업 다운로드를 수행했다. 운영 WordPress의 글·DB·크론·서비스·인증 정보는 수정하지 않았고 글 공개·서비스 재시작·배포·실제 DB 복원을 실행하지 않았다.
- 상세 백업 증거는 `backup-recovery-2026-09-20.md`, 편집 내용/검토 보류는 `editorial-improvements-2026-09-20.md` 참조.

## 우선순위별 구현 결과

1. **WhatsApp 명령·권한 통제 (로컬 완료, 운영 미적용):** `whatsapp-bridge/command_policy.js`, `index.js`에서 허용 명령을 정확히 `/publish <양의 정수 ID>`로 제한했다. 발신자가 자기 자신일 때도 자기 계정의 셀프 채팅에서만 허용하고, 다른 사용자로 보내는 자기 메시지·그룹·과거 재동기화 메시지는 거부한다. 외부 관리자는 명시적으로 등록된 숫자 JID/LID만 허용한다. 인증 디렉터리/기존 일반 파일은 실행 시 0700/0600, 생성 QR 0600, 프로세스 umask 077. `command_policy.test.js` 3개 회귀 테스트와 Node 구문 검사 통과. 공개용 CLI의 기존 검토 게이트는 그대로 유지한다.
2. **백업·복구 (로컬 완료, 운영 v3/전체복원 미검증):** v3는 DB·업로드·WordPress 플러그인/테마/MU 플러그인·비밀정보 제외 설정·비밀정보 별도 구성요소를 해시로 검증한다. 복구 명령은 DB 자격증명 확인 전에 v2/v3 구조·해시·gzip/중첩 경로를 검증하며 v2의 전체 복원을 거절하고 설정·비밀정보는 신규 제한 폴더에 선택적으로만 내보낸다. 오프사이트 동기화는 호스트키 검사·전송 전후 SHA·임시 다운로드 검증·원자적 이동을 사용한다. 실제 서버의 기존 v2 백업 3개를 **읽기 전용으로 다운로드**해 각각 무결성 검증 통과, 최신 v2는 `--verify-only` 통과. **v3 생성 후 실물 독립 복원은 하지 않았다.**
3. **썸네일 근거 없는 주장 제거 (로컬 완료):** 디자이너 기본 생성 텍스트를 검토된 원고 제목·카테고리·사이트 브랜드만으로 제한하고 무근거 금액·혜택·일정·기관 인증 배지 및 curator의 임의 텍스트 삽입을 삭제했다. 원고와 검토 근거 연결이 없는 포스터 URL은 자동으로 사용하지 않는다. 별도 검토한 포스터 URL을 명시적 인자로 넘기는 경로는 있지만 현행 `main.py`는 넘기지 않는다. 관련 디자이너 17개 테스트 통과. 이미지 원본에 이미 들어 있는 문구나 원고 제목 자체의 진위는 이 변경만으로 보증되지 않는다.
4. **배포/CI 재현성 (로컬 완료, 서버 재생성 금지 상태):** 실제 운영에서 관측한 Linux amd64 WordPress 이미지 digest `sha256:5a93c470ae8220fddf71f6ebe3bc94e615ddc2ae4d9810f795b830fb11c41a17`, MariaDB digest `sha256:07c0aaff7396b74cb7975cba78257178d188e30f531a5db2b617c48beef13c41`와 `127.0.0.1:8080:80` 포트를 로컬 Compose에 명시했다. npm 잠금 파일 추가, CI에 Node 구문/명령 단위 테스트와 Bash/Compose 정적 검사 추가. 최신 버전 무조건 pull·WP 초기화 스크립트·`down -v`는 실행하지 않았다.
5. **편집 원고·검사 품질 (로컬 사본 완료, 발행 보류):** 11개 구형 임시글 사본의 일반적인 독자 전가 안내·내부 편집 메모를 제거하고 출처·구체 조건을 유지했다. manifest의 로컬 SHA256 11개 갱신, 여전히 전부 `draft`/`human_final_review_required`. 구조화 원고에서 명백한 내부 편집 메모를 차단하는 좁은 검사와 테스트 2개 추가. 특정 정책의 최신 시행연도·지역 적용이나 의미상 중복은 공식 메타데이터/사람의 검토 없이 자동 판정할 수 없어 기존 게이트 유지; 이를 해결했다고 주장하지 않는다.

## 최종 로컬 검증

- 프로젝트 venv, `PYTHONPATH=agent-publisher`, `PYTHONIOENCODING=utf-8`: `python -m unittest discover -s agent-publisher/tests -q` → **154개 OK**. 백업 테스트는 합성 Docker와 실패 시나리오를 사용하며 실제 서버를 복원하지 않는다. 일부 기존 테스트는 Python 3.14 `tarfile.extractall` 관련 deprecation warning을 출력하지만 실패는 없었다.
- WhatsApp `npm ci --ignore-scripts --no-audit --no-fund` 및 `npm test` → 명령·권한 테스트 **3개 OK**. `node --check index.js`/`command_policy.js` 통과.
- Git Bash `bash -n agent-publisher/backup_daily.sh agent-publisher/restore_backup.sh` 및 Docker Compose `config --quiet` (더미 DB 환경변수) 통과. `git diff --check` 통과; Windows에서 Git의 LF/CRLF 변환 예정 경고는 있으나 whitespace 에러는 없다.
- 운영 read-only: WordPress 현재 실행 이미지 digest/포트 관측 일치, WhatsApp 서비스 실행 중. 실제 WhatsApp 두 계정 연결/명령 및 전체 운영 사이트 E2E는 테스트하지 않았다.

## 운영 배포 NO-GO: 충족해야 할 선행 조건

- **WhatsApp:** 운영 `index.js`는 과거의 넓은 명령 검사를 사용하고 내부에 기존 관리자 식별자 설정이 있다. 운영에는 새 `command_policy.js`, bridge `.env`, systemd owner EnvironmentFile 설정이 없다. `index.js` 하나만 배포하면 모듈 미존재로 시작 실패하고, 새 정책만 넣으면 기존 외부 관리자 명령이 차단될 수 있다. 운영 자격증명 파일/디렉터리 권한도 0664/0775로 개선이 필요하다. 기존 인증·설정·코드 백업, 비밀값 노출 없는 관리자 설정 이전, 전체 파일 동시 배포, 격리 의존성 설치 시험, 롤백 및 `/help`·`/status`만으로 실사용 확인 후 적용해야 한다. **유효한 `/publish` 명령은 테스트로 사용하지 않는다.**
- **WordPress:** 현재 운영 Compose는 일부 DB 비밀정보가 인라인인 반면 새 로컬 Compose에는 필수 `MYSQL_ROOT_PASSWORD`/`MYSQL_PASSWORD` 환경변수가 필요하고 서버 `wordpress/.env`가 존재하지 않는다. 관측된 실행 이미지 자체는 새 pin과 같아 재시작할 필요가 없다. 민감정보를 보호한 별도 `.env` 생성, 실제 유효 환경과 서비스/볼륨 매핑 비교, 독립 복원 확인 전 `docker compose up`, recreate, setup.sh 등을 실행하지 않는다.
- **백업 비밀정보:** v3의 `secrets.tar.gz`는 별도 구성요소지만 최종 아카이브 내부에서 **평문**이다. 파일/디렉터리 권한은 암호화를 대체하지 못한다. 전송·장기보관 암호화, 독립 키 수탁/복구, Windows ACL 및 원본 백업 진위 확인이 남아 있다. Nginx/TLS는 명시적으로 검토된 디렉터리 외 자동 완전 백업되지 않는다.
- **실제 독립 복원 및 품질:** v3 아카이브로 격리 WordPress를 띄워 로그인·글·이미지·플러그인·설정을 대조하지 못했다. 기존 11편은 별도 사람의 최신 공식근거 확인과 구조화 검토 전 공개할 수 없다.

## 안전한 후속 반영 절차

1. 현재 서비스와 백업의 버전·해시를 기록하고 제한된 별도 디렉터리에 배포 전 스냅샷을 보존한다. 정상 동작 중인 WhatsApp auth를 잘못된 과거 credentials로 롤백하지 않는다.
2. 실서비스를 건드리지 않는 스테이징에서 bridge 전체 파일/환경 로딩/잠금 의존성 설치를 검증한다. 관리자 번호는 로그·셸 히스토리·Git에 출력/저장하지 않고 보호된 환경 파일과 systemd drop-in으로 이전한다.
3. 기동/비공개 명령 스모크 테스트와 즉시 롤백 계획 확인 후 WhatsApp만 별도 작업 창에서 반영한다. 새 WordPress Compose는 유효 비밀정보와 복구 준비가 될 때까지 실서비스에 적용하지 않는다.
4. v3 생성/암호화와 독립 복원, 기존 구형 초안의 사람 검토가 통과한 뒤 백업 크론과 편집 파이프라인을 각각 반영한다. 배포 및 실서비스 검증 결과는 새 날짜/작업 기록에 별도로 작성한다.
