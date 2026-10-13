# Bloguito 대표이미지 R1–R5 구현·검증 기록 (2026-10-12)

## 기준/범위

- 기준 `main`: `9fd0201d98a7ea29e64a32cdae7e28e252d2faa6` (R0).
- 격리 개발 작업 트리: `C:/Projects/Bloguito-image-r1-r5-20261012`.
- 기존 `main`의 미커밋 문서와 실제 WordPress 글, 대표이미지, DB, SSH/sudo/cron/운영 설치를 변경하지 않았다.
- **운영 판정: NO-GO.** 검증 코드·실행 계약·검사 도구와 실제 신뢰할 수 있는 발급 서비스·격리 통합·3건 운영 증명을 구분한다.

## R1: 이미지 출처 확인

`agents/featured_image_trust.py`는 임의 `origin_claim`을 생성 도구의 증명으로 승격하지 않는다. 원본 전체 후보의 SHA256, 작업 ID, 대상과 생성 정책 SHA를 호스트 발급자의 별도 Ed25519 서명에 묶고 보호된 `/etc/bloguito/image-trust/host.pub.pem`으로 검증한다. 정상 서명 없이는 이미지 업로드가 중단된다. CLI나 환경변수에서 임의 공개키를 지정하여 신뢰앵커를 우회할 수 없다.

독립 감사에서 Windows 로컬 신뢰키 사용이 보호된 서버 발급자 검증을 대체할 수 없다는 HIGH 통합 문제를 발견해 수정했다. Windows production verifier 호출은 이제 항상 `protected_server_verifier_required`로 보류된다. 정상 서명으로도 서버 측 검증기 설치 전에는 노트북에서 이미지 업로드를 허용하지 않는다. 테스트 키 지정은 오프라인 검증 함수 테스트에만 사용할 수 있다.

공식 OpenAI Content Provenance API (`https://developers.openai.com/api/docs/guides/content-provenance`)의 검증 결과를 해석하는 오프라인 테스트 및 `scripts/security/openai_provenance_probe.py`를 추가했다. 최소한 OpenAI 발급자로 인식되는 신뢰된 C2PA 신호를 요구하고, SynthID만 존재하거나 불신 C2PA인 경우 보류한다. 이 API는 **이미지 출처 신호를 검사할 뿐 누가 어떤 작업으로 생성했는지 증명하지 않는다.** 따라서 API 응답을 그대로 서명된 `host_generation` 이벤트로 취급하지 않고, 별도 신뢰할 수 있는 발급자가 작업·원본을 결합해야 한다.

**미완료:** OpenAI API credential/호출 실제 응답, 원본을 ChatGPT task에 연결하는 호스트/신뢰 인간 인계 채널, 운영 호스트 서명 발급자와 검증키의 보호된 설치. mock 서명 긍정 테스트는 실제 ChatGPT 생성 증거가 아니다.

## R2: 실제 검수 및 선택 승인

`review_selection` 증거는 생성 호스트와 **서로 다른** Ed25519 발급자 공개키로 검증한다. 작업·정책·선택 원본 SHA·staging SHA·검수 영수증 SHA·manifest SHA·선택 번호/방식/actor 및 24시간 기한에 서명을 결속한다. 원본/검수 수정, 다른 게시물·정책 재사용, 검수자 자가 서명·위임 위조는 차단한다. 이 검사는 기존 R0 육안 검수 내용을 보완하지만 별도의 사람이 원본을 실제 관찰했는지 자체 증명하지 않는다.

**미완료:** 사용자의 실제 후보 선택 및 독립 심사 이벤트를 발행하는 신뢰 가능한 UI/서비스와 운영 검수자 인증. 발급키를 AI 실행자에게 주거나 검수 JSON의 자기 신고를 인증으로 오인하지 않는다.

독립 감사에서 기존 이미지의 파일 무결성 `--attest-existing` 경로가 실제 육안 승인 없이 `automated_visual_review` digest를 만들어 공개 승인까지 생성할 수 있는 HIGH 우회를 추가 발견했다. 정규 CLI와 `attest_current_featured_image` 하위 함수 모두 fail-closed로 차단하고 부정 테스트를 추가했다. 새 독립 심사 증거를 발급할 수 있게 되기 전에는 해당 레거시 자동 게시 승인 경로를 사용할 수 없다. WordPress 관리자 UI의 수동 발행 권한은 그대로 유지한다.

## R3: 서버 측 최소 권한 writer 시제품

