# Bloguito 성장 시스템 개발 로드맵 — 2026-10-03

## 목적

현재 Bloguito의 편집 시스템은 공식 source, semantic review, 중복 검사, WordPress CAS, backup, readback 같은 저장 안전성은 충분히 갖추고 있다. 이번 성장 시스템은 이 기존 계약을 바꾸지 않고 그 앞단에 **수요·성과 기반 의사결정 계층**을 추가한다.

2026-10-03 08:00 KST 정규 자동 실행은 현행 8개 카테고리를 오류 없이 순회했지만 유효한 reviewed brief가 없어 후보 0건, 신규 draft 0건으로 종료했다. 따라서 우선 병목은 작성기보다 신규 주제 discovery와 우선순위 판단이다.

이 로드맵은 성장 시스템을 독립 P 작업 단위로 나눈 현재 구현 기록이다. P0~P5의 수요/작업선정 루프에 이어 P6부터는 사이트 내부 구조와 reader value를 확장한다.

## P0 — Inventory 경계 정리

### 문제

`scripts/sync_post_catalog.py`와 `agent-publisher/sync_wordpress_inventory.py`가 모두 `agent-publisher/data/wordpress_inventory.json`을 사용하지만 기대하는 JSON 스키마가 다르다.

- 카탈로그 동기화: WordPress 상세 메타 배열
- 편집/중복 검사: `{schema_version, checked_on, posts}` 형태의 canonical lightweight inventory

같은 파일을 두 역할이 공유하면 로컬 카탈로그 동기화 후 자동 편집 경로가 잘못된 스키마를 읽을 수 있다.

### 구현

- `wordpress_inventory.json`은 편집·중복 검사 전용 canonical inventory로 유지한다.
- `sync_post_catalog.py`의 상세 snapshot은 `catalog_inventory.json`으로 분리한다.
- 두 runtime inventory 파일은 모두 Git 비추적 상태로 둔다.
- 카탈로그 생성 결과와 기존 `POST_CATALOG.md` 형식은 바꾸지 않는다.

### 완료 조건

- `sync_post_catalog.py` 실행이 `wordpress_inventory.json`을 덮어쓰지 않는다.
- 카탈로그 상세 snapshot은 `catalog_inventory.json`에 저장된다.
- `test_post_catalog.py`와 inventory 관련 표적 테스트가 통과한다.
- WordPress 게시물, cron, 공개 상태는 변경하지 않는다.

## P1 — Growth Analyzer와 Opportunity Queue

### 목표

이미 존재하는 `analytics_collector.py`의 GSC/GA4 snapshot을 콘텐츠 inventory와 결합해 신규 글 작성보다 먼저 **기존 페이지의 성장 기회**를 찾는다.

### 구현 예정

- private runtime 경로 `agent-publisher/data/growth/` 추가
- `agents/growth_analysis.py` 추가
- `scripts/build_growth_queue.py` 추가
- `growth_policy.json` 추가
- 페이지를 `winner`, `quick_win`, `growth_candidate`, `low_signal`, `too_early`, `seasonal_decay` 등으로 분류
- 분류 결과에 근거 지표와 confidence를 함께 저장
- raw GSC query와 성과 수치는 Git에 commit하지 않음

### 완료 조건

- 최신 analytics snapshot이 있으면 private `latest-opportunities.json`을 생성한다.
- 데이터가 부족하면 성과를 추정하지 않고 `low` confidence 또는 미판정으로 남긴다.
- 신규 글 생성이나 기존 글 수정은 이 단계에서 자동 실행하지 않는다.

### 2026-10-03 구현 결과

P1을 로컬 정본에 구현하고 현재 운영 데이터로 read-only dry run까지 완료했다.

