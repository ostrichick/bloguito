# 전체 프로젝트 스캔 및 우선순위 분석 — 2026-09-26

> 최신 통합 상태(2026-09-27): 1·3·5번 개선 브랜치를 main에 병합했다. 아래 최초 감사와 9/26 후속은 당시 기록이며, main 통합 검증은 마지막 후속 절을 따른다.

## 범위와 검증 기준

앞선 Markdown 152개 스캔을 바탕으로 현재 추적 파일 목록(372개), Python/WordPress/SSH/백업/분석/WhatsApp/CI 구성을 조사했다. 제외 디렉터리(.git, .venv, node_modules, tmp, data, content) 외 코드·설정 파일을 읽어 목록·크기·위험 패턴을 스캔한 집계는 Python 152, shell 11, JSON 16, YAML 3, JavaScript 3, PHP 12개다. 파일 목록/패턴 전수 스캔과 핵심 경로 상세 검토를 구분하며 모든 코드 줄의 정합성이나 모든 외부 의존성을 완전 감사했다고 주장하지 않는다. 실제 비밀값은 출력하지 않았다.

- 로컬 전체 Python: **489 tests, OK (skipped=1)**. 로그 `tmp/project-scan-tests-20260926.log`. 로그 첫 줄의 simulated transfer interruption은 실패 주입 테스트이며 실제 실패가 아니다.
- WhatsApp 명령 권한: **3 tests PASS**. package-lock 기반 npm audit: 보고된 취약점 **0**. Python 패키지 취약점 전체 감사는 하지 않았다.
- 최신 GitHub Test Suite: **success**, run https://github.com/ostrichick/bloguito/actions/runs/36241809511 . 로컬 PHP 전체 실행과 실브라우저 QA는 하지 않았다.
- 공개 REST 완전 조회: **41편**. `tmp/project-scan-20260926/public/public-rest-snapshot.json`, `triage.json`, `tmp/project-scan-20260926/public-report.md`. 공개 HTML과 저장 post_content는 구분한다.
- 운영 서버는 이미 구성된 WSL Tailscale SSH로 읽기 전용 확인. Nginx/Fail2ban/private-SSH service active, 사용자 cron은 04시 백업/08시 run_daily.sh 확인. 서버 설정·게시물·스케줄은 변경하지 않았다.
- Windows Bloguito Daily Backup Sync: 오늘 실행 결과 **0**, 로그에서 3개 검증 다운로드/14개 기존 검증 및 정상 완료 확인.
- GitHub analytics: 9/24 성공 후 9/25·9/26 실패. 9/26 실패 로그는 공개 SSH host-key scan 선언 이후 약 10초 뒤 exit 1. 로그 속 셸 코드에 인쇄된 오류 메시지 문자열을 실제 실행 오류로 혼동하지 않았다.

## 우선순위

### P1-1: reformat 경로가 검토 결합을 다시 찍는 허점

확인된 코드: `agent-publisher/agents/publisher.py:188-189`에서 기존 review의 policy_digest와 content digest를 현재 값으로 덮어쓴 뒤 validate_bundle을 호출한다. 이 때문에 검토 당시 정책/원고가 실제로 일치했는지 확인하기 전에 기존 서명을 재결합한다.

**모의 재현 완료:** 기존 fixture bundle의 두 review digest를 의도적으로 stale 값으로 변경했다. 실제 validator는 `review_not_bound_to_current_content`로 차단했다. 같은 bundle을 임시 디렉터리·모의 WordPress subprocess로 reformat_draft에 전달하면 update와 record 단계에 도달했다(`REFORMAT_ACCEPTED_STALE_DIGEST True RECORDED True`). validator 자체는 실제 함수를 사용하되 고정 fixture 시각으로 실행했다. 실제 WordPress 쓰기는 0건이다. 서버 publisher에도 동일 policy_digest 재기록 코드가 존재한다.

추천: 재기록 전에 원래 검토 결합을 검증하고, renderer 변경만의 이관을 별도 버전/명시적 migration 증거로 제한한다. 정책이나 실제 원고 digest가 다르면 전체 재검토를 요구한다. 정상 이관과 stale content/policy 거부를 회귀 검사한 뒤 공통 코드 전체 suite 1회 실행. 침해나 실제 잘못된 공개가 발생했다는 증거는 없다.

### P1-2: 공개 SSH 차단과 통계 전송 자동화 충돌

확인된 사실: `.github/workflows/google-analytics.yml:89,109`는 공인 IP에 ssh-keyscan/SSH를 수행한다. `wordpress/ssh/bloguito-ssh-private-only.service`는 tailscale0 외 신규 22번 접근을 DROP하며 운영에서 active다. 실제 analytics run 36109897279(9/25), 36227768010(9/26)이 failure다.

