# Bloguito 대표이미지 보안 R1–R5: 노트북 → Docker PC 인계

작성: 2026-10-13 KST. 실행 환경: `DubuLaptop` / `C:\Projects\Bloguito-image-r1-r5-20261012`.

## 0. 먼저 지켜야 할 범위

이 문서는 **운영 WordPress 배포 승인서가 아니다**. `R1/R2` 신뢰 가능한 독립 증거 발급자와 사용자 선택 승인 시스템이 아직 없다. `R3`는 제한형 writer의 개발 계약이며 운영 sudo/sshd/WordPress 권한 분리가 확인되지 않았다. `R4` Docker 기반 격리 환경, `R5` 신규 이미지 3건 실물 검증은 미실시이다. 따라서 운영 자동 업로드 **NO-GO**, 운영 게시물·운영 데이터베이스에 쓰기 **0회**를 유지한다.

R0 기준은 `9fd0201d98a7ea29e64a32cdae7e28e252d2faa6`; R1~R5 이전 개발 커밋은 `e049a2d5e6350a61b7bc4ca3d64db4538a077f63`와 `0720f1d600dd3dac6688a9042ba25de0a5bec686`이다. 최종 PC 인계 커밋 SHA와 원격 전달 성공/실패는 작업 종료 시 이 문서에 추가한다.

R3 PHP 고정 실행기(`scripts/security/featured_image_set.php`)의 2026-10-13 노트북 최종 SHA-256은 `E48890944F7B553B590B8CC03B053ADC07DC204DC28EC60B2E80A0C1C115F230`이다. **이 SHA를 고정하는 파일만 만든다고 서버에서 성공하는 것은 아니다.** PC에서 먼저 `php -l`, root-owned protected writer와 PHP 일치 해시·read-only mount·비관리자 WordPress 사용자 및 custom capability를 실측한 다음에만 root lock 파일로 승인할 수 있다. 이 파일의 의도된 쓰기는 이미 import된 이미지의 첨부 선택/ALT 두 metadata뿐이며 **신규 image media import는 미구현**이다.

`C:\Projects\Bloguito`의 `main`에는 작업 시작 전부터 수정 문서 `docs/INDEX.md`, `docs/POST_CATALOG.md`, `docs/clarity-integration-2026-09-29.md`와 사용자 작업 중 미추적 문서 3개가 있다. **reset/clean/stash/강제 체크아웃으로 이 파일들을 덮어쓰지 않는다.** 본 인계는 별도 `feat/featured-image-r1-r5-20261012` 브랜치를 대상으로 한다.

원본 메인에만 있던 사용자의 미추적 상세 계획 `docs/featured-image-trust-and-upload-process-hardening-plan-2026-10-12.md`를 **원본을 수정하지 않고**, 이 브랜치의 `docs/featured-image-r0-r5-origin-plan-snapshot-2026-10-12.md`로 정확히 복사하여 함께 인계한다. 두 파일의 SHA-256이 `3B7039288B76DD544B34F74097C9A8D09EBEFBB65AB03C0EA28C2340F1AA266B`로 일치함을 확인했다. 이는 계획 보존 사본이지 운영 승인서가 아니다.

## 1. 노트북에서 실제로 한 작업

