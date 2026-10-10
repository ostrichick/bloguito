# #889 국민연금 예상수령액 조회 — 발행 전 편집·검수 기록 (2026-10-10)

## 사용자 요청과 공개 상태

사용자가 요구한 다섯 기준: (1) 잠재 독자의 질문·의사결정 정보, (2) 불필요하게 긴 내용 정리, (3) Rank Math SEO 70~80점 이상을 목표로 하는 포맷, (4) 반복 없는 구체적 공식 링크, (5) 큰 한글 핵심 문구가 보이는 적합한 대표이미지. 수정 뒤 **발행 직전에 사용자 최종 검토가 필수**이며, 이번 작업에서는 공개하지 않는다.

원래 WordPress #889는 **draft**, 제목 '국민연금 예상수령액 조회: 출생연도별 수령나이와 확인 방법', SHA256 `7bb7aa678a7294d89bef9b2f4602e44936590e3825441f78ffcc67f3422423fa`, 대표이미지 #890이다. 작업 대상은 기존 검수 인덱스에 등록된 reviewed draft이며, 이전 검수 bundle의 brief ID/entity 및 관련 글 #724를 보존했다.

## 본문·SEO·출처 개선: 적용 완료

- 국민연금공단 공식 페이지 4개를 2026-10-10 새로 수집·해시 봉인한 뒤 **4/4 강제 live 재조회 일치** 확인. 새 NPS 출처에는 수령개시연령·조기/연기연금·10년 최소 가입기간·노령연금 매월 25일 지급 등의 직접 인용을 확보했다. 작성자와 분리된 GPT-6 독립 의미검토에서 source_support/conditions_preserved/question_answered/useful_lifetime/no_reader_deflection/no_unsupported_claims 각 true, issues 없음. 편집 전 버전의 10월 6일 서명을 소급 재사용하지 않고 새 원고 digest에 맞춰 계산. 사본은 무시 파일 `scratch/tasks/post-889-revision-20261010` 및 `scratch/tasks/post-889-audit-20261010`에 존재한다.
- 요약·4개 핵심 H2·두 비교표 중심의 약 **1,959자** 독자 텍스트. 로그인 없는 간단계산/모의계산 vs 인증 가입이력 기반 조회 차이, 생년월일/소득/가입 이력 입력 동선, 1952년생 이전~1969년생 이후 정상 수령나이, 최소 10년 가입 요건, 만 60세 기준 모의계산 가정과 조기·연기 선택의 금액 차이/조건을 명시했다. 수급신청은 별도로 해야 하며 예상액이 미래 확정액이 아니라는 점도 설명했다. 불필요한 FAQ·반복 공식 링크는 배제했다.
- 공식 URL 4개는 최종 저장 HTML에서 **각 1회**. 링크 텍스트: '국민연금공단 예상연금 조회 방법 선택', '로그인 없이 예상연금 모의계산 시작', '국민연금공단 노령연금 수급개시연령과 지급 시점', '국민연금공단 출생연도별 연금수령, 조기수령과 연기연금 안내'. 기존 내부 관련 글 #724('국민연금 조기수령 vs 연기연금 비교')는 별도 1회 보존, 실제 HTTP 200 확인.
- 기존 Rank Math title/focus keyword/description을 검토·SEO 설명문 개선. Focus keyword '국민연금 예상수령액 조회'가 제목/첫 단락/H2/SEO title/description에 존재하며 Rank Math 메타 필드 readback은 검수 bundle과 정확히 일치한다. 2026-10-10 추가 read-only 확인에서 Rank Math 플러그인 **v1.0.280 활성**, #889 `metadata_exists('post',889,'rank_math_seo_score') == false`, 반면 다른 글에는 수치 점수 메타 62개가 존재했다. 따라서 **#889 실제 숫자 점수는 NULL/미관측(0점이라는 뜻 아님)**. 70~80점 이상이라는 성공 보고 금지. 근거: `scratch/tasks/post-889-new-image-20261010/rank-math-readonly-evidence.json`.
- 신규 전역 코드 변경은 기존 reviewed draft에서 brief.existing_post_id가 비어 있던 과거 기록에 **동일 ID를 명시적으로 추가할 때만** 허용하고, 다른 ID/주제 변경은 계속 거절하도록 표적 수정을 했다. 기존 본문에 포함된 #724 관련 이동 링크는 누락을 발견해 복구했다. 정규 `edit-post`에서 원본 본문 SHA CAS/백업/공식 source validation/WordPress 저장·readback 성공. **최종 본문 SHA256 `9ae30527049af7d1e11f7c43d4d5e4d0ee61b6e78a32784a8531e9564a8cb978`**, 상태 draft 유지.
- WordPress 최종 별도 post/meta readback QA **19/19 PASS**. Microsoft Edge headless 로컬 동일 본문 렌더에서 560 CSS px 좁은 화면과 넓은 화면의 제목/표/요약/목차/CTA 가독성을 검사했다. 정보표는 스크롤 힌트 및 키보드 접근 가능한 `role=region`/`tabindex=0` 구조. CTA 대상 #724는 HTTP 200, 외부 공식 4개 URL은 수집기 live 재조회 PASS. `complete-task-qa`에서 `content-mobile-desktop`, `cta-destination`, `layout-accessibility`을 완료해 저장 작업 상태 complete.

