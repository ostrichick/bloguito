# 공개 글 반복 감사: 스케줄 등록 전 승인 패키지 — 2026-09-22

## 준비된 기능과 아직 승인받지 않은 운영 경계

`scripts/audit_legacy_posts.py`에 기존 일회성 감사 옵션을 보존하면서 **한 번만 실행하는 반복 모드** `--recurring-state-dir`를 추가했다. 스케줄을 자동 설치하는 코드는 없고, WP 인증·글 수정·메시지 전송·예약 게시·테마 수정이 없다. 일반 실행은 **익명 공개 WordPress REST `GET /wp-json/wp/v2/posts`**로 게시물 전체를 수집하여, 지정한 로컬 전용 폴더에 원본/보고/요약을 저장한다. `--dry-run`은 동일한 공개 REST 조회와 이전 성공본 비교·요약까지 하지만 로컬 폴더·잠금·체크포인트도 **생성·변경하지 않는다**. 이번에는 **실제 공개 사이트에 dry-run만 실행**했으며 운영 모드, Task Scheduler, cron, GitHub Actions, 알림 송신은 실행하지 않았다.

**범위:** 현재 공개된 `publish` 게시물의 REST 출력 HTML만 다룬다. 임시·예약·비공개·페이지·WordPress DB 원본은 제외된다. `rendered_sha256`은 REST 관측 HTML의 변경 감지용이지 `editorial_cli.py update-existing`에 필요한 DB 원본 `post_content` SHA가 아니다. 수집의 `complete=true`는 응답 페이지 헤더/개수·고유 ID의 일관성이지 게시 도중의 데이터베이스 트랜잭션 일관성이나 사실 검증 인증이 아니다. 모든 글의 사실·실제 레이아웃·외부 링크 기능은 계속 `unverified`이다.

## 읽기 전용 실행 문법

프로젝트 루트 Windows PowerShell에서 `.venv`와 명시적 읽기 전용 실행을 사용한다. 아래 `tmp/legacy_audit_20260922/audit-worker3/recurring`은 감사 전용 새 폴더 예시이며 **현재 운영 스케줄 목적지로 등록하지 않았다**.

```powershell
$env:PYTHONPATH=(Resolve-Path './agent-publisher').Path
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONDONTWRITEBYTECODE='1'

# 승인 전 허용된 공개 REST 조회 드라이런: 폴더, 스냅샷, 잠금을 만들지 않는다.
./agent-publisher/.venv/Scripts/python.exe -B scripts/audit_legacy_posts.py `
  --recurring-state-dir tmp/legacy_audit_20260922/audit-worker3/recurring `
  --dry-run
```

**이하 명령은 향후 명시적인 운영 승인 이후에만 사용하는 문법 설명이며, 이번 작업에서 실행하지 않았다.** OS 스케줄러에 등록되는 별도 명령은 제공하거나 실행하지 않는다. 한 번의 반복 실행과 실패/변경 시 종료 상태 해석을 위한 명령 예시는 다음과 같다.

```powershell
# 승인 후에만: 한 번 실행하고 완전한 로컬 스냅샷 저장.
./agent-publisher/.venv/Scripts/python.exe -B scripts/audit_legacy_posts.py `
  --recurring-state-dir tmp/legacy_audit_20260922/audit-worker3/recurring `
  --expected-hours 24 --retain 14 --strict-alert
```

옵션 `--expected-hours`는 1~744시간, `--retain`은 완전한 실행본 2~365개다. `--review-register`에는 **별도로 사람이 사실·공식 근거·시의성을 검증하고 `human_verified`를 기록한 JSON**만 사용한다. `docs/legacy-audit-automation-2026-09-22.md:40-62`에 스키마가 있다. 보안·무인 운영상 검토자 서명이나 위변조 방지 시스템은 아직 없다. 이 레지스터를 전달하지 않으면 `review_due`는 모든 글에서 `null`이고, 자동감사를 통과했다는 이유로 사람이 검토했다고 간주하지 않는다.

## 상태·파일의 수명 및 장애 복구

전용 폴더에는 `.bloguito-read-only-audit.json`이라는 소유 마커가 있어야 하며, 같은 사이트·스키마만 다시 사용한다. **내용이 있는 임의의 비표시 폴더를 채택하거나 프로젝트·`wordpress`·`agent-publisher`·`scripts`·`docs`·`.git` 안을 상태 디렉터리로 사용하지 못하도록 차단**한다. 정기 모드의 출력 구조는 다음과 같다.

```text
<승인된 전용 로컬 상태 폴더>/
  .bloguito-read-only-audit.json   # 스키마, 공개 사이트, 전용 소유 마커
  latest.json                      # 마지막 완전 성공본만 가리키는 원자적 포인터
  last-attempt.json                # 마지막 시도 complete/failed, 실패 시 에러 종류만
  runs/<UTC시각>-<무작위8자리>/
    public-rest-snapshot.json      # 공개 REST 원본 HTML·메타데이터 전체
    triage.json                    # 구조/후보/변경/재검토기한
    report.md                      # 사람 검토용 표
    alert-summary.json             # 발송하지 않는 기계 판독 알림 요약
```

