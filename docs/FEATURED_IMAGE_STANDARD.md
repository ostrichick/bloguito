# Bloguito 대표 이미지 표준

이 문서는 대표 이미지에 적용하는 현행 규약이다. 수동 작업과 스케줄러 모두 새로운 이미지 생성은 ChatGPT `image_gen` 결과만 허용한다. 무인 스케줄러가 해당 도구의 원본을 확보할 수 없으면 생성·발행을 차단한다. 도시별 월간 행사 포스트에는 [EVENT_POST_STANDARD.md](EVENT_POST_STANDARD.md)의 추가 규칙을 적용한다.

## 1. 일반 정보글의 기본 경로

대표 이미지를 **새로 생성**할 때는 작업 형태(수동·자동), 후보 수, 최종 선택 주체와 관계없이 반드시 **ChatGPT 이미지 생성 도구(`image_gen`)**를 사용한다. Gemini 생성기, 로컬 Pillow/SVG/도형 합성, 다른 이미지 생성기, 로컬 클립아트/텍스트 포스터는 생성 대체 경로가 아니다. 예외는 *새로 생성하는 행위가 아닌* 검증된 공식 포스터 원본 보존처럼 별도 정책에 명시된 원본 활용뿐이다.

별도 개수 요청이 없으면 ChatGPT는 글의 주제와 독자 의도를 바탕으로 대표 이미지 **후보 5개를 기본 생성**한다. 사용자가 후보 개수를 1개·3개 등으로 지정한 경우에는 **반드시 해당 개수를 우선**한다. 여러 후보는 단순한 색상·폰트 변형이 아니라 구도, 장면, 시각적 접근 중 적어도 하나가 실질적으로 달라야 한다. 후보 최종 선택은 **사용자 직접 선택 또는 사용자가 위임한 에이전트 선택** 모두 가능하다. 명시적 위임 없이 다중 후보를 임의 선택하지 않는다. 사용자가 1개 제작과 바로 업로드를 요청한 경우에는 그 1개가 선택된 것으로 처리할 수 있다.

후보 생성 단계에서는 특정 템플릿을 강제하지 않는다. 기존의 왼쪽 텍스트/오른쪽 장면 비율, 텍스트 위치, 텍스트 블록 수, 고정 줄바꿈, 지정 서체, 색상 수, 장면 영역 비율 같은 레이아웃 제약을 일반 정보글의 ChatGPT 후보에 적용하지 않는다. ChatGPT가 주제에 맞는 구도, 이미지 스타일, 텍스트 사용 여부와 위치를 자율적으로 결정한다.

## 2. 선택 전후의 규칙

### P0: 생성 작업별 정책/권한 기록

새 이미지 작업은 `agent-publisher/editorial_policy.json`의 `featured_image_policy` 버전과 SHA-256 digest를 실행 시 읽어 하나의 생성 정책으로 결합한다. `agents.image_generation_policy.new_image_generation_task()`는 매 작업에 새 `task_id`, 대상 `post_id` 또는 `brief_id`, 후보 수(일반 기본 5개, 해당 작업에서 지정하면 그 수), 선택 주체/명시 위임 상태, `image_pending=true`를 만든다. 과거 작업의 사용자 예외, Pillow 스크립트 주석이나 이전 채팅의 허용 기록은 새 작업의 생성 권한이 아니다. 해당 작업의 새로운 예외 지시가 있을 때만 **그 task_id·대상·승인 시각·만료 시각·승인 참조 해시**를 검증해 범위를 기록하며, 이 자체가 로컬 생성이나 `image_gen` 호출 사실의 증거가 되지 않는다. 정규 업로드에서 허용하는 생성 공급자는 계속 `image_gen`이다.

`AFTER_IMAGE`에는 `image_task_id`, `generator_policy_version`, `generator_policy_sha256`, `image_task`를 기록한다. 후속 단계는 `validate_current_image_task(post_id)`로 정책 버전/digest 및 작업 식별·예외 만료를 확인한다. 호스트 도구 호출 여부는 **실제 호출 결과와 기록된 신고**를 구분해야 한다. CoS 함수 목록에 `image_gen`이 없다는 관찰만 있으면 `awaiting_image_gen`이고, 현재 턴 ChatGPT 호스트 접근 불가 결과가 직접 관찰됐다고 신고하거나 무인 서버인 경우 `held_image_generation_unavailable`로 보류한다. CLI의 `evidence_level=caller_report_only`는 호스트 호출 증명이 아니다. 보류된 작업은 `image_pending=true`이며 이미지 저장·readback 완료를 주장하지 않는다. 이미지 없이 콘텐츠 초안을 저장해야 하면 별도 `prepare-draft`의 이미지 없는 경로를 사용한다.