추론(높음): host-key scan의 타임아웃과 실패가 새 공개 SSH 차단에 기인한다. 실패한 단계의 순서상 해당 실행은 통계 수집 명령 이전에 중단된 것으로 보인다.

추천: 공개 SSH 차단을 유지하면서 제한된 비공개 관리 경로로 통계 전달을 이관하고 host-key/forced-command/비공개 저장 보장을 유지한다. 수동 1회 성공, 서버 수신 파일의 생성 시각·무결성 확인, 다음 예약 실행 성공으로 완료 판정. 보고된 과거 성공을 현재 정상 작동의 근거로 사용하지 않는다.

### P1-3: 공개 글 3편의 출처 목록 복원 검토

공개 REST 실제 HTML에서 #70·#99·#229는 출처 제목/목록을 찾지 못했다. 별도 본문 추출에서도 하단이 FAQ로 끝난다. #70/#99에는 NOL 공식 상품 CTA가 있지만 하단 공식 출처 목록이 없다. #229는 본문 anchor 목록이 목차/FAQ뿐이며 외부 근거 링크가 없다. 이는 사실 내용 자체가 틀렸다는 판정과 구분한다.

추천: 현재 저장 원고와 검토 bundle을 먼저 대조해 누락이 수동 수정/렌더/저장 중 어느 단계인지 찾는다. 최신 공식 근거를 결합하고 정규 경로로 글별 검토·복원 후보를 준비한다. 특히 #229는 추석 배출일 안내이므로 9/27 종료 전후 검토와 함께 다룬다. 이번 분석은 기존 공개 글 변경 승인이 아니다.

### P2-1: 단기 콘텐츠 종료일과 사람 검토기한 관리

현재 공개 목록에는 추석 안내 #145/#163/#217/#219/#225/#229/#237/#239와 9/30 납기 #144가 있다. 기존 정책에도 글별 useful_until 예외가 남아 있다. 이번 감사에 review register를 제공하지 않아 41편 모두 review_unknown이며, 이것은 모든 글을 검토하지 않았다는 의미가 아니다. 저장소/서버 user cron/관련 timers/Bloguito Windows 작업 조회 범위에서는 정기 공개 글 감사의 운영 실행과 검토기한 등록부를 확인하지 못했다. 다른 계정/앱의 스케줄 존재 여부는 미확인이다.

추천: 9/27 종료 글과 9/30 기한 글부터 갱신·지난 일정 보존·상시 절차로 개편 중 적절한 처리안을 글별로 정하고 검토 등록부에 반영한다. 이후 기존 read-only audit 도구를 활용해 변경/기한을 추적한다. 자동화 등록·알림은 분석 범위에 포함하지 않았다.

### P2-2: 예약 파이프라인 실패를 종료 상태로 전달

`main.py:100-104`는 글 처리 오류를 stats에 넣고 계속 진행한다. 끝에서 stats를 반환하거나 sys.exit로 실패를 전달하지 않는다. 운영 run_daily.sh는 `set -e` 및 Python 실행 성공에 의존한다. 따라서 후보별 오류가 발생해도 명령은 정상 종료할 수 있다. 정상적인 정책 HOLD와 오류를 구분해야 한다.

추천: run_pipeline 결과를 반환하고 실제 오류/외부 장애에 대한 명시적 종료 정책과 실행 결과 기록을 추가한다. 승인 후보 0개나 정책상 보류만 발생한 실행을 장애로 오판하지 않는다. 알림 전달 실패도 기록하되 새 외부 알림은 사용자의 별도 요청 없이 보내지 않는다.

### P2-3: 로컬/예약 서버 버전과 배포 범위 명시

읽기 전용 SHA 대조에서 main.py/editorial.py/publisher.py/editorial_policy.json **4개 모두 로컬과 서버가 다르다**. 서버 writer 생성자는 구형 형태이며 로컬의 writing_enabled 분리 인터페이스와도 다르다. 로컬 편집 코드가 정본이고 수동 WordPress만 원격 실행하는 현행 설계에서는 차이 자체가 결함은 아니다. 그러나 매일 08시 예약 작성은 서버 코드로 실행되므로 로컬 489개 테스트 성공이 그 예약 코드의 검증을 대신하지 않는다.

추천: 수동 편집/예약 작성 각각의 배포 버전·허용 차이·설정 해시를 작은 release manifest로 기록한다. 예약 경로에 필요한 변경만 호환성/롤백 검증 후 배포하고 별도 smoke test를 남긴다. 로컬 파일을 전부 덮어쓰는 배포는 권하지 않는다.

