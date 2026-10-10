# Bloguito 공통 작업 지침

정확성을 우선한다. 확인한 사실·추론·미확인 사항을 구분하고, 다른 에이전트의 미커밋 변경을 덮어쓰지 않는다. 글 작성·주제 선정·자동화에서는 `docs/EDITORIAL_SYSTEM.md`와 `agent-publisher/editorial_policy.json`을 적용한다. 기본 저장 상태는 draft이며 명시적 공개 승인 없이 공개하지 않는다.

**사람의 WordPress 발행 권한:** 관리자가 로그인하여 WordPress 기본 편집기·글 목록·미리보기에서 직접 수행하는 공개/임시글 전환은 WordPress 본래의 권한으로 처리한다. AI 자동화에 요구하는 source/review/대표이미지 승인·attestation을 관리자의 수동 발행 버튼 노출이나 상태 변경의 필수 조건으로 적용하지 않는다. 누락된 대표이미지는 관리자에게 경고할 수 있으나 수동 발행을 차단하지 않는다. AI 에이전트는 로그인된 관리자 세션을 사용하거나 raw WP-CLI/REST/SQL로 이 제한을 우회해서는 안 되며, 자동화는 기본 draft, 공개는 글별 사용자 승인 후 정규 `promote-draft --confirm-publish` 경로만 사용한다. 접속 자격과 SSH/sudo 권한으로 우회 가능하다면 이 정책은 기술적으로 완전 강제되지 않으므로 권한 분리를 별도 관리한다.

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

**대표이미지 생성 MUST/CAN/MAY:** 새 대표이미지는 반드시 ChatGPT `image_gen.text2im` 도구로 만든다(MUST). 후보는 별도 지시가 없을 때 5개가 기본값이며 사용자 지정 수량을 우선한다(CAN). 사용자가 직접 선택하거나 명시적으로 선택을 위임한 에이전트가 고를 수 있다(MAY). ChatGPT 원본 저장·SHA 봉인·선택 후보 staging·업로드·readback 중 어느 단계든 실패하면 로컬 그림, Gemini, 스크린샷 등의 대체 경로를 사용하지 않는다. 수동 이미지 포함 CLI는 manifest/선택 번호/선택 주체/staging receipt 없이는 업로드를 차단한다. 자동 스케줄러에도 Gemini 생성 예외는 없다. 세부 계약은 `docs/FEATURED_IMAGE_STANDARD.md`를 따른다.

## 검증 범위

콘텐츠 한 건을 수정했다는 이유만으로 Python unit/regression suite를 실행하지 않는다. 콘텐츠 무결성은 해당 bundle의 결정론 검사, 필요한 source/review, CAS, backup, readback으로 검증한다. 브라우저 QA는 레이아웃·접근성 또는 CTA 동작처럼 실제 렌더/행동 확인이 필요한 변경에만 요구한다. 단순 문구·메타·대표이미지 교체는 결정론적 readback으로 끝낸다.

공유 코드·renderer·validator·publisher·transport·test infrastructure를 바꾸면 관련 표적 테스트를 먼저 실행한다. 영향 범위가 넓은 공통 코드 변경은 표적 테스트 통과 뒤 전체 suite를 한 번 실행한다. 문서만 바뀐 경우 전체 Python suite를 돌리지 않는다. 실제 코드 변경이 없는 콘텐츠 작업을 시스템 개선 작업으로 확대하지 않는다.

## 새 글과 출처

새 글 주제 탐색과 1차 중복 확인은 `docs/POST_CATALOG.md`에서 시작한다. 실제 저장 직전의 최신 WordPress inventory 확인은 정규 publisher가 수행한다. 구조화 plan과 sources가 완성된 일반 신규 draft는 `prepare-draft`를 사용하고, current review가 있으면 재사용한다. 저장 성공 뒤 `POST_CATALOG.md` 동기화가 실패해도 draft를 다시 만들지 말고 `python scripts/sync_post_catalog.py`만 재실행한다.

공식 출처·정보 유효 수명·직접 답변·조건 보존 원칙은 `docs/EDITORIAL_SYSTEM.md`가 정본이다. 현재 예매·판매·신청·재고처럼 빠르게 변하는 source는 캐시된 receipt가 있어도 필요 시 직접 재조회한다. 같은 원고·source·정책·reviewer 계약의 current semantic review는 재사용한다.

## 작업 범위와 파일

사용자가 요청한 범위를 우선 완료한다. 작업을 막지 않는 공통 코드·renderer·validator 개선점은 별도 TODO로 남기며 콘텐츠 작업에 끼워 넣지 않는다. 공통 코드 변경처럼 충돌 가능성이 큰 작업은 전용 Git worktree에서 격리한다. 정책 변경과 콘텐츠 적용을 같은 미검증 상태에서 섞지 않는다.

**임시 worktree는 작업 종료까지 책임진다:** 새 worktree가 필요한 작업은 코드 작성·표적/통합 검증·필요한 commit/push·승인된 배포와 readback 등 그 worktree가 필요한 **마지막 작업**을 마친 직후, 최종 결과 보고 전에 `python scripts/ops/retire_worktree.py <정확한 worktree 경로>` dry-run으로 확인하고 안전하면 `--apply`까지 실행한다. 주 사용 `main`은 유지한다. 이 도구는 통합됐거나 동일 패치가 반영된 브랜치, 미커밋/일반 미추적 변경이 없는 등록 worktree만 제거하며, Git 무시 파일은 main의 비추적 `scratch/tasks/worktree-retirement/`에 SHA 검증 후 보존한다. 브랜치에 미반영 변경이 있거나 뒤이어 테스트·배포·검토가 남아 있으면 자동 제거하지 말고 이유를 보고한다. `git worktree remove --force`, `git clean -fdx`, 직접 폴더 삭제로 안전 검사·증거 보존을 우회하지 않는다. 로컬 브랜치 정리는 이 도구가 안전한 조건에서 수행하고 원격 브랜치·stash는 자동 삭제하지 않는다. 여러 에이전트가 동시에 해당 worktree를 사용 중인 경우 마지막 작업자가 실행하도록 작업 책임자를 정한다.