- **수집 실패 전부 차단:** 누락된 `X-WP-Total/X-WP-TotalPages`, 총수·페이지 수 불일치, 중간 페이지 빈 결과, HTTP 503, 중복 ID, 비공개 글, JSON 오류는 중단한다. 부분적인 새 체크포인트를 게시하지 않는다. 모든 파일을 `.pending-...` 임시 실행 폴더에 먼저 기록한 뒤 완성 실행 폴더 이름으로 바꾸고, **실제 저장된 바이트의 SHA256**를 구해 `latest.json`을 가장 나중에 원자적으로 변경한다. Windows의 줄바꿈 변환 때문에 문자열 SHA와 실제 저장 바이트가 달라질 수 있는 문제를 테스트로 발견해 실제 저장 바이트 해시로 수정했다.
- **실패 기록:** 데이터 수집 중 예외 발생 시 이전 `latest.json`은 그대로 두고 `last-attempt.json`에는 `status=failed`, 단계, Python 예외의 **유형 이름만** 기록한다. 웹 URL/쿼리/비밀번호나 traceback을 JSON 또는 CLI stdout에 기록하지 않는다. `--strict-alert` 유무와 관계없이 실패 종료 코드는 **3**이다. 파일시스템 자체의 장애로 실패 기록도 기록되지 않을 수 있으므로 감독 측은 **프로세스 종료 코드와 마지막 실행 시각을 함께 확인**해야 한다.
- **중복 실행 방지:** `.audit.lock` 전용 디렉터리를 원자적 mkdir 방식으로 획득하고 현재 PID/시각/실행 ID만 기록한다. 잠긴 상태에서는 실행을 거부하고 기존 잠금을 삭제하지 않는다. 강제 종료/컴퓨터 재부팅 뒤 잠금이 남으면 운영자는 실제 해당 실행 프로세스 부재·실행 중 출력·PID 등을 확인하고 **사람 승인하에 해당 잠금만** 정리해야 한다. 다른 작업자의 잠금을 강제로 열거나 자동으로 만료 처리하지 않는다.
- **체크포인트 신뢰:** 재시작 시 성공 포인터의 사이트·스키마·UUID 형태·SHA256·전체 공개 REST 스키마/건수/중복을 다시 검사한다. 손상된 포인터·해시 불일치, `.pending` 미완성 실행본, 성공 포인터 없이 남은 runs는 **자동 복구하지 않고 중단**한다. 배포 담당자가 해당 상태를 별도로 검증·백업 후 정리해야 한다. 성공 포인터 교체 뒤의 실제 전원 장애·NTFS 물리적 내구성까지 보증하는 fsync 구현은 아니다.
- **보존과 유실 방지:** `--retain 14`는 정상 실행 후 이 도구가 만든 정규 실행 ID 폴더만 오래된 순으로 정리하며 **최신 포인터의 실행본은 무조건 보존**, 최대 14개의 완전 실행본을 유지한다. `.pending`, 알 수 없는 폴더나 심볼릭 링크, 다른 작업자의 파일은 삭제 대상으로 취급하지 않는다. 이상 폴더를 만나면 보존 정리 중단/주의 요약으로 남긴다. 출력 폴더 보안/디스크 용량과 14회 이전 장기 보관은 별도의 운영 승인 범위다. 비공개 원문은 수집하지 않지만 공개 HTML에 노출된 이메일/링크 등이 스냅샷에 들어 있으므로 작업 계정 전용 권한/백업 보안이 필요하다.

## 한 번의 실행이 알려주는 것과 알려주지 못하는 것

`alert-summary.json`과 stdout의 JSON에는 공개 글 수, 신규 ID, 본문 SHA/수정일/제목/URL 중 변경 필드, 과거 공개 목록에서 사라진 ID(삭제 원인 **미확인**), 별도 인간 검토 레지스터 기준 도래 ID 및 미등록 수, 모든 구조 후보 건수, **직전 성공 대비 새롭게 나타난 플래그만** ID별로 수록한다. 첫 기준점 실행에서 이미 있던 구형 레이아웃 25건을 전부 “새 오류”로 경보하지 않도록 했다. 마지막 성공과 이번 실행의 시간 차이를 `--expected-hours`로 비교해 누락된 *예상 실행 횟수*를 계산하고, 마지막 시도가 실패했다가 이번에 성공했으면 복구 경보도 포함한다. 시간 차이만으로 실패 원인을 파악하거나 실행하지 않는 동안 즉시 알림을 보낼 수는 없다.