### P2-4: 관리자 2FA 및 독립 백업 보호

최신 문서에는 TOTP 실제 등록이 후속 작업으로 남아 있고 이번 조사에서 사용자별 등록을 확인하지 않았다. backup_daily.sh는 비밀번호/설정 파일을 별도 secrets.tar.gz에 넣지만 암호화하지 않는다. Windows 동기화 자체는 오늘 정상이다.

추천: 관리자 TOTP 등록·복구코드 보관 상태를 사용자와 확인하고, PC/서버와 별개 장애를 견디는 암호화 오프사이트 사본을 설계한다. 새 VM 전체 DR는 비용과 운영 조건을 정한 뒤 별도 훈련한다. 암호화/보관 위치가 바뀌면 실제 복호화·복원까지 검사한다.

### P3: CI 보강과 성과 기반 콘텐츠 운영

CI PHP 단계는 ID/목차/기존 레이아웃 위주이며 새 security/front-end-polish/social-share 플러그인의 lint/계약 검사를 모두 실행하지 않는다. front-end-polish-test.php도 현재 workflow에 없다. 새 MU 플러그인을 CI 검사 목록에 넣는 작은 보강이 적절하다.

통계 전달이 복구된 뒤에는 실제 GSC query/page 성과로 주제 중복과 evergreen 우선순위를 결정한다. 지금은 검색 성과/수익을 새로 측정하지 않았으므로 주제 확장이나 구조 개편의 효과를 단정하지 않는다. 먼저 긴급 결함을 정리하고 대규모 재구조화·추가 자동화는 뒤로 둔다.

## 실행 권고 순서와 보존

검토 결합 허점 → 통계 전달 복구 → 출처 누락 3편의 복원 후보 → 9/27·9/30 콘텐츠 재점검 → 예약 오류 전달/버전 관리 → 2FA·오프사이트/DR → CI·성과 분석 순서를 권고한다. 콘텐츠 적용과 공유 validator 변경은 분리한다.

운영 쓰기/배포/스케줄 추가/메시지 송신은 수행하지 않았다. 기존 미추적 choyongpil_ticket_notice, project-optimization-audit 문서는 보존했다. 산출물은 Git 제외 tmp 증거와 이 MD뿐이다. 코드 수정·commit/push는 하지 않았다.


## 2026-09-26 후속 개선 — 사용자가 선택한 1·3·5번

사용자가 기존 우선순위 중 1·3·5번의 즉시 개선과 문서 갱신을 요청했다. 최초 감사 절의 “수정하지 않았다”는 당시 범위이며, 아래는 그 이후 실제 적용 결과다.

### 완료한 코드 및 운영 반영

- **1번 검토 결합 보존:** reformat_draft가 기존 review의 content/policy digest를 다시 찍지 않도록 수정했다. 원래 검토가 현재 원고·정책과 다르거나 만료되면 차단한다. 정상 renderer 이관과 원고·정책·만료 거부를 실제 validator와 모의 WP로 검사했다.
- **5번 실패 종료 전달:** run_pipeline이 결과를 반환하고 CLI가 처리 오류 발생 시 exit 1을 반환한다. 후보 없음/정책 HOLD는 exit 0이다. 알림 전송 실패는 notification_errors로 별도 집계하며 이미 완료한 발행 결과를 지우지 않는다. 이번 검증에서 실제 신규 발행이나 외부 알림은 실행하지 않았다.
- **3번 출처 표시 원인 수정:** #70/#99는 모든 근거 URL이 상단 CTA와 같을 때 하단 인용을 제외하는 기존 규칙 때문에 출처 목록 전체가 사라졌다. 별도 근거 페이지가 있으면 중복 제외를 유지하되, 출처가 하나도 남지 않으면 실제 인용 근거를 하단에 한 번 표시하도록 renderer·편집 지침을 수정했다. #229도 공식 서울시 근거를 새로 조회하고 출처 목록을 복원했다.
- 공유 코드·정책을 먼저 커밋한 뒤 콘텐츠를 재검토했다. #229의 검토용 q4가 실제 FAQ와 불일치한 것은 본문을 임의로 늘리지 않고 실제 FAQ 범위에 맞춰 정정한 후 독립 검토를 다시 통과했다.
- 세 글 모두 정규 updater의 최신 전체 WP inventory, 중복 검사, 최신 공식 원문 대조, 기존 본문 SHA 비교, 백업, 저장 후 검증을 거쳐 동일 ID에 적용했다. 제목·slug·publish 상태 보존을 updater가 확인했다. 공개 REST에서도 각 글 출처 제목 1개와 공식 링크 1개를 확인했다.

