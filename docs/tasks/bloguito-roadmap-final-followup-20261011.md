# Bloguito 5단계·14개 로드맵 추가 실측 및 운영 보완 (2026-10-11)

## 출발점과 실제 운영 변경

- 출발점: 통합 `2cde4f74f16cae2fa68180aafc431d258bca84bc`, 운영 `e10a20f29473c129c1ba0410c11ab2c8fd77e5d3`. 앞선 실제 MariaDB CAS·COMMIT 응답 유실·v3 전체 복원·런타임 롤백 CI PASS, Python 1,335건 및 운영 92/92 SHA 검증을 **다시 수행하지 않았다**.
- 이번 코드 릴리스: **`b6e0f51904a6e322bc82c4e496d2609b7ad974cf`**, inventory digest `e2b6b13723b8fca851977c656eda41c1c3b906534d264cb2831619db60252213`, **93개 파일**. 이전 설치 릴리스와 MU의 호환성 확인 후 정규 installer로 증분 운영 적용했다. 운영 신규 설치 결과 `editorial-release.json`/92→**93/93** installed byte SHA 일치, `run_daily.sh` 실행 가능, editorial lock 해제, MU SHA `d10d4b3bff10378f965b7e9db8d6d912c3ee99fdeb833136e0774939639794fa` 그대로 확인.
- 새 설치 자동 롤백 영수증: `/home/ubuntu/agent-publisher/backups/editorial-20261011T093956Z-997318161d0a/manifest.json` (현재 릴리스 직전 e10a20f 런타임의 파일별 사본). 기존 원본 MU 백업 `/home/ubuntu/agent-publisher/backups/mu-pre-e10a20f-20261011.bin` 및 사전 독립 v3 아카이브 `/home/ubuntu/backups/bloguito_backup_20261011_175028.tar.gz`도 보존. 비파괴 설치 전 `--preflight-only` 통과, 소프트웨어 설치 후 smoke PASS. 이미 통과한 v3 restore나 운영 백업 검사를 새로 실행하지 않았다.
- WordPress 공개 글 **#641**은 `publish`와 동일 저장 본문 SHA `78aa3ebed10a8eac20ae5e927f69e7a5b468b14e20b690a277e138a61aec3c17`가 재확인됐고 공개 canonical 이동 후 HTTP 200이었다. 신규 글 생성·본문 변경·공개 발행·비멱등 이미지 업로드는 **0건**.
- 정규 `0 8 * * * /home/ubuntu/agent-publisher/run_daily.sh`는 유지. 관측 마지막 성공한 08:00 로그는 **2026-10-11 08:00 (구 릴리스)** `growth_action=no_action`, `published=0`, `errors=0`. **2026-10-12 08:00 KST 신규 릴리스 예약 실행은 이 문서 작성 시점에 아직 도래하지 않았으며 미확인**. 수동 cron 실행 금지.

## F1·F2 운영 성능 정확성

- `scripts/ops/workflow_release_observer.py`는 운영 JSONL을 SSH로 읽기만 하고 확정 릴리스, action, route, transport, `workload_signature` 및 최소 5개 `live` 성공 표본을 대조한다. 기존 `summarize_workflow_metrics.py --compare-versions`도 작업 특성 누락/미분류를 비교 부적합으로 처리한다. 새 계측은 source 개수 구간과 image 포함 여부만 기록하고 원고·출처 URL·이미지 경로를 보관하지 않는다.
- 첫 검사: 운영 원본 `workflow-metrics.jsonl` **7개 기록/성공 4개**, 설치 `e10a20f` 이후 성공 0. 기존 보고서의 80건/34코호트는 이 운영 파일만으로 **재현되지 않으며**, 원본 자료가 증명되기 전 무단 합산 금지. 신규 `b6e0f5` 설치 후 **읽기 전용 `list-drafts` 1회 PASS**로 metrics 기록 기능이 정상 동작함을 확인했다. 현재 **운영 총 8개 행/성공 5행/신규 설치 릴리스 성공 1행**이며 이 1행은 비교 가능한 신규 글 생성·수정·이미지 교체가 아님. 비교 가능 코호트 0, **전체 작업 median/P90 및 SSH/WP 개선률은 미측정**.
- F2 운영 WP-CLI의 분리 2회 vs 단일 snapshot 조회를 글 #641의 동일 SHA·상태에서 각 **5회씩** 읽기 전용 측정했다. WP 프로세스 내부 호출 비용은 분리 조회 **median 4,391.99ms / P90 7,694.60ms / WP calls 2**, 통합 **median 2,377.42ms / P90 3,135.60ms / WP calls 1**. WordPress 내부 PHP 프로세스 실행 벤치마크일 뿐 실제 SSH adapter 왕복/전체 editorial 업무 지연/host 이미지 생성·인간 검수의 실측은 아니다. 표본 5쌍으로 인과적 업무 전체 속도 향상을 주장하지 않는다. 근거/한계 `docs/tasks/workflow-performance-live-20261011.md`.

## Q1 실제 전체 페이지·2배 시각 확대·CTA

