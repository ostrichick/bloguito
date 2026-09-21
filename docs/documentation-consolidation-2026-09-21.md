# 지침·문서 통합 작업 기록 — 2026-09-21

## 확인 및 판단

- 작업 전 기준 `main` 커밋 `1dad552`. 추적된 Markdown 34개와 추가 미추적 감사 문서 1개를 목록화하고, 링크·실행 파일 참조·실제 정책 진입점을 확인했다. `.clinerules`, `.continuerules`, `GEMINI.md`는 내용 해시가 동일한 40줄 중복 지침이었다. Antigravity의 `.agents/rules/bloguito-editorial.md`는 `trigger: always_on` 진입점이므로 삭제 대상이 아니다.
- `AGENTS.md`는 공통 작업 규칙, `docs/EDITORIAL_SYSTEM.md`는 서술형 콘텐츠 규약, `agent-publisher/editorial_policy.json`은 실제 정책 숫자의 정본으로 유지했다. `editorial.py`/`editorial_writer.py`/배포 스크립트가 읽는 `docs/EDITORIAL_SYSTEM.md` 위치는 변경하지 않았다.
- 과거 `README.md`, `PROJECT_HANDOVER.md`, `implementation_plan.md`, `walkthrough.md`는 오래된 백업 스키마·모델 순서·임시글과 공개 구분·성능 주장·테스트 개수를 반복했다. 과거 기록을 운영 명령으로 오인할 위험이 있어 **현재 안내와 당시 원본**을 분리했다.

## 수정 내용

1. README를 설치·구조·안전 경계만 남긴 시작 페이지로 줄이고, 인계서도 정본으로 연결하는 짧은 진입점으로 정리했다.
2. `docs/INDEX.md`에 규범/설정/운영/제안/날짜별 증거의 우선 용도와 문서 목록을 통합했다. `docs/OPERATIONS.md`에 실제 코드 경로, 안전한 테스트, draft·공개 구분, 백업/배포 체크리스트를 단일화했다.
3. 기존 루트 `PROJECT_HANDOVER.md`, `implementation_plan.md`, `walkthrough.md` 전체 원본은 각각 `docs/history/`로 보존하고 **기존 파일명에는 안내·링크를 유지**했다. 원본 첫머리에 과거 시점 경고를 넣고 이동으로 깨지는 상대 링크를 수정했다. 구 결과 기록에 남았던 개인 전화번호는 문서에서 삭제하고 위험한 과거 인증 방식만 설명했다.
4. Cline·Continue·Gemini·Antigravity의 파일명과 Antigravity `always_on` 표식은 유지하되 각 파일은 공통 정본을 읽도록 짧은 지침으로 통합했다. 공식 근거·중복·검토 실패 시 보류, 기본 draft, 명시 승인 없는 공개 금지 등 안전 조건은 유지했다.
5. 실제 내용이 없던 2026-09-18 편집 개선 문서를 가리키는 3줄 중복 안내 파일 `docs/improvement-editorial-features-2026-09-18.md`는 제거했다. 그 파일의 존재 이력은 Git에서 조회할 수 있고 후속 실제 검증 내용은 `docs/audit-remediation-2026-09-20.md`에 남아 있다.

## 검증과 범위

- Markdown 파일 40개에서 실제 상대 링크 97개를 확인해 **깨진 경로 0개**. 문서에 개인 전화번호 형태가 남아 있는지도 검사해 탐지 0건. `file:///` 형식의 역사 기록상 당시 서버 경로는 현재 링크로 취급하지 않는다.
- `PYTHONPATH=agent-publisher`, `PYTHONIOENCODING=utf-8`로 Python 전체 회귀 **162개 통과**. 해당 검사는 문서 수정이 게시·복구 작업을 실행하지 않는다는 점과 별개이며 운영 기능의 사실 정확도나 복구 성공을 증명하지 않는다. `git diff --check` 통과.
- 변경하지 않은 파일: `docs/EDITORIAL_SYSTEM.md`, `agent-publisher/editorial_policy.json`, WordPress 게시글/DB/서버, 과거 작업자가 수정해 둔 `agents/curator.py`, `agents/publisher.py`, 관련 테스트 2개, 기존 미추적 `docs/project-optimization-audit-2026-09-20.md`. 이 작업은 **로컬 문서 변경과 Git 반영만** 대상으로 하고 실제 운영 배포는 수행하지 않는다.

## 남은 한계

- 날짜별 감사·콘텐츠 수정 문서는 출처·게시글 ID·해시·배포 결과라는 고유 증거가 있으므로 일괄 합치거나 삭제하지 않았다. 최신 글 상태·서버 cron·백업 버전·WhatsApp 설정은 기록만으로 알 수 없고 실서버에서 재조회해야 한다.
- Cline·Continue·Gemini·Antigravity가 각 지침 파일을 실제로 로딩하는지 IDE 세션 전체 실행으로 확인한 것은 아니다. 파일명·Antigravity frontmatter·공통 참조 경로와 내용을 확인했다.
