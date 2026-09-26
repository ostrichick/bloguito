# Bloguito 문서 안내

이 문서는 **문서의 역할과 우선순위**를 구분하는 단일 목차다. 작업 당시의 보고서에 적힌 '완료', 테스트 개수, 운영 상태는 **해당 날짜의 기록**이지 현재 상태나 새로운 실행 허가가 아니다. 새 작업에서는 코드·운영 상태를 다시 확인한다.

## 처음 읽을 문서와 적용 순서

| 목적 | 정본 / 시작 위치 | 역할 |
| --- | --- | --- |
| 프로젝트 개요와 로컬 환경 | [README](../README.md) | 진입점·구성요소·빠른 시작만 요약 |
| 코딩·협업·배포 안전 규칙 | [AGENTS](../AGENTS.md) | 공통 작업 지침; 기존 미커밋 파일 보존 |
| 글 작성·검토·공개 정책 | [EDITORIAL_SYSTEM](EDITORIAL_SYSTEM.md) | 콘텐츠 업무의 유일한 서술형 현행 규약 |
| 검증 임계값과 모델 설정 | [editorial_policy.json](../agent-publisher/editorial_policy.json) | 코드가 읽는 설정값의 유일한 정본 |
| 명령어·백업·배포 체크리스트 | [OPERATIONS](OPERATIONS.md) | 현재 저장소의 코드와 확인 날짜를 구분한 운영 가이드 |
| 다른 AI로 인계 | [PROJECT_HANDOVER](../PROJECT_HANDOVER.md) | 최소 맥락과 정본 링크; 과거 370줄 이력의 재복제 없음 |
| 콘텐츠 구조·수요 실험 | [CONTENT_STRATEGY](CONTENT_STRATEGY_2026-09-20.md) | **제안**이며 현재 구현이나 배포 규약이 아님 |

**규범은 `AGENTS.md`·`EDITORIAL_SYSTEM.md`, 수치 설정은 코드가 읽는 `editorial_policy.json`이 기준이다.** 현재 기능·배포 여부는 실제 코드와 운영 환경에서 확인한다. 규범과 구현이 충돌하면 어느 쪽이든 안전 기준을 낮추거나 과거 문서를 근거로 우회하지 말고 보고·수정·검증한다. `OPERATIONS.md`는 실행 안내이고 날짜별 기록은 당시 증거일 뿐이다. 과거 기록으로 공개 승인이나 복원 안전성을 추정하지 않는다.

## 날짜별 작업 증거 (보존; 현재 지침 아님)

문서 간 설명이 겹치더라도 작업별 **검증 범위·게시물 ID·출처·원본 해시·롤백 기록**은 합치면 손실될 수 있어 원본을 남겼다. 아래 문서는 사실 판단 시 해당 시점과 환경을 반드시 함께 확인한다.

