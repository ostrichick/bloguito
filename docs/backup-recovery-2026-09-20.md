# Bloguito 백업·복구 P2 개선 및 검증 — 2026-09-20

## 범위와 적용 상태

- 로컬 코드만 수정: `agent-publisher/backup_daily.sh`, `agent-publisher/restore_backup.sh`, `scripts/sync_backups.py`, `agent-publisher/tests/test_backup_recovery_v3.py`. 기존 미커밋 협업 파일은 변경하지 않았다. 커밋·푸시·운영 배포·운영 복원은 실행하지 않았다.
- 기존 운영 통합 아카이브는 **v2**이고 이번 변경으로 **새로 생성하는 아카이브부터 v3**가 된다. v2를 `--verify-only`로 검사할 수 있지만 WordPress 확장 파일이 없으므로 실제 전체 복원을 거부한다. 새 스크립트의 운영 배포나 운영 크론 반영은 아직 검증되지 않았다.

## 스냅샷 범위와 비밀정보

| v3 구성요소 | 포함 범위 | 복원 경로 |
|---|---|---|
| `db.sql.gz` | MariaDB `wordpress` 덤프 | 명시적으로 승인한 실제 복원 시 대상 DB에 입력 |
| `uploads.tar.gz` | `wp-content/uploads` | 대상 컨테이너의 같은 경로에 추출. 이후 생성된 오래된 파일은 자동 삭제하지 않음 |
| `wp-content.tar.gz` | `wp-content/plugins`, `themes`, 존재하면 `mu-plugins` | 기존 디렉터리를 비공개 `.bloguito-prerestore-*`로 옮긴 후 스냅샷 디렉터리로 교체. 기존 디렉터리는 수동 확인·정리 전까지 보존 |
| `configs.tar.gz` | Compose, MariaDB/PHP 설정 및 에이전트 런타임 JSON | 런타임 JSON은 실제 복원 시 적용. 기타 설정은 `--export-configs`로 별도 추출하고 검토 후 수동 설치 |
| `secrets.tar.gz` | 존재하는 `.env` 파일, `config.py`, 컨테이너의 `wp-config.php`(존재 시), 명시적으로 제공된 Nginx 설정 트리 | `--export-configs NEW_DIR --include-secrets` 요청 시에만 새 0700 디렉터리로 추출; 운영 자격증명·Nginx 설정 자동 덮어쓰기 없음 |

백업 폴더는 0700, 결과 아카이브는 0600으로 설정한다. `NGINX_CONFIG_DIR`는 사용자가 **사전에 검토한 절대 경로의 정규 파일 디렉터리**를 제공한 경우에만 캡처한다. 심볼릭 링크가 있으면 실패한다. 실제 `/etc/nginx`, TLS 인증서 및 개인키 전체가 자동으로 포함되는 것은 아니다. `.env`가 없는 환경에서는 기존 컨테이너 환경변수의 DB 자격증명 검색을 유지하며, 존재하지 않는 파일을 백업했다고 주장하지 않는다.

**잔여 기밀성 위험:** `secrets.tar.gz`는 별도 구성요소이지만 최종 `.tar.gz` 내부에 **암호화되지 않은 평문**으로 담긴다. 파일 권한만으로 유출된 아카이브나 Windows 백업 폴더의 ACL·동기화 서비스 측 복사본을 보호할 수 없다. 오프사이트 장기 보관 전 암호화, 독립 키 보관·키 복구 절차·접근 통제를 설계해야 한다. SHA256은 손상 검출이며 공격자가 아카이브와 manifest를 모두 바꿀 때 출처 진위를 증명하지 못한다. 서명/신뢰 앵커는 구현하지 않았다.

## 검사·복원 절차

```bash
# 프로덕션 데이터에 접근하지 않고 manifest SHA256, gzip 및 내부 경로 검사
./agent-publisher/restore_backup.sh /secure/path/bloguito_backup_YYYYMMDD_HHMMSS.tar.gz --verify-only

# 일반 설정만 신규 제한 디렉터리로 추출 (실서비스에는 반영하지 않음)
./agent-publisher/restore_backup.sh /secure/path/snapshot.tar.gz --export-configs /secure/new-review-dir

# 명시적으로 요청할 때만 비밀 설정도 신규 디렉터리로 추출
./agent-publisher/restore_backup.sh /secure/path/snapshot.tar.gz --export-configs /secure/new-private-dir --include-secrets

# 독립 테스트 환경에서만 사전 스냅샷·작업 중지 후 실제 복원을 검토
./agent-publisher/restore_backup.sh /secure/path/snapshot.tar.gz --yes
```

