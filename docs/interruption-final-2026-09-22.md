# Bloguito 중단 작업 재개: 운영 적용 및 최종 검증 기록 — 2026-09-22

> 이 문서는 2026-09-22 18시대까지의 실제 관측·실행 결과다. 이전 `legacy-modernization-final-approval`, `interruption-layout-audit`, `interruption-automation-audit` 등의 **당시 미배포** 표현은 이 문서의 후속 운영 변경보다 오래된 기록이다. 모든 기존 문서를 지우거나 과거 시점의 사실을 현재 사실로 옮겨 적지 않았다. 의도하지 않은 Git 미커밋·미추적 변경은 보존했다.

## 최종 운영 상태

| 항목 | 직접 완료·검증된 결과 | 증거 및 한계 |
| --- | --- | --- |
| WordPress 콘텐츠 | 이전 단계의 #137·#127·#349·#113·#121·#105 정규 갱신을 실제 기록·라이브로 확인. 이번 재개에서는 **#218 하나만 추가 수정**. 전체 40건=공개 30·임시 10, #218 이외 **39건의 저장 본문·수정시각·제목·slug·상태 지문 불변**. | `tmp/legacy_audit_20260922/mu-stored-post-fingerprints.json` 및 `verify-post218-applied.py`의 최종 `PASS`. #218은 이전 저장 SHA `ab8afcf46da6fab8810ded080f939fe76f2ad20733a842af36cc0a3b26407c95` → 최종 `2bf12be8aa996aeeffe7cbbd5e8ffa48a427fa0216f17b4e5157fcb02a08eb3c`. 발췌문은 정규 업데이터가 허용한 기존 생성/빈 발췌문 조건만 적용, 나머지 메타데이터 유지. |
| 목차 MU | 기존 신규 구조 13편 자체 목차 보존, 구형 **13편(70·85·99·103·119·125·139·140·144·145·163·217·220)**에 목차 생성. 짧은 구형 63·77·81·219는 생성 안 함. | 운영 파일 `bloguito-legacy-toc.php`, SHA `6240c15ffe527665cacc7fd773944374a9cd7533f9a4c563206b99c4d2fedcdb`; 본문은 출력 시점만 변경. |
| 녹색 요약 상자 MU | 구형 16편의 `#11775a` 상자에 한정해 여백 CSS 적용, 그중 실제 여백 후보 9편. #85의 다른 색 상자와 새 구조 요약 상자는 대상 제외. | 운영 `bloguito-legacy-callout-spacing.php`, SHA `c9bae087d11eeb50ece97055fca99ed315a660730757063320eda908faaeba4b`; 라이브 CSS 실측 대상 16편+제외 표본 3편 **19/19 통과**. |
| #85 표 MU | 두 표에 캡션 2개·열 머리글 6개·행 머리글 7개·키보드 초점/수평 스크롤 영역 2개가 실제 운영 페이지에 적용됨. 다른 29편의 표 출력 변경 없음. | 운영 `bloguito-legacy-table-accessibility.php` 최종 SHA `dace4a9fe30b78260081bb68a2a5706c7ff6019a389f74c32aee7fc80c21caad`. 처음 설치한 버전은 필터 입력 SHA 불일치로 무변경이었음을 실제 QA에서 발견하여 아래처럼 수정·재배포. 최종 라이브 #85 첫 표에서 키보드 오른쪽 방향키 8회로 **360px: 280px, 390px: 250px 수평 이동** 직접 확인(`tmp/legacy_audit_20260922/live85-keyboard-qa.json`). |
| 실제 화면 | **26편 × 360/390/1280 CSS 확대 근사 = 78/78 자동 구조 조건 통과**, 목차 하나·앵커 유효·가로 넘침·검사 대상 이미지 파손·표 구조 결함 0. 최종 PHP 주석 정정 뒤 #85와 #218 **6/6 재검사 통과**. | Git 제외 `tmp/legacy_audit_20260922/liveqa-final-78-results.json`, 후속 `liveqa-results.json`, 캡처 `live-85-360.png` 등. 78상태 검사 중 브라우저 자원 차단 오류 **28건** 기록; 콘솔 오류 0이라고 주장하지 않는다. CSS `zoom:200%`는 브라우저 네이티브 200% 및 스크린리더 검증이 아니다. |