## 대표이미지: 새 파일 교체 완료 (2026-10-10 추가 작업)

초기 #890 JPG(1200×675)는 일반적인 노트/그래프/돋보기 그림으로 큰 핵심 한글 문구가 없어 사용자 기준 5번에 미달했다. 먼저 기존 이미지 내용과 맞는 ALT만 개선했으나, 이후 사용자가 **새 작업 세션·worker 등 가능한 경로를 찾아 실제 새 이미지를 제작·교체하도록 재지시**했다.

새 이미지의 배경 원본은 진짜 AI 생성 결과인 **Hugging Face Spaces `black-forest-labs/FLUX.1-schnell`**로, `generated-original-flux.png` SHA256 `061e176d7984e52e1cf04150d778aa74a976509e063ead75c599941338bd6549`를 보존했다. 이 모델이 생성한 아트워크에 사용자의 정확한 한국어 핵심 문구 '**국민연금 예상수령액**'와 부제 '**조회 방법 · 출생연도별 수령나이**'를 Pillow로 별도 조판한 **투명한 후처리 합성물**이다. ChatGPT `image_gen` 원본 또는 Canva 생성물이라고 **가장하지 않는다**. 이번 재개 세션의 네이티브 `image_gen` 시도에서는 **요청 주제와 무관한 건축·도시재생 인포그래픽**이 반환되어 채택하지 않았으며, 해당 결과를 #889 원본으로 취급하지 않았다. 실제 AI가 만든 금융 아트워크에 결정론적 조판을 추가했으며 모바일 480×270에서도 가독성 확인. 1200×675 JPEG SHA256 `cb388c061a7fd55dd27dbe649a9095a94deb8169187d79cc77ae2c6ecccd94e3`, 97,954 bytes. 원본·생성 엔드포인트·파라미터·이벤트·작업 SHA는 `scratch/tasks/post-889-new-image-20261010/generation-hf-provenance.json`, `final-image-qa.json`, `post889-external-image-proof.json`에 있다.

