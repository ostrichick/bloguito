# Bloguito 문서 안내

이 문서는 **문서의 역할과 우선순위**를 구분하는 단일 목차다. 작업 당시의 보고서에 적힌 '완료', 테스트 개수, 운영 상태는 **해당 날짜의 기록**이지 현재 상태나 새로운 실행 허가가 아니다. 새 작업에서는 코드·운영 상태를 다시 확인한다.

## 처음 읽을 문서와 적용 순서

| 목적 | 정본 / 시작 위치 | 역할 |
| --- | --- | --- |
| 프로젝트 개요와 로컬 환경 | [README](../README.md) | 진입점·구성요소·빠른 시작만 요약 |
| 코딩·협업·배포 안전 규칙 | [AGENTS](../AGENTS.md) | 공통 작업 지침; 기존 미커밋 파일 보존 |
| 공통 편집·검토·저장 안전 계약 | [EDITORIAL_SYSTEM](EDITORIAL_SYSTEM.md) | 모든 콘텐츠에 적용되는 공통 규칙과 정책 라우팅 |
| 일반 정보글 작성·수정 | [GENERAL_POST_STANDARD](GENERAL_POST_STANDARD.md) | 행사 포스트가 아닌 생활정보·정부서비스·복지·세금·건강·비용/조회형 글의 현행 표준 |
| 행사 일정형 글 전용 확장 | [EVENT_POST_STANDARD](EVENT_POST_STANDARD.md) | 월간 다중 행사 글의 작성·이미지·CTA·SEO·QA 세부 표준 |
| 대표 이미지 | [FEATURED_IMAGE_STANDARD](FEATURED_IMAGE_STANDARD.md) | 일반·행사 글의 서술형 이미지 품질 규칙; 기계 설정은 editorial_policy.json |
| 대표이미지 잠금 PC 검증 후속 | [수정·재검증 전달문](FEATURED_IMAGE_PC_VALIDATION_HANDOFF.md), [검증·복구 기록](FEATURED_IMAGE_LOCK_RECOVERY.md) | 2026-10-09 실제 DB 검증 실패 두 결함과 재현·완료 기준; 현재 정책이나 배포 승인으로 사용하지 않음 |
| 검증 임계값과 모델 설정 | [editorial_policy.json](../agent-publisher/editorial_policy.json) | 코드가 읽는 설정값의 유일한 정본 |
| 명령어·백업·배포 체크리스트 | [OPERATIONS](OPERATIONS.md) | 현재 저장소의 코드와 확인 날짜를 구분한 운영 가이드 |
| 콘텐츠 목록과 주제 대시보드 | [POST_CATALOG](POST_CATALOG.md) | 발행·임시글 현황 및 백로그 로컬 단일 정본 |
| 카테고리 구조와 당시 61편 이관표 | [2026-10-02 카테고리 개편](category-reorganization-2026-10-02.md) | 2026-10-02 기준 8개 카테고리, 당시 운영 term, 글별 이동표와 마이그레이션 원칙 |
| 다른 AI로 인계 | [PROJECT_HANDOVER](../PROJECT_HANDOVER.md) | 최소 맥락과 정본 링크; 과거 370줄 이력의 재복제 없음 |
| 콘텐츠 구조·수요 실험 | [CONTENT_STRATEGY](CONTENT_STRATEGY_2026-09-20.md) | **제안**이며 현재 구현이나 배포 규약이 아님 |

**공통 규범은 `AGENTS.md`·`EDITORIAL_SYSTEM.md`, 글 유형별 규범은 `GENERAL_POST_STANDARD.md` 또는 `EVENT_POST_STANDARD.md`, 대표 이미지 규범은 `FEATURED_IMAGE_STANDARD.md`, 수치·기계 설정은 코드가 읽는 `editorial_policy.json`이 기준이다.** 현재 기능·배포 여부는 실제 코드와 운영 환경에서 확인한다. 규범과 구현이 충돌하면 어느 쪽이든 안전 기준을 낮추거나 과거 문서를 근거로 우회하지 말고 보고·수정·검증한다. `OPERATIONS.md`는 실행 안내이고 날짜별 기록은 당시 증거일 뿐이다. 과거 기록으로 공개 승인이나 복원 안전성을 추정하지 않는다.