### #218 깨진 공식 링크: 실제 정상 경로로 교체

기존 생명보험협회 `https://cont.insure.or.kr/cont_web/information/information.do`는 HTTP 응답 코드만 200이었고 격리 Edge에서는 `/cont_web/common/404.jsp`와 `페이지를 찾을 수 없습니다`로 이동했다. 금융위원회 2026-07-07 공식 자료에 함께 명시된 손해보험협회 도메인에서 **`https://cont.knia.or.kr/submit/submit01`**을 실제 Edge로 방문해 HTTP 200·조회신청·STEP01 본인인증/STEP02 정보동의/STEP03 결과확인 화면을 확인했다. 개인정보 입력·인증·조회 제출·보험금 청구는 실시하지 않았다. KNIA는 일반 HTTP 수집기에 403을 돌려주므로 공식 출처로 가짜 수집 성공을 만들지 않고 재조회 가능한 금융위원회 2건·정부24 1건을 구조화 근거로 사용했다.

잘못된 협회 출처를 원고 인용 17곳에서 제거하고, 검증되지 않은 공제·미성년자 예외를 조정했으며 상속인 온라인 조회 가능 조건을 공식 FAQ 범위로 바로잡았다. 정확한 리뷰 입력 `tmp/legacy_audit_20260922/interruption-218/bundle.reviewed.json`은 **독립 의미 검토 6/6, 문제 목록 빈 배열**, `editorial_cli`의 해당 전체 원고 검토 및 목표 글 제외 사전검사 `ready`였다. **18시 전 이번 적용 직전 새 실제 전체 WP·공식 자료 preflight `ready`, 변경 사유 빈 배열, 공식 출처 SHA 일치**가 `interruption-218/approval-prime-fresh-01/approval-manifest.json`에 저장되어 있다. `scripts/update_existing_via_ssh.py`의 정규 출처 재조회·원본 SHA 비교·백업·read-after-write 경로에서 #218 단일 적용 정상 종료했다. 현재 저장 SHA 위 `2bf12...`와 검토 원고 완전 일치, 옛 404 링크 0개·새 CTA 1개·공식 출처 링크 3개를 독립 재조회했다. 실제 라이브 CTA를 Edge로 클릭 목적지 방문해 정확한 KNIA URL, HTTP 200, 단계 3개를 다시 확인했다. QA 종료 시 사이트 전용 UTM 시작 URL로 돌아갔다. `tmp/legacy_audit_20260922/post218-live-cta-qa.json`·`verify-post218-applied.py`가 증거다.

일반 `editorial_cli.py check`에 목표 글을 포함한 캐시 인벤토리를 그대로 넘기면 자기 게시물을 `duplicate_topic`으로 잡는 경로가 있다. 이 경고를 무시해 공개한 것은 아니다. 실제 기존 글 갱신용 `prepare_post_approval.py`와 `editorial_updater.py`는 **목표 #218을 제외한 전체 39건**에 대해 중복·기간·출처·리뷰를 검사하고, 실제 글의 CAS를 추가로 확인하므로 이 정규 경로를 사용했다. 이 구분은 차후 진단에서도 유지한다.

### #85 초기 설치 후 무변경 현상과 해결

초기 표 MU의 허용 지문 4개(저장 원본/REST 원본 및 두 TOC 조합)는 로컬 독립 PHP 101계약을 통과했으나, 실제 WordPress `the_content` 필터 priority 99가 제공한 전체 HTML은 그 네 값과 달랐다. **실제 출력 전 내용의 SHA `2024150df5e6258353c99376ea4b307a0206933b44ae891c9388a5ce324da9c9`(17,250바이트)**를 transient WP-CLI `eval`에서 읽기 전용으로 관측했다. 원래 WordPress 저장 원문 SHA는 `499afcf30df2cfbfdca7041e80bc139c90e1a8da5d5348837b77ee2b8e2cf065`로 보존됐다. `tmp/legacy_audit_20260922/probe-table85-filter-hashes.py`와 비공개 로컬 runtime HTML이 근거다.