### 검증과 배포 범위

- 최종 로컬 표적 테스트 **57개 통과**, 전체 Python **517개 OK, skipped=1**. 이후 코드 변경 없이 문서·콘텐츠만 처리했다.
- 서버는 로컬 전체 파일로 덮어쓰지 않고 기존 writer/inventory 인터페이스를 보존한 main.py, publisher.py, editorial.py 및 서버 편집 지침의 해당 부분만 변경했다. 서버 격리 테스트 **12개 OK**, 모듈 import 확인 및 파일 해시 기록 완료. 배포 출력의 isolated_tests=10은 초기 스크립트의 고정 메타데이터이며 실제 unittest 출력은 12개다.
- 서버 롤백 백업: /home/ubuntu/agent-publisher/backups/priority-fixes-20260926T130213Z/manifest.json. 콘텐츠 백업·검토 보고서는 정규 updater가 로컬 작업 checkout에 생성하며 비공개 원고/inventory는 Git에 포함하지 않는다.
- 증거: tmp/priority-fixes-20260926/renderer-final-tests.log, deployment.log, post-{70,99,229}-review.json, post-{70,99,229}-update.log, public-verification.json. 이 경로의 비공개 데이터와 토큰은 커밋하지 않는다.
- 관리 연결이 다른 작업의 설정 변경 중 일시적으로 끊겼다가 재연결됐다. 이 작업에서는 Tailscale 설정을 변경하지 않았다.
- NOL 공식 상품 원문 HTTP 200과 내용은 확인했다. headless 브라우저에서는 오류/빈 화면이 나타나 실제 잔여 좌석·결제 완료는 검증하지 않았으며 원고에도 그 성공을 주장하지 않는다.

### 남은 우선순위

1. **P1: 통계 전송 복구(기존 2번).** 공개 SSH 차단을 유지하며 analytics 전송 경로를 이관하고 수동·다음 예약 실행 및 서버 수신 무결성을 확인한다.
2. **P1: 9/27·9/30 종료 콘텐츠 재점검(기존 4번).** #229 출처 복원과 종료 후 재검토는 별개다. 추석·납기 글의 처리 방침과 검토 등록부부터 정리한다.
3. **P2: 로컬 수동 편집/서버 예약 코드의 release manifest(기존 6번).** 이번 호환 패치 해시는 남겼지만 전체 버전 차이 관리 체계는 미완료다. 다음 실제 예약 실행의 결과도 별도 관찰이 필요하다.
4. **P2: 관리자 TOTP·암호화 오프사이트 백업·새 VM DR(기존 7번).** 기존 날짜별 DR 기록과 실제 등록·독립 복원 완료를 구분해 확인한다.
5. **P3: 새 MU 플러그인 CI 검사와 통계 복구 후 검색 성과 기반 콘텐츠 우선순위.** 이번 작업에 추가 자동화·알림 등록은 포함하지 않았다.


### 공개 화면 확인

비로그인 QA 세션은 지정 UTM으로 첫 진입했다. 세 글 모두 360/390/1280px에서 페이지 가로 넘침 없음, 목차 대상 누락 0개, 표 caption·header·role=region·tabindex=0을 확인했다. 표 영역에 focus 후 Tab으로 다음 링크로 이동했다. 200%는 headless 환경에서 CSS zoom으로 모사했으며 실제 브라우저 메뉴 확대와 동일한 검증이라고 주장하지 않는다. 하단 공식 출처는 별도 모바일/데스크톱 및 확대 화면으로 확인했다. browser-qa.json의 sources=[]는 최초 측정에 사용한 잘못된 CSS selector 때문이며 출처 부재를 의미하지 않는다. 실제 ul.source-list는 public-verification.json 및 별도 browser-source-qa.json에서 확인했다.

운영 변경 SHA256: main.py 7b8fa5a9d1a4e4b4289d0370cd9aa0e3275623d41ff619fc6f93f0403a16e353, publisher.py b291c0209b4643e1e3ba16f29c92ab29e146628b98bc1b9cf5e6b941225ef56f, editorial.py ec927efbd49765a3f676d8f694823fe57e2875b9da064ce7fcde4e58e53e2434. 로컬과 서버 전체 코드가 같다는 뜻은 아니다.


## 2026-09-27 main 통합 후속

사용자가 main 통합을 요청해 codex/priority-fixes(f169bba)를 현재 main(0f555c3)에 병합했다. 기존 main의 독자 경험·관련 글·FAQ 편집 지침과 이번 출처 fallback 규칙을 함께 보존했다. docs/INDEX.md 충돌은 양쪽 작업 기록 링크를 모두 유지해 해결했다.