- `agent-publisher/growth_policy.json`을 추가해 freshness, confidence, winner, quick-win, growth-candidate, low-signal 기준을 editorial policy와 분리했다. 이 값은 검색 순위 예측이 아니라 작업 우선순위용 heuristic이다.
- `agent-publisher/agents/growth_analysis.py`를 추가해 GSC page 성과와 WordPress 현재 permalink/post ID를 보수적으로 결합한다. 매칭되지 않는 legacy, category, tag, 기타 URL은 현재 글에 추정 귀속하지 않고 별도 목록으로 남긴다.
- `scripts/build_growth_queue.py`를 재사용 도구로 추가하고 `scripts/maintained_scripts.json`에 등록했다. 기본 출력은 Git 비추적 `agent-publisher/data/growth/latest-opportunities.json`이다.
- `scripts/sync_post_catalog.py`의 private catalog snapshot에 WordPress가 실제 반환한 `permalink`를 추가했다. `POST_CATALOG.md` 표 형식이나 기존 editorial canonical inventory 계약은 변경하지 않았다.
- GA4 `pagePath` 수치는 채널 전체 값이라 organic 유입으로 오해하지 않도록 `ga4_all_channels` 참고값으로만 저장하고 성장 분류에는 사용하지 않는다.
- 새 글이라도 충분한 GSC click/impression/position 신호가 이미 기준을 넘으면 `winner`, `quick_win`, `growth_candidate`로 분류할 수 있다. 반대로 보고 기간 뒤 발행한 글이나 아직 신호가 부족한 최근 글은 `too_early`로 남긴다.
- 표본이 작은 노출은 `low` confidence로 유지하고, 매칭 실패 URL이나 작은 표본을 근거로 제목·본문 자동 수정 또는 신규 글 생성을 실행하지 않는다.
- 운영 서버의 최신 private analytics JSON과 현재 WordPress 69개 inventory를 읽기 전용으로 가져와 queue를 실제 생성했다. 현재 snapshot의 종료일은 2026-09-29라 이후 발행 글 다수는 정상적으로 `too_early` 상태이며, 상세 검색어·페이지 성과 수치는 private runtime JSON에만 유지한다.
- 표적 P1/P0/analytics/script-hygiene 테스트 30개가 통과했고, 공유 `agents/` 코드 변경에 따른 전체 repository regression은 **850 tests OK, skipped=0**으로 통과했다.

P1에서는 WordPress 게시물, 공개 상태, 운영 cron, 광고 설정을 변경하지 않았다. P2는 이 private Opportunity Queue를 신규 주제 후보의 demand evidence 중 하나로 사용하되, 자동 scheduler의 실제 gate 변경은 P2 구현·검증 뒤 별도 운영 적용 단계에서 수행한다.

## P2 — Topic Demand Gate

### 목표

`search_briefs.json`에 들어가기 전 후보 단계에서 실제 수요 근거와 추가 가치를 평가해, 자동 스케줄러가 검증되지 않은 아이디어를 바로 원고화하지 않게 한다.

### 구현 예정

- private `topic_candidates.json` 후보 저장
- `agents/topic_scoring.py` 추가
- 수요 근거, GSC 연관성, 클릭 필요성, AI answerability, added value, cluster 적합성, 유효기간, 경쟁 차별화를 점수화
- 자동 스케줄러에는 demand gate를 적용하고, 사용자가 직접 지시한 수동 작성에는 강제 차단하지 않음
- 점수는 검색 순위 예측값이 아니라 제작 우선순위로만 사용

### 완료 조건

- 자동 작성 후보는 측정된 demand evidence와 최소 점수/신뢰도 기준을 충족해야 `search_briefs.json` 승격 대상이 된다.
- 검색량을 측정하지 않았는데 측정한 것처럼 기록하지 않는다.
- 기존 `topic_reasons()`, source/review, draft-only 저장 안전 계약은 그대로 유지한다.

### 2026-10-03 구현 결과

P2를 로컬 정본에 구현하고 private runtime gate까지 초기화했다.

