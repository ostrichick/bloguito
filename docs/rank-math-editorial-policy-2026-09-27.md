# Rank Math 편집정책 개편 — 2026-09-27

## 목적

운영 글 다수가 Rank Math에서 낮은 점수를 받는 상황에서 100점 맞추기 자체를 목표로 삼지 않고, 기존 Bloguito의 정확성·공식 근거·독자 질문 우선 원칙을 유지하면서 기본 SEO 누락을 줄이도록 공통 편집정책을 개편했다.

## 변경 내용

- `primary_keyword`를 여러 관련 단어를 이어 붙인 태그 묶음이 아니라 하나의 짧은 주 검색어 구문으로 정의했다.
- 신규 글과 제목·lead를 다시 검토하는 전면 개편 글은 `brief.seo.title`, `brief.seo.description`을 함께 설계하도록 했다.
- SEO title은 주 포커스 키워드를 자연스럽게 포함하면서 독자용 제목과 같은 검색 의도·사실 조건을 유지하도록 했다.
- 포커스 키워드는 문맥상 자연스러운 경우 SEO 제목, lead, 본문, 관련 소제목 하나에 사용하되 기계적인 반복과 키워드 밀도 맞추기를 금지했다.
- 이미지 ALT는 실제 이미지 설명을 우선하고, 자연스러운 경우에만 포커스 키워드를 포함하도록 했다.
- 기존 공개 글의 slug는 Rank Math 점수 개선만을 이유로 변경하지 않도록 명시했다.
- Rank Math 점수는 발행 게이트가 아니며 75점 이상을 실무 목표, 80점 이상을 양호한 상태로 두었다. 50점 미만은 메타 누락·키워드 설계부터 확인한다.
- 내부 링크와 외부 공식 출처는 기존 의미·검증 정책을 유지하며 점수만을 위해 무관한 링크를 추가하지 않는다.

## 구현 정합성

신규 draft 등록 경로는 기존 `rank_math_focus_keyword`, `rank_math_description`에 더해 `rank_math_title`도 저장하도록 보완했다. `brief.seo`가 있으면 검토된 SEO title/description을 우선하고, 레거시 bundle에는 visible 제목과 lead를 보수적 기본값으로 사용한다. 제한형 SSH transport도 신규 draft 생성 작업에서 이 세 Rank Math 메타 키만 허용하도록 맞췄다.

기존 공개 글 updater에는 이 작업 시작 전에 다른 미커밋 변경으로 검토된 `brief.seo`를 Rank Math 3개 메타에 반영하는 기능이 이미 추가 중이었다. 이번 작업은 그 미커밋 코드를 덮어쓰거나 재구성하지 않았다.

## 검증

- `editorial_policy.json` JSON 파싱: PASS
- `git diff --check` 대상 변경 파일: PASS
- Windows 프로젝트 환경에서 `test_editorial_system.py`, `test_editorial_cli_via_ssh_transport.py`: **51 tests PASS**
- 첫 테스트 시도는 `PYTHONPATH` 미설정으로 `agents` import가 실패했으며, `OPERATIONS.md`의 Windows 테스트 환경변수를 적용한 재실행은 통과했다.

## 적용 범위와 남은 사항

이번 변경은 로컬 편집정책과 신규 WordPress draft 메타 저장 코드까지 반영했다. 운영 서버 코드 배포나 기존 게시물 일괄 SEO 수정은 수행하지 않았다. WP-CLI로 생성한 글은 Rank Math 관리자 편집기의 프런트엔드 점수 계산이 실행되지 않을 수 있으므로, 관측되지 않은 점수를 추정해 기록하지 않는다. 기존 글 개선은 별도의 전수 진단 후 우선순위를 정해 진행한다.
