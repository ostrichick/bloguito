# Bloguito 대표이미지 생성·검수·업로드 신뢰성 보완 계획 (2026-10-12)

> **상태: 계획 수립만 완료 / 구현·운영 배포 미착수.** 현행 기준선 `main` `d4f37c6`. 본 문서는 기존 `docs/featured-image-quality-recurrence-prevention-2026-10-11.md`의 **P0~P2 구현 후 검증에서 발견된 결함을 닫는 후속 계획**이다. 실제 근거는 `scratch/tasks/featured-image-pilot-20261012/validation-report-20261012.md`에 있다. 미완료 검증을 성공이라고 기록하지 않는다.

## 1. 성공 정의와 설계 원칙

사용자의 문제는 단순히 '검사 항목이 부족하다'가 아니다. **로컬 그림을 ChatGPT 생성물로 자가 신고하고, 이미지 관찰을 하지 않았는데 검수 PASS라고 쓰거나, 정규 승인 절차를 우회해서 운영 WordPress로 업로드할 수 있다는 것**이 핵심이다. 그러므로 검사표 항목을 더 늘리는 대신 **누가 무엇을 실제로 실행했는지 검증 가능한 통제 경계**를 만든다.

**최종 흐름:** 게시물별 승인/후보 수 확정 → 네이티브 이미지 생성과 저장의 독립 증거 확인 → 모든 원본 후보 SHA 봉인 → 실제 원본·축소본·최근 10건 비교 → 독립 검수 승인 → 서버가 동일 작업·승인·원본·게시물 CAS를 검증 → 1회 업로드 → WordPress 현물/ALT/본문/썸네일 readback.

- **문서의 `origin_claim`, 임의 JSON의 `PASS`, `review_actor`, 임의 task ID, 파일 해시만으로 신원·도구 호출을 인증하지 않는다.** SHA는 파일의 동일성만 확인한다. 이미지 안의 C2PA 유사 문자열 역시 검증된 서명·신뢰 체인 없이 호스트 호출 증거로 보지 않는다.
- 검증 가능한 ChatGPT 호스트 실행 증거 또는 별도 신뢰 가능한 사람이 승인한 원본 인계 채널을 **실제로 제공하지 못하는 환경**에서는 자동 이미지 업로드를 `held_provenance_unverifiable`로 보류한다. 대체 로컬 생성/Pillow/Canva/Gemini로 무단 전환하지 않는다. 필요한 글은 이미지 없이 임시글로 보류 가능하다.
- **사람의 WordPress 관리자 기능 자체를 박탈하지 않는다.** 제한하는 것은 AI 자동화 계정과 그 실행 자격으로 가능한 쓰기 경로다. 기존 관리자/백업/긴급 복구 권한은 분리 보존한다.
- 이번 계획은 원래 임시글 #922·#926·#928·#930·#932의 내용·대표이미지 교체나 발행을 포함하지 않는다. 정상 운영 통합·교체·발행은 별도 안전 판정 뒤 진행한다.

## 2. 우선순위/작업 묶음

| 작업 | 범위 | 선행 조건 | 검증 가능한 완료 기준 |
| --- | --- | --- | --- |
| **R0 — 직접 CLI 차단 보강 (P0)** | 보류/완료 작업 재사용, 조작된 task 권한, 후보 수, 오래된 검수 승인 차단 | 현재 코드 기준선만 필요 | 10/12 재현한 우회가 전부 원격 import **이전에** 거부 |
| **R1 — 진짜 생성/저장 출처 증거** | 네이티브 호스트·원본 바이트와 task 연결 | 호스트에서 제공 가능한 검증 채널 **실제 조사** | Pillow #922의 `image_gen` 거짓 신고가 PASS 불가, 호스트 미접근은 보류 |
| **R2 — 진짜 검수·선택 증거** | 자기 기입 JSON이 아닌 검수 실행자·원본 관찰/승인 결속 | R0 + 신뢰할 수 있는 검수 이벤트 공급원 | 가짜 여섯 PASS/2020년 timestamp/사용자 선택 위장 차단 |
| **R3 — WordPress 실행 권한 분리** | 운영 비정규 PHP/wp eval/관리자 SSH 직접 변경 우회 제거 | 기존 `security-least-privilege-rollout-2026-10-09.md` Stage A/B 설계와 사전 감사 | 자동화 자격으로 raw host/WP mutation 불가, 정규 서버 게이트만 허용 |
| **R4 — 격리 WordPress 실통합** | 진짜 WordPress/MariaDB 미디어 업로드·CAS·readback | R0~R3와 **Docker 사용 가능한 PC/격리 환경** | 정상/거부/동시성/SSH 유실 모두 실DB 시험 PASS |
| **R5 — 단계적 운영 확인** | 설치 검증, 신규 게시글 3건 시범, 정상/실패 판정 | R4 통과 및 정상 ChatGPT 이미지 생성 가능 | 3건 전체 생성·검수·업로드·readback 기록, 우회 0건 |