- 운영 공개 글 #641의 실제 Edge browser/CDP 390×844 **47개 연속 PNG**가 본문 전체 scrollHeight **22,016px**, 1280×900 **31개 PNG**가 **15,584px**까지 덮는다. 기존 첫 viewport의 `browser_pass`(TOC 12·표 4, 가로 넘침 없음)와 별도로 최신 `scripts/verify_full_page_browser_qa.py`에서 모든 화면 PNG SHA/차원/URL/post ID/연속 scroll 구간을 독립 재검증하여 `supplemental_full_page_verified` PASS. 원본 중 292px 누락된 캡처는 PASS로 쓰지 않고 새 `stable/` 시리즈를 사용. 연락처·로그인·WP mutation 없이 확인했다.
- CDP `Emulation.setPageScaleFactor(2)` 실제 `visualViewport.scale=2`를 390/1280 양쪽에서 확인했다. **시각적 page zoom이지 브라우저 메뉴 native 200% 확대 자체를 증명하지는 않음**. 기존 절반 viewport 트릭은 사용하지 않았다.
- `_blank` CTA를 실제 마우스 이벤트로 클릭하여 새 탭 `https://rsvn.science.go.kr/nsm/edcarsvn/edcarsvnDetail?edcPrgmid=2782`에서 Document HTTP **200 / text/html**을 관측했다. 원래 글 탭 보존, POST/폼 제출·예약 처리 0건. 이것은 supplemental CTA 증거이며 자동 WordPress task-state 승인/상태 변경이 아니다.
- 기존 인증된 관리자 Preview 탭이 확인되지 않았으므로 인증 미리보기는 **미검증**. 사용자가 기존 관리자 세션을 합법적으로 열어 제공할 때에만 수행 가능. 증거 원본 `scratch/tasks/q1-full-641-20261011/stable/full-page-evidence.json`, `stable/segments/`, `stable/contact-sheets/`, `cta-new-tab-evidence-final.json` (통합 worktree에 독립 복사). 첫 파일 SHA256 `a296246f229d5a2bae302f4157351d8b6575538543cacd272de19096b1bca811`, CTA receipt SHA256 `15a36a64332505976feaf112b5dbc583f453abdfa1743114e5b779ec20d4a881`.

## Q3/R1/R2 증분 보완

- Q3 결과 불명확 이미지 import에서 unique SHA 후보만으로 attachment를 자신의 것으로 채택하던 경로를 제거했다. 과거 호출이 실제 종료됐는지 확인되지 않으면 **썸네일 CAS조차 실행하지 않으며**, 재업로드 역시 금지. `image_import_attempt`의 원본 SHA·기존 attachment ID snapshot을 기준으로 **읽기 전용 후보**만 제시하고 SHA가 틀리면 조회를 시작하지 않는다. `image_outcome.attachment_id`가 원래 정확하게 저장됐고 종료 증거가 있는 정상 정규 복구 경로는 기존 CAS/readback을 유지한다.
- 신규 Draft S3 저널의 `begin→created(정확한 ID)→complete(같은 ID)` 기록을 불변으로 강화했다. 최초 저장된 ID가 다른 번호로 변경되거나 `created` 없이 완료되는 경로는 거부하고 일치하는 재실행만 idempotent로 취급한다. ID 불명확 상태에서 본문/제목만으로 임의 소유권 인정 또는 두 번째 `post create` 금지.
- R1 `agents/media_recovery_contract.py`에 모호한 미디어 상태의 공통 순수 판정 모듈을 새로 추출하고 `featured_image.py`와 `edit_orchestration.py`의 중복·위험한 SHA 자동 채택을 제거했다. 기존 공개 3개 CLI, 동시성 잠금, rollback/이미지 승인, 공식 출처·semantic review·CAS/readback은 유지.
- R2 운영 MU의 `manual_agent_delegated` 정책 SHA가 배포 상태와 일치하는 점을 읽기 전용 재확인했다. 실제 image_gen/save_image 호출의 **독립 호스트 증빙은 여전히 확보되지 않았고**, `origin_claim`, 후보 manifest만으로 이를 생성하거나 증명한다고 주장하지 않는다.

## 수용 기준 기반 14항목 판정