일회성 probe·중간 JSON/HTML·다운로드 원문은 Git 비추적 `scratch/tasks/<작업명>/`에 두고 같은 작업에서 재사용한다. 일회성 작업 때문에 `scripts/`나 `agent-publisher/tests/`에 임시 파일을 늘리지 않는다. 바이너리는 파일 경로·mount·정식 upload를 사용하고 Base64 chunk 전송을 일반 전달 경로로 만들지 않는다. 자세한 파일 수명주기는 `scripts/README.md`를 따른다.

## 원격 실행과 완료 보고

운영 WordPress 작업의 기본 transport는 Direct SSH `ssh bloguito`다. Tailscale은 Direct SSH로 처리할 수 없는 서버 관리·복구 상황에서만 명시적으로 선택한다. 로컬 코드·원고·테스트·공개 웹 QA에 Tailscale 상태 확인을 선행하지 않는다.

**복합 작업은 전 항목 완료가 원칙이다.** 사용자가 이미지 생성과 업로드·대표이미지 교체·검증 등 여러 작업을 함께 요청했다면 이미지 생성만 수행한 채 작업을 종료하거나 전체 완료로 보고하지 않는다. 생성된 원본을 저장하고 필요한 후속 작업을 모두 실행하며, WordPress 작업은 readback까지 확인한다. 진행 중 상태 공유는 가능하지만 완료 보고는 요청된 전체 작업의 성공 여부를 확인한 뒤에 한다. 불가피한 blocker가 있으면 완료로 표현하지 않고 완료 항목·미완료 항목·실제 실패 원인을 구분한다.

**CoS/SSH 연결 실패는 복구 시도가 먼저다.** CoS 또는 SSH 도구가 보이지 않거나 호출에 실패했다는 이유만으로 즉시 작업 불가를 선언하지 않는다. 우선 해당 도구를 다시 검색·호출하고, 접근 권한/세션/연결 상태와 재접속 가능한 경로를 점검하여 실제 복구를 시도한다. 복구에 성공하면 원래 작업을 끝까지 계속한다. 복구 시도 뒤에도 접속할 수 없는 경우에만 수행한 복구 단계와 관측된 오류, 미완료 작업을 명시하여 보고한다. 시도하지 않은 복구를 했다고 주장하지 않는다.

**이미지+업로드 연속 작업 진입:** 기존 post에 **한 개 후보의 즉시 업로드/에이전트 선택이 허용된** 새 대표이미지를 만들 때 `scripts/featured_image_followthrough.py begin --post-id ID`로 CoS/SSH 접근과 WordPress 기준 상태, `AFTER_IMAGE`를 **image_gen 호출 이전**에 확인·기록한다. 이미지 생성 직후 같은 대화의 CoS Core `save_image`로 원본을 저장하고 `featured_image_followthrough.py continue --post-id ID --source <저장원본> --selected-candidate 1 --selection-mode agent-delegated --alt-text <설명>`을 실행한다. 선택 주체가 사용자인 경우 `--selection-mode user`를 사용한다. 마지막 `status --post-id ID`가 `wordpress_verified=true`인지 확인하기 전에는 요청 전체를 완료로 답하지 않는다. 도구가 턴을 종료시켜 즉시 후속 실행이 불가능한 경우, 남은 작업을 완료로 주장하지 않고 체크포인트에서 재개한다. 선택 절차/다중 후보/안전 계약은 `docs/FEATURED_IMAGE_STANDARD.md`가 우선한다.

**도구 부재 판단의 증거:** CoS는 현재 도구 목록/코드 모드에서 Core 함수를 찾아 실제 `read` 또는 `exec_command` 호출까지 시도한다. SSH는 CoS `exec_command`로 `ssh -o BatchMode=yes -o ConnectTimeout=8 bloguito 'echo BLOGUITO_SSH_OK'` 등 읽기 전용 호출을 실행한다. 실패하면 도구 재탐색·세션/접속 경로 점검 및 가능한 한 번의 안전한 재시도를 기록한다. `image_gen`은 ChatGPT 호스트 제공 도구이므로 실제 도구 노출/호출 가능 여부를 확인하며, **로컬 Python 또는 CoS가 이미지 생성 도구 자체를 강제로 활성화할 수 있다고 주장하지 않는다.** 호출 가능한 도구가 없으면 접근 가능한 대체 연결·UI 활성화 경로를 점검하고 한계와 시도 결과를 보고한다. **실제 호출 없이** '도구가 없다/활성화 불가능하다'고 단정하지 않는다. 호스트 도구 호출 성공/실패는 로컬 CLI의 자가 신고보다 실제 호출 로그를 우선한다.

작업 종료에는 대상, 실제 변경, 공개 상태, 적용한 source/review/CAS/readback/QA 범위, 남은 blocker만 보고한다. 같은 기능의 기존 작업 기록이 있으면 그 문서에 후속 이력을 추가한다. 문서 역할은 `docs/INDEX.md`, 명령·복구·배포 상세는 `docs/OPERATIONS.md`를 따른다.