### R0. 즉시 고칠 논리 허점 — 기존 게이트를 우회할 수 없게

1. `agent-publisher/editorial_cli.py::_require_current_image_task`는 **현재 공식 작업 저장소**에서 작업을 읽고 `status=in_progress` 및 `validate_current_image_task()` 수준의 최신 본문/정책/만료/작업 대상 검증을 재사용한다. `held_image_generation_unavailable`, `complete`, 취소·만료·불일치 상태는 거부한다. 동일 규칙을 `prepare-draft`, `edit-post`, `replace-featured-image`, `featured_image_followthrough.py continue`의 **원격 쓰기 전** 한 개 공통 preflight로 연결한다.
2. `--image-task-record`는 디버깅·전달용 입력이지 승인 발급 수단이 아니다. 호출자 스스로 작성한 임의 JSON을 근거로 `agent-delegated`를 승인하지 않는다. **새 글**은 신뢰 가능한 별도 작업 등록 단계에서 brief ID에 결속된 승인 레코드가 생성되어야 한다. **기존 글**은 서버가 발급/보존한 현재 체크포인트만 승인 원천으로 사용한다. 사용자가 직접 선택했다고 주장하는 `--selection-mode user`에도 독립적으로 확인 가능한 선택 사건을 결속한다.
3. task의 `candidate_count`와 `manifest.candidates` **실제 수**가 정확히 일치해야 한다. 5개 기본이라면 정확히 5개(서로 다른 SHA·실제 시각적 구도 검토), 사용자 특정 글의 1개 지시가 확인된 경우에만 1개로 작업 시작/승인. `candidate_number` 선택·비교 집합 누락/중복/다른 원본을 거부한다.
4. 검수 시각은 인식 가능한 오프셋 포함 UTC/ISO8601만 허용하고 승인 생성 시각·해당 작업 단계와 합리적인 수명 정책을 적용한다. 2020년 같은 과거의 승인, 미래 승인, 현재 task 개시 이전 승인, 변경된 이미지/정책에 대한 재사용은 모두 `quality_review_expired_or_stale` 처리한다. **정확한 TTL은 운영 요구와 함께 테스트에서 고정**하고 작업 중단 후 정상 재개도 고려한다.
5. 과거 버전의 `AFTER_IMAGE` 체크포인트는 **자동으로 권한을 소급 부여하지 않는다**. 상태 조회는 허용하되 새 이미지를 올리려면 새 task·검수 승인으로 전환하고, 이미 import된 모호한 결과는 기존 `upload_attempt_started` fence를 유지하며 읽기 전용 reconcile한다.
6. `--attest-existing`는 기존 이미지의 **무결성 확인**과 새 이미지의 **시각 품질 승인**을 다른 상태로 남긴다. 기존 이미지가 현재 이미지와 일치한다는 사실로 새 검수를 했다고 기록하지 않는다. `import-section-image`는 원칙적으로 인라인 이미지 경로이며 대표이미지 변경 금지를 회귀 테스트에 명시한다.

**코드 후보:** `agent-publisher/editorial_cli.py`, `agent-publisher/agents/task_state.py`, `agent-publisher/agents/image_generation_policy.py`, `agent-publisher/agents/featured_image_quality_gate.py`, `scripts/featured_image_followthrough.py`, 관련 테스트. 이미 존재하는 CAS·stage 및 pipeline 상태 코드는 복제하지 않고 재사용한다.

### R1. 생성 출처의 '문자열'과 '증거'를 분리

