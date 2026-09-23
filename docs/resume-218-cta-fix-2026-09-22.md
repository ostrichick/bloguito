# 공개 게시물 #218 CTA 보완 후보 및 독립 재검토 — 2026-09-22

**결과(16:11 KST): 검토본 `ready`, 원본 저장 SHA·출처 4개 해시·전체 WordPress 인벤토리 일치. 운영 WordPress 수정은 이 담당 작업에서 수행하지 않았다.** 본문의 CTA가 빠졌다는 별도 라이브 브라우저 QA 결과를 받아, 기존 공식 출처 s1의 실제 조회 진입 경로를 확인하고 같은 정규 렌더러로 보완 후보를 만들었다.

## 검증한 행동 경로 및 표현 범위

- 공식 생명보험협회 출처 s1: `https://cont.insure.or.kr/cont_web/information/information.do`. 읽기 전용 HTTP 요청에서 **200**, 안내 본문에 `인터넷을 통한 신청`, `조회신청`, `365일, 24시간`이 있고 실제 화면의 `조회신청` 링크는 `http://cont.insure.or.kr`로 연결된다. 해당 HTTP 주소는 HTTPS 루트로 **302** 전환된다. HTTPS 루트는 200이지만 비브라우저 응답에 조회 양식이 드러나지 않아 로그인·본인인증 후 동작은 검증하지 못했다. 별도 담당자의 공개 브라우저 확인 역시 s1의 조회신청 버튼 존재를 확인했다.
- 정규 정책상 근거 URL은 자동으로 CTA가 되지 않는다. 이번 s1은 **실제 조회신청 버튼이 들어 있는 안내·진입 화면**으로 확인했으므로 출처 s1에만 `actions:[{"kind":"lookup","label":"내보험찾아줌 조회신청 안내·진입","url":"https://cont.insure.or.kr/cont_web/information/information.do"}]`를 넣었다. 안내 페이지 자체를 바로 인증 양식이나 단일 클릭 조회 완료 화면이라고 부르지 않도록 레이블을 제한했다. 화면에 노출되지 않은 SPA 내부 URL을 추정하거나 새 공식 URL을 만들지 않았다.
- 사전 검토 원본은 `tmp/legacy_audit_20260922/full-finance/post-218/bundle.json`이며, 네 출처의 `text`와 `sha256`은 재수집 전후 완전히 일치했다. 출처 s1 SHA: `540d9ef421f4cc35c2021c9602d77f37279c24946dbd1628b2f2a08365b6e41a`. 나머지 세 SHA는 각각 `e43860d1b3e16793deb5d7d7ea8ac3773c07b2269680e62a55f836612ebafed4`, `6efa67227241938f41f780e3bcea4c45c168eb8d69adc5eeaa950c95d5097213`, `54a3ab3d1204a1b025804264a9b61e0e10c1545032569231d5b7bf2623ea2e56`.

## 검토 후 확정한 후보

최초 **CTA만** 추가한 `cta-remediation-20260922-160539/`는 사전 규칙 `ready`였지만 독립 AI 검토에서 `semantic_review_failed`가 발생했다. 원고에 이미 공개돼 있는 계약자·수익자의 조회 주체가 누락됐고, 금융위원회 FAQ의 2025년 6월 생명보험 표준약관 이자 예시를 단순히 상품 약관 확인으로 넘긴다는 지적이었다. 처음부터 성공한 검토라고 기록하지 않는다.

보강 완료본은 다음 경로에 있다. 원고의 **기존 문장·제목·질문·FAQ·브리프·날짜 조건을 삭제하거나 변경하지 않았고**, s1에서 계약자·수익자의 미청구보험금 조회 가능 범위, s2에서 본인인증 후 간편청구와 **‘25년 6월 표준약관 예시**를 원문 연속 인용으로 추가했다. 중도보험금은 지급사유 다음 날부터 만기일까지 평균공시이율, 만기 후 첫 1년 50%·이후 2년 40%; 만기보험금은 만기 후 첫 1년 50%·이후 2년 40%라는 **표준약관 예시**와 실제 상품 약관 우선 조건을 함께 명시했다. 다른 혜택·자격·지급액을 창작하지 않았다.

