# Microsoft Clarity integration — 2026-09-29

- 운영 WordPress에 공식 `Microsoft Clarity` 플러그인 `0.10.33`을 설치·활성화했다.
- 설치 직후 운영 홈페이지는 HTTP 200을 유지했다.
- 이후 Microsoft 계정에서 Clarity 프로젝트 연결을 완료했고, 운영 WordPress의 `clarity_project_id`가 저장된 것을 재확인했다.
- 테마 파일을 직접 수정하지 않고 `wordpress/mu-plugins/bloguito-clarity-content-insights.php`를 추가했다. GeneratePress의 `generate_article_microdata` 필터를 사용해 단일 글의 바깥 `<article>`에만 `data-clarity-region="article"`을 추가한다.
- 아카이브/목록 article과 본문 안의 행사 카드용 `<article>`에는 이 속성을 추가하지 않는다.
- 공개 HTML에서 `https://www.clarity.ms/tag/<project-id>?ref=wordpress` 추적 스크립트와 `data-clarity-region="article"`이 함께 출력되는 것을 확인했다.

## 2026-10-11 성과 분석 접근 점검 및 다음 수집 단계

- 운영 WordPress의 Microsoft Clarity 플러그인 연결과 태그 설치는 확인됨. 그러나 현재 CoS 연결에 Clarity 대시보드/로그인 브라우저 제어 도구가 노출되지 않았고, 읽기 가능한 운영 프로세스·로컬 환경변수에 Clarity API 토큰이 확인되지 않았다. 검색한 ChatGPT 플러그인 목록에도 Clarity 직접 연동 앱이 확인되지 않았다. 이것은 프로젝트의 미수집·세션 0을 뜻하지 않는다.
- `wp_clarity_collect_events`는 HTTP 요청/수집 이벤트 저장소이지 Clarity의 사용자 세션·스크롤·rage/dead-click·녹화 집계가 아니다. Google GA4/WP Statistics의 세션·뷰와 혼용하지 않는다.
- Microsoft 공식 API 문서: https://learn.microsoft.com/en-us/clarity/setup-and-installation/clarity-data-export-api . 관리자 계정에서 `https://clarity.microsoft.com/` → **해당 프로젝트 → Settings → Data Export → Generate new API token**으로 토큰을 생성할 수 있다. 토큰은 채팅, Git, 작업 로그, WordPress 옵션, CLI 명령 인자에 넣지 않는다.
- **준비된 수집기:** `agent-publisher/clarity_collector.py`는 인증된 HTTPS `GET /export-data/api/v1/project-live-insights` 호출로 롤링 24시간 기본(옵션 48/72시간) 전체 요약/Device/URL 세 관점을 요청한다(기본 3회/일, API 프로젝트당 10회/일 한도). 응답을 무해한 에러 코드로 검사하고 비공개 `data/clarity/clarity-YYYY-MM-DD.json`에 날짜별 원자적 신규 저장한다. 출력 디렉터리는 Linux 0700, 파일은 0600을 요구하며 토큰/Authorization 헤더는 출력·저장하지 않는다. 동일 KST 날짜에 저장본이 있으면 다시 API 호출하지 않는다.
- 운영 준비 전제: 사용자가 **Clarity 프로젝트 관리자 세션에서 생성한 토큰**을 직접 개인 저장소의 0600 파일(예: `/home/ubuntu/.config/bloguito/clarity-token`)로 안전하게 설치하고 해당 상위 디렉터리 0700을 확인해야 한다. 노출 위험 때문에 토큰 내용을 ChatGPT에 붙여 넣지 않는다.
- Windows PowerShell에서 `ssh bloguito`를 실행해 운영 서버의 **직접 연결된 대화형 터미널**로 접속한 뒤 다음 명령을 한 줄씩 입력하면 터미널 화면과 셸 히스토리에 토큰을 표시하지 않고 저장할 수 있다. `read`의 비표시 입력 요청에서만 발급된 토큰을 붙여 넣는다.

  ```bash
  umask 077
  mkdir -p -m 700 /home/ubuntu/.config/bloguito
  read -r -s -p 'Clarity API token: ' CLARITY_TOKEN
  printf '\n'
  printf '%s' "$CLARITY_TOKEN" > /home/ubuntu/.config/bloguito/clarity-token
  unset CLARITY_TOKEN
  chmod 600 /home/ubuntu/.config/bloguito/clarity-token
  stat -c '%a %n' /home/ubuntu/.config/bloguito/clarity-token
  exit
  ```

  마지막 `stat` 결과는 `600 .../clarity-token`이어야 한다. API 토큰을 WordPress 플러그인 설정이나 GitHub 공개 저장소에 복사하지 않는다.
- 수집기 실행 예시(운영에 적절한 파일 설치·검증 뒤): `python3 agent-publisher/clarity_collector.py --token-file /home/ubuntu/.config/bloguito/clarity-token --output-dir /home/ubuntu/agent-publisher/data/clarity`. `--view summary`처럼 관점을 좁힐 수 있으나 그날 스냅샷이 존재하면 두 번째 실행은 건너뛰므로 첫 호출에서 필요한 관점을 결정한다. 인증된 live 200 및 응답 schema 확인, 비공개 권한·파일 readback 검증 전에 예약 작업을 만들지 않는다.
- API 기간은 **최근 1·2·3일의 롤링 기간**이지 7/30일 과거 일별 기록이 아니다. 매일 수집한 스냅샷을 단순 합산하면 시간 창 중복 및 비중복 사용자 수 때문에 왜곡될 수 있다. UTC 기준의 실제 `collected_at_utc`와 `window.hours`를 보존한다. 긴 기간의 행동 추이는 일별 관측 품질 확인 후 별도 집계 설계가 필요하다. API는 요청당 최대 1,000행이며 페이지네이션이 없다. UI의 과거 7/30일 뷰는 API의 소급 범위와 별개다.
- **2026-10-11 실제 상태:** 수집기 `agent-publisher/clarity_collector.py`를 운영 서버 `/home/ubuntu/agent-publisher/clarity_collector.py`에 신규 배치했고 로컬/서버 SHA-256 `d45f960c0acb88c02cc1f70921171df45c058d32e338c93313bddc03d4db156c` 일치와 서버 Python 구문 검사 성공을 확인했다. 오프라인 표적 테스트는 Windows 5/5 및 실제 서버 Linux 5/5 통과했고, 비공개 결과 폴더를 `.gitignore`에 추가했다. 서버의 `/home/ubuntu/.config/bloguito/`와 `/home/ubuntu/agent-publisher/data/clarity/`는 `ubuntu:ubuntu`/0700으로 생성했다. API 토큰 파일은 아직 존재하지 않으며 CLI의 실측 미호출 경로는 `clarity_collection_failed:token_file_unavailable`; 보고서 0개, Clarity cron 0건을 확인했다. 따라서 Clarity live 응답, 실제 사용자 지표, 자동 수집은 아직 미확인/미실행이다. 인증을 추가하면 **토큰이 현재 WordPress에 연결한 Clarity 프로젝트와 일치하는지** URL 관점/프로젝트 관리 화면에서 검증하고, 비공개 스냅샷의 원본 필드 단위를 확인한 뒤 GA4/WP 통계와 비교한다.