- `agent-publisher/agents/topic_scoring.py`를 추가했다. 후보별 총점은 100점이며 demand evidence 25, GSC relevance 15, click need 15, AI 대체 저항성 10, added value 15, cluster fit 10, useful lifetime 5, 경쟁 차별화 5로 구성한다. 이 점수는 제작 우선순위 heuristic이며 검색 순위·유입·수익을 예측하지 않는다.
- `growth_policy.json`에 `topic_gate`를 추가했다. 기본 자동화 기준은 70점 이상, `medium` 이상 confidence, 최근의 측정 demand 존재, useful lifetime 30일 이상, added value 존재다. 외부 demand evidence는 Keyword Planner, Google Trends, Naver DataLab의 실제 측정값만 허용한다.
- `gsc_terms`는 P1의 `top_queries_global`에 문자 단위로 실제 포함된 query만 연관 신호로 계산한다. 임의의 의미 유사도·검색량 추정은 하지 않고, GSC report와 외부 evidence가 정책상 오래되면 점수에서 제외한다.
- `scripts/score_topic_candidates.py`를 재사용 CLI로 추가했다. private `data/growth/topic_candidates.json`을 읽어 `topic-candidate-scores.json`을 atomic write하며, 처음에는 `--init-empty`로 빈 private candidate document를 명시적으로 만들 수 있다. 실제 후보 형식 참고용으로만 `agent-publisher/data/topic_candidates.example.json`을 추적한다.
- `RadarAgent`의 scheduled discovery는 이제 `load_briefs(..., require_growth_gate=True)`를 사용한다. 현재 score report가 없거나 stale하거나, brief ID/category/primary keyword와 score가 맞지 않거나, measured demand/점수/confidence 조건을 통과하지 못하면 자동 작성 후보로 반환하지 않는다.
- score report는 `growth_policy.json`의 단순 version 숫자뿐 아니라 `topic_gate` 전체 설정 digest에도 결합한다. 점수 가중치·최소점수·freshness 조건 등이 바뀌면 이전 score report는 즉시 자동화 승인 근거로 사용할 수 없다.
- 수동 `load_briefs()` 기본값과 editorial CLI는 growth gate를 강제하지 않는다. 따라서 사용자가 직접 지시한 글은 검색 성장 점수만으로 차단되지 않는다. 자동화 gate를 통과한 경우에도 기존 `topic_reasons()`, duplicate 검사, source freshness, semantic review, draft-only 저장 계약은 그대로 유지한다.
- private runtime에 빈 `topic_candidates.json`을 초기화하고 2026-09-29 종료 P1 opportunity report를 기준으로 score report를 실제 생성했다. 아직 새 주제에 대한 별도 수요 측정 작업을 수행하지 않았으므로 후보 0건, eligible 0건이 정확한 초기 상태다. 과거 `search_briefs.json` 항목에 측정값을 소급 추정해 승인하지 않았다.
- 측정값이 0인 예시 candidate를 별도 scratch dry run한 결과 46점, `low` confidence, `no_fresh_measured_demand_evidence`로 자동화 보류되어 fail-closed 동작을 확인했다.
- 현재 private candidate state가 빈 상태인 실제 로컬 Radar probe에서도 `복지/지원금` 자동 후보 0건으로 정상 보류됐다. 2026-10-03 재점검에서도 Keyword Planner/Google Trends/Naver DataLab의 실제 측정 자료나 collector가 아직 없어 후보 0건을 유지했다. P2 관련 표적 테스트는 통과했고, 공유 agents 코드 변경에 따른 전체 repository regression은 **860 tests OK, failures=0, errors=0, skipped=0**으로 통과했다.

P2 구현 자체는 WordPress 게시물, 공개 상태, 운영 cron, 광고 설정을 변경하지 않는다. 서버의 정규 cron에 이 gate를 실제 적용하려면 배포 시 execution host에도 최신 analytics/P1 queue와 private candidate/score state를 준비해야 한다.

## P3 — Daily Growth Planner

### 목표

P1의 기존 글 Opportunity Queue와 P2의 신규 주제 score를 결합해 정규 자동 실행이 매일 **기존 글 개선 / 신규 draft / 아무것도 하지 않음** 중 하나만 선택하게 한다. 새 글 생산 자체를 성공 기준으로 두지 않는다.

### 2026-10-03 구현 결과