- **실제로 생성한 후보 N개 전부**를 생성 직후 CoS Core `save_image`로 각 원본을 로컬 `candidate-1`~`candidate-N` 안정 경로에 저장한다. 저장 도구는 반드시 현재 대화에서 ChatGPT가 생성한 **원본**만 저장해야 한다. 실패하면 브라우저 스크롤·nth 재시도·Base64 변환·별도 bridge·로컬 재그리기로 우회하지 않고 해당 후보를 차단하여 원인을 보고한다. 이어 `seal_featured_image_candidates.py`로 후보 번호·경로·SHA-256·format/dimensions를 manifest에 고정한다. 원본 저장·decode·seal 실패 후보는 선택지로 제시하지 않는다.
- 로컬에 고정한 N개 후보는 사용자가 비교·선택하려는 경우 모두 보여준다. 사용자가 에이전트에 선택을 위임한 경우에는 직접 품질을 비교해 선정 이유를 남기며, 사용자가 비교 화면을 요구하지 않았다면 별도의 선택 응답을 기다릴 필요가 없다.
- 선택 주체는 `user` 또는 `agent-delegated` 중 하나로 명시한다. `agent-delegated`는 사용자의 명시적 선택 위임·1개 즉시 업로드 지시에만 사용한다. 위임이 없으면 사용자 선택을 받아야 한다.
- 선택이 확정되기 전에는 어느 후보도 WordPress 대표 이미지로 지정하지 않는다. 선택한 candidate 번호를 해당 파일/SHA에 결합하며, 선택 이후에는 브라우저 히스토리에서 다시 이미지를 찾아 저장하지 않는다. 브라우저 캐시·스크린샷·클립보드·Base64 재조립·별도 대화 파일 bridge는 일반 후보 이미지 전달 경로에 사용하지 않는다.
- 선택된 원본 후보를 그대로 후속 업로드의 source로 사용하며 후보 번호를 바꾸거나 다른 후보로 대체하지 않는다. WordPress 규격에 맞추기 위한 결정론적 1200×675 staging은 허용하되 비율이 다른 경우 피사체를 잘라내지 않고 전체 전경을 보존한다.
- 생성 대표이미지의 staging 기본 출력은 WebP다. `stage_featured_image.py --candidate-manifest <manifest> --selected-candidate N --selection-mode user|agent-delegated <candidate-file>`에서 manifest와 선택 주체/번호는 필수이며 선택 source의 sealed path/SHA와 정확히 같아야 한다. 글자 품질 등 이유로 무손실이 필요한 특수 경우에만 PNG를 명시적으로 선택한다. 로컬 staging은 전경을 유지한 크기·형식 변환만 허용하며 장면 재제작·그리기는 금지한다.
- 선택 후에는 정규 `replace-featured-image` 또는 신규 draft의 `--image-path` 경로로 업로드하고 thumbnail readback을 확인한다.
- 이미지 생성 호출 때문에 작업 turn이 끊기는 환경에서는 `AFTER_IMAGE` 체크포인트를 남겨 다음 turn에서 후보 선택·업로드 작업을 이어간다.

### 사용자가 ChatGPT 이미지 공유 링크로 기존 원본을 지정한 경우

사용자가 **직접** `https://chatgpt.com/s/m_...` 링크를 제공하고 그 안의 이미지를 선택한 경우, 동일 채팅의 CoS `save_image` 호출을 과거에 수행했다고 거짓으로 기록하지 않는다. 공유 페이지의 실제 HTML에 포함된 `chatgpt.com/backend-api/estuary/public_content/enc/...` 공식 원본 다운로드 URL을 통해 ChatGPT `image_gen` 원본 PNG를 받을 수 있을 때만 허용한다. 캐시 썸네일/OG 미리보기/스크린샷은 원본 대신 사용하지 않는다.

