# 통신 미환급액 공개 글 #243 보강 — 2026-09-21

## 범위 및 결과

- 대상: 이미 공개된 WordPress 게시물 **#243**. 기존 글 제목·고유주소·공개 상태를 유지하고 본문만 갱신했다. 신규 게시물은 생성하지 않았다.
- 요약 상자 하단의 과도한 간격을 줄이기 위해 요약 문단에 `margin:10px 0 0`을 적용해 문단 **하단 마진을 0**으로 지정했다. 상자 자체의 패딩은 유지했다.
- 기존 간략한 안내에 통신 미환급액 발생 유형, KT·SK텔레콤·LG유플러스·SK브로드밴드 및 알뜰폰 망 조회 범위, 온라인 조회 제한 대상, 회원가입 없는 조회 절차, 이메일 인증과 본인 명의 계좌 신청, 지급 소요·통신장애 시 문의, 통신사별 연락처를 추가했다. FAQ는 6개다.
- 편집 도중 다른 작업이 기존 글의 내부 편집 메모를 제거한 사실을 원문 해시 비교로 발견해 최초 배포 시도를 중단했다. 차이를 비교한 뒤 **새 원본 해시**로 다시 검증하고 갱신했다. 다른 작업자의 수정 이력을 덮어쓰지 않았다.

## 근거와 편집 검사

- 공식 자료: `https://www.smartchoice.or.kr/smc/service/refund01.do`, `/smc/service/refund.do`, `/smc/service/refundGuide.do`, `/smc/service/refund_05.do`, `/smc/support/faq.do?tab=C` (모두 `www.smartchoice.or.kr`). 이 문서들을 실제로 수집해 인용 원문 및 해시를 편집 bundle에 보존했다.
- 새 글 작성 대신 기존 글을 갱신해야 하므로 중복 검사에서 대상 ID만 제외하고 **다른 모든 글은 그대로 검사**했다. 구조화된 원고와 인용의 검증, 별도 모델 의미 검토, 공식 출처 재조회 및 해시 비교를 수행했다. 로컬·서버의 `editorial_cli.py review/check` 결과는 `ready`이며 문제 목록은 비어 있었다.
- 사이트 갱신 전 대상 #243의 본문·상태·제목과 해시를 확인하고, 수정 직전에 다시 검사했다. 이전 본문 전체 백업: 서버 `/home/ubuntu/agent-publisher/data/editorial_runs/public-edit-243-20260921T090700.json` (개인정보가 포함될 가능성이 있는 원문은 Git에 보관하지 않음).
- 갱신 후 WordPress에서 게시물 ID `243`, 상태 `publish`, 기존 제목·슬러그, 렌더된 본문 일치를 검증했다. 재동기화한 운영 목록의 본문 SHA-256은 `5c65c08a1350ec39b1888d5371d415c61c9075c7ffbb624a318122836ac12774`이다.
- 공개 URL 직접 HTTP 조회: **200**, 요약 문단 하단 마진 0, FAQ 카드 6개, 본문 단계 4개 확인. 최종 본문 사본은 `content/draft-revisions-2026-09-20/243.html`; `manifest.json`의 #243 항목만 공개 상태·해시·검토 결과를 동기화했다.
- 전 과정에서 로그인한 개인 계정의 신청 완료 화면이나 실제 은행 입금은 테스트하지 않았다. 공식 안내의 절차와 실제 홈페이지에 공개된 HTML까지 검증했다.

## 재사용 가능한 변경

- `agent-publisher/agents/editorial_updater.py`: 공개 글 하나를 지정해 현재 공개 상태·원본 본문 SHA·최신 출처·검토 결과를 검증한 다음 기존 글의 본문만 갱신하고 원문 백업 및 사후 검증을 수행한다.
- `agent-publisher/editorial_cli.py update-existing`: 위 기능을 명시적 `--post-id`, `--expected-content-sha256`, `--confirm-update`와 연결했다. 새 글 생성이나 공개 상태 변경은 하지 않는다.
- `agent-publisher/tests/test_editorial_updater.py`: 기존 글 ID/상태 유지, 기존 본문 변경 시 중단, 명시적 승인 요구를 검증한다.

**배포 범위:** 새 updater 모듈을 서버의 `agents`에 추가하고 수정한 CLI는 별도 `/tmp` 경로에서 실행했다. 기존 서버 `editorial_cli.py`를 덮어쓰거나 전체 서비스를 재시작하지 않았다. 정상적인 코드 동기화는 이 변경들의 별도 Git 반영 여부에 따르며, 이번에 WordPress 본문 자체는 실제 공개 배포했다.
