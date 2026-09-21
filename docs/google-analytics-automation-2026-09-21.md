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

## 추가 진행: 장기 키 없는 GitHub OIDC 경로 (2026-09-21 후속)

- 공개 저장소 `ostrichick/bloguito`의 GitHub Actions OIDC를 이용해 **Actions 작업에서만** 짧은 Google 토큰을 발급하는 경로를 조사했다. VPS 자체는 GitHub OIDC 토큰을 받을 수 없으므로 기존 `run_analytics.sh`의 키 파일 인증을 GitHub 워크플로에서 그대로 쓰거나, GitHub OIDC 인증 성공을 VPS 크론 인증 성공으로 간주하지 않는다. 검색어 원본을 공개 저장소/Actions 아티팩트/로그에 올리지 않는다.
- Google Cloud Shell에 사용자 승인으로 접속하고, 프로젝트 `bloguito-analytics`의 프로젝트 번호를 확인했다. `iam.googleapis.com`, `iamcredentials.googleapis.com`, `sts.googleapis.com` 사용 설정 명령이 `finished successfully`를 반환했다. 기존 Search Console/GA4 API는 활성 상태로 조회했다.
- `bloguito-reports` Workload Identity Pool 생성 명령이 `Created workload identity pool`을 반환했다. GitHub의 **변경 불가능한 저장소 ID·소유자 ID, `main` 브랜치, 전용 보고서 워크플로 경로 및 `schedule`/`workflow_dispatch` 이벤트**로 제한된 OIDC 공급자 생성 명령까지 전송했으나, 후속 확인 도구 요청이 보안 상태 불확실로 차단되어 **공급자의 최종 생성 여부는 미확인**이다. 제한 조건을 완화하거나 장기 키 생성으로 우회하지 않았다.
- 공급자의 존재·조건 확인 및 서비스 계정에 대한 `roles/iam.workloadIdentityUser`의 저장소 한정 바인딩, GitHub Actions 인증 테스트, 비공개 보고서 전송 경로, 수집 스케줄은 **실행/검증하지 않았다**. 특히 현재 GitHub 저장소는 공개 상태이므로 보고서 JSON/검색어를 워크플로 아티팩트나 커밋으로 저장하면 안 된다. 사용자 개입 또는 인증 설정을 수행할 수 있는 신뢰된 환경에서 WIF를 확인한 뒤, 서버에 제한된 수신 경로를 별도로 구현·검증해야 한다.
- 이 단계에서도 운영 VPS의 `analytics_collector.py`는 존재하고, 인증 파일은 없으며, 분석 전용 cron 행도 없음을 확인했다. 사용자 통계가 자동으로 수집되고 있다고 알리지 않는다.

## 공급자 확인·실 API 인증 성공 및 비공개 전달 준비 (후속)

