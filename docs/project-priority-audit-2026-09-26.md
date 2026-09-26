# 전체 프로젝트 스캔 및 우선순위 분석 — 2026-09-26

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
