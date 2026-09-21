# Search Console·GA4 자동 통계 수집 — 2026-09-21

## 목적과 사실 상태

- `lifeinfo24.org`의 검색 유입 키워드와 GA4 방문 지표를 매번 CSV로 전달하지 않고 수집하는 읽기 전용 독립 기능이다. 공개 글·WordPress·Site Kit 설정은 수정하지 않는다.
- 서비스 계정 `bloguito-report-reader@bloguito-analytics.iam.gserviceaccount.com`은 사용자 브라우저에서 생성·확인했고, Search Console URL 속성에 `제한적`, GA4 생활정보24 속성에 `뷰어`로 확인됐다. 두 API 사용 설정은 사용자가 완료했다고 보고했다. 권한 목록 존재는 **자동 인증/실수집 성공을 뜻하지 않는다**.
- 실제 운영 GA4 속성 ID `554325332`는 당시 WordPress의 Site Kit 설정 중 ID 필드만 조회했다. Search Console URL 속성은 `https://lifeinfo24.org/`이다. 운영 서버는 QEMU 기반 외부 VPS로, gcloud·AWS 명령이나 관리형 Google 실행 신원은 당시 확인되지 않았다.
- Google 공식 지침은 외부 워크로드에 **Workload Identity Federation(단기 인증)**을 우선 권장한다. VPS에는 신뢰할 만한 외부 IdP 연결이 아직 없다. GitHub OIDC는 별도 GitHub Actions 워크로드에 적합하지만 VPS 크론에 그대로 적용되지 않으며, 현재 공개 저장소의 Actions 아티팩트에 원시 검색어를 올리지 않는다. 장기 서비스 계정 키가 필요하면 별도 보안 검토·회전/폐기 계획 하에서만 발급한다.

## 구현

- `agent-publisher/analytics_collector.py`: Google ADC로 인증, Search Console `webmasters.readonly`/GA4 `analytics.readonly` 권한 범위. Google API 두 도메인에만 POST. GSC 검색어·페이지·일별 클릭/노출/CTR/순위, GA4 일별 활성 사용자/세션/조회수·기본 채널별 세션/사용자·페이지 경로별 조회수/사용자를 조회한다. 기본 종료일은 UTC 3일 전이며 28일을 집계한다. Search Console은 `dataState=final`로 요청한다.
- 성공한 **양쪽 API의 전체 응답**만 완성된 스냅샷으로 반환하고 `data/analytics/google-analytics-YYYY-MM-DD.json` 및 같은 이름의 `.md` 보고서를 작성한다. 임시 파일(0600)→원자적 교체, 저장 디렉터리(0700). HTTP 403/401, 네트워크 실패 등은 오류 코드만 표준 오류로 보고하고 Google 응답 본문·키·토큰·원시 검색어는 로그에 남기지 않는다. 실패하면 성공 상태를 출력하지 않는다.
- `agent-publisher/run_analytics.sh`는 개인 인증 파일 `data/analytics/reader-credentials.json`을 사용하는 VPS 실행 진입점이다. 인증 파일 0600·디렉터리 0700을 검사한다. 파일은 반드시 운영 서버에만 보관하고 Git, 채팅, 로그, 공개 웹루트에 두지 않는다. 새 파일은 `.gitignore`에 의해 추적 제외된다. 기존 백업은 `data/` 루트의 JSON만 포함하므로 이 인증 파일은 복구 시 별도 재발급이 필요할 수 있다.
- `tests/test_analytics_collector.py`는 실제 Google 호출 없이 성공·완성 전 실패·빈 결과·잘못된 응답·기간·개인 파일 권한·원자적 덮어쓰기·링크 대상 거부·보고서 렌더링을 검증한다. Windows에서는 심볼릭 링크 생성에 권한이 없으면 해당 한 테스트만 건너뛴다. Linux에서 재검증한다.

## 운영 설치 절차 (성공 확인 후에만 크론 활성화)