공유 페이지 원본·원본 이미지의 SHA256, 원본 토큰에 명시된 정확한 공유 메시지 ID와 이미지 file ID, 원본 사이즈를 `user_shared_image` provenance로 봉인한다. `origin_claim.save_tool=chatgpt_user_shared_original_url`로 명시하며 `cos_core.save_image` 호출로 포장하지 않는다. 사용자가 지정한 후보만 `selection_mode=user`로 검증하고 동일 stage/manifest/CAS/readback 정규 업로드를 거친다. 타 도메인·다른 파일 ID·변경된 HTML·불일치 SHA·agent-delegated 선택은 모두 차단한다. 이 경로는 **이미 생성된 사용자 지정 ChatGPT 원본의 전달**만 허용하며 로컬/타사 이미지 생성 예외가 아니다.

### ChatGPT + CoS 즉시 업로드 경로 (기존 포스트, 1개 후보 즉시 업로드)

1. 먼저 CoS Core 연결을 실제 호출로 확인한다. 에이전트에게 **한 후보 즉시 선택을 명시적으로 위임한 경우** `python scripts/featured_image_followthrough.py begin --post-id 856 --selection-mode agent-delegated --explicit-delegation`을 사용한다. 사용자 선택이면 `--selection-mode user`로 시작한다. WordPress 기준 상태·새 `image_task_id`·정책 digest가 `AFTER_IMAGE`에 기록된다. `probe`는 접속 장애 진단에만 사용한다. 기존 active/held 체크포인트는 `status`부터 확인한다.
2. ChatGPT 네이티브 `image_gen`에서 해당 포스트 주제에 맞는 후보를 생성한다. 한글 이미지라면 글자가 정확히 보이는지 확인한다. 생성에 성공하면 **같은 채팅의 CoS Core `save_image`로 원본을 로컬 `scratch/tasks/<작업명>/candidate-1.png`에 저장**한다. 이미지 생성 직후 턴이 종료된 경우 이 작업을 재개할 수 있도록 사전 체크포인트를 유지한다.
3. 먼저 `seal_featured_image_candidates.py`로 원본을 SHA 봉인하고 `stage_featured_image.py`로 선택 번호/주체를 결속해 WebP를 만든다. `review_featured_image_candidates.py prepare --manifest <manifest> --preview-dir <검수축소본폴더> --output <검수template.json>`을 실행한다. 검토자가 **모든 후보 원본과 모바일 축소본**을 실제로 열어 템플릿의 여섯 품질 항목 및 표시된 레이아웃 유사 쌍의 판단·근거를 채운 뒤 `review_featured_image_candidates.py finalize --template <검수template.json> --staged <staged.webp> --selected-candidate 1 --selection-mode agent-delegated --task-id <begin의 image_task_id> --review-actor agent-delegated --review-method direct_agent_visual --selection-reason "검토한 장면과 타 후보 대비 선택 근거" --output <검수receipt.json>`으로 검수 결과를 만든다. 합격인 경우에만 `python scripts/featured_image_followthrough.py continue --post-id 856 --source <저장원본> --selected-candidate 1 --selection-mode agent-delegated --visual-review-receipt <검수receipt.json> --alt-text "해당 이미지 설명" --resume`를 사용한다. **사전 staging이 있으므로 `--resume`이 필수**다. 정규 명령은 작업 선택 권한·품질 증거·원본 SHA와 CAS·readback을 검사하며 모호한 import를 재시도하지 않는다.
4. `continue` 성공 응답의 `verification.missing_requirements=[]`, `verification.wordpress_verified=true`를 확인하면 완료로 보고한다. 응답 유실·모호한 결과 등에서는 `python scripts/featured_image_followthrough.py status --post-id 856`를 통해 읽기 전용 상태 확인을 수행하며 무작정 재업로드하지 않는다.

