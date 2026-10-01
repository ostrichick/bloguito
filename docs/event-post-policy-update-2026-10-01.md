# 2026-10-01 행사 포스트 정책 보강

## 범위

부산 10월 행사 Draft #648과 대구 10월 행사 Draft #657을 실제로 보강하면서 확인된 반복 문제를 `EVENT_POST_STANDARD.md`와 `OPERATIONS.md`의 현행 행사 규칙으로 승격했다. 이번 작업은 정책 문서만 수정했으며 WordPress 글, renderer, validator, `editorial_policy.json`의 기계 설정은 변경하지 않았다.

## 반영한 운영 교훈

1. **이미지 탐색에는 종료 조건이 필요하다.** 행사별로 상업 재사용 근거와 화질이 충분한 실제 사진 1개를 확보하면 추가 후보 탐색을 중단한다. 지자체·공공기관의 공공저작물 자료실과 공공누리를 가장 먼저 확인한다.
2. **공공기관 게시 사진도 개별 이용조건을 확인한다.** 공공누리 제1유형은 우선 사용 후보로 두고, 제2·4유형은 수익화 블로그에서 제외한다. 제3유형은 원본 변경 없이 사용할 수 있을 때만 검토한다. 공공누리 표시가 없으면 기관 사이트에 게시됐다는 이유만으로 자유이용을 추정하지 않는다.
3. **현재 WordPress 본문이 행사 목록의 최종 기준이다.** 대구 #657에서는 과거 작업 기록의 7번째 행사가 `달성 대구현대미술제`였지만 최신 본문은 `2026 대구예술제`로 바뀌어 있었다. 이미지 mutation 직전에 live 행사명과 section 순서를 다시 읽고 후보를 `event_name`에 재결합하도록 규칙화했다.
4. **언론·블로그·SNS 사진은 원권리자 추적 단서로 제한한다.** `기관 제공` 표시만으로 재사용 허락을 추정하지 않고, `재판매 및 DB 금지` 등 제한이 있으면 기사 사진은 즉시 제외한다.
5. **이미지 도구 실패를 반복하지 않는다.** 정상 이미지가 특정 디코더에서만 실패하면 동일 호출을 반복하지 않고 축소본·다른 디코더·다른 원본 URL로 전환한다.
6. **독자용 출처 목록과 내부 evidence를 분리한다.** 대구 #657의 하단 출처가 16개까지 늘어난 사례를 기준으로, 독자 화면에는 행사별 핵심 공식 출처 1개 정도와 필요한 공통 출처만 남긴다. 대표곡·프로필·미러·보조 기사 등은 핵심 판단에 필요하지 않으면 내부 evidence에만 보존한다.
7. **이미지 권리 근거는 이미지 가까이에 둔다.** 공공누리·권리 근거는 caption/provenance에 기록하고, 주요 사실 출처와 중복되지 않는 한 하단 출처 목록에 다시 늘어놓지 않는다.

## 수정 파일

- `docs/EVENT_POST_STANDARD.md`: 이미지 탐색 순서·종료 조건, 공공누리 유형별 판정, live 행사 재결합, 비율 보존, 실패 예산, 독자용 출처 압축 규칙과 금지 관행을 추가했다.
- `docs/OPERATIONS.md`: 행사 section 이미지 한정 수정의 Simple Task 분류와 행사 작업의 이미지·출처 실행 원칙을 보강했다.

`docs/EDITORIAL_SYSTEM.md`와 `agent-publisher/editorial_policy.json`은 이 작업 이전부터 다른 미커밋 변경이 존재했고, 이번 보강은 새 수치 임계값이나 schema 변경이 아니라 행사 전용 서술 규칙이므로 수정하지 않았다. `EDITORIAL_SYSTEM.md`는 이미 `EVENT_POST_STANDARD.md`를 행사 일정형 글의 전용 확장 규약으로 연결한다.

## 검증

- 문서 diff와 링크 구조를 수동 검토했다.
- 문서 전용 변경이므로 전체 Python regression은 실행하지 않았다.
- `git diff --check`로 공백·patch 형식 오류가 없는지 확인한다.
- 운영 WordPress나 서버 배포는 이번 정책 문서 변경의 범위가 아니다.

## P0~P2 운영 경량화 구현

후속 분석에서 부산·대구 행사 글의 실제 병목이 source 수집보다 **본문 이미지 import의 반복 WordPress 왕복, 단일 행사 수정에도 발생하는 전체 semantic review, 변경 범위와 무관한 inventory·browser QA**에 있다는 점을 확인해 정책뿐 아니라 실행 코드를 함께 경량화했다.