`scripts/security/bloguito_ssh_write_gate.py`, `bloguito_wp_image_writer.py`, `sshd.bloguito-ssh-write.example`, `sudoers.bloguito-ssh-write.example`가 격리 제안이다. SSH 요청은 고정된 `wp-write featured-image-set <32hex>` 형식만 허용한다. 서버 writer는 root 소유의 승인 request spool·서명 발급자·버전 고정 PHP 해시·원문/썸네일 CAS·중복 시도 fence·최소 권한 WordPress 사용자를 요구한다. 발급되지 않은 서명·임의 WP CLI/PHP 경로·관리자 인수·셸 인수는 거부한다.

**미완료:** 고정 PHP runtime과 신규 미디어 **import**를 담당하는 실제 제한형 writer, 서버 계정/권한 분리, 진짜 WordPress CAS/readback, root 정책/운영 복구 경로, 기존 `ubuntu` 관리자 권한의 AI 접근 단절. 현재 구현은 attachment 지정 계약 시제품이며 운영 배포 불가.

## R4: 격리 WordPress/MariaDB 통합

노트북에는 Docker/Podman/설치된 WSL 배포판, PHP/MySQL/WP CLI가 확인되지 않았다. `wordpress/docker-compose.yml`은 고정된 컨테이너명과 영속 볼륨을 쓰므로 그대로 격리 시험장으로 사용하지 않는다. R0 CAS·SSH 유실·업로드 retry 관련 mock regression은 정상이나 실제 DB row count, media import 1회, 경합·lost response·roll back, ALT/본문/썸네일 현물 검증은 **0건**이다.

**미완료:** 별도 Docker PC에서 격리 WordPress/MariaDB 환경과 root writer를 올리고 정상·차단·경합·응답 유실 케이스를 실제 실행해야 한다.

## R5: 새 이미지 3건 수용 기준

`scripts/verify_featured_image_pilots.py`는 서로 다른 주제, post ID, task ID, 이미지 파일을 가진 정확히 3건을 검사한다. 실제 원본/staging 해시, R1/R2 서명 파일, 글 기준 상태·ALT·URL 계획을 검사하지만 **사용자가 작성한 WordPress JSON은 라이브 성공 증거로 취급하지 않는다.** 신뢰 가능한 별개 WordPress readback이 없으면 언제나 NO-GO(exit 2). 예제값·임의 JSON·mock 증명으로 3건 완료를 만들 수 없다.

**미완료:** 실제 네이티브 생성 원본 3개와 독립 승인, 최소 권한 WordPress 실제 저장·읽기 검증 3건 모두 부재. 실제 글을 수정하거나 발행하지 않았다.

## 품질·릴리스·보존 상태

- 로컬 표적 테스트: `test_featured_image_trust.py` 10 PASS, `test_openai_provenance_probe.py` 3 PASS, `test_ssh_image_writer_r3.py` 8 PASS, `test_featured_image_pilots.py` 11 PASS, 기존 image/SSH 관련 162 PASS(모두 mock/오프라인).
- 전체 Python suite는 최종 커밋 후 clean tracked snapshot에서 재실행한다. 빌더는 작업 트리 변경이나 Git 비추적 신규 모듈을 정상적으로 거부하므로 해당 개발 중 실패는 R1~R5 기능 실패로 오인하지 않는다.
- 릴리스 inventory에 신뢰 검증 모듈 1개가 추가되어 canonical inventory는 88개, digest `c78f576e9d9eb9ad4b2cabc667c777b2601bc4e4b059e98d5dd3a697b82b944d`다. 설치 성공과 별개로 **실제 운영 설치는 수행하지 않는다.**

## 운영 GO가 되기 위한 조건

1. 실측된 OpenAI 원본 출처 API 성공 및 **작업/후보 원본 결속을 검증하는 독립 발급자**와 키 보호.
2. 별도 사용자 선택·독립 심사 승인 발급자 및 해당 사건의 신뢰 가능한 관찰 기록.
3. 실제 미디어 import를 포함한 최소 권한 root server writer, AI 자격의 임의 wp eval/sudo/PHP 사용 불가 증명.
4. R4 실제 격리 WP/MariaDB 부정/정상/concurrency 테스트 PASS 및 릴리스 SHA·rollback 검증.
5. R5 서로 다른 주제 실제 3건의 원본·승인·WP 저장/ALT/불변 필드/readback 성공 확인.

이 중 어느 한 단계라도 실패하거나 증거를 얻을 수 없으면 **NO-GO**로 보류한다.