전체 지문 검사를 없애거나 본문을 DB에서 고치는 대신, 실제 관측한 **그 하나의 전체 SHA만** 표 MU의 허용 목록에 추가했다. 실제 priority 99 입력을 PHP 표 보정 함수에 다시 넣어 캡션 2·열 6·행 7·영역 2·반복 멱등성 모두 통과했다. 별도 현재 30편 공개 REST fixture 계약은 **101개 통과·변경 ID 정확히 [85]**였다. 초기 MU `afe44b8e...`와 보강 중간본 `d7f8bbf9...`는 서버의 SHA 조건부 단일 파일 교체 때 각각 `.previous`로 보존했다. 최종본 `dace4a9f...`으로 바꾼 뒤 실제 공개 #85 **360/390/1280px 모두 PASS**를 재검증했다. 과거 비활성 MU 파일이 있었다는 이유로 성공을 소급 주장하지 않는다.

## 백업·자동화: 배포 전후 보호와 실제 정기 v3 전환

1. 기존 2026-09-22 **04:00** 아카이브 `/home/ubuntu/backups/bloguito_backup_20260922_040001.tar.gz`는 v2로 manifest+DB+uploads+configs 네 파일만 있고 구성요소 SHA 3개 `--verify-only` 통과했다. 플러그인/테마/MU를 포함한 v3 전체 복원이 가능한 파일이라고 간주하지 않았다.
2. MU 배포 전 별도 v3 `/home/ubuntu/backups/bloguito-v3-predeploy-1e77bb8ccf354ed1980498315c2c97c9/bloguito_backup_20260922_172840.tar.gz` SHA `7e924b474ad1c26f993ec0f7186c9d81d9c1a15a29c9cf497e6218b961cd8508`, 배포 후 별도 v3 `/home/ubuntu/backups/bloguito-v3-postdeploy-659f940fd18b42b0a2f2cb92859c221a/bloguito_backup_20260922_180624.tar.gz` SHA `f462916af8fc000a0f693faad4a51eccff9f79eeba36b1776e3b5f796bf08e93` 생성. 두 아카이브 모두 v3 구성요소 SHA/gzip/중첩 경로 `--verify-only` 통과, **복원은 하지 않음**. 배포 후 아카이브 안에서 이번 운영 MU 세 파일의 SHA를 개별 재검증해 운영본과 완전 일치했다.
3. 기존 `backup_daily.sh`의 7일 삭제가 백업 디렉터리 전체를 재귀 검색해 의도적으로 분리한 사전·사후 백업도 지울 수 있는 것을 발견했다. `find "$BACKUP_DIR" -maxdepth 1`로 정기 백업 **루트의 파일만** 정리하도록 수정. 합성 fixture에서 10일 된 루트 정기 파일이 삭제되고 동일 파일명의 하위 격리 보관본은 유지되는 회귀검사 통과. 코드 `agent-publisher/backup_daily.sh` 및 `agent-publisher/tests/test_backup_recovery_v3.py`.
4. 운영 기존 백업 스크립트 SHA `283da062...`, 복원 스크립트 `d421237a...`를 검사한 뒤 제한 폴더 `/home/ubuntu/backups/bloguito-v3-cutover-3fc7f24d37c8413f9f22c8d72fd3b798/`에 **원본 바이트·모드와 SHA 일치 보호 사본**을 남겼다. 운영에서 정확한 두 파일만 원자적 파일명 교체, 현재 `backup_daily.sh` SHA `d2f84fbc0152e39c08491b503547757df398d91a579d714fd0cc221593c6bba9`, `restore_backup.sh` SHA `4ca62cee29145eacbeb48b839ad580068880ec18696e8f6c1e96b6780ed2dd09`. 교체 전후 crontab SHA 동일하며 **기존 04:00 정기 백업·08:00 초안 생성 두 항목 그대로**다. 다음 날 04:00 스케줄이 실제 기동할지는 아직 그 시각이 되지 않아 미검증이다.
5. 교체된 **운영 경로** `/home/ubuntu/agent-publisher/backup_daily.sh` 자체를 격리 백업 폴더에서 실제 한 번 실행해 `/home/ubuntu/backups/bloguito-v3-cutover-3fc7f24d37c8413f9f22c8d72fd3b798/validation/bloguito_backup_20260922_181252.tar.gz`를 성공 생성했다. SHA `1a630717ed4ec83ded9b9a179a6831528b878da68aea70a4fbee734452a5e147`; 교체된 **운영** `restore_backup.sh --verify-only`가 v3 전체 구성요소·압축·경로를 검증하고 종료 0. 이전 04:00 v2 및 보호된 배포 전후 아카이브 3개 모두 같은 시점 서버에 보존됨을 `ls`로 확인했다. 이 검증도 DB를 복원한 것은 아니다.
6. 별도 공개 글 반복 감사는 Git 제외 Windows 전용 `tmp/legacy_audit_20260922/interruption-audit-baseline/`에 정상 성공 스냅샷을 두 번 생성했다. 17:50~17:50 기준 수집 30편·다음 기준 대비 변경 0, **18:07:43에 #218의 `rendered_sha256/modified` 변화 1건을 `public_inventory_changed` 및 신규 후보로 감지**, 18:09:14 다음 실행에서는 변경 0·경보 0·정상 종료 0. 이는 공개 REST·사람 검토 등록 0의 국지적 동작 증거이며 정책 정확도/실사용 스케줄을 뜻하지 않는다. `review_unknown_count=30`은 별도 검증된 사람 검토 등록부가 없기 때문이다.