- `R1`: 사용자 자가 작성 JSON 대신, ChatGPT 생성 증거의 task·원본 SHA·후보 목록에 독립 Ed25519 서명을 요구하는 검증기. Windows 로컬 신뢰키 경로는 운영 승인 불가로 차단. OpenAI Content Provenance 검사 API 연동 도구는 출처 **신호**만 확인하며 자체적으로 인증 이벤트를 발급하지 않는다.
- `R2`: 별도의 검수자 서명을 manifest·receipt SHA, staging SHA, 사용자/위임 선택·task ID에 결합. 기존 이미지의 무결성만으로 `automated_visual_review` 승인 발급하던 `--attest-existing` 경로 차단.
- `R3`: root 소유 승인 spool, 제한형 SSH forced command, Ed25519 이중 서명, 버전·SHA 잠금, 1회 쓰기 시도 fence와 PHP 처리 계약. 보호된 운영 서버 설치·원자적 메타데이터/파일 확인은 별도 검증 필요.
- `R4`: 노트북에는 Docker, PHP 및 WP/MariaDB 실제 격리 테스트 런타임이 없어 local/mock만 확인. 실제 격리 실행은 PC용 테스트 구성과 명령을 따른다.
- `R5`: 실제 서로 다른 주제 3건의 서명된 원본/승인/WordPress readback을 요구하는 검사기를 작성. 인위적으로 성공 처리하거나 가짜 WordPress JSON을 운영 검증으로 받아들이지 않는다. **실제 인수 0/3건**.
- `PublisherAgent.publish(image_path=...)` 같은 내부 스케줄러 경로가 직접 WP-CLI media import를 호출하던 우회 경로를 fail-closed로 차단한다. 신뢰 가능한 writer가 없을 때 글을 먼저 생성한 후 이미지 업로드에 실패하는 반쪽 상태를 만들지 않는다.

## 2. PC 인계 직후 순서 (이 순서 변경 금지)

1. **브랜치/원격 동기화**: feature 브랜치 커밋과 원격을 확인한다. `main`의 미커밋 사용자 문서는 건드리지 않는다.
2. **독립 신뢰·승인 발급**: R1의 실제 ChatGPT 생성 이벤트/원본 SHA를 확인할 호스트 발급자와 R2의 사용자 승인 권한자를 분리한다. private signing key는 AI worker/웹 루트/Git/공유 scratch에 두지 않는다. 공개키도 root가 통제하는 별개 경로에서 설치한다. 단순 이미지 AI 감지 결과나 JSON 값은 발급 권한이 아니다.
3. **격리 WordPress / MariaDB 실DB만 먼저 구성**: 신규 project, 임시 볼륨/계정/암호와 별도 루프백 포트를 사용하고 기존 `wordpress/docker-compose.yml`(고정 `wordpress_app`, `wordpress_db` + 운영형 영속 볼륨)을 그대로 실행하지 않는다. 운영 SSH/WordPress와 어떤 서비스·볼륨도 공유하지 않는다.
4. **R3 PHP writer 및 SSH/sudo 정책 검증**: PHP 구문 lint, `root` 소유 실행 파일 해시/읽기 전용 mount, 독립 발급자 공개키, WordPress non-admin capabilities, 첨부파일·ALT·본문/제목/slug/상태 SHA CAS와 원자적 쓰기/readback 시험. 컨테이너 런타임 SHA를 미리 고정하고 다른 경로의 raw `wp eval` 및 관리자 sudo는 AI 계정으로 사용할 수 없어야 한다.
5. **R4 부정/정상·경합 시험**: 정상 1회, 이미지·선택 바꿔치기, 서명 위조·만료, 독립 검수 부재, 두 번 호출, 실패 후 응답 유실, 미디어 import 중 경합, 서버 본문/썸네일 변경, ALT/attachment SHA 읽기 복구, 서버 프로세스 중단·재시도 제한을 시험한다. WordPress `posts`/`postmeta`/`attachments` 레코드 수가 기대한 범위인지 직접 확인한다.
6. **R5 최소 3건 실물 QA**: 서로 다른 주제의 실제 `image_gen` 원본 3개를 생성/검수/사용자 또는 명시 위임 선택하여 신뢰 발급·서버 업로드/ALT/본문/thumbnail/readback. `verify_featured_image_pilots.py`의 오프라인 NO-GO 결과를 성공으로 바꾸지 말고, 신뢰할 수 있는 독립 읽기 채널과 실제 결과가 확보된 뒤 인수 판단을 확장한다.
7. **독립 감사·결정**: signed proof, 파일 해시, 권한 우회 차단, data race, 관리자 수동 WP UI 발행 가능 여부, release manifest, 롤백 자료까지 PASS해야 운영 GO를 검토한다. 그때까지 운영 배포·글 공개·대표이미지 교체 금지.