## 2026-10-13: Docker 없는 노트북에서 수행한 추가 구현

사용자 요청에 따라 `C:/Projects/Bloguito-image-r1-r5-20261012` 격리 브랜치에서 로컬로 가능한 범위만 추가 구현했다. Docker, PHP CLI, 운영 WP/MariaDB 실행 없이 완료했다는 뜻이지 실제 WP E2E 검증을 통과했다는 의미는 아니다. 운영 SSH/DB/WordPress와 기본 `main`은 변경하지 않았다.

### 경계 강화 및 표적 회귀

- `PublisherAgent.publish(image_path=...)`가 스케줄러가 제출한 로컬 이미지와 자가 계산한 승인 SHA만으로 `wp media import`를 시작하던 별도 우회 통로를 `scheduled_image_trusted_writer_unavailable`로 **draft 생성 전** 차단했다. 스케줄러에서도 이 의도된 중단을 오류 대신 안전 보류로 분류한다. 공식 포스터 경로는 독립 출처/권한 계약 없이 이전 자동 이미지 API를 사용하지 않도록 보류된다.
- OpenAI Content Provenance API의 명세상 OpenAI issuer, `outcome=detected`와 `validation_state=trusted` **또는** `valid`를 공급자 출처 *신호*로 처리하도록 조정했다. 이것은 호스트 생성 작업 증명이나 R2 승인 서명으로 승격되지 않는다. 해당 API를 자격 증명으로 직접 호출하지 않았고 실제 생성 성공을 주장하지 않는다.
- R3 고정 PHP 실행기 `scripts/security/featured_image_set.php` 작성. 첨부 이미지가 **이미 별도로 import되어 있는 경우에만** WordPress 일반 게시물의 `_thumbnail_id`와 첨부의 `_wp_attachment_image_alt`만 변경한다. PHP는 입력 JSON allowlist, root writer의 사전 SHA 잠금/서명 승인 계약, 전용 비관리자 WordPress 권한/사용자 검사, InnoDB 테이블 확인, post·attachment·meta row lock, content/title/slug/excerpt/status·기존 thumbnail/ALT CAS, 실제 attachment 파일 SHA/MIME/경로 확인, 원자적 metadata transaction·readback/실패 시 rollback을 요구한다. 신뢰 서명 검증은 root Python writer가 책임진다. **미디어 신규 import 기능은 여전히 R3의 미완료 부분**이다.
- PHP 계약 테스트 `test_featured_image_php_contract.py`는 이 파일과 root writer의 인터페이스를 정적 확인한다. 실제 PHP CLI가 없으므로 `php -l` 및 PHP 런타임 실행은 PC에서 해야 한다.
- PC 전용 `scripts/ops/image_r4_pc_fixture.py` + `image_r4_pc_smoke.py`와 `test_featured_image_r4_pc_fixture.py`는 별도 무작위 project, 내부 전용 네트워크, 신규 MariaDB/WordPress named volumes, 합성 이미지 3개, WP-CLI 임시 컨테이너, 합성 DB CAS/ALT/SHA/경합 실험을 준비한다. **실제 R3 root writer가 아닌 합성 fixture의 DB 동작 확인**이다. `docs/featured-image-r4-pc-runbook-2026-10-13.md`를 정본으로 사용한다. 노트북에서는 Compose 파일 생성/정적 검사만 가능하다.
- PC 작업 순서 및 정확한 재개 지시는 `docs/featured-image-pc-handoff-2026-10-13.md`에 별도로 기록했다. 이 문서는 다른 프로젝트나 타 에이전트의 변경을 교란하지 않고 같은 feature 브랜치에서 재개하도록 작성되었다.

### 반드시 남기는 운영 blocker

독립적으로 서명할 **실제 ChatGPT 이미지 생성 호스트 증거 및 사용자/독립 검수 승인 발급자**, 신뢰 private key 격리, 실제 서버 root-owned 승인 request spool과 읽기 전용 PHP mount, 제한 SSH/sudo OS 설치, 안전한 신규 미디어 import writer, WordPress 실DB 정상/부정/경합/응답 소실 시험, 새 실제 대표이미지 3건 시범 수용은 아직 완료하지 않았다. 테스트용 signer/synthetic PNG/모의 WordPress/스케줄러 출력은 이 blocker를 해결하지 않는다. **운영 NO-GO, WordPress 실제 mutation 0, R5 실물 0/3**.