### P0

- 행사 section의 **위치 카드는 유지하되 본문 이미지는 선택 요소**로 변경했다. 권리·화질이 충분한 사진을 정해진 탐색 범위에서 찾지 못했으면 이미지 없이 section을 완료할 수 있다.
- `import-section-images` batch 경로를 추가해 여러 이미지를 `게시글 baseline 1회 → N개 attachment import·개별 검증 → 최종 게시글 readback 1회`로 처리한다. 기존 단일 `import-section-image`는 호환 유지한다.
- 행사 v1의 소수 `event_name` section과 해당 overview 행·일정/source만 바뀐 경우 `event-delta` profile로 해당 행사만 의미 검토한다. 행사 추가·삭제, 제목·lead·SEO·공통 구조 변경은 계속 full `standard-event`다.
- `validation_plan.qa_targets`에 변경 행사명을 기록하고 `complete-task-qa --qa-event-name`으로 실제 변경 section을 확인하지 않으면 작업을 완료 상태로 닫을 수 없게 했다.
- 제목·`required_title_terms`·공식 URL·관련 글·카테고리 등 사이트 중복 판단 필드가 그대로인 localized 수정은 전체 WordPress inventory를 생략하고 대상 post CAS와 기존 reviewed site context를 재사용한다.

### P1

- 행사 SEO exact-match는 SEO title·description에는 유지하되 독자 본문은 **lead 또는 관련 H2/H3 한 곳**이면 충분하도록 완화했다.
- source에 선택적 `volatility=static|live`를 도입했다. 정적 행사 일정·장소·프로그램 source는 같은 작업에서 기본 120분 receipt를 재사용할 수 있고, 예매·신청·매진·재고 같은 live-state 문구는 표시와 관계없이 항상 재조회한다.
- `event-delta`는 영향받은 source ID를 계산해 그 source만 강제 refresh하고, 나머지 안정된 source는 receipt를 재사용한다.
- 행사 semantic reviewer에서는 CTA scope·image field·rights URL 같은 결정론적 구조 검사를 반복하지 않고 원문 지지, 조건 보존, 과장·연도 혼동, 독자 판단 가능성에 집중하도록 했다.
- 내부 evidence 전체는 그대로 보존하면서 `public_citation`과 `citation_group`으로 독자용 하단 출처를 대표 자료 중심으로 압축할 수 있게 했다.
- `image.rights_label`과 `rights_url`을 caption 옆에 렌더해 공공누리 등 이미지 권리 근거를 하단 출처와 중복시키지 않아도 된다.

### P2

- 공식 행사 사진은 더 이상 16:9를 강제하지 않는다. 최소 화질 검사는 유지하고 renderer는 원본 비율을 보존해 표시한다.
- 행사 전용 상세 규칙은 `EVENT_POST_STANDARD.md`를 정본으로 두고 `EDITORIAL_SYSTEM.md`의 중복 설명을 줄였다.
- 행사 bundle의 policy fingerprint에만 `EVENT_POST_STANDARD.md`와 event validator contract digest를 포함한다. 일반 글은 행사 정책 변경 때문에 review cache가 불필요하게 무효화되지 않는다.
- 새 행사 정책 때문에 기존 full review anchor가 오래된 첫 수정은 `event-delta`를 억지로 통과시키지 않고 자동으로 full semantic review에 안전 전환하며, 이후 같은 정책 아래의 localized 수정부터 scoped review를 사용할 수 있다.

### P3~P4

- validation plan에 `candidate_profile`, `minimum_safe_profile`, `selected_profile`, promotion 이유를 기록한다. 사용자가 Fast/image-only를 요청했더라도 실제 diff가 사실·source·CTA·layout·행사 전역 검증을 요구하면 자동으로 상위 Standard profile로 승격한다.
- 실행 전 `Planned validation` 한 줄로 profile, route, 선택 test file 수, source/review 방식, 변경 행사와 QA 범위를 표시한다.
- workflow metrics는 기존 세부 timing을 유지하면서 `validation/source/review/wp/browser/image/other` category 합계를 함께 기록한다. 기존 metrics 행도 stage 이름으로 category를 복원해 비교할 수 있다.

### P5~P6