1. 첫 작업은 **호스트가 제공하는 실제 이벤트/원본 식별자/검증 가능한 콘텐츠 출처가 무엇인지 조사**한다. `image_gen` 호출 성공, CoS `save_image` 결과와 파일 SHA를 현재 `task_id`·후보 번호에 결속할 수 있는지 테스트. 제공하지 않는 시스템에 존재하지 않는 서명/API/이벤트 ID를 만들어 쓰지 않는다.
2. 계층 정의: `host_verified`(독립된 신뢰 경계에서 재검증할 수 있는 호스트·원본 증거), `trusted_human_handoff`(사용자가 실제 원본을 직접 확인하고 신뢰 가능한 승인 채널로 특정 task/SHA를 지정한 제한 경로), `self_reported`(단순 문자열/클라이언트 로그), `unavailable`. **자동 업로드는 `host_verified`로만** 진행하는 것을 기본으로 하고, 사용자 직접 인계는 별도 명시 승인 시에만 신뢰 가능한 채널로 처리한다. 확인 불가능하면 보류한다.
3. 증거 스키마는 검증 가능한 원본 이벤트 식별, `task_id`, 후보 번호, 원본 해시, 실제 발급자, 발급 시각, 재사용 방지 값을 포함한다. 서명이 가능하다면 **AI/일반 CLI 계정이 서명 비밀키를 보유하지 않게** 분리한다. C2PA가 있다면 신뢰 앵커까지 검증한 경우에만 참고하고, C2PA 유무만으로 모든 ChatGPT 생성물을 판정하지 않는다.
4. 봉인 도구 `scripts/seal_featured_image_candidates.py`는 자가 신고 `origin_claim`을 생성 사실로 승격시키지 않는다. 정규 실행기는 업로드 전에 *원본 SHA마다* 실제 출처 검증 결과가 붙었는지 검사한다. 예전 사전 봉인된 이미지도 자동 `host_verified`로 승격하지 않는다.
5. 호스트 증거를 제공할 수 없는 현실적 제약이 확인되면 자동 경로를 `NO-GO`로 명시하고 검증 가능한 사용자 직접 선택/원본 전달 제품 흐름이 설계될 때까지 사용하지 않는다. 이 항목의 '완료'는 가짜 PASS를 만드는 것이 아니라 **보안성 있게 성공 또는 보류하는 것**이다.

### R2. '체크리스트 작성'과 '관찰·승인 사건' 구분

1. 기존 `review_featured_image_candidates.py`의 템플릿은 **검수 보조 도구**로 유지한다. 실제 사람이 원본·240×135 미리보기·최근 10건(확보 가능한 범위)을 보았다는 자기 진술만으로는 독립 증거가 아니다.
2. 검수 승인은 AI와 권한이 분리된 reviewer/승인 수단에서 발행하거나 신뢰할 수 있는 호스트 실행 기록을 확인한다. 원본 SHA·모바일 preview SHA·비교 대상 목록·후보 수·검수 항목별 근거·사용자/위임 선택 사건·검수 주체·task_id·시각을 결속한다. 검수자가 볼 수 없는 매체나 작업은 `quality_review_pending`, 불합격은 `quality_review_failed`다.
3. 자동 심미 평가는 주제 적합성·반복 카드/PPT 디자인·본문 문구 정확성·실제 모바일 가독성을 지원하는 **검토 의견**일 뿐, 증명된 호스트 호출 및 신뢰할 수 있는 승인 주체를 대체하지 않는다. 기록만 채워 넣고 `observed_full_size=true`로 만드는 조작은 거부한다.
4. 운영 효율을 위해 **명백한 정상 1개 후보(사용자 요청 시)**에는 독립 검수 1회, 기본 다섯 후보에는 중복 검사 후 적합한 후보를 선택한다. 불확실하면 사용자 확인/보류. 자동 재시도 제한·실패 이유를 기록하며 일괄 업로드를 위해 품질을 희생하지 않는다.

### R3. 실제 권한 분리 — 우회 PHP 업로드 근본 차단