**기본 대표이미지 정책은 ChatGPT `image_gen` 한정으로 유지**한다. 이번 사용자 재지시의 즉시교체 요구를 이행하기 위해 자동화·다른 포스트에 적용되지 않는 **#889 한정 명시적 외부 이미지 예외 검증 경로**를 작업 중 임시로 마련했다. 기존 본문 SHA `9ae305...`, 전 썸네일 #890, 임시글 상태, 외부 원본/파일/한글 검수 SHA를 모두 검사한 뒤 **정규 `replace-featured-image`의 백업·락·WP CAS·media import·readback** 경로로 실행했고, 이를 발행 승인/attestation으로 취급하지 않았다. 교체 완료·서버 재조회·체크포인트 정합성 복구 후 **일회성 검증 코드와 CLI 플래그는 Git 추적 코드에서 다시 제거**하여 프로젝트의 향후 image_gen 제한을 그대로 유지했다. 임시 검증 코드 사본과 테스트는 별도 무시 경로의 `post889-exception-verifier-source.py`, `post889-exception-verifier-tests.py`에 보존했다.

**WordPress 대표이미지 #912 교체 확인:** `https://lifeinfo24.org/wp-content/uploads/2026/10/editorial_cover_889_1f2e655570a64758808c6da232bd369f.jpg`. 서버 내부 실제 첨부 JPG의 SHA256 `cb388c...`는 로컬 최종 파일과 일치. `wp_get_attachment_metadata` 1200×675, `image/jpeg`, ALT '**국민연금 예상수령액 조회 방법과 출생연도별 수령나이 안내 이미지**', WP #889 본문 SHA unchanged, `draft`, `_thumbnail_id=912` 전부 read-only 검증 **8/8 PASS**. 근거: `scratch/tasks/post-889-new-image-20261010/post889-image-readback.json`.

첫 정규 업로드 명령은 WP 저장·readback을 마친 후 이전 native-only `AFTER_IMAGE` 체크포인트가 미완료여서 Python exit 1이 발생했다. **절대 재업로드하지 않고**, WP #912 실제 SHA·ALT·상태를 대조한 뒤 원래 대기 중이던 native 흐름을 사용자의 이번 예외 지시로 대체한 사실(`image_gen_native_used=false`, `cos_core_save_image_used=false`)을 기록하여 checkpoint와 task state를 `complete`로 안전하게 재조정했다. 마지막 `featured_image_followthrough.py status --post-id 889`: `missing_requirements=[]`, `wordpress_verified=true`. 한글 제목 품질 기준은 실제 새 파일로 충족했다.

## 결과와 남은 승인

- WordPress: **#889 draft**, 동일 제목/slug, 본문 SHA `9ae30527049af7d1e11f7c43d4d5e4d0ee61b6e78a32784a8531e9564a8cb978`, **새 썸네일 #912**/새 ALT, source-link 중복 0.
- 기록: `scratch/tasks/post-889-audit-20261010/final-qa.json`, `edit-receipt.json`, `qa-completion.json`, `image-alt-receipt.json`, `independent-semantic-review.md`; WordPress 저장 전 백업은 정규 publisher receipt에 보존.
- 테스트: 이전 shared editorial draft identity guard의 표적 테스트 29+12 PASS. 이번 한시적 #889 외부 출처 예외 검증 테스트 7 PASS, 기존 image 교체 테스트 32 PASS, 후속 체크포인트 테스트 15 PASS, SSH CLI transport 62 PASS. 임시 예외 런타임 모듈을 아직 Git에 등록하지 않았을 때 전체 1,195개 중 릴리스 manifest 검사 10개가 실패해 해당 로그를 별도 보존했다. **예외 코드를 원위치 복원한 후 전체 common Python 최종 1,188 PASS, skipped=1, exit 0** (`scratch/tasks/post-889-audit-20261010/full-regression.log`). 정규 운영 코드에 영구적인 예외는 남기지 않았다.
- **사용자 발행 전 검토 필수**. 대표이미지 크고 정확한 한글 문구는 완료했으나 **Rank Math 실제 숫자 점수는 여전히 확인 불가**. 게시물 자동 발행 승인은 따로 생성하지 않았다. 관리자의 실제 편집기에서 점수가 확인되면 현재 본문/이미지와 같은 revision인지 대조해야 한다. `promote-draft`/발행 실행 없음.
