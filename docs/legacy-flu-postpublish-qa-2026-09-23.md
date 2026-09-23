# 독감 글 #63·#81 v3 게시 후 독립 확인 및 #140 추가 점검 — 2026-09-23

## 직접 검증 결과

**2026-09-23 09:16~09:18 KST 읽기 전용 조사.** 작업자는 전날 QA 기록을 현재 증거로 재사용하지 않고 서버 `wp post get <ID> --format=json`만 실행하는 기존 `scripts/prepare_post_approval.py::read_wp_json()`으로 글별 저장 원본을 가져와 **UTF-8 `post_content` 전체 SHA-256와 최종 v3 번들 `render()`의 전체 문자열 일치**를 확인했다. 승인 manifest에 보관된 기존 제목·slug·게시일 및 `publish` 상태도 실서버에서 직접 비교했다. 새 HTTP GET으로 공개 REST(`/wp-json/wp/v2/posts/<ID>`)와 개별 일반 공개 페이지를 별도 읽어 내용과 HTML 구조를 비교했다. 공개 페이지가 브라우저에서 시각적으로 표시되는지까지 인증한 것은 아니다.

| ID | 실서버 저장 SHA-256 = 최종 검토 렌더 = prime 예상 | WP 제목·slug·게시일·`publish` | REST/일반 공개 HTML |
| --- | --- | --- | --- |
| **#63** | `128f680d38734c1fcc4f7edcd40cf96e186632092665d9a3999330014568a541` 모두 일치 | 모두 보존; 수정 `2026-09-23 09:12:25` | 양쪽 HTTP 200, REST 가시 본문과 실저장 본문 일치, 직접 공개 HTML 구조 PASS |
| **#81** | `959d932cb488e8c85685ef37333478635ac6d0bb29d819985b469d83fbb71c3f` 모두 일치 | 모두 보존; 수정 `2026-09-23 09:13:13` | 양쪽 HTTP 200, REST 가시 본문과 실저장 본문 일치, 직접 공개 HTML 구조 PASS |
| **#140 (prime 추가 요청)** | `9a0d8c8b1db3b1bd9fcf93bdde1781ce6bdb35fd97d38a9919c58df16404f1b1` 모두 일치 | 모두 보존; 수정 `2026-09-23 09:14:28` | 양쪽 HTTP 200, REST 가시 본문과 실저장 본문 일치, 직접 공개 HTML 구조 PASS |

대조 원본: `tmp/legacy_audit_20260923/prime/post-{63,81}-review-v3-candidate.json`, `prime/approval-{63,81}-reviewed-v3/approval-manifest.json`, #140은 `civic2/post140-fresh-unreviewed.json`(파일명은 생성 시점의 역사적 이름이며 현 파일에 새 독립 review 포함) 및 `civic2/post140-approval-fresh/approval-manifest.json`. 이번 점검의 결과는 `civic2/flu-postpublish-readonly-results.json`, `civic2/passport-postpublish-readonly-results.json`, `civic2/public-html-readonly-results.json`. 서버 원본 문자열, PRIVATE 백업 및 다른 초안 정보는 일반 보고서·대시보드에 복사하지 않았다.

## 직접 공개된 본문의 의미·동작 구조