1. 기존 `docs/security-least-privilege-rollout-2026-10-09.md` **Stage A(읽기 전용 SSH 계정 제안, 미배포)**, **Stage B(안전한 쓰기 계약, 미구현)**를 출발점으로 한다. 정상 실행을 `ubuntu`의 `sudo`/`docker`/`lxd` 권한 또는 임의 `wp eval`로 계속할 수 있다면 Python 검사만으로는 안전하다고 주장하지 않는다.
2. 자동화용 **좁은 서버 쓰기 게이트**를 설계한다. root 소유 고정 실행 파일 또는 인증된 서버 측 API가 *허용된 명령*(`prepare-draft`, `edit-post`, `replace-featured-image`와 허가된 metadata)과 엄격한 payload, 작업·생성·검수 승인, WordPress 본문/기존 이미지 CAS, import fence 및 읽기 검증만 받는다. 일반 임의 PHP, 다른 컨테이너, 쉘 인수/파일 쓰기, `wp eval`, 플러그인·Cron 변경은 금지한다.
3. AI/작업용 SSH 키는 별도 제한 계정·forced command·비 Docker/sudo/lxd 그룹·최소 WP capability로 제한한다. 별도 관리자 `ubuntu`·SSH/Tailscale 복구·백업·운영 스케줄러를 보존하고, AI가 여전히 관리자 키에 접근 가능한 동안에는 권한 분리 완료를 주장하지 않는다.
4. 이미 존재하는 `scratch/tasks/**/attach-image-once.php` 같은 자료는 **증거로 보존**하되 실행 런처에서 재사용하지 않는다. 실행 가능한 독립 PHP 업로드, 직접 WP-CLI와 우회 import를 부정 테스트로 포함하고 CI 정적 패턴 탐지를 추가한다. 정적 탐지는 권한 경계의 대체가 아니다.
5. 독립 서버에서 read-only 계정 → 허용된 제한 쓰기 계정 → 기존 무인 스케줄러 마이그레이션을 **각각 분리된 변경/복구 단계**로 진행한다. root 복구 키와 crontab/백업은 검증 전 변경하지 않는다. 설치·sudoers·sshd/권한 변경은 격리 Ubuntu에서 검증 후 운영에 단계적으로 적용하며 모든 변경은 명시적인 readback/rollback을 갖는다.

### R4. 재발 사례 중심 E2E / R5. 운영 검증

| 시험 | 기대 결과 |
| --- | --- |
| 2026-10-11 #922 Pillow PNG를 `image_gen`으로 신고하여 seal/stage | 해시는 검증되더라도 **출처 인증 실패**, 실제 미디어 import **0건** |
| 가짜 여섯 항목 PASS와 `observed_full_size=true`만 기입 | 독립 reviewer 사건 부재 → 거부, import **0건** |
| 기본 5개 후보 작업인데 manifest에 1개만 등록 | 후보 수 불일치 → 거부. 사용자 지정 1개 작업만 통과 가능 |
| `reviewed_at=2020`, 미래 시각, 작업/정책/원본 SHA 변경 | 검수 보류/재승인 필요, import **0건** |
| `--image-task-record`로 권한을 자가 발급, `user` 선택 사칭 | 독립 등록/승인 사건 미검증 → 거부 |
| checkpoint가 `held`·`complete`·취소·만료 | 세 정규 CLI와 followthrough 모두 원격 import 이전 거부 |
| 가짜 승인 + 임시 PHP/`wp eval`로 WordPress 접근 시도 | **자동화 최소 권한**으로 거부; 관리자 수동 WP UI는 보존 |
| 정상 호스트 검증 가능한 원본, 별개 유효한 reviewer, 후보 수/선택/작업 일치 | 서버 측 1회 업로드·ALT·`_thumbnail_id`/본문 SHA/URL/공개상태 readback PASS |
| 본문/썸네일 경합, 결과 수신 유실/중복 호출, WP media 실패 | CAS와 import fence, 수동 reconcile, 중복 미디어 생성 **0건** |
| 자동 배포/스케줄러에서 image_gen 사용 불가 | `held` 보류, 로컬 폴백/자동 게시 0건, 운영 상태와 이유 보고 |

- 먼저 **Python 부정 테스트에서 현재 재현 실패가 다시 발생하는지** 확인(R0); 그다음 참/거짓 origin 및 review 증거 주입 테스트(R1/R2), 제한 SSH/권한 격리 테스트(R3), 마지막 실 WordPress/MariaDB 업로드와 소실 응답·경합 검증(R4)을 진행한다. 기존 1,265 PASS는 기준선일 뿐 새로운 시나리오에 대한 증명이 아니다.
- 2026-10-12 노트북에는 Docker/WordPress 격리 구동 수단이 확인되지 않았다. 실DB는 Docker 가능한 **기존 별도 PC의 격리 WordPress 환경**에서 현 revision으로 재검증한다. 운영 서버/실제 임시글을 E2E 시험장으로 사용하지 않는다. 이전 10/10 다른 revision의 실DB 15그룹 PASS를 이 revision의 수용 근거로 대체하지 않는다.
- R4까지 PASS한 뒤 실사용 신규 글 **서로 다른 주제 최소 3건**을 시범 운영한다. 각 건별 실제 호스트 생성 이벤트/파일 SHA·검수·선택·server CAS·이미지/ALT/readback을 확인하고 **자동 우회 0건**, 누락 승인 0건, 중복 업로드 0건을 인수 조건으로 한다. 3건만으로 주관적 만족도를 보장할 수 없으므로 사용자가 시각적으로 거절한 사례는 모두 품질 기준의 교정 자료로 남긴다.