1. 서버 파일이 실제 배포됐는지 확인하고 `python -m py_compile analytics_collector.py`, `bash -n run_analytics.sh` 및 오프라인 테스트를 실행한다.
2. 장기 키 대신 외부 신원 제공자를 연결할 수 있으면 `GOOGLE_APPLICATION_CREDENTIALS`에 키가 아닌 WIF 구성 파일을 지정해 직접 `analytics_collector.py`를 실행한다. 현재 `run_analytics.sh`는 **서비스 계정 키 파일 전제**라 WIF 경로에 쓰려면 런처를 교체해야 한다. 키를 사용할 경우 관리자가 키를 안전한 경로에 직접 배치하고 소유자 `ubuntu`, 모드 0600, 디렉터리 모드 0700을 재검증한다. 키는 채팅에 붙여 넣거나 GitHub Secrets 없는 공개 저장소에 추가하지 않는다.
3. `./run_analytics.sh`를 수동 실행해 종료 코드 0·`analytics_collection_ok`를 확인하고, JSON/MD 결과에 실제 Search Console·GA4 데이터가 있는지 확인한다. 빈 데이터는 성공 호출과 구별해 검토한다.
4. 이 테스트가 성공한 **뒤에만** 사용자 `ubuntu`의 crontab에 예시 `30 6 * * * /home/ubuntu/agent-publisher/run_analytics.sh >> /home/ubuntu/agent-publisher/data/analytics/collector.log 2>&1`을 추가한다. `collector.log`는 private 폴더 안에 두고 기존 백업·08:00 글 작성 크론을 변경하지 않는다. 일일 수집 시점을 바꾸면 크론 시간과 Google 통계 지연 기간을 따로 기록한다.
5. `data/analytics/`는 비공개 내부 수집물이며 외부 웹·GitHub 저장소·공개 링크로 공유하지 않는다. 주간 분석은 별도 ChatGPT 연동 경로가 검증되기 전까지 자동 전달됐다고 주장하지 않는다. Google API의 검색어 공개 제한·익명화와 GA4 세션/검색 클릭 정의 차이를 보고서에 유지한다.

## 미완료/롤백

- 수집 코드의 준비, 서비스 계정의 실제 API 인증 및 자동 스케줄 운영은 **서로 다른 상태**다. 인증이 없거나 실호출이 실패하면 크론을 먼저 켜지 않는다.
- 수집을 중단하려면 분석 전용 크론 행만 제거한다. 필요하면 서비스 계정 사용자를 Search Console/GA4에서 각각 제거하고 인증 키를 폐기한다. WordPress Site Kit 연결은 건드리지 않는다. 수집된 JSON/MD를 지울 때는 별도의 확인과 보존 정책을 적용한다.

## 실제 반영 및 검증 증거 (2026-09-21 KST)

- 작업 시작 기준 Git `27e58f9`. 다른 에이전트의 `agents/`, `editorial_cli.py`, 각종 테스트, `docs/EDITORIAL_SYSTEM.md`, `docs/INDEX.md` 및 기존 미추적 문서는 편집하지 않았다.
- 로컬 전용 테스트: **8개 통과 중 Windows symlink 권한 사유로 1개 건너뜀**. `bash -n run_analytics.sh` 통과. 서버 `/home/ubuntu/agent-publisher/data/editorial_runs/analytics-stage-20260921/`에 3개 파일(수집기·런처·테스트)을 보내 Linux 독립 테스트 **8개 모두 통과**, 서버 Python 컴파일·Bash 문법 검사 통과.
- 운영 서버 `/home/ubuntu/agent-publisher/analytics_collector.py`와 `run_analytics.sh`는 이전에 없던 새 파일로 배포했다. 서버의 코드와 스테이징 사본 SHA256이 각각 일치함을 확인했다. 기존 공개 글·WordPress/Site Kit·기존 크론은 수정하지 않았다.
- 키 파일이 없을 때 실제 런처는 `analytics_collection_failed:credential_file_unavailable`만 출력하고 실패했다. 당시 `data/analytics/` 및 분석 크론 행이 없음을 확인했다. 이후 인증 파일을 안전하게 받을 빈 `data/analytics/` 디렉터리만 모드 0700으로 만들고 키 부재를 재확인했다. **실제 GSC/GA4 API 조회·키 없는 토큰 발급·비공개 보고서 생성·일일 자동 실행은 미검증/미설정**이다.
- Google Cloud 서비스 계정의 키 화면에는 장기 키 보안 경고가 표시됐다. 장기 키 생성 자동화 요청은 보안 상태를 확인할 수 없어 도구가 차단했으며 이를 우회하거나 키를 생성하지 않았다. 직접 인증 정보가 없으므로 여기서 수집 성공 또는 완전 자동화를 주장하지 않는다. 사용자의 안전한 인증 제공 또는 별도 WIF 실행 플랫폼 결정이 다음 의존 작업이다.