- `agent-publisher/agents/growth_planner.py`와 `scripts/build_daily_growth_plan.py`를 추가했다. 결과는 Git 비추적 `data/growth/daily-growth-plan.json`에 atomic write한다.
- `growth_policy.json`에 `daily_planner` 계약을 추가했다. P1/P2 입력은 각각 최대 14일 freshness를 요구하고, 기존 글은 `medium` 이상 confidence의 `quick_win`, `growth_candidate`만 작업 후보로 삼는다. 기본 정책은 existing improvement를 eligible 신규 주제보다 우선한다.
- 결정은 `existing_improvement`, `new_draft`, `no_action` 중 정확히 하나다. invalid/stale 입력은 `no_action`으로 fail closed한다.
- `main.py` 정규 scheduler가 planner를 작성 단계보다 먼저 실행한다. `existing_improvement`와 `no_action`일 때는 WordPress inventory sync, Radar, Curator, Writer, Designer, Publisher를 시작하지 않는다. 기존 공개 글을 자동으로 수정하지도 않는다.
- `new_draft`일 때만 WordPress inventory를 갱신하며 planner가 선택한 `category_key`와 `brief_id` 하나만 Radar에 전달한다. 따라서 같은 날 다른 eligible brief가 있더라도 임의로 추가 생산하지 않는다.
- 운영 요약 알림에 Growth Planner action과 기존 글 post ID 또는 신규 brief ID를 포함하도록 했다. 0건 작성은 정상 성공 결과다.
- 현재 2026-09-29 종료 실데이터로 dry run한 결과 `Post #345` 고속버스 취소표 글이 `quick_win`, `high` confidence로 선택되어 `existing_improvement`가 결정됐다. 현재 P2 신규 eligible 후보는 0건이다.
- P3/P2 pipeline 표적 회귀 29개가 통과했고, 저장소 정식 validation runner의 전체 repository regression은 **869 tests OK, failures=0, errors=0, skipped=0**으로 통과했다. UTF-8 검사와 `git diff --check`도 통과했다.

P3는 공개 글을 자동 수정하지 않는다. 동일 existing opportunity가 계속 유효하면 이후 정규 실행에서도 신규 draft를 계속 보류할 수 있으며, 이는 생산량보다 관측된 개선 기회를 우선하도록 한 의도적 fail-closed 동작이다. 실제 개선 완료를 자동 인식하거나 작업 비율을 조절하는 completion/work-log 계층은 후속 단계에서 다룬다.

## P4 — Growth Work Log / Completion Layer

### 목표

P3가 선택한 기존 글 개선을 실제로 완료한 뒤에도 같은 **수정 전 GSC 표본** 때문에 동일 post가 매일 다시 선택되는 문제를 막는다. 단순 선정은 완료가 아니며, 실제 편집과 readback이 끝난 작업만 private completion state에 기록한다.

### 2026-10-03 구현 결과

- `agent-publisher/agents/growth_work_log.py`와 `scripts/record_growth_work.py`를 추가했다. 완료 이력은 Git 비추적 `data/growth/growth-work-log.json`에 atomic write한다.
- 완료 기록은 `existing_improvement`인 **완료 당일의** `daily-growth-plan.json`에만 결합할 수 있고, 선택된 `post_id`가 다르거나 기준일이 다르거나 현재 `daily_planner` policy digest와 plan digest가 다르면 기록을 거부한다. plan을 선택했다는 이유만으로 자동 완료되지는 않는다.
- 각 기록은 `completed_on`, 당시 `opportunity_period_end`, `recheck_after`, classification, recommended action을 보존한다. 기본 재관측 기간은 `existing_recheck_days=14`다.
- Daily Growth Planner는 completion log를 읽고 Opportunity report의 **기간 종료일**이 `recheck_after`에 도달하기 전에는 완료된 post를 기존 글 후보에서 제외한다. 단순히 달력상 14일이 지났다는 이유로 옛 GSC 표본을 다시 평가하지 않는다.
- 재관측 기간이 지난 새 GSC report에서도 해당 글이 `quick_win`/`growth_candidate` 조건을 다시 만족하면 정상적으로 재진입할 수 있다. 완료된 1순위가 억제된 동안 다른 기존 개선 후보나 P2 eligible 신규 주제가 있으면 다음 후보로 진행한다.
- work log가 아직 없는 환경은 빈 이력으로 취급해 기존 P3 동작을 유지한다. 반대로 파일이 존재하지만 형식이 잘못됐거나 미래 완료 기록 등 무결성 오류가 있으면 신규 작성을 허용하지 않고 `no_action`으로 fail closed한다.
- 2026-10-03 후속 운영 적용에서 #345의 실제 `edit-post`/readback 완료를 확인한 뒤 production/local work log에 완료를 기록했다. `recheck_after=2026-10-17`이며 동일 2026-09-29 GSC 표본을 사용하는 다음 plan은 `no_action`으로 바뀌었다. 따라서 selection 자체가 아니라 실제 편집 완료 뒤에만 suppression이 시작되는 P4 계약이 운영에서도 확인됐다.
- P4/P3 표적 회귀 26개가 통과했고, 저장소 정식 validation runner의 전체 repository regression은 **879 tests OK, failures=0, errors=0, skipped=0**으로 통과했다. UTF-8 검사와 `git diff --check`도 통과했다.

