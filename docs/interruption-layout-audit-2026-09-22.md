# 중단 작업 감사: 본문 레이아웃·목차·상자·표 접근성 — 2026-09-22

## 판정과 시점

**2026-09-22 약 17:23~17:30 KST, 읽기 전용 재검증.** 최신 실측 기준은 [`resume-layout-current-census-2026-09-22.md`](resume-layout-current-census-2026-09-22.md)의 16:29:36 KST 공개 REST 30/30편 스냅샷이다. 17시대 공개 REST를 별도 재요청해 `HTTP 200`, `X-WP-Total=30`, 응답 배열 30개를 확인했고, 스냅샷과 **각 게시물 ID의 `content.rendered` SHA256 및 `modified`를 대조한 변화는 0건**이었다. 이 확인은 17시대 조회까지의 사실이며 그 뒤의 WordPress 갱신과 배포 직전 원문을 보증하지 않는다. 본 감사는 기존 코드·문서·WordPress·운영 서버를 수정하지 않고 이 신규 보고서만 작성했다. 로컬 HEAD `c58b7aa`, 여러 작업자의 추적/미추적 변경 보존.

**결론: 현행 로컬 PHP 세 파일은 테스트 가능한 배포 후보이나 실제 운영에는 모두 미설치다.** 서버 `wordpress_app:/var/www/html/wp-content/mu-plugins/`의 새 읽기 전용 `ls`와 `sha256sum`에서 `bloguito-post-id-column.php`(`6e3c383122341d37c0a1921a4c0cc62bf1d82b964775e52b459f2d478d6d47cd`)와 `bloguito-social-share.php`(`5e57c16a2f47e98ca24cfba766174ea0a1429138dce92670afb610fe4aa2f00e`) 두 파일만 확인했다. PHP CLI는 8.3.33, LuckyWP TOC 2.1.14는 `inactive`, WP Super Cache 3.1.3은 `active`, `advanced-cache.php`는 drop-in으로 확인됐다. 서버 설치 전까지 로컬 PHP의 동작은 공개 페이지에 나타나지 않는다.

| 작업 / 로컬 후보 | 현재 정확한 영향 범위 | 상태와 SHA256 |
| --- | --- | --- |
| 목차 `wordpress/mu-plugins/bloguito-legacy-toc.php` | 현재 13편: **70, 85, 99, 103, 119, 125, 139, 140, 144, 145, 163, 217, 220**. 다른 17편 원본 출력 유지. 구형 63·77·81·219는 내용 길이/앵커 조건상 목차를 추가하지 않는다. | 로컬 파일 존재, 서버 **미설치**. `6240c15ffe527665cacc7fd773944374a9cd7533f9a4c563206b99c4d2fedcdb`. Git 추적 파일. |
| 구형 초록색 박스 `wordpress/mu-plugins/bloguito-legacy-callout-spacing.php` | `#11775a` 좌측 테두리 상자 **16편**의 직계 문단 CSS 선택자 일치: 63,70,77,81,99,103,119,125,139,140,144,145,163,217,219,220. 그중 하단 여백을 인라인 지정하지 않은 **9편**: 70,99,119,140,144,145,163,217,220. #85의 `#147d64`와 신규 요약 13편은 불일치. | 로컬 파일 존재, 서버 **미설치**. `c9bae087d11eeb50ece97055fca99ed315a660730757063320eda908faaeba4b`. Git 미추적 파일, 다른 작업자의 원본 보존. CSS는 HTML의 잘못된 `</p>`를 저장 원고에서 고치지 않는다. |
| #85 표 `wordpress/mu-plugins/bloguito-legacy-table-accessibility.php` | 현재 #85 **표 두 개만** 출력 시 변경. 표 원문 셀·순서 보존, caption 2/열 머리글 6/행 머리글 7, 수평 스크롤 영역 2. 나머지 29편 불변. | 로컬 파일 존재, 서버 **미설치**. `afe44b8ec982c8f2856506ea41d6f3edf5bd1511e9fc856aa4a85c1f0a683f5f`. Git 미추적 파일. 전체 입력 `$content` SHA가 허용한 네 가지 중 하나가 아니면 오류 없이 원문 반환. |

현행 30편은 신규 렌더러 `.bloguito-article` **13편**, 구형 **17편**이다. 신규 13편 모두 자체 목차가 하나 있다. 위 TOC 소스는 기존 25개 ID 허용목록을 갖지만 신규 구조 감지로 해당 13편을 배제한다. `missing_toc_candidate=17`은 실제 TOC 설치 대상 17편을 뜻하지 않는다. [`legacy-layout-rollout-2026-09-22.md`](legacy-layout-rollout-2026-09-22.md)·[`legacy-layout-approval-package-2026-09-22.md`](legacy-layout-approval-package-2026-09-22.md)의 **19편 목차/24편 초록 상자**는 일부 게시물이 구형이던 과거 시점의 결과다. 현재 운영 적용 집합으로 복사하지 않는다.