## 회귀·Git 및 복구 범위

- 전체 Python 테스트 **281개 OK, skipped=1**, 마지막 전체 재실행 종료 0. v3 표적 백업 7개 통과, Bash 백업·복원 구문 검사 통과, `git diff --check` 종료 0(기존 파일의 CRLF 변환 경고는 존재). PHP 목차 합성 23개, 현행 실제 30편 표 계약 101개, live PHP runtime 표 조건 및 브라우저 78/78·CSS 19/19 통과. 브라우저의 총 자원 차단 오류 28건은 별도 계측/자원 로딩 진단 범위다.
- 레이아웃 코드·workflow와 해당 테스트 정확히 4파일만 `13711a3`으로 커밋·`main` 푸시했으며 GitHub Actions Test Suite **성공**: <https://github.com/ostrichick/bloguito/actions/runs/35708393291>. 정기 백업 보존 수정 코드와 표적 테스트 정확히 2파일만 `979dfac`으로 별도 커밋·`main` 푸시했으며 **해당 CI도 성공**: <https://github.com/ostrichick/bloguito/actions/runs/35709245242>. 기존 다른 작업자의 수정·미추적 파일은 해당 커밋에 넣지 않았다. 코드 Git 적용·운영 MU 설치·운영 백업 도구 적용·게시물 #218 수정은 각기 실제 완료 범위를 구별한다.
- **전체 복원 미실시.** `restore_backup.sh --yes`는 DB·업로드·확장·런타임 JSON을 덮어쓰므로 라이브에서 시험하지 않는다. 별도 VM/Docker daemon·DB·볼륨·비밀정보 분리·재시작 후 글/이미지/플러그인 기능 검증이 있어야 격리 복원 성공을 주장할 수 있다. 비밀 구성은 v3 아카이브 안에 **암호화되지 않은** `secrets.tar.gz`로 별도 저장되므로 외부 보관 전 암호화·키 보관 정책도 미결이다. 서버 압축본과 디렉터리는 0600/0700이지만 유출 파일 암호화까지 보장하지 않는다. 이 백업을 개별 MU만 되돌릴 목적으로 전체 복원해서는 안 된다.
- 설치 MU만 되돌릴 때에는 **현재 파일 SHA와 배포 때의 SHA 일치**를 확인해 그 파일 하나를 플러그인으로 인식되지 않는 이름으로 격리하고 페이지 캐시를 검증한다. TOC 설치 token `8fc2bd1bb2f24daa80a3d48ffcb3ecd8`, CSS token `ed9834bd1d974a3084d29b831536df50`; #85 초기·중간 SHA 사본은 위 `.previous` 경로. 사용자나 타인이 바꾼 최신 파일을 무조건 제거하거나 운영 DB 전체를 덮지 않는다. 이번에는 운영 오류가 최종 수정으로 해결돼 롤백 자체는 실행하지 않았다.