| 코드 | 의미 | 알림 방식 |
| --- | --- | --- |
| `public_inventory_changed` | 새 글·기존 글 변경·공개 목록 이탈 | JSON/종료코드만, 실제 알림 전송 없음 |
| `review_due` | 별도 인증 레지스터와 현재 공개 HTML 해시 기준 기한 도래/본문 변동 | 같은 방식 |
| `new_layout_source_or_review_candidates` | 기준점 이후 새로 발견된 휴리스틱 플래그 | 후보이며 실제 오류 인증 아님 |
| `missed_expected_runs` | 지난 성공 대비 기대 주기를 초과 | 다음 실행이 있을 때만 감지 |
| `recovered_prior_failure` | 직전 실패 기록 후 이번 성공 | 실패 중에는 외부 감독기가 종료 코드 3 확인 필요 |
| `retention_requires_attention` | 과거 스냅샷 정리 오류 | 최신 완전 스냅샷은 남김 |
| `audit_failed` | 수집/체크포인트/잠금/검증 중 실패 | CLI JSON에 Python **예외 종류만**, 종료 3 |

정상 수집에 변경 등 경보가 있어도 기본 종료 코드는 **0**이고 `--strict-alert`를 직접 지정한 경우 `attention_required=true`에 **2**, 실패에는 **3**을 반환한다. **종료 코드 2는 감사 실패가 아니라 검토할 변경 존재**라는 점을 감독 측에서 분기해야 한다. JSON에는 `alert_codes`만 기록하며 이메일·Slack·카카오·SMS·WhatsApp API 호출과 알림 수신자 설정 코드는 **전혀 없다**.

## 실제 수행한 비운영 검증

- 기존 `test_legacy_post_audit.py` 9건에 다중 실행 시나리오 **5건을 추가**, 표적 단위검사 **14건 통과**(최종 0.266초, 종료 0). 별도 테스트 fixture의 임시 폴더에서만 완전 실행 모드를 시험했다. 동작검사 항목: dry-run byte-free, 실제 본문 변경 감지, 25시간·50시간 누락 감지, 2개 스냅샷 보존, 별도 검토기한 도래, 중복 잠금/손상 SHA 중단, HTTP 503 및 **101건 중 2페이지 503**일 때 마지막 성공 포인터·기존 데이터 유지, 직전 실패 복구, 예외 메시지에 URL 비밀이 있어도 CLI 출력에 유출하지 않는 동작.
- `scripts/audit_legacy_posts.py`와 전용 테스트의 `compile(...,'exec')` **문법 검사 2개 통과**, `.pyc` 의도적 쓰기 없음.
- 실제 공개 REST `--dry-run` 실행 관측: **2026-09-22 13:05:53 KST**, 공개 게시물 **30편** 완전 수집, 종료 코드 **0**, 첫 기준점 미존재, 검토기한 미확인 **30편**, 기존 구조 후보 `legacy_layout=25`, `missing_toc_candidate=25`, `source_section_missing_candidate=12`, `box_paragraph_spacing_candidate=14`, `reader_deflection_candidate=1`. 실행 직후 `DRY_RUN_STATE_CREATED=False` 확인. 이 첫 실행에서는 기준점 부재로 “변경 0”이 실제 변화가 없다는 뜻이 아니라 비교할 과거 검증본이 없다는 의미다. 첫 실행 때 기존 플래그를 전부 `new_flags`라고 잘못 알리던 과탐지는 관측 후 코드에서 수정했다. **2026-09-22 13:08:54 KST에 실제 공개 REST 드라이런을 재실행**하여 30편 완전 수집·플래그 기존 수치 동일·`new_flags_by_post_id={}`·`alert_codes=[]`·`attention_required=false`, 종료 코드 **0** 및 `FINAL_DRY_RUN_STATE_CREATED=False`를 확인했다. 여전히 성공 기준 스냅샷을 저장하지 않은 두 드라이런이므로 실제 변경 없음 여부는 판별할 수 없다.
- 사용자 승인 없이 **상태 유지 운영 실행·스케줄 등록·외부 알림 송신·WordPress 관리/서버 접근·Git 조작은 일절 수행하지 않았다**. 실제 운영 14회 연속·동시 서로 다른 Windows 계정·정전/디스크 고갈·감독 서비스의 이메일 전달은 미검증이다.

## 승인자가 최종 결정해야 할 사항

이 문서는 스케줄 승인이나 기한 도래 보고를 대체하지 않는다. 실제 운영 담당자는 **정기 감사 실행 시작일/시간·주기(권장 검토 예시: 1일 1회이나 미승인)**, 전용 상태 디렉터리의 접근권한과 디스크/14회 보존 정책, 종료 코드 2/3 처리와 장애 통지 수신자·연락 수단, 미실행 감지 감독 방식, 별도 사람 검토 레지스터의 작성·검증 책임과 검토 주기, 실패 잠금/미완성 실행본 수동 복구 절차를 명시적으로 승인해야 한다. 이 항목들이 결정돼도 실제 등록·최초 운영 실행은 **별도 사용자 승인 후** 진행한다.