- **#63 / #81**: 공개 REST에서 각각 최신 v3 리드가 정확히 보이며, 목차 **1개 / 연결 5개 / 잘못되거나 중복된 앵커 0**, 공식 출처 목록 각 **2건**. 각 글에 `인플루엔자 지정의료기관 검색 ↗` CTA **1개**, `https://nip.kdca.go.kr/irhp/mngm/goVcntMngm.do?menuCd=333`로 결합된 것을 REST와 실제 일반 공개 페이지 HTML에서 확인했다. 이는 **링크의 현재 목적지 문자열 확인**이며 09:16 이후 최종 외부 화면의 JS 검색·백신 재고·예약 성공을 재연한 의미가 아니다.
- **가장 중요한 연령 한정 재검증:** 양쪽 REST와 공개 HTML 모두 `65세 이상 어르신 중 면역저하자 등 고위험군`이라고 범위를 명시하고, 연령대 일반 개시일과 무관한 **10월 6일 의료진 상담 후 접종**으로 안내한다. #63은 기존 ‘면역저하자 등’만 열거한 v2를 더는 게시하지 않는다. 이 표현은 65세 미만 면역저하자가 국가 무료접종 지원 대상이라고 독자에게 확장하지 않는다. 표적 구절과 최종 v3 원고 문장이 동일함을 검사했다. 독립 의학적 개별 접종 자격 판정은 시행하지 않았다.
- **#140**: 공식 여권 수령 관련 기존 여권 유효기간·신분증 지참, 법정대리인 예외, 신청 완료 후 수령기관 변경 불가가 REST 본문에 남아 있다. 목차 **1개 / 앵커 4개 전부 유효**, 공식 출처 **1건**. CTA는 **0개**로 실제 검사 결과를 기록한다. 해당 최종 검토 번들의 링크 없는 안내를 사후에 새 신청 버튼이 생겼다고 주장하지 않는다. 행동 링크 신설이 필요하면 목적지별 별도 실화면 검증과 전체 재검토가 필요하다.
- 일반 공개 페이지의 서버 반환 HTML은 **세 글 각각 HTTP 200**, `.bloguito-article` **1개**, 목차 **1개**, 모든 목차 앵커 목적지 유일, 출처 #63·#81 2개 및 #140 1개, 위 CTA 수 및 독감 연령 범위가 REST의 구조 검사와 일치했다. 세 건 모두 정적 HTTP 검사는 PASS다. 실제 화면의 겹침·가로 넘침이나 JavaScript 콘솔 상태까지 이 결과로 추론하지 않는다.

## 격리 Edge 재사용 불가 — 브라우저 QA 미완료

과거 스크립트 `tmp/legacy_audit_20260922/liveqa-live-posts.mjs`를 **자신의 Git ignored `tmp/legacy_audit_20260923/civic2/liveqa-live-posts.mjs`로 복사**해 실행했다. 기존 스크립트는 127.0.0.1:9237에 연결된 기존 QA Edge 탭만 찾으며, 연결 거부 시 브라우저를 새로 시작하지 않는다. 이번 실행은 **`ECONNREFUSED 127.0.0.1:9237`로 즉시 종료**했다. 실행 중 msedge/chrome/brave 프로세스의 `--remote-debugging-port` 매개변수에서도 사용 가능한 포트가 나오지 않았다. 새 브라우저·프로필·포트를 생성하거나 다른 작업자의 탭을 탈취하지 않았다.

따라서 **360px·390px·1280px CSS 200% 시각 QA, JavaScript 콘솔, 새 스크린샷, 네이티브 200% 확대, 보조기술·전 구간 키보드 접근성**은 이번 조사에서는 모두 `미검증`이다. 과거 9월 22일 스크린샷을 v3 게시 후 증거로 사용하지 않는다. 기존 QA Edge를 다시 사용할 수 있을 때 개인 복사본에서 `node tmp/legacy_audit_20260923/civic2/liveqa-live-posts.mjs 63 81 140`을 실행하면 자기 폴더에만 새 결과와 3개 뷰포트별 스크린샷이 생성되도록 했다. 이 실행이 현재 성공했다는 기록은 없다. QA 세션이 가능해지면 `AGENTS.md`의 UTM URL로 첫 진입한다.

## 수정 경계

이번 담당자는 WordPress·서버의 읽기 명령과 공개 HTTP 요청만 실행했다. 운영 글 변경·복원·공개·Git stage/commit/push는 수행하지 않았다. 작업 중 새로 작성한 것은 이 MD와 위 `civic2/` 내부 검사 스크립트/JSON, 복사된 QA 스크립트뿐이며 9/22 QA 파일과 다른 작업자의 v3 자료는 변경하지 않았다. 저장 해시 및 정적 본문 점검은 **2026-09-23 09:16~09:18 KST 시점**의 결과이고 이후 누군가 수정했는지까지 보장하지 않는다.