## 근거 부족 및 사용자·운영 판단이 남은 별도 작업

| 대상 | 현재 보류 이유 및 필요한 증거 |
| --- | --- |
| **게시물 #103** | 목포시 자체 독감 예방접종 연령 상한을 9/16 공식 보건소 공지 **15~65세**, 9/18 시 보도자료 **15~64세**로 서로 다르게 발표. 첨부 HWP의 81개 기관은 국가사업 기관으로, 시 자체사업 자격·기관 충돌을 해결하지 못함. 공식 서면 정정/현행 대상별 의료기관 확인 전 수정 보류, 기존 6/6 검토를 재활용하지 않음. |
| **게시물 #145** | 실제 제목·주제는 2026 추석 **고속도로 통행료**이며 KTX/버스 취소표 글이 아님(#217은 별도). 9/27 종료까지 5일이라 정책 최소 30일 위반; 예외는 #225 한 건에만 존재. 임의 evergreen 분류·기한 연장·주제 바꿔치기 불가. 별도 유효 근거/기간·정책 승인 없이는 적용 보류. |
| **#127·#349 및 다른 보류 원고** | #127 모바일 홈택스 출처 링크는 실제로 홈택스 메인으로 이동해 국세환급금 조회 폼 직접 진입을 아직 확인하지 못함. #349는 YES24 네 지역 투어 **목록 일정**까지만 확인, 좌석·결제 성공 미확인. 기타 시한·공식 자료/주제 중복/기관별 적용 차단 원고는 `docs/resume-longtail-preflight-2026-09-22.md`의 과거 상태를 최신 현황으로 단정하지 않고 새 정식 전체 bundle·독립 리뷰·fresh preflight가 있을 때만 재판정. |
| **별도 반복 감사 스케줄** | 코드·로컬 기준선 및 변경 경보 동작은 입증했으나 서버에는 감사 스크립트·별도 감사 cron이 없고, **실행 호스트/시각·작업 계정/상태 폴더 권한·경보 수신처/감독기·사람 검토 레지스터 책임**이 확정되지 않았다. 임의 09:00 스케줄이나 외부 알림 주소를 만들지 않았다. 04:00 v3 백업 정기 작업과 구분. |
| **운영 후속 검증** | 다음 실제 04:00 v3 cron 실행과 다른 호스트 격리 전체 복원, 오프사이트 암호화/복호화·키 복구, 네이티브 200% 확대·스크린리더, 조회 사이트의 로그인/개인정보 제출·실제 청구는 아직 검증하지 않았다. 7일 정기 보관 정책과 장기 보관본/용량 관리의 운영 결정 필요. |

위 항목의 공식 모순·기간 정책·운영 담당/알림 수신처를 임의 추정하여 해소했다고 쓰지 않는다. 이전 작업 자료는 `docs/interruption-content-audit-2026-09-22.md`, `docs/interruption-layout-audit-2026-09-22.md`, `docs/interruption-automation-audit-2026-09-22.md`, `docs/interruption-ci-and-recovery-2026-09-22.md`, `docs/resume-layout-current-census-2026-09-22.md`에 보존한다. 이 문서는 그 후 실제 적용과 새 검사 사실을 합친 최종 기록이다.