## P5 — Work Mix / Rotation Policy

### 목표

P4로 동일 기존 글의 반복 선택은 막았지만 actionable existing 후보가 여러 개이면 신규 글이 계속 뒤로 밀릴 수 있다. P5는 **실제로 완료된 작업**을 기준으로 기존 글 개선과 신규 draft의 비율을 관리하되, 수요 gate를 통과하지 않은 신규 글을 비율 맞추기 용도로 만들지 않는다.

### 2026-10-03 구현 결과

- `growth-work-log.json` schema v1을 호환 확장해 `existing_improvement`뿐 아니라 scheduler가 실제 생성한 `new_draft` 완료도 기록한다. 기존 P4 로그는 그대로 유효하다.
- 신규 draft 완료 기록은 현재 `daily-growth-plan.json`의 `new_draft` action, policy digest, 당일 plan, 선택된 `brief_id`에 결합된다. WordPress draft 저장이 성공한 뒤에만 `main.py`가 자동 기록한다.
- 한 번 draft를 만든 `brief_id`는 같은 P2 score report에 계속 남아 있어도 다시 신규 후보로 선택하지 않는다. 이는 rotation과 별개인 중복 생성 방지 계약이다.
- `daily_planner`에 `work_mix_lookback_actions=8`, `target_existing_ratio=0.5`를 추가했다. existing/new가 둘 다 eligible이면 최근 완료 작업에 다음 action 하나를 가정했을 때 목표 50:50에 더 가까워지는 쪽을 선택한다. 수학적 동률은 직전 완료 action 반대쪽으로 회전하고, 이력이 전혀 없을 때만 `prefer_existing_improvement=true`가 tie-breaker로 작동한다.
- 한쪽 작업만 eligible이면 rotation 비율을 맞추기 위해 다른 작업을 합성하지 않는다. 따라서 신규 수요 후보가 없으면 기존 개선만 진행할 수 있고, existing opportunity가 없으면 검증된 신규 draft만 선택할 수 있다.
- 신규 WordPress draft 저장은 성공했지만 private work log 기록만 실패한 경우 `growth_log_errors`로 별도 보고한다. 이미 만들어진 draft를 실패로 간주해 다시 만드는 동작은 하지 않는다.
- 표적 테스트에서 `existing → new → existing` 회전, 완료된 new brief 재선정 차단, P4 기존 글 recheck, post-save work-log 실패의 비치명 처리를 검증했다. 이후 #345 실제 개선 완료가 production work log에 기록되어, 신규 eligible 후보가 없는 현재 planner는 `no_action`을 반환한다.
- P5 관련 표적 회귀 32개가 통과했고, 저장소 정식 validation runner의 전체 repository regression은 **885 tests OK, failures=0, errors=0, skipped=0**으로 통과했다. UTF-8 검사와 `git diff --check`도 통과했다. production work log의 첫 완료 기록은 #345이며 recheck 기준일은 2026-10-17이다.

## P6 — Content Cluster / Internal Links

### 목표

개별 글을 독립 페이지로만 운영하지 않고 사람이 검토한 주제 cluster를 통해 관련 글 후보를 안정적으로 연결한다. 내부 링크를 늘리기 위해 임의 글을 생성하거나 공개글을 자동 수정하지 않으며, hub page도 추천 대상으로만 남긴다.

### 2026-10-03 구현

