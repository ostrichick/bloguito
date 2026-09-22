# 기존 공개 글 정기 감사 준비 — 2026-09-22

## 결과와 역할

`scripts/audit_legacy_posts.py`를 **읽기 전용 전수 감사의 단일 진입점**으로 확장했다. 기존 `scripts/audit_published_facts.py`의 좁은 알려진 위험 탐지 함수(`published_content_risks`)를 재사용하며, 두 독립 보고서를 합쳐 사실 검증 완료처럼 취급하지 않는다. 이번 변경은 로컬 스크립트·해당 테스트·이 문서만 포함하며 WordPress·운영 서버·Git·정기 스케줄러를 건드리지 않았다.

공개 WordPress REST의 `posts` 엔드포인트만 수집한다. 비공개 글·임시글·고정 페이지는 공개 API만으로 목록 완전성을 증명할 수 없어 대상이 아니다. 서버의 원본 저장 HTML과 공개 REST의 `content.rendered`는 다를 수 있다. `rendered_sha256`은 **공개 HTML 변경 감지용**이며 `editorial_cli.py update-existing`에 필요한 WordPress 원본 `post_content` 해시가 아니다.

## 실행과 출력

프로젝트 루트의 Windows PowerShell에서 기존 프로젝트 venv를 사용한다. 매회 **새로운 Git 제외 `tmp/` 하위 폴더**를 지정하고, 최초 결과를 다음 실행의 비교 기준으로 보존한다. 이 작업의 샘플 실행 폴더는 `tmp/legacy_audit_20260922/audit-worker3-smoke1/`, `audit-worker3-smoke2/`이며 현재 날짜의 운영 정기 실행 경로로 지정한 것은 아니다.

```powershell
./agent-publisher/.venv/Scripts/python.exe scripts/audit_legacy_posts.py `
  --snapshot-dir tmp/legacy_audit_20260922/run-01 `
  --report tmp/legacy_audit_20260922/run-01/report.md

./agent-publisher/.venv/Scripts/python.exe scripts/audit_legacy_posts.py `
  --previous-snapshot tmp/legacy_audit_20260922/run-01/public-rest-snapshot.json `
  --snapshot-dir tmp/legacy_audit_20260922/run-02 `
  --report tmp/legacy_audit_20260922/run-02/report.md