- 사용자가 제공한 Cloud 콘솔 화면에 `bloguito-reports` 풀의 공급자 1개·활성 표시가 있었다. Cloud Shell `providers describe github-main`으로 실제 공급자 존재 및 GitHub 소유자 ID·저장소 ID·`main`·전용 워크플로 경로·`schedule`/`workflow_dispatch` 제한 조건을 확인했다. 서비스 계정에 `roles/iam.workloadIdentityUser`를 해당 풀의 **저장소 ID 속성 하나에만** 바인딩했고, `get-iam-policy`의 해당 ID 존재를 확인했다. Google 계정 키는 만들지 않았다.
- 전용 `.github/workflows/google-analytics.yml`을 `main`에 추가하고 수동 인증 검사를 실행했다. GitHub Actions 실행 `35598895966`은 `success`였고 `analytics_collection_ok end=2026-09-18 search_query_rows=1 ga4_day_rows=4`로 두 API의 **실호출 성공**을 입증했다. 이는 검색어 전체 결과가 아니라 반환 행 수이며, 원시 검색어·사용자 데이터·자격증명은 GitHub 아티팩트·커밋·로그로 저장하지 않았다.
- 운영 서버에 `analytics_receiver.py`/`receive_analytics.sh`를 신규 배포하고, Linux 수신기 테스트 5개·Python 컴파일·Bash 문법 검사를 통과했다. 전용 SSH 공개키는 기존 `authorized_keys`를 백업한 뒤 `restrict,command="/home/ubuntu/agent-publisher/receive_analytics.sh"`로만 추가했다. 별도 키를 이용한 **잘못된 JSON 및 원격 명령 실행 시도 모두 차단**을 직접 확인했다. 수신기는 최대 4 MiB·엄격한 스키마·시간·메트릭·행 수를 검증하고 운영 `data/analytics/`의 0700 디렉터리 안에 원자적으로 JSON/Markdown을 0600으로 저장한다. WordPress/Site Kit/기존 크론은 수정하지 않았다.
- 다음 워크플로 수정은 임시 러너에서만 단기 OIDC로 조회한 JSON을 호스트 공개키 지문 고정(서버 SSH를 통해 확인한 ED25519 지문) 및 제한 SSH 키로 서버의 강제 수신 명령에 표준입력 전송하도록 설계했다. 개인 데이터는 GitHub 저장소·아티팩트·로그에 게시하지 않고 러너 임시 디렉터리를 정리한다.
- **현재 남은 수동 의존 단계:** 저장소 Actions 암호화 Secret `BLOGUITO_ANALYTICS_SSH_KEY`에 전용 **SSH 개인키**를 계정 소유자가 GitHub 설정 화면에서 직접 등록해야 한다. 도구의 안전 검사가 개인키를 GitHub Secrets로 전송하는 요청을 차단했으므로 우회하지 않았고, Secret 목록 조회에서도 등록된 항목이 없었다. 개인키의 값은 채팅·출력·Git에 적지 않는다. 사용자는 로컬 사용자 전용 OS 임시 디렉터리의 `bloguito-analytics-report-20260921.key` 파일을 직접 열어 전체 내용을 해당 Secret에 등록하고, 등록 후 키 파일을 폐기해야 한다.
- **Secret 등록 전 절대 금지:** GitHub Actions에 `schedule` 추가, 자동 실행 성공 표시, 개인정보 포함 아티팩트 게시, VPS `run_analytics.sh` 크론 등록. 등록 이후 수동 `workflow_dispatch`로 전송·파일 권한·내용 존재를 확인한 다음에만 일정 트리거를 추가한다. 현재 원격 VPS의 `/home/ubuntu/agent-publisher/run_analytics.sh`는 서비스 계정 JSON 파일을 요구하는 *다른 경로*로서 이 OIDC 흐름과 무관하다.
- 롤백: 새 Actions 워크플로 비활성화, `BLOGUITO_ANALYTICS_SSH_KEY` Secret 폐기, `authorized_keys`에서 정확히 `bloguito-analytics-report-ingest` 전용 제한 키 **한 줄만** 검증 후 제거한다. 기존 SSH 키나 WordPress 로그인·Site Kit는 수정하지 않는다. 보고서 보존/삭제는 별도 사용자 지시를 따른다.

## 공급자 확인 뒤 인증 실험 (2026-09-21 후속)

- 사용자가 전달한 Google Cloud 워크로드 아이덴티티 화면에서 `bloguito-reports` 풀의 공급자 수 1, 사용 설정 상태를 확인했다. Cloud Shell에서 `github-main` 공급자의 이름 및 조건을 직접 조회했으며 저장소/소유자의 불변 ID, `main`, 전용 `.github/workflows/google-analytics.yml`, `schedule`/`workflow_dispatch` 제한이 존재한다.
- 서비스 계정에 `roles/iam.workloadIdentityUser`를 `attribute.repository_id/1367302611`로 한정해 연결했다. Cloud Shell에서 서비스 계정 IAM 정책을 다시 조회해 해당 저장소 ID 포함 여부 `IAM_BOUND`를 확인했다. Google Cloud 프로젝트의 광범위한 IAM 역할은 추가하지 않았다.
- 신규 `.github/workflows/google-analytics.yml`은 **일단 수동 실행만 허용**한다. GitHub Actions OIDC → 서비스 계정 가장 → 두 Google API 조회를 시험한다. 결과 JSON/MD는 러너의 임시 디렉터리에만 작성해 작업 종료 시 삭제하며, 로그는 행 수·성공/실패 코드만 포함하고 쿼리나 보고서 원문을 공개 아티팩트/커밋으로 내보내지 않는다.
- 수동 실조회에 성공하더라도 **VPS 영구 보관·매일 예약 실행·ChatGPT 자동 연동은 별개**다. 공개 저장소에서는 비공개 전달 경로가 구축·검증되기 전까지 `schedule`을 추가하지 않는다. 기존 VPS cron을 바꾸거나 서비스 계정 키를 만들지 않는다.