main.py의 미커밋 표시를 다시 조사한 결과 작업 파일의 Git blob hash와 HEAD blob hash가 모두 7b74fb5c121fcd3e098e09718394540ffecf2a4b로 같았고 실제 diff도 없었다. 원본 파일과 index를 tmp/main-integration-20260927/에 백업한 뒤 해당 파일만 Git index 갱신해 표시를 해소했다. 이는 다른 작업의 코드 내용을 삭제한 조치가 아니다. 미추적 감사/문서 스캔 파일도 먼저 백업한 뒤 브랜치의 추적 문서로 통합했다. choyongpil_ticket_notice와 project-optimization-audit-2026-09-20.md는 미추적 상태 그대로 보존했다.

통합 상태에서 표적 테스트 21개 OK, 전체 Python 517개 OK(skipped=1), git diff --check 통과. 로그는 tmp/main-integration-20260927/targeted-tests.log 및 full-tests.log에 있다. 로그 첫 줄 simulated transfer interruption은 기존 실패 주입 검사이며 전체 suite 실패가 아니다. publisher의 review 재기록 제거, main의 return stats/non-zero exit, 출처 fallback과 양쪽 편집 지침 보존을 대조했다.

이번 작업은 Git main 통합·문서 상태 정정이다. 서버 재배포·공개 글 재저장·브라우저 QA는 수행하지 않았으며 9/26 운영 검증을 오늘 새로 수행한 것으로 표현하지 않는다. 두 편집 정책 변경이 함께 포함되므로 새 원고 수정 때는 통합된 최신 정책 fingerprint로 검토해야 하며, 과거 검토 digest를 다시 찍어 우회하지 않는다. 남은 운영 우선순위는 위 목록을 유지한다.

## 2026-10-02 후속 감사 — 구조적 리팩터링과 효율 개선

### 점검 기준과 현재 상태