```

선택적인 `--review-register tmp/.../human-review-register.json`은 **이미 사람의 공식 출처 검증과 검토 기한 기록이 별도로 완료된 경우**에만 전달한다. 레지스터를 자동 생성하거나 기존 감사 결과를 검토 완료로 변환하는 기능은 없다. 세 출력 파일은 다음과 같다.

| 파일 | 내용 |
| --- | --- |
| `public-rest-snapshot.json` | 스키마 버전 2, 사이트·총수·페이지 수·완전 수집 표시·조회 시각·공개 REST 원본 전체. 다음 실행의 `--previous-snapshot`으로 사용. |
| `triage.json` | 게시물마다 ID·제목·공개 URL·게시/수정시각·`rendered_sha256`, 구조/인용·링크 후보, 변경 필드, 레지스터 상태·기한, 집계·비교 목록이 있는 기계 판독 보고서. |
| `report.md` | 사람이 읽는 전수 표와 신규/변경/공개 목록 이탈/기한 도래 목록. |

기본 사실·실제 브라우저 서식·외부 링크 동작은 **모든 글에서 `unverified`**다. 제목·본문 내용이나 주소에서 단순 발견한 패턴은 `candidate`이고 오류 확정이 아니다. 출처 항목 유무, 외부 근거 링크 부재, 비활성·HTTP 링크, 목차 앵커·상자 문단 여백을 **본문 HTML 구문으로만** 검사한다. 공식 원문 개정 여부, 링크 도착 화면·접수 가능 여부, 모바일 렌더링, 법률·금액·신청 조건의 정확성을 네트워크로 별도 확인하지 않는다.

## 페이지 누락과 이전 스냅샷 안전성

REST의 매 페이지에서 `X-WP-Total` 및 `X-WP-TotalPages`를 읽고 총수·페이지 수가 페이지당 100건 계산과 일치하는지, 전체 페이지의 헤더가 변하지 않는지, 중간·마지막 페이지의 글 수, 고유 ID, `publish` 상태, HTTPS 공개 URL·날짜·본문·제목 형태를 검사한다. HTTP 오류·헤더 누락·부정확한 페이지 크기·중복/비공개 글·JSON 오류가 발생하면 예외와 비정상 종료로 **부분 결과를 반환하거나 출력 파일을 생성하지 않는다.** 이미 존재한 이전 보고서는 실패 시 그대로 남을 수 있으므로 운영자는 반드시 프로세스 종료 코드를 확인해야 한다. 정상 완료본만 임시 로컬 파일에 기록하고 각 출력으로 바꾼다. `public-rest-snapshot.json`을 마지막에 기록하여 완전 스냅샷 기준점으로 사용한다.

이전 비교에 쓰이는 스냅샷은 같은 사이트에서 생성한 **버전 2·`complete=true`·전체 수와 중복 검증 통과본**이어야 한다. 2026-09-22 초기 전수 조사처럼 완전성 메타데이터가 없는 과거 JSON은 비교 기준으로 받아들이지 않으므로 첫 회차를 새로운 기준점으로 실행한다. 원본 스냅샷을 이번 실행 출력 경로로 지정하면 입력 덮어쓰기를 거부한다. 변경 판정은 `rendered_sha256`, `modified`, `title`, `url` 네 필드의 차이를 기록하며 새 ID와 공개 목록에서 사라진 ID도 식별한다. 공개 목록에서 사라졌다는 결과만으로 삭제·비공개 전환 등 이유를 추측하지 않는다. 공개 중 수정을 동반한 경쟁 상황은 매 페이지 총수 변화·중복 검사를 통해 일부 포착하지만 모든 동시 편집을 검출할 수 있는 WordPress 트랜잭션 스냅샷은 아니다.

## 선택적 검토기한 레지스터

레지스터는 다음 형식의 별도 **수동 검증 기록**만 읽는다. `site`는 실제 감사 사이트와 일치해야 하며 ID·해시 중복·잘못된 날짜·출처·검증자 누락 등 구조 오류가 있으면 전체 감사를 중단한다. 아래는 형식 설명이며 실제 검증 기록으로 사용해서는 안 된다.

```json
{
  "schema_version": 1,
  "site": "https://lifeinfo24.org",
  "entries": [
    {
      "id": 137,
      "rendered_sha256": "<현재 공개 HTML의 실제 SHA256 64자리 소문자 16진수>",
      "verification_status": "human_verified",
      "verified_by": "<실제 검토 담당자>",
      "verified_at": "2026-09-22T12:00:00+09:00",
      "review_until": "2026-10-01",
      "source_urls": ["https://www.nts.go.kr/"]
    }
  ]
}
```

현재 본문 해시가 기록과 다르면 `review_register_status=content_changed`, `review_due=true`로 재검토한다. 날짜가 오늘과 같거나 이전이면 `due`/`true`, 유효한 미래 기한이면 `scheduled`/`false`다. 레지스터가 없거나 개별 기록이 없으면 `review_due=null`(미확인)으로 남긴다. 이는 출처 본문이나 근거가 최신이라는 인증이 아니며, 레지스터의 출처 URL 자체를 다시 읽지 않는다. 해시만 일치해도 별도로 시의성과 검토 날짜를 관리해야 한다. 게시물 본문을 수정하거나 게시·삭제하는 동작은 없다.

## 이번 로컬 검증과 운영 경계

- `test_legacy_post_audit.py` 표적 테스트 9건 통과, `audit_legacy_posts.py`·테스트 파일 `py_compile` 통과. 정상 다중 페이지(101편), 총수·페이지 불일치, 빈 중간 페이지, 헤더 누락, HTTP 503, JSON 타입 오류, 중복·비공개 글, 링크 후보, 레지스터 유효성/본문 해시 불일치, 이전 완전 스냅샷 비교, 수집 실패 시 출력 파일 미생성을 검사했다.
- 라이브 공개 REST 두 차례 읽기에서 각각 30편을 완전 수집했다. 두 번째 실행이 첫 번째의 v2 스냅샷을 비교한 결과 신규 0, 변경 0, 공개 목록 이탈 0, 그대로인 글 30편. 첫 실행 기준 구조 후보는 구형 25, 목차 후보 25, 출처 섹션 누락 후보 12, 박스 여백 후보 14, 독자 전가 후보 1편이었다. 레지스터 미제공으로 30편 검토기한 전부 미확인. 이 숫자는 두 번의 조회 당시 값이며 다음 실행의 현재 수와 다를 수 있다.
- 레지스터와 브라우저 실기기, 동시 편집 중 스냅샷의 원자성, 스케줄 운영 안정성은 실제 운영 검증하지 않았다. 크론·GitHub Actions·서버 작업 등록은 **하지 않았다**. 장기 자동화를 활성화하려면 출력 저장·알림 수신 담당자·비정상 종료 처리·레지스터 작성 절차를 별도로 승인하고 검사한다.