## GitHub SSH Secret 등록 후 실전 검증 (2026-09-21 후속)

- 사용자 완료 보고 뒤 `gh secret list`에서 `BLOGUITO_ANALYTICS_SSH_KEY`의 등록 시각만 확인했다. GitHub Secret 값 자체는 조회할 수 없으며 값을 채팅·Git·로그에 내보내지 않았다. 운영 수신기, 전용 `authorized_keys` 항목, 0700 저장 디렉터리가 존재하고 보고서 디렉터리는 비어 있음을 확인했다.
- 수동 실행 `35602115419`: Google OIDC 및 양쪽 API 조회 성공(`search_query_rows=1`, `ga4_day_rows=4`), SSH 전송 실패(`libcrypto`, `Permission denied`). 로컬 원본 `.key`는 `ssh-keygen -y -f` 검사에 성공하고 전용 업로드 키의 공개 지문과 일치했다. Secret의 실제 형식은 불명확하다.
- `9eca66e`에서는 Windows CRLF를 정규화하고 로컬 키의 공개 지문과 일치하는지 확인하도록 변경했다. 수동 실행 `35602337056`은 본문 조회 전에 `analytics_delivery_failed:invalid_ssh_secret_format`으로 실패했다. `7e507d0`에서는 BOM/주변 공백 및 문자 그대로의 `\\n` 복사도 정규화하고 비밀값 내용 없이 완전한 OpenSSH 개인키 헤더·푸터를 검사하도록 변경했다. 수동 실행 `35602509717`은 `analytics_delivery_failed:ssh_secret_is_not_complete_private_key`로 종료됐다.
- 따라서 **현재 GitHub에 입력된 값은 완전한 개인키로 인식되지 않는다.** 사용자가 GitHub Secret 값에 로컬 `.key` 파일의 **전체 텍스트(시작/끝 마커 포함)**를 다시 붙여 넣어 교체해야 한다. `.pub` 또는 파일 경로 문자열을 입력하지 않는다. 성공한 업로드가 없으므로 일일 `schedule`을 추가하지 않았으며 VPS `run_analytics.sh` 크론도 설치하지 않았다. 임시 개인키는 재등록 필요로 아직 폐기하지 않았다.
- 복구 후 수동 `workflow_dispatch` 성공 및 서버의 실제 JSON/MD 존재·0600 권한·원문 비공개 검사를 완료해야 예약 실행을 활성화한다. 사용자 데이터는 공개 작업 로그·아티팩트·커밋에 게시하지 않는다.

## Secret 파일 직접 등록 및 일일 자동 실행 활성화 (2026-09-21 후속)