- `agent-publisher/data/content_clusters.json`에 schema v1 cluster registry를 추가했다. 초기 cluster는 `civil-documents`와 `pension`이며 post ID는 한 cluster에만 속하도록 검증한다.
- `agents/content_clusters.py`는 `brief.cluster_id`를 현재 WordPress inventory에 결합해 실제 `publish` 상태인 같은 cluster 글을 최대 2개 반환한다. URL은 기존 검증 계약인 `https://lifeinfo24.org/?p=ID`만 사용하고 현재 수정 대상 post는 제외한다.
- scheduler writer는 모델이 원고 plan을 반환한 뒤, semantic review 전에 cluster 후보를 `plan.related_posts`에 deterministic하게 결합한다. `cluster_id`가 있을 때 모델이 임의로 만든 related link는 cluster 후보로 대체한다. cluster가 없는 기존 brief는 기존 동작을 유지한다.
- `search_briefs.json`의 서류 발급/연금 관련 일부 brief에 `cluster_id`를 명시했다. 신규 brief는 해당 cluster가 실제로 맞는 경우에만 이 필드를 추가한다.
- `scripts/build_content_cluster_report.py`를 추가했다. canonical WordPress inventory의 `content_urls`에서 명시적 `?p=ID` 링크만 세어 incoming 0 / 같은 cluster outgoing 0인 공개 글을 `orphan_candidate`로 추천한다. `content_urls`가 없는 snapshot에서는 orphan 판정을 하지 않는다.
- orphan report와 cluster registry는 **추천/검토 계층**이다. 기존 공개글 자동 edit, hub page 자동 생성, permalink 의미 추정은 하지 않는다.

## P7 — Value-first / AI-answerability

### 목표

정답 한두 문장으로 쉽게 대체되는 주제는 단순 설명글 생산으로 자동 승격하지 않고, 독자가 클릭해서 수행할 가치가 있는 계산/판정/비교/공식 행동/문제 해결/조회 등을 brief 단계에서 명시한다. 이 gate는 자동 scheduler에만 적용하며 사용자가 직접 지시한 글을 막지 않는다.

### 2026-10-03 구현

- scheduled brief metadata로 `intent_type`, `ai_answerability`, `added_value`를 추가했다. intent는 `guide`, `lookup`, `application`, `calculator`, `comparison`, `decision`, `troubleshooting`으로 제한하고 AI answerability는 `low/medium/high`만 허용한다.
- `added_value`는 P2의 기존 recognized value 목록을 그대로 재사용해 서로 다른 두 정책 목록이 drift하지 않도록 했다.
- `agents.topic_scoring.brief_value_gate_reasons()`가 scheduler용 metadata를 fail-closed로 검증한다. `ai_answerability=high`인데 added value가 하나도 없으면 `high_ai_answerability_without_added_value`로 보류한다.
- `load_briefs(..., require_growth_gate=True)`만 P2 demand gate 뒤에 P7 value gate를 적용한다. `require_growth_gate=False`인 수동 경로는 이 gate를 적용하지 않는다.
- 현재 tracked `search_briefs.json` 13개에 metadata를 명시했다. 단순 guide 여부가 아니라 실제 독자 행동에 맞춰 application/lookup/calculator/comparison/decision/troubleshooting을 구분했다.
- P7에서는 `Review.Checks`나 semantic review response schema를 변경하지 않았다. value 설계는 semantic fact-review와 분리된 brief-selection contract로 유지한다.

## P8 — Interactive Tool Pilot

### 목표

AI 답변에서 설명만 읽고 끝나는 대신 독자가 자신의 조건을 직접 넣어 결과를 얻는 결정론적 도구를 제공한다. 첫 pilot은 정책 자격판정보다 입력과 계산 경계가 단순한 **최저임금 월급 계산**이다. 기능 구현과 실제 신규 글 생성은 분리하며, 실제 글은 여전히 P2의 측정 수요 gate를 통과해야 한다.

### 2026-10-03 구현

- `editorial_schema.GeneralPlan`에 optional `reader_tools`를 추가했다. 현재 허용 type은 `minimum_wage_monthly`, formula는 `moel_weekly_holiday_v1` 하나뿐이다.
- `agents/reader_tools.py`에 Python reference calculation과 deterministic renderer를 구현했다. 입력은 시급, 주 소정근로시간, 주휴 적용 여부이고 월 환산시간과 세전 예상 월급을 계산한다.
- 공식 고용노동부 예시의 단시간 주휴 계산 `(주 소정근로시간 / 40) × 8시간`과 주40시간+유급주휴 8시간의 월 환산 209시간 경계를 pilot formula로 고정했다. 주 15시간 미만에서는 주휴 toggle이 켜져도 주휴시간을 0으로 처리한다.
- `validate_reader_tools()`는 calculator intent/value, 최저임금 topic scope, official-source evidence exact binding, 허용 formula와 숫자 경계를 검증한다. 모델이 임의 `script`나 다른 formula를 plan에 넣으면 거부한다.
- renderer는 고정 JavaScript만 출력하고 모델 문자열은 title/default numeric/evidence 구조 데이터로만 받는다. native input, `aria-live`, responsive grid, JavaScript-disabled 안내를 포함한다.
- tool evidence source ID도 기존 공식 출처 footer에 포함한다. 연장/야간/휴일 가산수당과 세금/공제는 범위 밖임을 reader-facing 안내에 명시한다.
- P8은 기존 공개글을 자동 수정하지 않고 실제 2027 최저임금 글도 만들지 않았다. 외부 수요 측정이 없는 현재 P2 eligible 신규 후보 0건 상태를 우회하지 않는다.