- 요청 범위는 최근 업데이트 확인, 프로젝트 구조 평가, 개선 우선순위 제안이다. 코드 리팩터링·서버 배포·글 변경·공개 전환은 수행하지 않았다.
- 시작 기준은 clean `main` / `origin/main`의 `0e1d1c8`. 점검 도중 다른 작업에서 `fa463e2`(category display names)가 추가됐으므로 하나의 고정 snapshot으로 모든 결과를 설명하지 않는다. 해당 변경은 수정하거나 되돌리지 않았다.
- 추적 파일 목록·Python AST·핵심 편집/출처/렌더/transport/저장/배포 코드, 정책 문서, CI 결과, Direct SSH 운영 조회, 공개 홈페이지 텍스트를 대조했다. 현재 inventory scan은 484 tracked files, Python 207개, Markdown 198개다. 모든 코드 줄·외부 서비스·공개 글의 사실관계를 전수 감사한 결과는 아니다.
- Direct SSH로 WordPress 7.1.2, WordPress/MariaDB container running, 공개 62편·draft 7편을 확인했다. 공개 홈페이지에서도 최근 보건증·가족관계증명서·주택연금·세종 행사·모바일 주민등록증 글과 8개 현행 category menu를 확인했다. legacy `life-health`와 미분류 term은 count=0으로 남아 있다. 삭제 필요성은 별도 판단 대상이다.
- 로컬 전체 Python: 822 tests, `OK (skipped=1)`, 20.872초. 증거: `scratch/tasks/project-efficiency-audit/python-tests.log`. 실행 중 일부 실패 주입/argparse 메시지는 실제 suite 실패와 구별했다.
- 동일 시작 SHA의 GitHub Actions [37002368388](https://github.com/ostrichick/bloguito/actions/runs/37002368388): Python 822 tests / errors=10, WordPress PHP contract와 infrastructure job은 PASS. 10개 error entry 중 9개는 Designer font/generated-cover 관련, 1개는 event renderer의 `kakao_map_javascript_key_missing_or_invalid`. CI 실패가 곧 운영 이미지나 공개 지도 장애라는 증거는 아니다.
- analytics 최근 3회(9/30, 10/1, 10/2)는 failure. 최신 [36984863152](https://github.com/ostrichick/bloguito/actions/runs/36984863152)는 private collect/deliver step에서 exit 1이다. 이 조사에서 구체적 원인은 확정하지 않았다. 로그에 출력된 `analytics_delivery_failed` 셸/파이썬 소스 문자열을 실제 오류 발생 증거로 취급하지 않았다.
- 운영 `editorial.py`, `editorial_writer.py`, `temporal_validation.py`, `volatility.py`의 SHA256은 로컬과 일치했다. 운영에는 신규 `edit_orchestration.py`가 없고 구 `copywriter.py`가 남아 있다. policy JSON hash도 점검 중 로컬 값과 다르며, category 이름 변경이 동시에 있었으므로 개별 diff 확인 없이 잘못된 배포라고 단정하지 않는다. 운영 entrypoint/config의 차이와 구 파일의 실제 참조 여부도 추가 확인해야 한다.

### 이미 이루어진 개선

현행 코드·지침에서 확인한 개선은 정상 mutation 진입점 3개 통합, single change classifier, source/review 재사용, per-post reviewed manifest, 공유 edit bookkeeping, 정규 CLI parser를 재사용한 SSH request 정규화, General/Event schema 분리, policy exception registry, critical-fact registry pilot, volatility/current-value period 계약이다.

과거 P12~P15 기록에는 legacy CLI/shim/WordPress 보정 플러그인 제거와 PHP runner/backup transport/DR validator 통합도 있다. 이를 새 개선으로 다시 제안하지 않는다. volatility legacy fallback 전체 제거와 critical-facts 전체 데이터화는 아직 완료된 상태가 아니다.

### 우선순위와 완료 조건

| 순서 | 확인한 근거 | 권장 변경 | 완료 판정 |
| --- | --- | --- | --- |
| 1 | 로컬 PASS / CI errors=10; 이미지 테스트가 설치 font·generator에 의존하고 event render test는 지도 key에 의존 | 단위 테스트용 image provider/font/config를 명시적으로 주입. 실제 브랜드 font 설치·검증은 별도 integration contract로 실행. 이미지 실패 시 보류하는 운영 정책은 유지 | 비밀 설정 없는 clean Windows/Linux 환경에서 동일 unit 결과, 필수 font contract PASS, GitHub 전체 green |
| 2 | analytics 3회 실패; 로컬·운영 module 구성과 policy가 부분적으로 다름; installer는 config/main 문자열 patch와 import smoke 중심 | private analytics 실패 지점을 구별하는 비민감 진단 추가. release SHA/file hashes/필수 module/obsolete file 명시 목록과 entrypoint smoke 추가. 설정은 코드와 환경 파일로 분리하는 방향으로 점진 전환 | analytics 실제 private 전달 성공, 예정 실행 성공, release manifest와 설치 파일 일치. 유지할 환경 설정은 보존하고 구 파일은 참조 확인 후 제거 |
| 3 | `editorial.py` 1,759줄, `render()` 455줄, `validate_bundle()`에 content/source/site/review 분기 집중 | policy loading/fingerprint, evidence validation, HTML rendering을 역할별 module로 추출. 기존 import와 함수 API는 초기 유지 | 같은 bundle의 HTML·reason code·review binding이 동등하고 기존 CAS/readback/public backup contract 유지 |
| 4 | `editorial_writer.py` 1,311줄에 Pydantic schema·model 호출·HTTP/PDF·기관/게시물별 parser가 혼재 | schema, source fetch/extraction, model reviewer/writer로 분리. source adapter는 정확한 host/path/query matching을 유지 | 기존 source text/hash, source_id, date/amount preservation, redirect/size/HOLD behavior 동등 |
| 5 | SSH `make_transport()` 410줄; runtime `patch('subprocess.run', ...)`로 process 전체 subprocess 경로 교체 | 명시적인 WordPress transport interface를 주입하고 실행 context의 권한·target allowlist를 집중. 한 번에 모든 호출자를 바꾸지 않고 thin adapter부터 도입 | 임의 post/field/command 거부, CAS/readback, 불명확한 media import 무재시도 유지; 일반 subprocess와 WP transport 분리 검증 |
| 6 | catalog 유형은 title keyword로 추정하고 volatility는 reviewed lifecycle metadata로 판단. 예: 연도 있는 건강검진 title은 catalog에서 evergreen | category는 term ID/slug로 표시명과 분리; lifecycle은 reviewed manifest 우선, metadata 없는 글은 추정임을 표시. API 기반 저장 안전성 판단과 catalog용 표시를 구분 | catalog가 annual/seasonal/live 여부를 근거 수준과 함께 표시하고 운영 validation 판단을 덮어쓰지 않음 |
| 7 | critical facts는 vaccination pilot만 data registry로 이동; legacy followup/reference 기간 검증이 남아 있음 | 단순 연도별 금액·날짜·명칭만 registry로 순차 이동. 의미·계산·조건 충돌은 Python 유지. fallback 종료는 검토 완료 metadata·운영 관찰 뒤 결정 | 같은 이유 코드/PASS/HOLD, 잘못된 registry fail closed, 기존 reviewed bundle 호환 |

### 속도와 측정

로컬 runtime metrics에서 2026-10-01 이후 성공 기록 129개를 action별로 집계했다. `ssh-edit-post` 13회 median 42.3초, `ssh-prepare-draft` 7회 63.6초, `ssh-replace-featured-image` 8회 60.8초(기록된 WP 왕복 평균 9회)다. `sources` 25회 median 1.28초, `check` 12회 17ms다. 워크플로 전체 소요시간에는 원고 작성·사람 승인·다른 UI 시간이 포함되지 않는다.

이는 관측 표본이며 코드 버전/transport별로 분리된 최신 경로 벤치마크가 아니다. 이미 제거된 action이 일부 포함되고 `ssh-import-section-image`에 WP roundtrip=0으로 기록된 점은 미계측 가능성이 있다. median이나 phase 평균을 합산하여 전체 작업 시간을 만들지 않는다.

따라서 module 분리만으로 실행이 빨라진다고 약속하지 않는다. metrics에 code/release SHA, route, transport, cache/review reuse, image upload/readback/catalog sync timing을 추가하고, 같은 최신 경로를 비교할 수 있는 표본을 먼저 만든다. 이후 WP 조회 snapshot 중복과 연결 재사용을 개선하되 저장 직전 CAS와 저장 뒤 readback은 유지한다.

### 실행 권장 단위와 범위 제한

1. 첫 변경은 CI 재현성 복구만 분리한다. 정책이나 HTML을 동시에 바꾸지 않는다.
2. analytics 복구와 release 일치 검증은 운영 작업으로 별도 진행한다.
3. 두 번째 코드 변경은 editorial renderer 추출로 제한한다. 그다음 schema/source adapter 분리와 transport interface를 독립 변경으로 진행한다.
4. catalog metadata 정합성과 metrics version attribution을 맞춘 뒤 성능 최적화한다.
5. 큰 신규 framework, DB 전환, 모든 파일의 재배치, 모든 legacy fallback 일괄 삭제는 현재 근거로 우선하지 않는다.

일정·절감률·수익 상승은 측정하지 않았으므로 수치로 보장하지 않는다. full restore drill, 취약점 전체 감사, 모든 글의 공식 출처 재검토, 시각적 브라우저 QA는 이번 범위 밖이다. archive 안의 `attach_remaining_thumbs.py` AST syntax error는 역사 자료의 상태이며 현재 실행 경로의 결함으로 우선순위를 높이지 않았다.

이번 변경은 이 기존 감사 문서에 후속 분석을 추가한 것뿐이다. 분석 도구/중간 JSON/로그는 Git 비추적 `scratch/tasks/project-efficiency-audit/`에 저장했다. 새 코드·Git commit/push·서버 배포·WordPress mutation은 수행하지 않았다.


## 2026-10-02 권장 순서에 따른 개선 실행

사용자의 후속 실행 요청에 따라 `codex/project-efficiency` worktree에서 변경을 분리했다. 앞의 감사 결과는 당시 관측이며, 이 절이 이후 실행 결과다. WordPress 본문·메타·공개 상태 변경은 수행하지 않았다.

- **CI:** Linux CJK collection에서 Korean Black face를 찾아 검증하도록 수정하고 CI font package를 명시했다. event 단위 테스트는 공개 테스트용 map key를 주입한다. 운영의 font/map key 실패 시 보류 정책은 유지한다.
- **배포/통계:** 설치 전 release inventory·SHA·필수 module을 검사하고 backup/rollback 및 설치 receipt를 기록한다. 환경 변수 config에 한해 main/config를 정확히 함께 배포하며 `.env`와 runtime data를 보존한다. 참조가 없는 allowlist의 `copywriter.py`만 retire한다. 실제 public SSH firewall 제한을 확인했고, 기존 제한을 유지한 채 인증된 HTTPS private-report receiver를 추가했다. 실제 Google 전달과 설치 hash의 최종 확인은 main 통합 후 아래 운영 검증에 기록한다.
- **역할 분리:** HTML renderer를 `article_renderer.py`, 원고/검토 schema를 `editorial_schema.py`, HTTP/PDF 수집을 `source_collector.py`, 기관별 parser를 `source_extractors.py`로 추출했다. 기존 facade API를 유지하고 source/reviewer fingerprint에 추출 module을 포함했다. 원본과 추출 renderer의 general/event/no-FAQ fixture HTML이 byte-identical하다.
- **명시적 transport:** process 전체 subprocess patch를 실행 context의 WordPress adapter로 교체했다. 일반 subprocess 분리, context 중첩/오류 복원, 병렬 context 전달, post/command allowlist, CAS/readback, 불명확한 media import 무재시도 계약을 확인했다.
- **목록/측정:** category slug를 함께 조회하고 검토된 원고의 본문·review·lifecycle이 유효할 때만 저장 metadata를 표시한다. 나머지는 추정으로 표시한다. metrics schema 2에 code/release version과 실제 SSH 왕복을 추가하고 미계측은 unknown으로 유지한다.
- **조회 최적화:** image-only 경로의 연속 post/thumbnail 읽기를 한 read-only snapshot으로 묶고 한 번만 소비한다. 다른 호출 후 재사용하지 않으며 import 전 확인과 저장 후 readback을 유지한다. 운영 post 844의 3회 교차 비교에서 결과 SHA/thumbnail 일치, SSH 2→1회, 중앙값 8.46→3.46초(약 59% 감소)를 확인했다. 이는 해당 조회 쌍만의 수치이며 이미지 교체 전체 시간을 뜻하지 않는다.

로컬 전체 Python **843 tests, OK (skipped=1)**. 표적 renderer/source/review/transport/catalog/installer 검사와 rollback 실패 주입을 먼저 통과했다. GitHub [37009366350](https://github.com/ostrichick/bloguito/actions/runs/37009366350)의 Python·WordPress PHP·infrastructure 3 job PASS. 로그/비공개 probe는 Git 비추적 `scratch/tasks/project-efficiency-audit/`에 둔다.

critical-fact 전체 registry 이관, 모든 legacy fallback 제거, 큰 framework/DB 전환은 이번 증거로 우선하지 않는다. 다음 예약 analytics run, 전체 이미지 교체 시간, 모든 공개 글의 최신 공식 정보, full restore drill은 이 코드 검사만으로 검증했다고 주장하지 않는다.

### main 통합 및 운영 검증

[PR #2](https://github.com/ostrichick/bloguito/pull/2)를 merge하여 main `ea36c6d`에 반영했다. main CI [37009885241](https://github.com/ostrichick/bloguito/actions/runs/37009885241)의 Python·WordPress PHP·infrastructure가 모두 PASS다. 기존 로컬 감사 addendum은 scoped stash로 보관한 뒤 통합 문서의 prefix와 완전히 일치하는지 확인했다.

해당 revision의 코드·policy/document **66 files**를 운영에 설치했다. 원본 release와 실제 설치 파일 SHA256 불일치 0개, runtime receipt와 설치 파일 불일치 0개를 독립 조회했다. entrypoint/registry import와 운영 Korean Black font (`Noto Serif CJK KR`, `Black`)가 정상이다. rollback manifest는 `/home/ubuntu/agent-publisher/backups/editorial-20261002T125804Z/manifest.json`이다. env/runtime state를 release에서 제외했고 retired copywriter가 없는 것을 확인했다.

실제 main 수동 analytics [37009904788](https://github.com/ostrichick/bloguito/actions/runs/37009904788)에서 Google 인증·수집·HTTPS 전달이 성공했다. 서버 `google-analytics-2026-09-29.json`은 schema 2, collected_at `2026-10-02T12:58:13.053328+00:00`, SHA256 `6a56b8d3077b354264a924ebb858411c9ccb737ac60c47350eefb9b911f2e1f3`, mode 600이며 freshness/schema validation PASS다. 보고기간 종료일은 Google 데이터 지연을 반영하며 수집 시각과 구분한다. 보고서 원문은 Git/log/artifact에 올리지 않았다. receiver restart 후 active, nginx 검사 PASS, live GET/unauthorized POST/invalid authorized snapshot이 각각 405/401/400임을 확인했다. root token file 600, stage directory 700이며 전달용 token 복사본은 제거했다. 다음 예약 실행(KST 10/3 11:17, GitHub 지연 가능)은 아직 발생하지 않았다.

실제 inventory 69편(공개 62·draft 7)을 다시 읽어 POST_CATALOG를 동기화했다. 본문/review/lifecycle이 맞는 7편은 저장 원고 근거, 나머지는 추정으로 표시했다. 기존 curated backlog를 보존했다. 공개 홈페이지 HTTP 200과 최근 글 제목을 다시 확인했다. 이는 전체 글 내용·출처 최신성이나 시각적 QA를 검증한 것은 아니다. 공개 전환·본문·thumbnail/meta 수정은 이번 작업에 없다.

GitHub main 코드 통합, 운영 release 설치, 실제 private report 수신, 공개 HTTP smoke를 각각 확인했다. 후속 catalog/운영 증거 문서 commit은 배포 대상 코드에 영향을 주지 않으므로 runtime revision은 `ea36c6d`로 유지한다.
