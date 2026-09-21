# 중복 목차 조사 및 LuckyWP 비활성화 — 2026-09-21

## 범위와 원인

- 사용자가 김건모 공개 게시물 #349의 목차 중복 제거, 다른 글의 중복 조사 및 원인 플러그인 비활성화를 요청했다.
- 기준 로컬 커밋: `de3092b`. 사전 미커밋 파일인 `curator.py`, `publisher.py`, `test_editorial_system.py`, `test_ticket_validation.py`, `docs/project-optimization-audit-2026-09-20.md`는 건드리지 않았다.
- WordPress 공개 게시물 29개를 `wp post list`의 실제 저장 본문과 공개 URL `?p=ID`의 HTTP 응답 HTML로 전수 비교했다. **29개 모두 HTTP 200, 응답 오류 0개.**
- #218, #243, #304, #349: 본문에 `bloguito-toc`가 각각 1개, 렌더된 화면에는 해당 목차와 `lwptoc` 목차가 각각 1개씩 있어 **중복 4개**를 확인했다.
- 나머지 25개 공개 글은 본문 자체 목차가 없고 LuckyWP의 `lwptoc` 자동 목차 1개만 사용했다. 공개 글의 본문에서 `[lwptoc]` 숏코드는 발견되지 않았다.
- 원인 플러그인: **LuckyWP Table of Contents 2.1.14**, 당시 `active`. 옵션 `lwptoc_autoInsert`의 `enable=true`, `position=beforefirstheading`, `postTypes=["post"]` 설정으로 자동 목차가 삽입되고 있었다. 독립적인 Bloguito 렌더러도 4개 글의 자체 목차를 작성하므로 함께 출력됐다.

## 실제 변경·백업

- WordPress 본문, 다른 플러그인, 로컬 게시물 생성 코드는 변경하지 않았다. 사용자의 명시적 비활성화 요청에 따라 `wp plugin deactivate luckywp-table-of-contents --allow-root`로 **플러그인 1개만 비활성화**했다. 이후 `wp plugin get`과 전체 플러그인 목록 모두 `inactive`를 반환했다.
- 변경 전 `active_plugins`, `lwptoc_autoInsert`, `lwptoc_general`, 플러그인 상태 JSON을 서버 전용 `/home/ubuntu/agent-publisher/data/editorial_runs/toc-plugin-20260921/`에 권한 제한을 적용해 보존했다. Git에는 추가하지 않는다. 설정 삭제나 플러그인 제거(언인스톨)는 실행하지 않았다.
- 공개 페이지에서 비활성화 결과가 바로 확인돼 캐시 전체 삭제·서버 재시작은 수행하지 않았다.

## 변경 후 검증 및 영향

| 항목 | 확인 결과 |
| --- | --- |
| 공개 게시물 29개 HTTP | 29개 모두 200, 오류 0개 |
| 자체 목차+LuckyWP 중복 | 4개 → **0개** |
| #218·#243·#304·#349 | 자체 `bloguito-toc` 각 1개 유지, `lwptoc` 각 0개 |
| 다른 25개 공개 글 | 기존 LuckyWP 전용 목차가 사라짐. **현재 별도 목차 0개**이며 글 본문은 이번 작업에서 수정하지 않음 |
| #349 공개 글 추가 검사 | HTTP 200, 목차 1개, 지역/공연 날짜/공연장 표 4행, 공식 예매 링크 4개, FAQ 1개 유지 |
| 홈 | HTTP 200 |
| 기타 플러그인 | `wp plugin list`에서 기존 다른 6개 일반 플러그인 활성 상태 유지 확인 |

**범위상 유의:** 중복은 제거됐지만, 플러그인만으로 목차를 제공하던 25개 글은 이제 목차가 없다. 사용자가 원인 플러그인의 비활성화를 명시적으로 요청했으므로 그대로 적용했다. 이 25개에 Bloguito 자체 목차를 추가하려면 별도 게시물 이관·검수 작업이 필요하며 여기서는 승인 범위를 넓혀 전체 본문을 수정하지 않았다.

## 되돌리는 방법과 잔여 사항

- 기존 기능 복구가 필요하다면 변경 전 백업 및 당시 옵션·활성 플러그인 목록을 확인한 다음 `sudo docker exec wordpress_app wp plugin activate luckywp-table-of-contents --allow-root`로 **재활성화**할 수 있다. 단, 그대로 재활성화하면 4개 글의 중복이 재발하므로 사전에 개별 글 제외 또는 자동 삽입 설정 변경을 검토해야 한다. 롤백은 실행하지 않았다.
- #349의 `post_modified`가 후속 읽기에서 `2026-09-21 18:25:48`로 표시돼 이전 표 개선 기록의 `18:04:24`와 달랐다. 이 작업은 플러그인 활성 상태만 변경했으므로 다른 본문 갱신의 원인은 단정하지 않는다. 공개 페이지에서 표·버튼·FAQ를 다시 확인했다.
- 사용자 화면의 캐시·모바일 브라우저별 실제 시각 렌더는 별도 실기기 테스트를 하지 않았다. 사이트 공개 HTML에서 중복이 없음을 검증했다.