이 단일 명령 경로는 **한 개 후보를 바로 업로드하도록 선택이 위임된 경우**만 지원한다. 기본 5개/다중 후보를 비교·선택하는 요청에는 기존 후보 전체 봉인 및 사용자 선택 경로를 사용한다. CoS의 함수 목록에서 `image_gen`이 검색되지 않아도 ChatGPT의 네이티브 이미지 생성 기능 전체가 불가능하다는 의미는 아니다(#889에서 같은 채팅의 생성 성공). 실제 네이티브 호출 결과를 기준으로 판단한다. CLI는 ChatGPT `image_gen`을 실행하거나 비활성화된 호스트 도구를 강제로 활성화하지 못하며, 이미지 생성 호출이 턴을 종료시키는 플랫폼 동작도 바꿀 수 없다. 체크포인트는 **중단 후 이어하기 기록**이지 호스트의 자동 재호출을 보장하지 않는다.

**업로드 전 품질 계약:** `visual-review-receipt`에는 작업 ID, 현재 정책 버전·해시, 봉인 원본 및 staging SHA, 후보 번호·선택 주체, 전체 후보 실제 관찰 결과, 최근 이미지 비교 결과와 선택 이유가 필요하다. 검수 템플릿은 모두 `UNVERIFIED`로 시작하고 유사도 점수만으로 자동 PASS를 만들지 않는다. 수동 `prepare-draft --image-path`에는 현재 brief ID에 연결된 `--image-task-record`, `--image-task-id`, `--visual-review-receipt`가 추가로 필요하며, 기존 글 수정/교체는 `AFTER_IMAGE`의 task 기록 또는 정확히 그 글에 연결된 새 task 기록을 검증한다. JSON의 검수 진술은 관찰의 기록이지 실제 호스트 호출이나 독립적인 사람의 시각 관찰을 암호학적으로 인증하는 수단은 아니다.

**R0 임시 fail-closed 운영 제한(2026-10-12):** `--image-task-record`는 호출자가 직접 만들 수 있어 이미지 업로드의 독립적인 승인 원천이 아니다. 별도 신뢰 가능한 작업 등록 기능(R1/R2)이 마련되기 전까지 `prepare-draft --image-path`의 즉시 이미지 업로드는 **거부**하고, 신규 글은 이미지 없이 임시글로 저장한 후 별도 승인된 이미지 작업으로 이어간다. 기존 글 변경 시에도 현재 `AFTER_IMAGE`가 `in_progress`이고 import 미시작·작업/선택/검수 증빙이 일치해야 한다. `held`, `complete`, 취소 상태 및 과거 검수 승인, 기본 5개 후보 중 1개만 제출한 기록을 거부한다. 작업 파일/검수 JSON은 여전히 생성 호스트·사람의 실제 관찰을 인증하지 못하므로 **R1~R3가 끝날 때까지 자동 업로드를 재발 방지 완료로 보고하지 않는다**.

**R1/R2 검증기와 적용 전제(2026-10-12):** 정규 이미지 업로드 사전검사는 서명된 두 사건을 추가 요구한다. 후보 manifest 옆의 `<manifest>.host-proof.json`에는 신뢰할 수 있는 ChatGPT 호스트 증거 발급자가 확인한 **전체 후보 원본 SHA·작업 ID·정책 SHA**가, 검수 receipt 옆의 `<receipt>.review-proof.json`에는 별도의 실제 검수·선택 승인자가 확인한 **receipt·manifest SHA·선택 후보·작업 ID**가 결합되어야 한다. 서명은 각각 `/etc/bloguito/image-trust/host.pub.pem`, `review.pub.pem`의 별도 Ed25519 신뢰 앵커로 검사한다. 두 공개키는 운영 측이 독립적으로 provision해야 하며 private signing key는 AI 실행 자격에 노출하면 안 된다. **이 저장소에는 발급용 도구/비밀키/신뢰할 수 있는 호스트 증명 공급자가 포함되지 않는다.** 단순 `origin_claim`, 검수 JSON 또는 테스트용 임시 서명을 운영 인증으로 간주하지 않는다. 발급 채널·검증 가능한 운영 서버 writer·격리 DB 테스트 전까지 자동 업로드는 `held_provenance_unverifiable`로 보류하고, 운영 판정은 `NO-GO`다. 정상 관리자 WordPress UI의 직접 발행 기능은 이 자동화 제약의 대상이 아니다.

**Windows 신뢰경계:** 현재 CoS 노트북(Windows)은 Linux root 소유권·쓰기 권한 검사를 수행할 수 없으므로 자동 업로드 검증기를 항상 `held_provenance_unverifiable:protected_server_verifier_required`로 보류한다. `/etc/bloguito`와 비슷한 Windows 로컬 경로에 공개키를 복사해도 허용하지 않는다. 서명 인증은 별도 보호된 Linux 서버 측 writer가 최종 판단해야 하며, 해당 실제 writer 설치는 아직 완료되지 않았다.

**기존 이미지의 별도 승인 경계:** `replace-featured-image --attest-existing`은 파일/ALT/본문이 그대로라는 무결성 확인만으로 별도의 육안 검수 승인을 발급할 수 없으므로 자동 발행 attestation 경로를 보류한다(`existing_image_independent_visual_approval_required`). 등록되지 않은 `visual_reviewed=True` 자체 신고나 모델이 만든 SHA digest는 사용자·독립 검수자가 이미지를 실제 승인했다는 증거가 아니다. 독립 승인 발급자가 마련되기 전까지 기존 표지의 자동 승인 완료를 주장하지 않는다. 관리자 WordPress UI의 본래 수동 발행 권한은 영향을 받지 않는다.

## 3. 품질 기준

자유로운 구성을 허용하되 대표 이미지로서 다음 기준은 유지한다.

- 글의 핵심 주제와 이미지가 직접 관련되어야 한다.
- 모바일 썸네일과 데스크톱에서 핵심 피사체나 메시지를 알아볼 수 있어야 한다.
- 사람의 얼굴·손·신체, 문서, 제품 등 핵심 요소에 명백한 생성 오류가 없어야 한다.
- 이미지에 글자가 있다면 읽을 수 있고 내용이 정확해야 한다.
- 오래된 웹 배너, 저품질 클립아트, 깨진 글자처럼 명백히 품질이 낮은 결과는 후보에서 제외하고 다시 생성한다.

## 4. 스케줄러 자동 발행 예외

**스케줄러에서도 새 대표이미지에 Gemini나 로컬 이미지를 생성해 사용하지 않는다.** 스케줄러는 ChatGPT 이미지 생성 도구의 실제 출력과 sealed candidate/staging receipt를 제공받을 수 없는 경우, 새 커버를 만들어 발행하는 작업을 **실패 차단**해야 한다. 자동 게시 성공을 위해 생성 제공자를 바꾸거나 로컬 이미지를 대체하는 것은 금지한다.

스케줄러의 비전 검수는 실제 ChatGPT 원본을 검사하는 용도에만 사용할 수 있다. 검수가 생성 원본을 대체하거나 새 장면을 합성할 권한을 주지는 않는다.

## 5. 공개 전 이미지 승인 결속

이미지 업로드 성공이나 1200×675 규격 통과만으로 공개 자격을 만들지 않는다. 수동 경로는 사용자 후보 선택, 스케줄러 경로는 자동 비전 검수 통과가 있어야 versioned publication attestation을 만들 수 있다. 이 attestation은 현재 reviewed 본문 SHA, 제목 SHA, 대표 attachment ID, 이미지 파일 SHA, ALT SHA, review digest, source/review freshness와 `requires_live_state` 여부에 결합한다. attestation 생성 시 current policy의 review binding과 source declaration/freshness 검사를 다시 통과해야 한다.

본문·제목·대표이미지·ALT·원본 파일 중 하나라도 승인 뒤 바뀌거나 검토 시간이 만료되면 공개 게이트는 실패한다. 성공적으로 공개되면 attestation은 소비되어 삭제하므로 공개 글을 다시 draft로 되돌린 경우 과거 승인을 재사용하지 않는다. 과거 draft에는 승인 기록을 임의로 backfill하지 않는다.

로그인한 WordPress 관리자의 직접 발행 권한은 본래대로 유지한다. Python 자동 발행은 `promote-draft --confirm-publish`과 attestation을 요구한다. `requires_live_state=true`인 글은 현재 판매·신청·예매·재고 상태를 정규 경로에서 재조회하고 reviewed snapshot과 비교해야 한다.

## 6. 행사 포스트

도시별 월간 행사 포스트와 공연·콘서트의 공식 포스터 처리에는 별도 현행 규칙이 있을 수 있다. 해당 글에는 `EVENT_POST_STANDARD.md`와 공식 포스터 보존 규칙을 우선 적용한다.
