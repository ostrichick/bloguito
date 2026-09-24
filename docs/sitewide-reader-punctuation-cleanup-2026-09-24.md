# 독자용 가운데점 전면 정리 — 2026-09-24

## 사용자 요청

블로그 전체 게시물에서 여러 요소를 나열할 때 사용하던 가운데점 문자를 쉼표로 통일하고, 이후 작성되는 글에서도 같은 문자를 사용하지 않도록 요청받았다.

## WordPress 전체 게시물 정리

공개, 초안, 검토대기, 예약, 비공개 상태를 포함한 WordPress post 38개를 전수 조사했다.

- 대상 글: 32개
- 제목: 47회
- excerpt: 40회
- 본문: 502회
- 변경 방식: 가운데점과 주변 공백을 쉼표+공백으로 정규화
- slug와 공개 상태는 변경하지 않음

업데이트 전에 32개 대상 글의 제목, 상태, slug, excerpt, 본문 전체를 백업했고, 각 글을 수정하기 직전에 동일한 원본인지 다시 확인했다.

- 전체 백업: agent-publisher/data/editorial_runs/middle-dot-cleanup-20260924T154729.json
- 적용 보고서: tmp/middot-audit-20260924/apply-report.json
- 적용 후 WordPress 38개 글의 제목, excerpt, 본문에서 U+00B7 잔여: **0건**

## 공통 UI 정리

게시물 저장 본문을 모두 수정한 뒤 공개 페이지를 검사했을 때 #99와 #70에서 공유 UI가 별도로 가운데점 문자를 삽입하고 있음을 확인했다.

원인은 운영 MU 플러그인 /var/www/html/wp-content/mu-plugins/bloguito-social-share.php 였다.

- 기존 운영 SHA256: 5e57c16a2f47e98ca24cfba766174ea0a1429138dce92670afb610fe4aa2f00e
- 기존 서버 롤백본: /home/ubuntu/bloguito-social-share.php.pre-comma-20260924T160403
- 새 운영 SHA256: 92ab73e7e97a4c519a36c3088d62a536b21ef060864530646525b6fde34a691a
- 새 기준본: wordpress/mu-plugins/bloguito-social-share.php
- PHP 문법 검사: PASS

공유 버튼 문구와 안내문은 쉼표를 사용하도록 바꿨다.

또한 모든 글 상단과 HTML 제목에 쓰이는 WordPress blogname도 다음처럼 수정했다.

- 이전: 생활정보 24 | 정부 지원금 [가운데점] 절세 [가운데점] 복지 생활 백과
- 현재: 생활정보 24 | 정부 지원금, 절세, 복지 생활 백과

WordPress object cache와 WP Super Cache의 페이지 캐시를 비운 뒤 공개 화면을 재검사했다.

## 재발 방지

공통 편집 시스템은 앞으로 독자에게 보이는 다음 필드에서 U+00B7을 허용하지 않는다.

- 제목과 소제목
- 요약과 본문
- 표 caption, header, cell
- FAQ
- CTA와 관련 글 라벨
- 공식 사이트 안내 라벨
- 하단 출처 라벨

공식 원문 스냅샷과 evidence 인용문은 사실 검증을 위해 원문 그대로 보존한다. 공식 자료 제목 자체에 가운데점이 있어도 독자 화면에는 별도 citation_label을 사용해 쉼표 표기로 제공한다.

validate_bundle()은 독자용 문자열에서 U+00B7을 발견하면 reader_middle_dot_disallowed로 발행을 보류한다.

## 최종 검증

- WordPress 전체 38개 글의 저장 제목, excerpt, 본문: 잔여 0건
- 공개 글 34개 + 홈페이지 1개, 총 35페이지 HTTP 200 전수 확인
- 공개 페이지의 전체 텍스트와 HTML title: 잔여 0건
- 공개 페이지 스캔 결과: tmp/middot-audit-20260924/public-page-scan.json
- 로컬 published_posts.json의 기존 기록 제목도 현재 WordPress 제목으로 동기화