- 최종 검토 번들: `tmp/legacy_audit_20260922/full-finance/post-218/cta-remediation-20260922-160906-v2/bundle.reviewed.json`
- 정규 검토 보고서와 HTML: 같은 폴더 `review-report.json`, `bundle.reviewed.html`; 독립 미검토 HTML은 `preview.UNREVIEWED.html`로 구별한다.
- 독립 모델 검토 `2026-09-22T16:10:10.808034+09:00`: `source_support`, `conditions_preserved`, `question_answered`, `useful_lifetime`, `no_reader_deflection`, `no_unsupported_claims` **6개 모두 true**, `issues=[]`. 정규 `editorial_cli.py review`와 이어진 `check --inventory .../public-inventory-excluding-self.json` 모두 `ready`, 오류 이유 없음, 종료 코드 0. 검토 전 점검 역시 `ready`였다. 사용된 인벤토리 파일에는 #218을 제외한 같은 날짜 공개 글 29편이 있고, 최종 사전검사에서는 별도로 운영의 전 상태 목록을 읽었다.
- 기존 공개 콘텐츠 SHA256 `ba0db058e53d2ccc893968859561ca4203b9c109fbe8aff7a02949cfa9ed2f82` → 제안 HTML SHA256 `1e234fd11d256672af1e39f74b5a6b3e967eb81cc31191ca8c72092d0879030e`. 새 HTML에는 `.bloguito-cta` **정확히 1개**이며 공식 s1 링크와 제한적 레이블이 존재한다.

## 최신 운영 원본 대조 및 적용 경계

`scripts/prepare_post_approval.py --post-id 218`을 사용해 **읽기 전용**으로 다시 작성한 승인 패키지: `tmp/legacy_audit_20260922/full-finance/post-218/cta-remediation-20260922-160906-v2/approval-fresh-20260922-161049/`.

- `approval-manifest.json` 캡처 16:11:05 KST: `preflight_status=ready`, `reasons=[]`, `source_hashes_match_live=true`, 원문 저장 SHA와 제안 HTML SHA가 위 값과 정확히 일치한다.
- 전체 운영 게시물 목록: ID 중복 없이 **40개**(공개 30, 임시 10); #218은 정확히 한 건의 `publish`. 당시 제목 `내보험 찾아줌 숨은 보험금 조회·청구 방법과 지급 조건`, 원 게시일 `2026-09-20 08:32:43`, 최근 수정 `2026-09-22 15:57:12`. 원본 저장 `post_content`는 바로 이전 `bundle.json` 렌더 HTML과 **문자열까지 완전 일치**하며 CTA는 0개였다.
- 비공개 전체 원본 백업은 패키지 내부 `post-original.PRIVATE.json`이고 파일 SHA256 `c611c0bb9d1e380829e5801198007711be57055c6f4b796fafd9e9ea9ef7b24c`를 실제 바이트 재검산해 일치했다. 사전 승인 HTML `proposed-reviewed.html`은 현재 최종 원고를 새로 렌더한 결과와 **문자열까지 완전 일치**한다. 텍스트 변경은 `content-diff.txt` 27줄과 `compare-preview.html`에서 검토할 수 있다. 백업 JSON은 Git·공개 배포 대상이 아니다.
- 현재 `post_excerpt`는 163자로 비어 있지 않으며 기존 본문의 자동 생성 요약과 정확히 일치한다. 정상 업데이트를 실행할 경우 검토한 새 lead에 근거한 발췌문으로 갱신되는 것이 현행 `editorial_updater.py`의 조건상 예상 동작이다. 제목·슬러그·상태·카테고리·대표 이미지·원 게시일은 변경 대상이 아니다.