**R4 합성 fixture 성공과 실제 R4 인수 성공은 다르다.** `image_r4_pc_smoke.py`는 WP-CLI의 정확한 `stale_post_cas`/`stale_thumbnail_cas` 거부 메시지를 요구하며 일반 Docker 장애를 충돌로 위장해 PASS시키지 않는다. 로그에는 synthetic 비밀번호를 포함하지 않고, 해당 fixture의 생성된 파일 외에는 컨테이너에 노출되지 않도록 디렉터리 symlink/junction·추가 파일 검사도 한다. 이 방어는 PC의 실제 Docker/WordPress 실행 결과까지 대신하지 못한다.

## 3. PC에서 하지 말아야 할 것

- 운영 서버를 시험 WordPress처럼 사용하거나 운영 DB/볼륨 복제본을 권한 없이 연결하지 말 것.
- `docker compose -p`만 바꾼 채 기존 고정 `container_name`이 있는 운영 compose를 실행하지 말 것.
- R1/R2의 **테스트용 임시 private key**를 운영 서명 발급 키라고 간주하지 말 것. `origin_claim`, `review_result=pass`, 이미지를 보여 준 챗 기록만으로 자체 서명하지 말 것.
- 사용자 승인/독립 검수/이미지 생성이 실제 확인되지 않았는데 `GO`, `3/3 PASS`, `WordPress verified` 등으로 표시하지 말 것.
- 실DB에서 media import 이후 응답을 잃었을 때 무조건 import 재시도하지 말 것. request id 일회성 fence를 조회하고 수동 reconciliation 필요 여부를 판단할 것.
- 기존 `main` 미커밋 문서, 기존 운영 설정, 다른 에이전트 작업 중 worktree를 정리하지 말 것.

## 4. PC에 남기는 필수 산출물

PC용 격리 compose/harness 명령·실행 실패 원인·통과 조건은 `docs/featured-image-r4-pc-runbook-2026-10-13.md`를 따른다. 구현·오프라인 테스트 출처는 `docs/featured-image-r1-r5-implementation-validation-2026-10-12.md`, 정책은 `docs/FEATURED_IMAGE_STANDARD.md`, 기존 사용자 작업 계획의 **검증된 동일 SHA 사본**은 `docs/featured-image-r0-r5-origin-plan-snapshot-2026-10-12.md`다.

검수 후 최종 보고에는 `Git SHA`, 테스트 합격/실패·skip, Docker/WP 실제 서비스 접근 여부, WordPress mutation 건수, 생성 원본·검수 사건·서버 인증 정보의 출처, R4/R5 각각의 실제 인수 결과, 잔여 blocker, 운영 GO/NO-GO를 구분해 기록한다.

## 5. PC 재개용 지시

> `ostrichick/bloguito`의 feature branch `feat/featured-image-r1-r5-20261012` 최신 커밋을 체크아웃하고 `docs/featured-image-pc-handoff-2026-10-13.md`, `docs/featured-image-r4-pc-runbook-2026-10-13.md`, `docs/featured-image-r1-r5-implementation-validation-2026-10-12.md`, `AGENTS.md`를 읽어라. 이 작업은 Bloguito 대표이미지 R1–R5 보안 보강의 PC 단계이며, 노트북에서 작성·검증한 코드를 무단 재설계하지 말고 남은 작업을 직접 격리 Docker WordPress/MariaDB에서 검증한다. 테스트 포스터/데이터만 사용하고 운영 WordPress/DB/SSH/실제 게시물은 수정하지 마라. R1/R2 신뢰 서명 발급자, R3 fixed PHP writer와 최소 권한, R4 경합·응답 소실·CAS/ALT/readback, R5 실제 서로 다른 주제 3건을 각각 완료/차단으로 보고해라. 정상 이미지 출처 증거·실제 사용자 승인 또는 위임이 없으면 운영 자동화는 반드시 NO-GO를 유지해라. 기존 main의 미커밋 문서를 보존하고, 테스트/코드 검증 결과와 남은 장애물을 문서에 기록해라.`