복원 전에 전체 아카이브의 필수 구성요소·크기·해시 및 내부 경로를 검증하고 경로 이동·링크를 거부한다. `--verify-only`는 DB 암호나 Docker를 요구하지 않는다. 실제 복원은 DB·업로드·확장 파일·에이전트 JSON을 순서대로 변경하므로 **단일 트랜잭션/무중단 복원이 아니다**. 스테이징 서버에서 서비스 중단, DB·업로드·테마·플러그인·사이트 로그인·사이트맵·미디어를 검증해야 한다. 기존 업로드를 덮어쓰기 방식으로 추출하므로 백업 시점 이후의 파일이 남을 수 있다. 호스트의 Compose/Nginx 설정과 인증서·도메인·소유권까지 자동 복구하지 않는다.

## 오프사이트 동기화

`python scripts/sync_backups.py`는 SSH 설정의 기본 별칭 `bloguito`를 사용한다. 필요하면 `BLOGUITO_BACKUP_SSH_HOST`, `BLOGUITO_BACKUP_REMOTE_DIR`, `BLOGUITO_BACKUP_LOCAL_DIR` 환경변수로 변경할 수 있다. 호스트키는 사용자가 **직접 지문을 확인하여 사전에 등록**해야 한다. SSH/SCP는 `BatchMode=yes`, `StrictHostKeyChecking=yes`로 연결하며 코드에는 서버 IP·개인 PC 키 위치를 저장하지 않는다. 원격 SHA256 확인 → 별도 `.part` 파일 다운로드 → 로컬 해시·원격 해시 재확인 → manifest/내부 tar 검사 → 같은 디렉터리에서 `os.replace` 순으로 확정한다. 기존 백업을 재사용할 때도 무결성을 재검사하고 실패 시 이전 파일을 보존한다. 다운로드 디렉터리/아카이브 파일 접근권한을 관리하고 Windows ACL은 별도로 점검한다.

## 검증한 사실과 미검증 항목

- 로컬 합성 백업: 실제 Docker 엔진 대신 테스트 함수로 DB/WordPress 아카이브를 제공해 v3 전체 5개 구성요소, Nginx 선택 포함, 일반 설정과 비밀정보의 분리 및 manifest 검증 성공.
- `test_backup_recovery_v3.py`: 총 **7개 통과**. v3 검증/설정 추출, 비밀정보 명시 선택, 해시 손상, 경로 이동/링크/잘못된 구성요소 경로 거부, 기존 설정 보호, 원자적 동기화/전송 실패 시 원본 보존, 호스트키 설정 확인. 기존 `test_backup_restore.py`의 **3개 통과**. Bash 구문 및 `git diff --check` 통과.
- 신뢰된 SSH 호스트 별칭을 통해 운영 서버에 **읽기 전용** 접근하여 2026-09-20의 기존 v2 통합 백업 **3개를 로컬 ignored `backups/`로 다운로드**. 각 원격 SHA256을 다운로드 전후 대조하고 로컬 아카이브/내부 구성요소를 검증하여 세 개 모두 성공. 운영 최신 v2 중 `bloguito_backup_20260920_185439.tar.gz`는 수정된 `restore_backup.sh --verify-only`도 성공. 원격 백업의 실제 DB/사이트 복원은 수행하지 않았다.
- **미검증:** 새로운 v3 스크립트의 운영 서버 정기 실행, 실제 WordPress 데이터의 격리 호스트 전체 복구, Nginx/인증서의 독립 호스트 재구축, 복구 후 글·미디어·플러그인 기능, 오프사이트 저장소 암호화·키 복구 및 사이트 중단 없는 복구 시간. 운영 서버 코드·서비스·크론 및 원본 백업에는 쓰기 작업 없음.