운영 적용 담당자는 실행 직전에 원본 저장 SHA·전체 인벤토리·출처 SHA·검토 유효성을 다시 확인하고 승인 범위 안에서 정규 `scripts/update_existing_via_ssh.py` 경로를 사용해야 한다. 이 후보의 기대 원본 저장 SHA는 **`ba0db058e53d2ccc893968859561ca4203b9c109fbe8aff7a02949cfa9ed2f82`**다. 원본이 바뀌면 이 해시를 임의 교체해 덮어쓰지 말고 차이를 재검토한다. 적용 후에는 실제 공개 브라우저에서 CTA·목차·내용·발췌문·모바일 화면과 링크 동작을 검사한다. 해당 배포 후 QA, 실제 로그인 조회, 복구 리허설은 **이 작업에서 미수행**이며, WordPress 쓰기·Git 커밋·푸시도 실행하지 않았다.

## 긴급 정정: 운영 브라우저 404로 위 CTA 후보 폐기, v3 복구 — 16:19~16:26 KST

**이전 섹션의 `cta-remediation-20260922-160906-v2/`는 더 이상 적용할 후보가 아니다.** 별도 담당자의 실제 Edge 검증에서 `https://cont.insure.or.kr/cont_web/information/information.do`가 해당 브라우저에서 `/cont_web/common/404.jsp` 오류로 이동했다. 추정 대체 경로인 사이트 루트 `/cont_web/`와 `intro.do`도 별도 브라우저 점검에서 404로 관측됐다. HTTP 직접 읽기의 200과 HTML의 조회신청 버튼 존재만으로 독자의 실제 브라우저 도착을 증명할 수 없다는 반례다. 작동이 확인되지 않은 새 URL을 임의로 CTA로 제공하지 않는다.

이미 반영된 v2의 실제 WP 저장 `post_content` SHA256 **`1e234fd11d256672af1e39f74b5a6b3e967eb81cc31191ca8c72092d0879030e`**를 다시 읽어 v2 렌더 HTML과 문자열까지 일치함을 확인했다. `cta-remediation-20260922-161800219170-v3-fallback/`에 **깨진 공식 s1 행동 링크만 제거**한 세 번째 원고를 새로 생성했다. 계약자·수익자 조회 가능 범위, 생명보험 표준약관의 기간별 50%·40% 이자 예시와 다른 보강된 본문·인용·공식 출처 네 건의 원문·SHA는 v2 그대로 유지했다. 독립 모델 재검토(16:19:13 KST)에서 6개 항목 모두 참·`issues=[]`, 정규 CLI `review/check`는 `ready`, 라이브 전체 상태 인벤토리·저장 본문·출처 재조회 검사 역시 `ready`, 이유 `[]`, 원문 해시와 기존 게시글 제목·공개 상태 일치였다.

- **유일한 최종 v3 원고:** `tmp/legacy_audit_20260922/full-finance/post-218/cta-remediation-20260922-161800219170-v3-fallback/bundle.reviewed.json`
- **읽기 전용 최신 승인 패키지:** 같은 폴더의 `approval-fresh-20260922-1619/approval-manifest.json`, 원문 백업·텍스트 diff·비교 미리보기.
- **v3 HTML SHA256:** `ab8afcf46da6fab8810ded080f939fe76f2ad20733a842af36cc0a3b26407c95`; `.bloguito-cta` **0개**. 이 대체는 실제 조회 링크의 브라우저 정상 작동이 증명되기 전까지 깨진 버튼이 보이지 않도록 하는 긴급 복구다. 검증한 원고의 사실 보강은 유지했다.

이 담당자는 WordPress에 쓰지 않았다. 별도 적용 후 **16:26 KST 읽기 전용 WordPress 재조회**에서 게시물 #218 저장 본문 SHA가 v3 제안 SHA `ab8afcf4…`와 정확히 일치하고 공개 상태·CTA 0개·최근 수정시각 `2026-09-22 16:20:23`인 것을 관측했다. 이 값은 운영 저장 상태 확인이며 실제 사이트의 캐시·브라우저 404 해소 또는 인증 후 조회 가능성을 별도로 보증하지 않는다. 생명보험협회나 검증 가능한 공식 운영 주체가 실제 동작하는 조회 진입 URL을 제공할 때에만 새 근거 수집·독립 재검토·사전검사를 거쳐 CTA를 다시 추가해야 한다.