## P9 — Measured Demand Collector

### 목표

P2가 형식만 준비한 외부 demand evidence를 실제 공식 측정 경로와 연결하되, 외부 키워드 도구가 새 주제를 무제한 발명하지 않도록 GSC query seed를 먼저 사용한다. 측정 인프라가 없거나 provider 응답이 비어 있으면 후보 0건/미측정 상태를 정상 결과로 유지한다.

### 2026-10-03 구현

- `agents/topic_demand.py`와 `scripts/collect_topic_demand.py`를 추가해 사람이 검토한 private `topic_candidates.json`만 enrich하도록 했다. collector 자체는 topic/category/click need/AI answerability/added value를 생성하지 않는다.
- 첫 provider는 NAVER API HUB의 공식 Naver DataLab 통합 검색어 트렌드 API다. 현재 공식 계약인 `POST https://naverapihub.apigw.ntruss.com/search-trend/v1/search`와 `X-NCP-APIGW-API-KEY-ID`/`X-NCP-APIGW-API-KEY` 헤더를 사용한다. 최대 5개 keyword group, group당 최대 20개 검색어라는 provider 경계를 지키며 고정 HTTPS endpoint만 호출한다. credential이나 오류 response body는 로그에 남기지 않는다.
- 기본 수집은 신선한 P1 GSC query와 후보 `gsc_terms`가 문자 정규화 기준으로 실제 매칭된 candidate만 대상으로 한다. stale GSC report나 매칭이 없는 후보는 외부 호출 전에 보류한다. 운영자가 이미 별도로 검토한 후보는 명시적 `--include-unseeded`로만 예외 측정할 수 있다.
- DataLab의 상대 ratio는 절대 검색량으로 승격하지 않는다. 최근 90일 완료 날짜의 주간 ratio 평균을 `metric=relative_interest`로 기록하고 period/time unit/query group/aggregation을 evidence에 함께 보존한다. provider가 data point를 반환하지 않으면 0을 만들어내지 않는다.
- P2 validation도 source-specific metric allowlist를 추가해 Keyword Planner의 `avg_monthly_searches`와 Trends/DataLab의 `relative_interest`를 교차 오표기하지 못하게 했다.
- 2026-10-03 NAVER API HUB 결제수단/서비스/Application 설정과 Client ID/Secret 준비를 완료하고 첫 live measurement를 수행했다. GSC에 실제 노출된 `시외버스 취소표` 계열 reviewed private candidate 1건은 Naver DataLab 주간 상대 관심도 평균 `33.0623`을 반환했고, P2 재점수 결과 74점/`medium` confidence로 `eligible_for_automation=true`가 됐다. 이 값은 절대 검색량이 아니라 해당 조회 묶음/기간 안의 상대값이다.
- live 호출에서 API HUB가 주간 구간 경계에 맞춰 요청 기간 `2026-07-05~2026-10-02`를 응답 기간 `2026-06-29~2026-10-03`으로 정규화하는 실제 동작을 확인했다. collector는 이제 time unit별 제한된 boundary expansion만 허용하고 요청 기간과 provider 반환 기간을 둘 다 evidence에 기록한다.
- P3 planner dry run은 이 후보를 `new_draft` 대상으로 선택했지만 tracked `search_briefs.json`에는 같은 `brief_id`의 사람이 검토한 brief가 아직 없다. scheduled Radar probe도 대상 brief 0건으로 fail closed했다. 따라서 측정 통과만으로 WordPress draft가 생성되지는 않으며, 별도 source/duplicate/lifecycle 검토 후 reviewed brief 승격이 다음 단계다.
- 후속 duplicate review에서 WordPress #345 본문을 직접 확인한 결과, 기존 글이 이미 티머니GO의 고속/시외 선택, 시외버스 통합예매 CTA, 시외버스 잔여좌석 재조회, 취소표 알림 확인, 시간대/터미널 대안을 포함하고 있어 `시외버스 취소표` 후보와 실질 검색 의도가 겹쳤다. 따라서 이 후보는 새 `search_briefs.json` 항목으로 승격하지 않는다.
- private candidate에는 optional `review_disposition`을 두고 `duplicate_existing`이면 `duplicate_post_id`와 `reviewed_at`을 필수로 기록한다. 이 상태의 후보는 기존 measured evidence를 보존하되 외부 provider 재측정에서 제외되고 P2 score report에도 `duplicate_existing_post` reason으로 남아 `eligible_for_automation=false`가 된다. 이는 수요 신호가 있다는 이유만으로 이미 해결한 검색 의도를 새 글로 중복 생산하지 않기 위한 fail-closed 경계다.

