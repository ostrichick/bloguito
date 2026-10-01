# Bloguito 공통 작업 지침

정확성을 우선한다. 확인한 사실·추론·미확인 사항을 구분하고, 다른 에이전트의 미커밋 변경을 덮어쓰지 않는다. 글 작성·주제 선정·자동화에서는 `docs/EDITORIAL_SYSTEM.md`와 `agent-publisher/editorial_policy.json`을 적용한다. 기본 저장 상태는 draft이며 명시적 공개 승인 없이 공개하지 않는다.

## 정규 작업 경로

일반 콘텐츠 작업의 상위 진입점은 세 개만 사용한다.

- 새 글: `prepare-draft`
- 기존 reviewed 글 수정: `edit-post`
- 대표이미지만 교체: `replace-featured-image`

과거 `edit-draft`, `revise-draft`, `fast-revise-draft`, `update-existing`, `update-draft`, `quick-image-replace`, `replace-legacy-draft`, `publish` 공개 CLI는 제거됐다. reviewed state가 없는 legacy draft를 고치기 위해 별도 호환 mutation 경로를 되살리지 않는다. 해당 글은 사용자가 수정할 시점에 현행 편집 지침에 맞춰 처리한다. 과거 HTML이나 작업 기록만으로 reviewed provenance를 합성하지 않는다. 공개 전환은 별도 생명주기 작업이며, 사용자가 글별로 승인한 뒤 `promote-draft --confirm-publish`를 사용한다.

`edit-post`는 코드의 단일 change classifier가 변경을 분류한다. 표현·중복 제거·기존 사실 재배치 같은 Simple 변경은 기존 source를 재수집하거나 full semantic review를 다시 하지 않는다. 새 사실·숫자·날짜·제목·출처·CTA·카테고리·현재 판매/신청/예매 상태 등은 Standard로 올려 필요한 source freshness와 full semantic review를 수행한다. 에이전트가 Fast/Standard, QA scope, regression profile을 각각 따로 추론하지 않는다.

## 항상 유지하는 무결성

WordPress mutation은 대상 Post ID와 현재 상태를 읽고, 저장 직전 CAS를 확인하며, 저장 뒤 readback으로 원하는 상태를 검증한다. 공개 글의 본문 변경은 변경 전 백업을 유지한다. 동시 변경이나 예상하지 못한 SHA가 보이면 중단한다. 공개 상태 변경은 별도 명시적 승인이 필요하다. 새 사실이나 근거가 바뀐 경우 공식 source와 의미 검토를 생략하지 않는다.

대표이미지 전용 교체는 본문 editorial source/review 경로를 열지 않는다. 현재 본문 SHA와 `_thumbnail_id`를 읽고 이미지 파일을 검증한 뒤 media import, thumbnail 확인, attachment/ALT 확인, 본문 SHA·제목·slug·상태·발췌문 보존을 readback한다. media import는 비멱등이므로 결과가 불명확한 실패에서 자동 재import하지 않는다. 이미지 생성이 포함된 복합 작업은 생성만으로 완료 처리하지 않으며, 필요한 경우 `AFTER_IMAGE` 체크포인트로 후속 업로드·지정·readback을 이어간다.

## 검증 범위

콘텐츠 한 건을 수정했다는 이유만으로 Python unit/regression suite를 실행하지 않는다. 콘텐츠 무결성은 해당 bundle의 결정론 검사, 필요한 source/review, CAS, backup, readback으로 검증한다. 브라우저 QA는 레이아웃·접근성 또는 CTA 동작처럼 실제 렌더/행동 확인이 필요한 변경에만 요구한다. 단순 문구·메타·대표이미지 교체는 결정론적 readback으로 끝낸다.

공유 코드·renderer·validator·publisher·transport·test infrastructure를 바꾸면 관련 표적 테스트를 먼저 실행한다. 영향 범위가 넓은 공통 코드 변경은 표적 테스트 통과 뒤 전체 suite를 한 번 실행한다. 문서만 바뀐 경우 전체 Python suite를 돌리지 않는다. 실제 코드 변경이 없는 콘텐츠 작업을 시스템 개선 작업으로 확대하지 않는다.

## 새 글과 출처

새 글 주제 탐색과 1차 중복 확인은 `docs/POST_CATALOG.md`에서 시작한다. 실제 저장 직전의 최신 WordPress inventory 확인은 정규 publisher가 수행한다. 구조화 plan과 sources가 완성된 일반 신규 draft는 `prepare-draft`를 사용하고, current review가 있으면 재사용한다. 저장 성공 뒤 `POST_CATALOG.md` 동기화가 실패해도 draft를 다시 만들지 말고 `python scripts/sync_post_catalog.py`만 재실행한다.

공식 출처·정보 유효 수명·직접 답변·조건 보존 원칙은 `docs/EDITORIAL_SYSTEM.md`가 정본이다. 현재 예매·판매·신청·재고처럼 빠르게 변하는 source는 캐시된 receipt가 있어도 필요 시 직접 재조회한다. 같은 원고·source·정책·reviewer 계약의 current semantic review는 재사용한다.

## 작업 범위와 파일

사용자가 요청한 범위를 우선 완료한다. 작업을 막지 않는 공통 코드·renderer·validator 개선점은 별도 TODO로 남기며 콘텐츠 작업에 끼워 넣지 않는다. 공통 코드 변경처럼 충돌 가능성이 큰 작업은 전용 Git worktree에서 격리한다. 정책 변경과 콘텐츠 적용을 같은 미검증 상태에서 섞지 않는다.

일회성 probe·중간 JSON/HTML·다운로드 원문은 Git 비추적 `scratch/tasks/<작업명>/`에 두고 같은 작업에서 재사용한다. 일회성 작업 때문에 `scripts/`나 `agent-publisher/tests/`에 임시 파일을 늘리지 않는다. 바이너리는 파일 경로·mount·정식 upload를 사용하고 Base64 chunk 전송을 일반 전달 경로로 만들지 않는다. 자세한 파일 수명주기는 `scripts/README.md`를 따른다.

## 원격 실행과 완료 보고

운영 WordPress 작업의 기본 transport는 Direct SSH `ssh bloguito`다. Tailscale은 Direct SSH로 처리할 수 없는 서버 관리·복구 상황에서만 명시적으로 선택한다. 로컬 코드·원고·테스트·공개 웹 QA에 Tailscale 상태 확인을 선행하지 않는다.

작업 종료에는 대상, 실제 변경, 공개 상태, 적용한 source/review/CAS/readback/QA 범위, 남은 blocker만 보고한다. 같은 기능의 기존 작업 기록이 있으면 그 문서에 후속 이력을 추가한다. 문서 역할은 `docs/INDEX.md`, 명령·복구·배포 상세는 `docs/OPERATIONS.md`를 따른다.