## 이번에 직접 수행한 검증

- 로컬 PHP 세 파일의 SHA256을 재계산하여 위 기록과 완전 일치 확인. 실제 운영 PHP 8.3.33에 세 소스 각각을 **표준입력만으로** 전달해 `php -l` **3/3 종료 0**, 모두 `No syntax errors detected in Standard input code`. 서버 소스 파일 생성·WordPress 부트스트랩 없음.
- `wordpress/tests/legacy-toc-contract-test.php`에 현재 목차 PHP를 메모리에서 삽입하여 동일 운영 PHP 표준입력으로 실행: **23/23 검사 통과, 종료 0**.
- `wordpress/tests/legacy-table85-accessibility-test.php`와 기존 격리 fixture `tmp/legacy_audit_20260922/layout-worker2/public-posts-snapshot.json` 및 #85 저장/출력 원문에 현재 두 PHP 소스를 메모리에서 삽입하여 운영 PHP 표준입력 실행: **101 검사 통과, 30개 게시물 중 변경 ID `[85]`만 확인**. REST+TOC 기준 SHA `0b5ae88f3a60e5a7958806f7e1861e8c8525ddbe94d47ba33d9f390118e375f3`와 일치. 기존 fixture 실행기 전체를 재실행하지 않고 쓰기 부분을 제외한 동일 PHP 계약 하네스만 재실행했다. 첫 PowerShell 대용량 JSON 직렬화 시도는 결과 없이 오래 실행돼 해당 감사 프로세스만 종료하고 위 Python 메모리 fixture로 성공적으로 다시 검증했다.
- `./agent-publisher/.venv/Scripts/python.exe -B -m unittest discover -s agent-publisher/tests -p test_legacy_post_audit.py -q`는 **14건 통과, 종료 0**. 현행 30편 스냅샷에 대한 기존 TOC+표 순수 함수 **147건**과 #85 브라우저 미리보기 3상태는 최신 census 문서 및 `tmp/legacy_audit_20260922/current-census-worker3-final/php-current-census.json`에 기록돼 있다. 이번 테스트는 실제 WordPress 훅·GeneratePress CSS·캐시를 통한 운영 페이지 통합 테스트가 아니다.
- 원격 `wp plugin list --fields=name,status,version --format=csv` 및 운영 MU SHA를 읽기 전용으로 재확인했다. `/home/ubuntu/backups/bloguito_backup_20260922_040001.tar.gz`는 04:00 생성 약 16MB로 **파일 존재만** 직접 확인했으며, 이 파일을 v3 완전백업이나 독립 복구 성공으로 판단하지 않는다. prime이 별도 수행한 백업 검증 결과는 해당 작업 기록을 기준으로 취급한다.

## 설치·원복 판단을 좌우하는 남은 작업