## 작업 순서와 경계

1. **P0**: inventory 파일 역할 충돌을 먼저 제거한다.
2. **P1**: P0의 안정된 inventory와 기존 analytics snapshot을 읽어 Opportunity Queue를 만든다.
3. **P2**: P1의 성과 신호를 신규 주제 후보 평가에 연결한다.
4. **P3**: P1/P2를 합쳐 당일 자동 실행의 작업 유형과 단일 대상을 결정한다.
5. **P4**: 실제 완료된 기존 글 개선을 기록하고 충분한 새 GSC 관측기간 전까지 같은 과거 신호를 재선정하지 않는다.
6. **P5**: 실제 완료 이력으로 existing/new 작업 mix를 관리하고 성공한 신규 brief의 재선정을 막는다.
7. **P6**: curated cluster로 신규 원고의 related-post 후보를 결합하고, explicit-link orphan 후보를 read-only로 찾는다.
8. **P7**: scheduler brief에 intent/AI-answerability/added-value를 명시하고 AI로 쉽게 대체되는 무가치 설명글을 자동 작성에서 보류한다.
9. **P8**: allowlisted structured reader tool을 deterministic하게 렌더해 계산/판정형 클릭 가치를 제공한다.
10. **P9**: reviewed candidate를 GSC-seeded official provider 측정으로 enrich하고 상대값/절대값 경계를 source-specific metric으로 강제한다.

P0~P5는 운영 배포와 #345 실제 completion loop까지 확인했다. P6도 기존 공개글을 자동 수정하지 않으며, writer 경로에 배포할 때는 release revision과 08:00 cron smoke를 별도로 확인한다.

## 2026-10-03 P0 실행 기록

P0를 로컬 정본에 구현했다.

- `scripts/sync_post_catalog.py`의 상세 snapshot 경로를 `agent-publisher/data/catalog_inventory.json`으로 분리했다.
- `agent-publisher/data/wordpress_inventory.json`은 `sync_wordpress_inventory.py`와 `search_intent.py`가 사용하는 canonical lightweight inventory로 남겼다.
- 새 `catalog_inventory.json`은 runtime state이므로 `.gitignore`에 추가했다.
- `test_post_catalog.py`에 카탈로그 동기화가 별도 snapshot을 쓰면서 기존 canonical inventory 바이트를 변경하지 않는 회귀 테스트를 추가했다.
- P0 경계 표적 테스트 `tests.test_inventory_cache_lifecycle`, `tests.test_lightweight_inventory`, `tests.test_post_catalog`는 19개 모두 통과했다.
- 카탈로그/analytics 호환 확인 `tests.test_post_catalog`, `tests.test_analytics_collector`는 22개 모두 통과했다.
- `git diff --check`는 통과했다. `docs/INDEX.md`의 기존 CRLF 작업트리 경고만 출력됐고 공백 오류는 없었다.

이번 P0에서는 WordPress 게시물, 공개 상태, 운영 cron, 서버 코드를 변경하지 않았다. P1은 이 분리된 inventory 경계를 전제로 private Growth Analyzer와 Opportunity Queue를 구현한다.