- 사용자가 파일 리디렉션을 이용해 GitHub Secret을 교체했다고 보고했고, `gh secret list`에서 `BLOGUITO_ANALYTICS_SSH_KEY`의 수정 시각 `2026-09-21T13:32:33Z`를 확인했다. Secret 값 자체는 조회하거나 출력하지 않았다.
- 수동 Actions 실행 [35606379576](https://github.com/ostrichick/bloguito/actions/runs/35606379576)은 전체 성공했고, 비공개 전송 명령이 `analytics_ingest_ok end=2026-09-18`을 반환했다. Google API 조회 역시 `analytics_collection_ok end=2026-09-18 search_query_rows=1 ga4_day_rows=4`를 반환했다. 반환 행 수는 전체 방문 수·전체 검색어 수가 아니다.
- 운영 서버 `/home/ubuntu/agent-publisher/data/analytics/`에 `google-analytics-2026-09-18.json`(7176 bytes)과 `.md`(880 bytes)가 존재하고, 저장 디렉터리 권한 0700·파일별 0600을 확인했다. JSON 파싱, `schema_version=1`, 28일 기간 `2026-08-22 ~ 2026-09-18`, 검색어 1행·GA4 일별 4행, Markdown 비어 있지 않음을 원문을 노출하지 않고 검증했다. 공개 GitHub 로그·아티팩트·커밋에 원시 보고서를 업로드하지 않는다.
- 위 성공 후 `.github/workflows/google-analytics.yml`의 GitHub Actions 일정 `17 2 * * *`(UTC 02:17 / KST 11:17)를 활성화했다. GitHub 예약 작업은 지연될 수 있으며, 최초 예약 실행은 아직 미래이므로 그 실행의 성공은 별도로 확인해야 한다. 날짜 범위는 실행 시점의 UTC 날짜에서 3일 이전까지 28일이다. 기존 VPS의 서비스 계정 키 기반 `run_analytics.sh` 크론은 설치하지 않고 기존 크론과 WordPress/Site Kit는 변경하지 않는다.
- 자동화 중지 시 GitHub 워크플로의 `schedule`만 제거하거나 워크플로를 비활성화한다. 향후 인증키 교체 시 `BLOGUITO_ANALYTICS_SSH_KEY`와 서버의 강제명령 전용 공개키를 함께 교체한다. 통계 보고서의 ChatGPT 자동 전달/직접 접근은 별도의 연동이므로 아직 검증한 것으로 간주하지 않는다.

## QA/일반 방문을 혼동하지 않도록 구분하는 후속 개선 (2026-09-22)

- 기존 스냅샷은 **과거 데이터**다. Direct 53세션을 사람 53명·봇 53명 또는 개발자 53명으로 역분류할 증거는 없다. 자연 검색 클릭도 실제 사람을 보증하지 않는다. 향후 보고서에서도 Direct를 기본적으로 `사람/봇 미확인`으로 표시한다.
- 운영 WordPress Site Kit의 `googlesitekit_analytics-4_settings` 중 민감정보가 아닌 두 필드만 WP-CLI `option pluck`으로 확인했다: `trackingDisabled=["loggedinUsers"]`, `useSnippet=true`. 즉 **로그인 상태**는 Site Kit에서 이미 GA 수집 제외 대상으로 설정돼 있다. 다른 코드로 추가 차단하거나 변경하지 않는다. 이 설정이 지난 비로그인 에이전트 방문을 식별하거나 과거 데이터에 소급 적용되지는 않는다.
- GA4의 실제 내부 트래픽 필터를 `활성`으로 변경하면 해당 데이터가 영구적으로 처리되지 않는다. **속성의 IP 규칙·데이터 필터는 만들거나 변경하지 않았고**, 필터 상태를 미확인한 상태에서 이벤트에 `traffic_type=internal`도 일괄 주입하지 않는다. 공식 테스트 필터를 추가로 구성하려면 GA4 속성 편집자 권한과 식별할 IP/범위 확인이 필요하며, 먼저 `테스트` 상태에서 검증한다. 특히 다른 IP를 사용하는 원격 에이전트 전체를 사용자의 IP 하나로 식별할 수는 없다.
- 대신 별도 권한이나 영구 제외 없이 GA4 기본 제공 세션 수동 소스/매체로 QA 유입을 식별한다. **비로그인 에이전트의 브라우저 첫 진입**은 `https://lifeinfo24.org/?utm_source=bloguito_qa_agent&utm_medium=internal_test&utm_campaign=site_checks`, **소유자 비로그인 테스트의 첫 진입**은 `https://lifeinfo24.org/?utm_source=bloguito_qa_owner&utm_medium=internal_test&utm_campaign=site_checks`를 사용한다. `AGENTS.md`에 에이전트 진입 규칙을 기록했다. URL의 UTM은 인증 수단이 아니며, 일반 독자에게 배포하거나 Google 검색용 정규 링크로 사용하지 않는다. 로그인 상태라면 Site Kit가 애초에 측정을 제외하므로 태그가 보이지 않는 것이 정상일 수 있다.
- 수집기 스냅샷 v2는 기존 GSC/GA4 보고서 외에 GA4 `sessionManualSourceMedium`+`sessionDefaultChannelGroup`의 `sessions`를 조회하고 **QA 에이전트 / QA 소유자 / 태그 없는 Direct / 나머지 미확인**으로 구분한다. QA 태그 외의 방문은 `사람`으로 표시하지 않는다. 채널별 세션 합계와 소스별 합계가 다르거나 응답이 잘리면 결과를 불완전으로 표시/실패시킨다. 수신기는 스키마 v1도 유지해 기존 보고서를 읽을 수 있다.
- QA 태그는 해당 URL로 시작한 **앞으로의 세션만** 식별한다. 자발적 태그 없이 방문한 비로그인 사용자·JS를 실행하는 봇·태그를 누락한 에이전트는 여전히 미확인이다. 최초 실측 tagged 세션은 GA4 처리 지연 후 다음 예약 수집에서 재확인한다. 이 방법은 Google의 내부 트래픽 데이터 필터를 만들었다는 뜻이 아니다.
- 일일 스케줄 커밋 `4e38f09`를 `main`에 푸시한 뒤 원격 워크플로 YAML에서 `schedule: 17 2 * * *`를 확인했다. 해당 커밋의 수동 재실행 [35606725963](https://github.com/ostrichick/bloguito/actions/runs/35606725963)은 전체 성공하고 `analytics_collection_ok` 및 `analytics_ingest_ok`를 반환했다. 같은 커밋의 GitHub `Test Suite` [35606673535](https://github.com/ostrichick/bloguito/actions/runs/35606673535)도 성공했다. 로컬 관련 테스트 13개 실행에서 실패 0건·Windows 심볼릭 링크 권한으로 1개 건너뜀을 확인했다.
- 재실행 후 서버에서 JSON·Markdown의 존재와 0600/0700 권한, 기간·행 수를 다시 확인했다. VPS crontab에는 기존 백업 및 초안 생성 항목 2개만 남아 있다. OS 임시 폴더에 있던 업로드용 전용 개인키와 대응 공개키 파일을 올바른 공개 지문과 일치하는지 확인한 뒤 각각 삭제했다. GitHub Secret과 서버 강제명령 수신 공개키는 유지했다.
- **예약 실행 자체의 첫 실제 실행과 장기 신뢰성은 아직 관측하지 않았다.** GitHub의 예약 시각은 지연될 수 있다. WordPress/Site Kit 및 기존 글·서버 크론을 건드리지 않았으며, 민감한 보고서의 자동 ChatGPT 전달 기능은 별도 단계다.

### QA 방문 구분 배포 및 실 API 검증 결과

- 기존 무관한 `agents/curator.py`, `agents/publisher.py`, 다른 에이전트의 테스트 및 `docs/INDEX.md` 미커밋 변경은 보존하고, `AGENTS.md`·분석 수집기/수신기 및 전용 테스트/이 문서만 커밋 `4a67eec`로 푸시했다. 필터를 활성화하거나 WordPress의 Site Kit 옵션을 변경하지 않았다.
- Windows 관련 테스트 **17개, 실패 0·symlink 권한으로 1개 건너뜀**; 서버 격리 디렉터리의 Linux 관련 테스트 **17개 모두 통과**, Python 컴파일 검사 통과. 기존 운영 수집기와 수신기는 격리 백업 후 신규 버전으로 교체했으며 배포 파일과 격리 검증본의 SHA256이 각각 같음을 확인했다. 구형 스냅샷 형식도 수신기에서 테스트했다.
- 실제 Google 조회·비공개 업로드 수동 실행 [35668182242](https://github.com/ostrichick/bloguito/actions/runs/35668182242) **성공** (`analytics_collection_ok`, `analytics_ingest_ok`), 수신 서버에 스냅샷 v2가 생성됐다. 서버 `/home/ubuntu/agent-publisher/data/analytics/google-analytics-2026-09-18.json` 7999바이트 및 `.md` 1314바이트, 폴더 0700·파일 0600 재확인. 원시 방문 데이터·인증 정보는 GitHub 로그·아티팩트·커밋에 업로드하지 않았다.
- 과거 집계 2026-08-22~09-18을 v2로 재조회한 보고서는 `QA 에이전트 0세션`, `QA 소유자 0세션`, `태그 없는 Direct 53세션`, `QA 태그 없는 기타 4세션`으로 표시한다. **0건은 이전에 에이전트/소유자가 방문하지 않았다는 증거가 아니라, 과거 세션에 전용 QA UTM이 없었다는 의미**다. 현재 비로그인 QA URL로 실제 GA4 세션이 발생했는지는 미검증이다. GA4 처리 지연 및 수집 종료일 UTC 3일 전 조건상 향후 새 태그 방문이 보고서에 나타날 때 확인해야 한다.
- GitHub 예약 실행 `17 2 * * *`는 유지했고 기존 VPS cron·WordPress 게시물·사용자 트래픽은 수정하지 않았다. 실제 GA4 IP 내부 트래픽 **테스트** 필터는 별개이며 미설정 상태다. 스스로 식별하지 않은 방문은 일반 독자 수로 산정하지 않는다.