1. **현행 대상 범위 고정:** 설치 직전 공개 REST 30/30을 한 번 더 조회해 수정시각과 SHA·13편의 TOC 변경 ID·녹색 16편·#85 저장 `post_content` SHA `499afcf30df2cfbfdca7041e80bc139c90e1a8da5d5348837b77ee2b8e2cf065` 및 REST 출력 SHA `9791443dbf4c5c9f43236c034bb4e321f8dc14cc69fed44b7710d7b98cbe644a`를 확인한다. REST 출력 SHA는 저장 본문 갱신용 SHA를 대체하지 않는다. 범위 승인에 13편 전부가 포함되지 않으면 TOC 허용목록을 좁혀 다시 검사한다. 게시물 본문 내용·출처의 승인과 출력용 CSS/MU 승인도 구별한다.
2. **운영 백업/스테이징:** 운영 named volume 내부 실제 MU 경로에 한 파일씩 설치한다. `/home/ubuntu/wordpress` 저장소에 복사하는 것으로는 운영 설치가 아니다. 원본 기존 MU 두 파일과 그 SHA를 보호하고, 설치 파일 이름 부재·독립된 스테이징 이름·실제 SHA·운영 PHP 문법을 확인한다. 04:00 파일명/크기만으로 v3 백업을 주장할 수 없으며, 배포 책임자가 검증한 실제 v3 아카이브의 무결성·복구 대상까지 확인해야 한다. `wordpress/setup.sh`, `install_editorial_release.py`, 전체 DB 복원, Docker Compose 재생성은 단일 MU 배포 수단이 아니다. 안전한 실제 한 파일 설치 및 `.disabled` 롤백 명령은 최신 [`resume-layout-current-census-2026-09-22.md`](resume-layout-current-census-2026-09-22.md) **82~151행**에 있고 해당 bash 두 블록은 과거 `bash -n` 검증만 받은 예시다.
3. **한 파일 설치 후 멈춰 실증:** TOC 한 파일만 먼저 설치했다면 서버 MU SHA/`must-use` 확인, 비로그인 첫 진입은 규정된 `?utm_source=bloguito_qa_agent&utm_medium=internal_test&utm_campaign=site_checks`, 공개 30편에서 **13편 TOC 추가·17편 원래 유지·중복 0·앵커 1:1**, 특히 #85 요약 안 H2 제외 및 원래 두 표 보존을 확인한다. 페이지 캐시에서 옛 HTML이 제공되는지 먼저 확인하고 승인된 캐시 운영 절차로만 무효화한다. `wp cache flush`만으로 WP Super Cache의 페이지 캐시가 전부 제거된다고 보지 않는다. 첫 파일 실제 검증 후에만 CSS, 그 다음 표 파일을 독립적으로 설치·검증한다.
4. **상자/표 실제 사용자 QA:** CSS 설치 후 선택자 해당 16편과 제외 14편(#85·신규 요약 포함)을 DOM 및 `getComputedStyle`/상자 좌표로 전후 대조한다. CSS는 저장 HTML의 잘못된 문단 닫힘을 수리하지 않는다. 표 설치 후에는 **#85 두 표 모두** caption 2, `scope=col` 6, `scope=row` 7, 키보드로 포커스 가능한 가로 스크롤 2개와 29편 무변경을 확인한다. 전체 `$content` SHA 차이로 #85 필터가 **조용히 아무것도 적용하지 않을 수 있다**. 파일 설치·PHP lint 성공만으로 동작 판정하지 않는다. 360/390px 전체 본문·키보드 스크롤/앵커와 브라우저 **실제 네이티브 200% 확대**, 가능한 보조기술 사용을 별도로 검증한다. 현재 브라우저 결과의 CSS `zoom:200%`는 네이티브 확대 통과가 아니다.
5. **한 파일 단위 원복:** 실제 설치된 파일이 승인된 배포 SHA와 정확히 같고 `.disabled` 대상이 비어 있을 때만 같은 파일을 MU 로더가 읽지 않는 숨김 이름으로 이동한다. 기존 두 MU·타 개선 파일·WordPress DB/게시물·다른 작업자 변경은 그대로 둔다. 이후 실제 캐시·HTML·30편 영향 범위를 재확인한다. 해시가 달라졌거나 다른 파일이 있으면 중단하고 변경 원인을 조사한다. 전체 DB 복원을 단일 파일 롤백으로 사용하지 않는다.

## 브라우저 및 본문 잔여 결함

최신 기록의 신규 11편 × 360/390/1280 CSS 200% 근사 **33/33 자동 구조 검사 통과**는 MU 설치 전 결과이며, 해당 검사 세션의 콘솔 자원 오류 **13건**을 오류 0으로 축소할 수 없다. #85 실제 PHP 변환 로컬 미리보기는 3개 화면 구조 PASS, 모바일 키보드 스크롤 260/230px, 콘솔 차단 자원 오류 1건이지만 **운영 MU 설치 후의 결과가 아니다**. 실제 기기·스크린리더·네이티브 확대는 미검증이다.

별도 콘텐츠 문제는 이 레이아웃 승인으로 해결되지 않는다. #218은 이전 직접 CTA의 실제 브라우저 404를 확인한 뒤 CTA 자체가 제거됐으나 공식 출처 목록에 같은 작동 실패 URL이 하나 남았다. #127의 홈택스 출처 링크는 브라우저에서 메인으로 이동하고 원고의 직접 조회 입력 화면은 확인되지 않았다. 게시물의 공식 근거/CTA 갱신은 `editorial_cli.py`의 전체 원문·모델 검토·해시 게이트에 따라 별도 처리한다. #85 저장 HTML 자체를 표 후보 HTML로 바꾸는 경로는 전체 구조화 bundle 검토/정상 `update-existing` 또는 동등하게 승인된 안전 경로가 준비되기 전 보류한다. 이 감사는 해당 결함을 새로 재현하거나 게시물을 편집하지 않았다.

**작업 경계:** 새 파일 이외의 저장소 파일 수정·Git stage/commit/push 없음. SSH는 MU 목록/SHA·플러그인 상태·PHP stdin 테스트·백업 파일 메타데이터 확인에만 사용했다. WordPress 쓰기, 파일 설치/삭제, 캐시 비우기, cron 변경, 배포 및 운영 브라우저의 MU 후속 검사는 하지 않았다.
