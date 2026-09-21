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
| 편집 시스템 구축·설계 | [검색 의도](search-editorial-policy.md), [공통 시스템 구현](editorial-system-implementation-2026-09-14.md), [벤치마크 반영](benchmark-reflection-2026-09-15.md), [콘텐츠 전략 제안](CONTENT_STRATEGY_2026-09-20.md) |
| 자동화·안전성 | [운영 감사·수정](audit-remediation-2026-09-20.md), [1~5순위 코드 개선 당시 상태](implementation-execution-2026-09-20.md), [백업·복구 v3 당시 구현과 미검증](backup-recovery-2026-09-20.md), [Site Kit 이관](sitekit-and-editorial-handoff-2026-09-20.md) |
| 공개 콘텐츠 품질 | [2026-09-20 공개 글 점검](published-content-review-2026-09-20.md), [내부 정정 문구 제거](internal-editorial-notes-cleanup-2026-09-21.md), [통신 미환급액 #243](telecom-post-243-revision-2026-09-21.md), [#218 보강·운영 반영](post-218-expansion-2026-09-21.md), [#349 김건모 일정 표·운영 반영](kim-gunmo-schedule-table-2026-09-21.md) |
| 임시글·편집 보류 | [2026-09-20 임시글 전수 점검](draft-content-review-2026-09-20.md), [원고 사본 문구 정리](editorial-improvements-2026-09-20.md), [버스 취소표](bus-cancellation-draft-2026-09-21.md), [버튼 목적지 #345](action-links-draft-fix-2026-09-21.md) |
| 과거 임시글별 기록 | [9/13](review-drafts-2026-09-13.md), [9/14](review-drafts-2026-09-14.md), [9/15 1차](review-drafts-2026-09-15.md), [9/15 2차](review-drafts-2026-09-15-batch2.md), [9/15 3차](review-drafts-2026-09-15-batch3.md) |
| 단일 수정 기록 | [편집 중복 정정](editorial-correction-2026-09-13.md), [에너지 FAQ](energy-faq-correction.md), [9/15 서식 복원](format-fix-2026-09-15.md), [세금 카테고리](category-tax-addition-2026-09-15.md), [카테고리 소개 문구](category-description-broadening-2026-09-21.md), [관리자 글 ID](admin-post-id-column-2026-09-21.md) |

`docs/project-optimization-audit-2026-09-20.md`는 기존 **미추적 작업 파일**이므로 이 정리에서는 편집·이동·삭제·커밋하지 않는다. 과거 0바이트 문서에 대한 설명만 남긴 `improvement-editorial-features-2026-09-18.md`는 중복된 안내라 별도 실내용은 없었으며, 감사 근거는 [`audit-remediation-2026-09-20.md`](audit-remediation-2026-09-20.md)에 남는다.

## 지침과 작업 기록을 구별하는 방법

- `.clinerules`, `.continuerules`, `GEMINI.md`, `.agents/rules/bloguito-editorial.md`는 도구별 **진입점**이지 독자적인 편집 정책이 아니다. 항상 `AGENTS.md`와 `EDITORIAL_SYSTEM.md`로 연결한다.
- 오래된 계획서나 결과 보고서의 CLI 예시·DB 비밀번호 처리·발행/공개 표현을 그대로 실행하지 않는다. 현재 명령은 [운영 가이드](OPERATIONS.md)와 `editorial_cli.py --help`로 확인한다.
- 날짜별 문서에는 당시의 사실 주장과 미검증 항목이 섞여 있다. 새 보고서에서는 확인된 사실 / 추정 / 미확인을 분리하고 **서버 배포와 로컬 변경을 따로 기록**한다.