- task-state를 v5로 확장해 동일 failure signature를 최대 2회까지만 같은 경로에서 허용한다. 2회째 실패 후에는 source 대체/수동 검토, 기존 media 재사용·무이미지, transport reconcile, full review/fallback model 등 다음 안전 경로를 기록하고 같은 재시도를 차단한다.
- Rank Math·thumbnail·ALT post meta는 고정 batch protocol로 여러 `post meta get/set` 왕복을 한 번의 read 또는 write+readback으로 통합했다. reviewed public/draft뿐 아니라 legacy draft도 canonical guarded mutation/meta helper를 사용한다.

### P7~P8

- `section-image-review/v1`과 local review cache를 추가해 동일 source URL+content SHA의 권리·화질 provenance를 재사용한다. 안전 후보 하나를 확보하면 이미지 탐색을 끝내고, 검토된 기존 WordPress attachment는 URL/title/ALT/MIME을 다시 확인한 뒤 재import 없이 사용한다.
- 이미지가 필요하지 않은 section은 명시적인 `no_image` 결정으로 정상 완료한다.
- 별도 retry/cache/transport 구현을 새로 만들지 않고 canonical task-state, source/review/image purpose-specific cache, `wordpress_mutation` helper를 재사용한다. 과거 `update_existing_via_ssh.py`는 별도 transport가 아니라 unified adapter로 전달하는 compatibility shim으로만 유지한다.

### 안전장치 유지

- `event_name ↔ event_entries` 1:1 binding, 날짜·숫자 evidence, image rights, section CTA binding, CAS, 저장 후 readback은 제거하지 않았다.
- 이미지 batch import도 각 attachment의 ALT·title·MIME·URL을 검증하고 featured image, Rank Math meta, 본문이 변하지 않았는지 최종 확인한다.
- 이번 구현 자체는 WordPress 글을 수정하거나 공개하지 않는다.

### 구현 검증 결과

- P0~P2 직접 영향 모듈의 표적 회귀 **137/137 PASS**.
- `git diff --check`는 이번 변경 파일 범위에서 PASS했다. 문서 파일의 LF→CRLF 경고는 현재 Windows checkout의 line-ending 안내이며 patch 오류는 아니다.
- 공유 코드 변경 규칙에 따라 전체 `agent-publisher/tests`를 1회 실행했다. **775 tests 실행, failures 6, errors 5, skipped 1**이었다.
- 전체 suite의 11개 실패/오류는 이번 P0~P2 표적 테스트에서는 재현되지 않았고, 현재 작업 시작 전부터 존재하던 다른 미커밋 작업과 연결된다: `test_groups.json`에 아직 등록되지 않은 새 테스트 3개(`test_calc_script.py`, `test_designer_fonts.py`, `test_wp_render.py`)로 인한 validation-runner 오류 5개, 별도 대표이미지 designer 변경 관련 실패 1개, 별도 국민연금 projection calculation 변경 관련 실패 4개, 현재 `POST_CATALOG.md`와 오래된 backlog 기대값 불일치 1개다. 이 파일들을 이번 행사 최적화 작업에서 임의 수정·되돌리지 않았다.
- 운영 WordPress post mutation, 공개 전환, 서버 배포는 수행하지 않았다.

### P3~P8 구현 검증 결과

- P3~P8 직접 영향 모듈과 기존 P0~P2 회귀를 합친 표적 테스트 **191개 PASS**. validation router/profile promotion, metrics category, task retry budget, guarded/meta batch WordPress I/O, section image review/cache/reuse, SSH transport, draft/public/legacy mutation 경로를 포함한다.
- 변경 Python 파일 `py_compile` PASS, scoped `git diff --check` PASS. 문서의 LF→CRLF 메시지는 Windows checkout line-ending 안내뿐이다.
- 공유 인프라 변경 후 전체 suite를 다시 실행해 **791 tests, failures 6, errors 5, skipped 1**을 확인했다. P3~P8 통합 중 잠시 추가된 validation SSH test 오류는 planned-summary test fixture를 새 contract에 맞춰 수정한 뒤 해소됐다.
- 최종 남은 11건은 P0~P2 완료 시점과 동일한 범위다: validation manifest에 등록되지 않은 별도 untracked test 3개로 인한 오류 5개, 별도 designer safety 실패 1개, pension projection 실패 4개, 현재 카탈로그와 오래된 backlog 기대값 불일치 1개다. 이번 작업에서 해당 별도 미커밋 변경을 수정·삭제·되돌리지 않았다.
- 운영 WordPress 글 수정, 공개, 배포, commit, push는 수행하지 않았다.
