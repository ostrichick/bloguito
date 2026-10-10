# #889 국민연금 예상수령액 조회 — 발행 전 편집·검수 기록 (2026-10-10)

## 사용자 요청과 공개 상태

사용자가 요구한 다섯 기준: (1) 잠재 독자의 질문·의사결정 정보, (2) 불필요하게 긴 내용 정리, (3) Rank Math SEO 70~80점 이상을 목표로 하는 포맷, (4) 반복 없는 구체적 공식 링크, (5) 큰 한글 핵심 문구가 보이는 적합한 대표이미지. 수정 뒤 **발행 직전에 사용자 최종 검토가 필수**이며, 이번 작업에서는 공개하지 않는다.

원래 WordPress #889는 **draft**, 제목 '국민연금 예상수령액 조회: 출생연도별 수령나이와 확인 방법', SHA256 `7bb7aa678a7294d89bef9b2f4602e44936590e3825441f78ffcc67f3422423fa`, 대표이미지 #890이다. 작업 대상은 기존 검수 인덱스에 등록된 reviewed draft이며, 이전 검수 bundle의 brief ID/entity 및 관련 글 #724를 보존했다.

## 본문·SEO·출처 개선: 적용 완료

- 국민연금공단 공식 페이지 4개를 2026-10-10 새로 수집·해시 봉인한 뒤 **4/4 강제 live 재조회 일치** 확인. 새 NPS 출처에는 수령개시연령·조기/연기연금·10년 최소 가입기간·노령연금 매월 25일 지급 등의 직접 인용을 확보했다. 작성자와 분리된 GPT-6 독립 의미검토에서 source_support/conditions_preserved/question_answered/useful_lifetime/no_reader_deflection/no_unsupported_claims 각 true, issues 없음. 편집 전 버전의 10월 6일 서명을 소급 재사용하지 않고 새 원고 digest에 맞춰 계산. 사본은 무시 파일 `scratch/tasks/post-889-revision-20261010` 및 `scratch/tasks/post-889-audit-20261010`에 존재한다.
- 요약·4개 핵심 H2·두 비교표 중심의 약 **1,959자** 독자 텍스트. 로그인 없는 간단계산/모의계산 vs 인증 가입이력 기반 조회 차이, 생년월일/소득/가입 이력 입력 동선, 1952년생 이전~1969년생 이후 정상 수령나이, 최소 10년 가입 요건, 만 60세 기준 모의계산 가정과 조기·연기 선택의 금액 차이/조건을 명시했다. 수급신청은 별도로 해야 하며 예상액이 미래 확정액이 아니라는 점도 설명했다. 불필요한 FAQ·반복 공식 링크는 배제했다.
- 공식 URL 4개는 최종 저장 HTML에서 **각 1회**. 링크 텍스트: '국민연금공단 예상연금 조회 방법 선택', '로그인 없이 예상연금 모의계산 시작', '국민연금공단 노령연금 수급개시연령과 지급 시점', '국민연금공단 출생연도별 연금수령, 조기수령과 연기연금 안내'. 기존 내부 관련 글 #724('국민연금 조기수령 vs 연기연금 비교')는 별도 1회 보존, 실제 HTTP 200 확인.
- 기존 Rank Math title/focus keyword/description을 검토·SEO 설명문 개선. Focus keyword '국민연금 예상수령액 조회'가 제목/첫 단락/H2/SEO title/description에 존재하며 Rank Math 메타 필드 readback은 검수 bundle과 정확히 일치한다. **현재 WordPress `rank_math_seo_score` 필드는 없음. 실제 70~80점 이상 획득은 실측 불가**이며, 임의 수치나 가짜 성공 보고 금지.
- 신규 전역 코드 변경은 기존 reviewed draft에서 brief.existing_post_id가 비어 있던 과거 기록에 **동일 ID를 명시적으로 추가할 때만** 허용하고, 다른 ID/주제 변경은 계속 거절하도록 표적 수정을 했다. 기존 본문에 포함된 #724 관련 이동 링크는 누락을 발견해 복구했다. 정규 `edit-post`에서 원본 본문 SHA CAS/백업/공식 source validation/WordPress 저장·readback 성공. **최종 본문 SHA256 `9ae30527049af7d1e11f7c43d4d5e4d0ee61b6e78a32784a8531e9564a8cb978`**, 상태 draft 유지.
- WordPress 최종 별도 post/meta readback QA **19/19 PASS**. Microsoft Edge headless 로컬 동일 본문 렌더에서 560 CSS px 좁은 화면과 넓은 화면의 제목/표/요약/목차/CTA 가독성을 검사했다. 정보표는 스크롤 힌트 및 키보드 접근 가능한 `role=region`/`tabindex=0` 구조. CTA 대상 #724는 HTTP 200, 외부 공식 4개 URL은 수집기 live 재조회 PASS. `complete-task-qa`에서 `content-mobile-desktop`, `cta-destination`, `layout-accessibility`을 완료해 저장 작업 상태 complete.

## 대표이미지: 품질 미완료, ALT만 개선

기존 대표이미지 #890 JPG는 1200×675이지만 추상적인 노트/그래프/돋보기 그림으로 **큰 한글 제목이나 '국민연금 예상수령액·수령나이' 메시지가 전혀 없음**. 이미지 품질 다섯 번째 조건 불합격. 새 ChatGPT image_gen 원본이 현재 이 세션에 제공되지 않으므로 프로젝트가 금지하는 Pillow/SVG/타사 이미지 생성으로 대체하지 않았고, **새 이미지 업로드는 수행하지 않았다**.

정규 `replace-featured-image --alt-only`에서 기존 #890 이미지 내용에 맞는 ALT '국민연금 예상수령액 조회를 상징하는 계산 그래프와 돋보기 일러스트'만 변경, WP readback 통과, 본문 SHA·상태·이미지 ID 보존. ALT 수정은 새 핵심 문구가 보이는 대표이미지로 바꾼 것과 다르다. 사용자 검토 시 새 이미지의 품질 충족이 **발행 전 남은 주요 과제**다.

## 결과와 남은 승인

- WordPress: **#889 draft**, 동일 제목/slug, 새 본문 SHA `9ae30527049af7d1e11f7c43d4d5e4d0ee61b6e78a32784a8531e9564a8cb978`, 기존 썸네일 #890/개선 ALT, source-link 중복 0.
- 기록: `scratch/tasks/post-889-audit-20261010/final-qa.json`, `edit-receipt.json`, `qa-completion.json`, `image-alt-receipt.json`, `independent-semantic-review.md`; WordPress 저장 전 백업은 정규 publisher receipt에 보존.
- 테스트: 바뀐 shared editorial draft identity guard의 표적 테스트 29+12 PASS, 전체 common Python **1,188 PASS**. 전체 suite stderr를 별도 로그에 보존.
- **사용자 발행 전 검토 필수**. 현재 Rank Math 실측 점수와 새 큰 글씨 대표이미지 두 가지는 완료했다고 주장하지 않는다. 사용자 직접 WordPress 편집기에서 점수를 확인할 수 있고, 새 ChatGPT 원본이 확보되면 정규 `replace-featured-image`로 바꾸고 thumbnail/readback 검증을 추가한다. `promote-draft`/발행은 실행하지 않았다.