## 날짜별 작업 증거 (보존; 현재 지침 아님)

문서 간 설명이 겹치더라도 작업별 **검증 범위·게시물 ID·출처·원본 해시·롤백 기록**은 합치면 손실될 수 있어 원본을 남겼다. 아래 문서는 사실 판단 시 해당 시점과 환경을 반드시 함께 확인한다.

| 분야 | 기록 |
| --- | --- |
| 9월 12일 초기 계획·구현 | [초기 계획 원본](history/implementation_plan-2026-09-12.md), [초기 결과 원본](history/walkthrough-2026-09-20.md), [구 종합 인계 이력](history/PROJECT_HANDOVER-2026-09-20.md) |
| 편집 시스템 구축·설계 | [검색 의도](search-editorial-policy.md), [공통 시스템 구현](editorial-system-implementation-2026-09-14.md), [벤치마크 반영](benchmark-reflection-2026-09-15.md), [콘텐츠 전략 제안](CONTENT_STRATEGY_2026-09-20.md), [생활정보 본문 UX 비교](article-layout-benchmark-2026-09-21.md) |
| 정보글 본문 구조 개선 | [기본 구조·코드·운영 적용 기록](article-layout-implementation-2026-09-21.md) |
| 자동화·안전성 | [운영 감사·수정](audit-remediation-2026-09-20.md), [1~5순위 코드 개선 당시 상태](implementation-execution-2026-09-20.md), [백업·복구 v3 당시 구현과 미검증](backup-recovery-2026-09-20.md), [2026-09-25 애플리케이션/데이터 격리 복구 훈련](backup-restore-drill-2026-09-25.md), [2026-09-26 호스트 단위 DR 확장 훈련](host-disaster-recovery-drill-2026-09-26.md), [Site Kit 이관](sitekit-and-editorial-handoff-2026-09-20.md), [중복 목차 전수 조사·LuckyWP 비활성화](toc-duplicate-plugin-deactivation-2026-09-21.md), [2026-09-26~10-01 작업 흐름 최적화 P1~P8](workflow-optimization-2026-09-26.md), [2026-10-01 P9~P11·WhatsApp 제거](project-simplification-p9-p11-2026-10-01.md), [2026-10-01 P12·P14·P15·P13 후속 단순화](project-simplification-p12-p15-p13-2026-10-01.md) |
| 2026-10-06 백업 암호화 후속 검증 | [보안 하드닝 기록의 2026-10-06 후속 절](security-hardening-2026-09-25.md) | 암호화 사본 인증·복호화 검증과 예약 작업 수동 실행 당시 결과; 전체 새 VM DR 및 다음 예약 실행 확인과 구분 |
| Simple Task·이미지 연속 실행 | [2026-09-30 Fast Path·Completion Guard 구현](simple-task-image-continuation-2026-09-30.md) |
| 태그 거버넌스 | [2026-09-26 운영 태그 258개 분류와 신규 자동 태그 중단](tag-governance-2026-09-26.md) |
| 공개 콘텐츠 품질 | [2026-09-20 공개 글 점검](published-content-review-2026-09-20.md), [내부 정정 문구 제거](internal-editorial-notes-cleanup-2026-09-21.md), [통신 미환급액 #243](telecom-post-243-revision-2026-09-21.md), [#218 보강·운영 반영](post-218-expansion-2026-09-21.md), [#349 김건모 일정 표·운영 반영](kim-gunmo-schedule-table-2026-09-21.md), [로이킴 #99·무명전설 #70 이미지 교체](concert-cover-update-2026-09-21.md) |
| 임시글·편집 보류 | [2026-09-20 임시글 전수 점검](draft-content-review-2026-09-20.md), [원고 사본 문구 정리](editorial-improvements-2026-09-20.md), [버스 취소표](bus-cancellation-draft-2026-09-21.md), [버튼 목적지 #345](action-links-draft-fix-2026-09-21.md), [전입신고·세대주 확인 #475](movein-household-draft-2026-09-25.md) |
| 과거 임시글별 기록 | [9/13](review-drafts-2026-09-13.md), [9/14](review-drafts-2026-09-14.md), [9/15 1차](review-drafts-2026-09-15.md), [9/15 2차](review-drafts-2026-09-15-batch2.md), [9/15 3차](review-drafts-2026-09-15-batch3.md) |
| 단일 수정 기록 | [편집 중복 정정](editorial-correction-2026-09-13.md), [에너지 FAQ](energy-faq-correction.md), [9/15 서식 복원](format-fix-2026-09-15.md), [세금 카테고리](category-tax-addition-2026-09-15.md), [카테고리 소개 문구](category-description-broadening-2026-09-21.md), [관리자 글 ID](admin-post-id-column-2026-09-21.md) |

`project-optimization-audit-2026-09-20.md`는 **2026-10-09 로컬 Git에서 추적 중인 역사 기록**이다([파일](project-optimization-audit-2026-09-20.md)). 과거 0바이트 문서에 대한 설명만 남긴 `improvement-editorial-features-2026-09-18.md`는 중복된 안내라 별도 실내용은 없었으며, 감사 근거는 [`audit-remediation-2026-09-20.md`](audit-remediation-2026-09-20.md)에 남는다.

## 지침과 작업 기록을 구별하는 방법

- `.clinerules`, `.continuerules`, `GEMINI.md`, `.agents/rules/bloguito-editorial.md`는 도구별 **진입점**이지 독자적인 편집 정책이 아니다. 항상 `AGENTS.md`와 `EDITORIAL_SYSTEM.md`로 연결한다.
- 오래된 계획서나 결과 보고서의 CLI 예시·DB 비밀번호 처리·발행/공개 표현을 그대로 실행하지 않는다. 현재 명령은 [운영 가이드](OPERATIONS.md)와 `editorial_cli.py --help`로 확인한다.
- 날짜별 문서에는 당시의 사실 주장과 미검증 항목이 섞여 있다. 새 보고서에서는 확인된 사실 / 추정 / 미확인을 분리하고 **서버 배포와 로컬 변경을 따로 기록**한다.

## 최근 추가 점검

- [2026-10-03 성장 시스템 P0~P5 로드맵](growth-system-roadmap-2026-10-03.md): inventory 경계 정리, GSC/GA4 Opportunity Queue, 신규 주제 demand gate, 일일 planner, completion log, existing/new work-mix rotation의 구현 순서와 완료 조건을 기록.
- [2026-10-02 카테고리 8분류 개편](category-reorganization-2026-10-02.md): `생활/건강 정보`의 과밀과 지역 행사 분산을 해소하기 위한 8개 평면 taxonomy, 실서버 61편 전수 재분류표, WordPress term/메뉴 마이그레이션 원칙을 기록.
- [2026-10-02 일반 정보 포스트 정책 4단계 후속 계획](general-post-stage4-plan-2026-10-02.md): 4.1 General/Event schema 분리, 4.2 post-specific exception registry, 4.3A/B volatility freshness를 완료하고, 4.4는 2026 인플루엔자 규칙을 첫 데이터/엔진 분리 파일럿으로 적용한 상태와 후속 종료 조건을 기록.
- [2026-10-02 volatility 기반 freshness 4.3 영향도 점검](general-post-stage4-3-impact-2026-10-02.md): 8개 카테고리 구조와 기존 reviewed bundle을 기준으로 metadata-only 도입, migration report, live source 재검증, 기존 content_type fallback의 안전한 전환 순서를 정리.
- [2026-10-02 volatility migration report](volatility-migration-report-2026-10-02.json): 기존 `search_briefs.json` 13건의 lifecycle/live-state 후보, 신뢰도, 충돌, review window 상태를 read-only로 제안. 원본 brief와 WordPress 상태는 수정하지 않음.
- [2026-10-02 reviewed volatility migration report](volatility-migration-report-2026-10-02-reviewed.json): 현재 review가 유효하고 legacy gate와 호환되는 2건에 수동 확정한 explicit metadata와 migration 제안 일치 여부를 함께 기록. 만료 brief와 WordPress 상태는 수정하지 않음.
- [2026-10-01 프로젝트 간소화 P9~P11 및 WhatsApp 제거](project-simplification-p9-p11-2026-10-01.md): validation registry 제거, per-post reviewed manifest 저장 구조, WSL SSH 연결 재사용, section-image 왕복 축소, 운영 WhatsApp service 제거와 전체 회귀 검증 기록.

- [2026-09-29 #598 임플란트 건강보험 대표 이미지 문구 정정](post-598-cover-text-fix-2026-09-29.md): 대표 이미지 좌측 하단 알약 배지의 '팩트' 단어를 제거하고 '안내'로 수정한 WebP를 재생성하여 운영 WordPress의 대표 이미지(_thumbnail_id=679)로 교체 및 실서비스 검증을 완료한 기록.
- [2026-09-28 로컬 콘텐츠 카탈로그와 주제 백로그 갱신](post-catalog-workflow-2026-09-28.md): 새 글 탐색의 로컬 카탈로그 우선 사용, 저장 후 1회 동기화, 이미 draft/공개 글로 작성된 백로그 주제 자동 제외와 실제 WordPress 카테고리 반영을 정리한 기록.
- [2026-09-27 Rank Math 편집정책 개편](rank-math-editorial-policy-2026-09-27.md): 짧은 단일 포커스 키워드, SEO title/description, 자연스러운 본문 배치, 기존 slug 보존, 75/80점 가이드와 신규 draft의 Rank Math title 저장을 정리한 기록.
- [2026-09-27 하이패스 미납통행료, 모바일 주민등록증 evergreen 임시글 2편](hipass-mobile-id-drafts-2026-09-27.md): 최신 운영 인벤토리와 공식 원문, 독립 의미 검토를 거쳐 모바일 주민등록증 #559와 하이패스 미납통행료 #560을 신규 `draft`로 저장하고 저장 본문과 최종 WordPress 상태를 재검증한 기록.
- [2026-09-26 작업 흐름 최적화 10개 항목 및 fast-edit 후속 설계](workflow-optimization-2026-09-26.md): Tailscale 선행 확인 제거, 중복 AI review·전체 WP inventory 왕복 축소, 승인 전 패키지 역할 분리, 로컬 편집 코드+제한형 원격 WordPress 실행, 동시작업 격리·단계형 테스트/브라우저 QA·정책 읽기 캐시·작업 기록 통합을 적용한 기록. 후속 절에는 reviewed draft의 표 재구성·문구 다듬기·중복 FAQ 삭제 같은 소규모 변경을 전체 inventory/전체 의미검토/전체 source 재수집 없이 처리하는 fast-edit 경로를 설계했다.
- [2026-09-25 자동차검사·안심상속 evergreen 임시글 2편](evergreen-auto-inheritance-drafts-2026-09-25.md): 자동차검사 #470과 안심상속 #471을 현재 공식 원문과 독립 검토로 작성하고 대표 이미지를 연결한 뒤 두 글 모두 draft 상태와 저장 HTML을 검증한 기록.
- [2026-09-25 Evergreen 주제 조사](evergreen-topic-research-2026-09-25.md): 운영 WordPress 36개 공개글·6개 초안을 기준으로 계절성 편중과 중복 클러스터를 확인하고, 외부 SERP·공식자료를 대조해 자동차검사·미납통행료·생활행정·상속·공공요금 등 20개 evergreen 후보의 편집 우선순위를 정리했다. 검색량·Search Console 성과는 미측정으로 명시.
- [2026-09-22 요약 상자 상하 여백 전수 점검 및 수정 준비](callout-spacing-audit-2026-09-22.md): 공개 글 30편의 구형 상자 24편에서 확인된 잘못된 문단 태그·여백 문제, 한정 CSS 수정, 운영 미적용 및 검증 범위.
- [2026-09-22 플러그인 업데이트 실패 복구](plugin-update-ownership-repair-2026-09-22.md): 실제 운영 파일 소유권 오류, Site Kit·WP Statistics 업데이트, 독립 백업과 사후 확인 기록.
- [2026-09-24 #233 휴일 약국, 안전상비의약품 임시글 보강](post-233-safety-otc-refresh-2026-09-24.md): 지정 13종과 실제 유통 11종 구분, 편의점 가격 참고표, 새 한글 대표 이미지, 판매 제한과 E-Gen 경로를 보강하고 같은 ID를 draft로 유지한 반영 기록.

- [2026-09-26 요약 박스 제목 통일](summary-label-unification-2026-09-26.md): 기존 글 54편 전수 조회, 50편 제목 변경, 신규 생성 기본 제목 고정, 백업 및 전수 보존 검증.
- [2026-09-26 편집·독자 경험·수익화 분석 및 1~4번 개선, 9/27 마무리](editorial-reader-revenue-audit-2026-09-26.md): 첫 답변 거리, 관련 읽기, 구형 서식/발췌문, FAQ 지침과 공통 화면을 운영에 적용하고 #470·#231·#345를 정규 경로로 갱신한 기록. 전체 과거 글 이관이나 수익 효과 검증은 아님.

- [2026-09-26 프로젝트 우선순위 감사 및 1·3·5번 개선](project-priority-audit-2026-09-26.md): 검토 결합 보존, 오류 종료 전달, 공개 글 3편 출처 복원과 서버 배포·검증 및 남은 우선순위.
- [2026-09-28 부산 10월 축제 일정 임시글 #648](busan-october-festivals-draft-2026-09-28.md): 페스티벌 시월, 부산국제영화제, 부산국제록페스티벌, 자갈치축제 등 10월 주요 행사를 비교표·지도·CTA로 정리한 임시글 작업 기록.
- [2026-09-28 대구 10월 축제 일정 임시글 #657](daegu-october-festivals-draft-2026-09-28.md): 판타지아대구페스타, 대구국제오페라축제, 달성 100대 피아노 등 10월 주요 행사를 비교표·지도·CTA로 정리한 임시글 작업 기록.
- [2026-09-28 세종 10월 축제 일정 임시글 #665](sejong-october-festivals-draft-2026-09-28.md): 당시 임시글 작성 과정을 보존한 역사 기록. 2026-10-06 공개 REST 재확인 당시 글 상태는 `publish`였다.
- [2026-09-28 광주 10월 축제 일정 임시글 #666](gwangju-october-festivals-draft-2026-09-28.md): 당시 임시글 작성 과정을 보존한 역사 기록. 2026-10-06 공개 REST 재확인 당시 글 상태는 `publish`였다.
- [2026-10-02 프로젝트 UTF-8 인코딩 하드닝](encoding-hardening-2026-10-02.md): Windows CP949 환경의 subprocess 경계를 UTF-8 strict로 고정하고 저장 정책·CI 검사·PowerShell 로그 인코딩을 보강한 기록.


## 작업별 사후 기록 및 하네스 관리 규칙 (`docs/tasks/`)

단일 포스트 단위의 일회성 패치, 롤백, 특정 기능 하네스 **Markdown 기록**은 루트 docs/의 오염을 방지하기 위해 docs/tasks/<주제_또는_포스트ID>/ 하위에 생성하고 Git으로 보존한다. 이미지, JSON, 브라우저 프로필 같은 실행 산출물은 이 경로에 영구 보존하지 않고 scratch/tasks/ 수명주기를 따른다. 이 디렉터리의 오래된 체크박스나 `Active` 표시는 당시 작업 스냅샷일 수 있으므로 현재 재개 상태로 해석하지 않는다. 실제 재개 여부는 현행 task-state와 Git 상태를 우선한다.
- [Post #621 카카오맵 연동 및 실사 이미지/카드 패치 하네스 모음](tasks/post-621/): Post #621 전용 지도 연동, 축제 요약 카드, 실사 이미지 패치 및 롤백 사양서 5종을 **역사 기록**으로 보존. 문서 안의 미완료 체크박스는 현재 실행 대기 작업을 뜻하지 않는다.