## 3. 구현/검토/통합 순서

1. 현재 main의 다른 사용자/에이전트 변경을 확인하고 별도 worktree에서 **R0을 우선** 구현한다. 먼저 독립 감사가 재현한 held/complete, 5↔1, 2020 검수, 호출자 task 승인 위장을 **실패하는 회귀 테스트**로 고정한 후 수정. 이 단계만 통과했다고 운영 배포하지 않는다.
2. R1은 **1차로 호스트 증거를 실제로 얻을 수 있는지 타당성 조사**한다. 가능한 경우 발급자·무결성 검증 구현, 불가능하면 사용자 개입 없이 자동 업로드는 `held`로 남기는 설계를 확정한다. 외부 검증 수단이 존재한다는 근거 없이 자가 발급 서명 키를 추가하지 않는다.
3. R2는 승인 수행자와 승인 증거를 **R1과 독립된 신뢰 경계**에서 생성/검증한다. 이미지 평가 문구를 추가하는 것과 검수 권한 제어 구현을 혼동하지 않는다.
4. R3는 기존 10/09 SSH 최소 권한 계획에 대한 **호환성·연쇄 영향 분석**을 선행한다. 서버 측 쓰기 게이트·계정/cron 권한/백업 분리·sshd 설정을 격리 환경에서 확인하고 관리자를 위한 복구 접근을 실측한 다음에만 운영 cutover 진행.
5. R0~R3 각 묶음마다 표적/부정/정상 회귀, 전체 Python suite 및 release manifest 해시 검증, 보안/기능 독립 감사를 수행한다. 허용 작업이 비정상적으로 막히는 회귀도 함께 판정한다. 현재 `main`의 미커밋 파일은 덮어쓰지 않는다.
6. R4의 실DB 시험 통과 전에는 **자동 이미지 업로드 운영 적용 `NO-GO`**. 운영 적용은 별도 변경 단위로 정규 build/install, revision/파일 SHA/readback 확인, 장애 시 안전한 배포 rollback을 갖는다. 이미 시작된 미디어 import를 임의로 재시도하지 않는다.
7. R5의 새 이미지 3건 파일/WordPress 현물 QA까지 확인되면 비로소 **이 개선 작업의 운영 수용 `GO`**로 평가한다. 기존 저품질 대표이미지를 자동 교체하거나 임시글을 발행하지 않는다.

## 4. 변경 범위와 완료 보고의 기준

- **예상 코드**: `agent-publisher/editorial_cli.py`, `agents/task_state.py`, `agents/image_generation_policy.py`, `agents/featured_image_quality_gate.py`, `agents/featured_image_quality_review.py`, `agents/featured_image.py`, `scripts/seal_featured_image_candidates.py`, `scripts/featured_image_followthrough.py`, `scripts/editorial_cli_via_ssh.py` 및 통합 테스트. R3는 기존 `scripts/security/` 및 별도의 **server-side allowlist writer** 설계가 필요하다. 최종 파일은 구현 범위를 조사한 후 확정한다.
- **보고 형식**: R0~R5 각각 구현 SHA / 테스트 PASS·FAIL / 독립 감사 / 실제 호스트·WP 쓰기 여부 / 운영 설치 여부 / 차단된 위험과 잔여 위험. 모든 결함이 수정되기 전에는 `재발 완전 방지`라고 표현하지 않는다.
- **현재 작업 범위**: 이 문서 작성과 현재 코드/증거 조사만 허용했다. 새 코드 변경, Git 커밋/병합, SSH/WP 운영 계정·서버 수정, 실제 이미지 생성/발행/대표이미지 교체는 수행하지 않는다.