| 분야 | 기록 |
| --- | --- |
| 9월 12일 초기 계획·구현 | [초기 계획 원본](history/implementation_plan-2026-09-12.md), [초기 결과 원본](history/walkthrough-2026-09-20.md), [구 종합 인계 이력](history/PROJECT_HANDOVER-2026-09-20.md) |
| 편집 시스템 구축·설계 | [검색 의도](search-editorial-policy.md), [공통 시스템 구현](editorial-system-implementation-2026-09-14.md), [벤치마크 반영](benchmark-reflection-2026-09-15.md), [콘텐츠 전략 제안](CONTENT_STRATEGY_2026-09-20.md), [생활정보 본문 UX 비교](article-layout-benchmark-2026-09-21.md) |
| 정보글 본문 구조 개선 | [기본 구조·코드·운영 적용 기록](article-layout-implementation-2026-09-21.md) |
| 자동화·안전성 | [운영 감사·수정](audit-remediation-2026-09-20.md), [1~5순위 코드 개선 당시 상태](implementation-execution-2026-09-20.md), [백업·복구 v3 당시 구현과 미검증](backup-recovery-2026-09-20.md), [2026-09-25 애플리케이션/데이터 격리 복구 훈련](backup-restore-drill-2026-09-25.md), [2026-09-26 호스트 단위 DR 확장 훈련](host-disaster-recovery-drill-2026-09-26.md), [Site Kit 이관](sitekit-and-editorial-handoff-2026-09-20.md), [중복 목차 전수 조사·LuckyWP 비활성화](toc-duplicate-plugin-deactivation-2026-09-21.md), [2026-09-26 작업 흐름 최적화 10개 항목](workflow-optimization-2026-09-26.md) |
| 태그 거버넌스 | [2026-09-26 운영 태그 258개 분류와 신규 자동 태그 중단](tag-governance-2026-09-26.md) |
| 공개 콘텐츠 품질 | [2026-09-20 공개 글 점검](published-content-review-2026-09-20.md), [내부 정정 문구 제거](internal-editorial-notes-cleanup-2026-09-21.md), [통신 미환급액 #243](telecom-post-243-revision-2026-09-21.md), [#218 보강·운영 반영](post-218-expansion-2026-09-21.md), [#349 김건모 일정 표·운영 반영](kim-gunmo-schedule-table-2026-09-21.md), [로이킴 #99·무명전설 #70 이미지 교체](concert-cover-update-2026-09-21.md) |
| 임시글·편집 보류 | [2026-09-20 임시글 전수 점검](draft-content-review-2026-09-20.md), [원고 사본 문구 정리](editorial-improvements-2026-09-20.md), [버스 취소표](bus-cancellation-draft-2026-09-21.md), [버튼 목적지 #345](action-links-draft-fix-2026-09-21.md), [전입신고·세대주 확인 #475](movein-household-draft-2026-09-25.md) |
| 과거 임시글별 기록 | [9/13](review-drafts-2026-09-13.md), [9/14](review-drafts-2026-09-14.md), [9/15 1차](review-drafts-2026-09-15.md), [9/15 2차](review-drafts-2026-09-15-batch2.md), [9/15 3차](review-drafts-2026-09-15-batch3.md) |
| 단일 수정 기록 | [편집 중복 정정](editorial-correction-2026-09-13.md), [에너지 FAQ](energy-faq-correction.md), [9/15 서식 복원](format-fix-2026-09-15.md), [세금 카테고리](category-tax-addition-2026-09-15.md), [카테고리 소개 문구](category-description-broadening-2026-09-21.md), [관리자 글 ID](admin-post-id-column-2026-09-21.md) |

`docs/project-optimization-audit-2026-09-20.md`는 기존 **미추적 작업 파일**이므로 이 정리에서는 편집·이동·삭제·커밋하지 않는다. 과거 0바이트 문서에 대한 설명만 남긴 `improvement-editorial-features-2026-09-18.md`는 중복된 안내라 별도 실내용은 없었으며, 감사 근거는 [`audit-remediation-2026-09-20.md`](audit-remediation-2026-09-20.md)에 남는다.

## 지침과 작업 기록을 구별하는 방법

- `.clinerules`, `.continuerules`, `GEMINI.md`, `.agents/rules/bloguito-editorial.md`는 도구별 **진입점**이지 독자적인 편집 정책이 아니다. 항상 `AGENTS.md`와 `EDITORIAL_SYSTEM.md`로 연결한다.
- 오래된 계획서나 결과 보고서의 CLI 예시·DB 비밀번호 처리·발행/공개 표현을 그대로 실행하지 않는다. 현재 명령은 [운영 가이드](OPERATIONS.md)와 `editorial_cli.py --help`로 확인한다.
- 날짜별 문서에는 당시의 사실 주장과 미검증 항목이 섞여 있다. 새 보고서에서는 확인된 사실 / 추정 / 미확인을 분리하고 **서버 배포와 로컬 변경을 따로 기록**한다.

## 최근 추가 점검

- [2026-09-26 작업 흐름 최적화 10개 항목 및 fast-edit 후속 설계](workflow-optimization-2026-09-26.md): Tailscale 선행 확인 제거, 중복 AI review·전체 WP inventory 왕복 축소, 승인 전 패키지 역할 분리, 로컬 편집 코드+제한형 원격 WordPress 실행, 동시작업 격리·단계형 테스트/브라우저 QA·정책 읽기 캐시·작업 기록 통합을 적용한 기록. 후속 절에는 reviewed draft의 표 재구성·문구 다듬기·중복 FAQ 삭제 같은 소규모 변경을 전체 inventory/전체 의미검토/전체 source 재수집 없이 처리하는 fast-edit 경로를 설계했다.
- [2026-09-25 자동차검사·안심상속 evergreen 임시글 2편](evergreen-auto-inheritance-drafts-2026-09-25.md): 자동차검사 #470과 안심상속 #471을 현재 공식 원문과 독립 검토로 작성하고 대표 이미지를 연결한 뒤 두 글 모두 draft 상태와 저장 HTML을 검증한 기록.
- [2026-09-25 Evergreen 주제 조사](evergreen-topic-research-2026-09-25.md): 운영 WordPress 36개 공개글·6개 초안을 기준으로 계절성 편중과 중복 클러스터를 확인하고, 외부 SERP·공식자료를 대조해 자동차검사·미납통행료·생활행정·상속·공공요금 등 20개 evergreen 후보의 편집 우선순위를 정리했다. 검색량·Search Console 성과는 미측정으로 명시.
- [2026-09-22 요약 상자 상하 여백 전수 점검 및 수정 준비](callout-spacing-audit-2026-09-22.md): 공개 글 30편의 구형 상자 24편에서 확인된 잘못된 문단 태그·여백 문제, 한정 CSS 수정, 운영 미적용 및 검증 범위.
- [2026-09-22 플러그인 업데이트 실패 복구](plugin-update-ownership-repair-2026-09-22.md): 실제 운영 파일 소유권 오류, Site Kit·WP Statistics 업데이트, 독립 백업과 사후 확인 기록.
- [2026-09-24 #233 휴일 약국, 안전상비의약품 임시글 보강](post-233-safety-otc-refresh-2026-09-24.md): 지정 13종과 실제 유통 11종 구분, 편의점 가격 참고표, 새 한글 대표 이미지, 판매 제한과 E-Gen 경로를 보강하고 같은 ID를 draft로 유지한 반영 기록.