| 항목 | 판정 | 여전히 충족하지 못한 수용 조건 |
| --- | --- | --- |
| S1 | 완료 | 다음 신규 릴리스 08:00 실행 관측은 별도 운영 추적 |
| S2 | 완료 | 운영 임의 이미지 교체 없이 CI/테스트 CAS로 검증, 콘텐츠 적용은 별도 |
| S3 | 완료 | 소유권을 알 수 없는 Draft 자동 채택은 설계상 차단 |
| T1 | 완료 | 실제 주제별 수동 의미검토는 건별로 지속 |
| T2 | 완료 | 서로 다른 파일들의 전역 DB 트랜잭션이라는 주장은 하지 않음 |
| T3 | 완료 | 신규 Draft 메타 실제 DB CAS·rollback 검증은 기존 CI에서 완료 |
| T4 | 완료 | 공식 자료 선택 추출과 source/review freshness 계약 구현 |
| F1 | **부분** | 이전/신규 동질 완료 표본 최소 5건씩 미확보, 전체 작업 성능 미측정 |
| F2 | **부분** | WP 읽기 미시 벤치 PASS, 실제 SSH roundtrip/전체 작업 wall clock 개선 미측정 |
| Q1 | **부분** | 전체 공개 글/CTA/시각적 2x는 검증, native 브라우저 메뉴 200%·인증 Preview·보조 QA task-state 결합 미검증 |
| Q2 | 완료 | 후보 보고 도구 구현, 실제 검색 유입 인과 평가는 별도 |
| Q3 | **부분** | 확인된 ID의 정규 복구 강화, 소유권 불명 비멱등 복구는 절대 자동 수행 불가 |
| R1 | **부분** | 신규 안전한 media contract 분리, 남은 대형 편집·SSH 전송 구조는 단계적으로 개선 필요 |
| R2 | **부분** | imagegen/CoS 실제 호스트 도구의 독립 attest 불가 |

**합계:** 구현 완료 8개, 부분 6개, 완전히 미착수 0개. 현재 새 signed runtime은 운영 적용됐으나 모든 항목의 원래 수용 기준이 달성된 것은 아니다.

## 필요한 사용자 개입 및 앞으로의 검증

1. **지금 즉시 필요한 비밀번호/승인 없음.** 10월 12일 08:00 KST 이후 정규 cron 실제 로그·lock·`PIPELINE_RESULT`·post ID·metadata/image readback을 조회해야 한다. 이전 11일 08:00 성공을 새 릴리스의 성공으로 전용하지 않는다.
2. 인증된 WordPress Draft Preview까지 검사하려면 **기존 정당한 관리자 브라우저 세션 제공**이 필요하다. 아직 이를 요구하지 않고 공개 글 실측만 반영했다.
3. image_gen 호스트 원본 호출을 독립 증명할 수 있는 정확한 API/서명 로그가 제공되지 않는다면 provenance 증빙 범위는 기존 SHA·selection actor·staged receipt까지만 유지한다. 임의 attestation 생성 금지.
4. 응답 유실로 attachment/process ownership이 불명확한 경우에는 이전 작업의 **정확한 original receipt와 종료 확인**이 있어야만 정규 검토와 CAS를 거친다. 없다면 작업은 차단하며 자동 재업로드·공개 발행하지 않는다.
5. 추후 정상적으로 승인된 실제 글 작업의 충분한 동질 샘플이 누적되어야 F1/F2 전체 성능 비교가 가능하다. 샘플 수를 채우기 위해 신규 글이나 이미지를 인위적으로 생성하지 않는다.

원본 `main`의 기존 미커밋 문서와 다른 세션의 worktree를 그대로 보존했다. 이 후속 작업은 코드/릴리스 설치 외에는 기존 글·이미지/카탈로그/운영 cron 일정을 변경하지 않았다.

## 2026-10-11 19:02 KST 이후 읽기 전용 후속 확인

- 통합 HEAD `cbfa50b203b6ab575b81a903bde140df5632a238` clean, 운영 `editorial-release.json` revision `b6e0f51904a6e322bc82c4e496d2609b7ad974cf`, inventory digest `e2b6b13723b8fca851977c656eda41c1c3b906534d264cb2831619db60252213`, MU 기록 SHA `d10d4b3bff10378f965b7e9db8d6d912c3ee99fdeb833136e0774939639794fa` 및 매일 08:00 cron 등록 유지. 편집 잠금 디렉터리 없음. 이 확인은 설치 영수증 및 일부 운영 상태 read-only 검사이며 **93개 바이너리 SHA 재검증은 아님**.
- 기존 보고에서 원본 위치가 불명확했던 성공 80건/34코호트는 원본 `main`의 ignored 로컬 `agent-publisher/data/editorial_runs/workflow-metrics.jsonl`에서 재현됐다. 160행 중 성공 80행, SHA `92DC6BCC852D6830EE2475C9091E0DECA0AB0DAC38D3150643C70B29022730DC`. 그러나 34개 코호트 전부 검증된 릴리스·workload가 없어 비교 부적합. 운영 서버의 8행 별도 로그와 합산 금지. 세부 근거는 `docs/tasks/workflow-performance-live-20261011.md` 추가 조사 참조.
- 현재 설치 릴리스 observer는 운영 8행/성공 5행/신규 성공 1행/전 릴리스 성공 0행, 비교 가능한 코호트 0, `performance_claim=unmeasured`. 2026-10-12 08:00 KST 실행은 여전히 미래이므로 확인되지 않았다.
- 새 공개 발행·본문 수정·미디어 upload·cron 수동 실행·재배포 없음. 원본 `main`의 미커밋 자료와 Q1 ignored PNG 증거를 보존한다. Q1 native browser menu 200%, 인증 Preview, R2 실제 image_gen 호스트 증빙 및 Q3 미확정 미디어 ID/종료 증거는 새 증빙이 없어 이전 판정을 유지한다.
