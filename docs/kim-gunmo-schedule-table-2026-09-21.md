# 김건모 공연 일정 표 개선·운영 반영 — 2026-09-21

## 대상 및 변경 범위

- 대상은 기존 WordPress 공개 글 **#349** 하나다. 공개 주소: <https://lifeinfo24.org/?p=349>.
- 원래 제목 `김건모 콘서트 예매: 35주년 투어 대구·전주·광주·고양 일정`, 슬러그, `publish` 상태를 유지했다. 기존 [초안 생성 기록](kim-gunmo-concert-draft-2026-09-21.md)의 `draft`는 당시 상태이며 수정 직전 실제 상태는 `publish`였다.
- `STEP 1. 지역별 공연 일정 한눈에 보기`의 지역별 날짜·공연장 설명 두 문단을 **지역 / 공연 날짜 / 공연장** 3열, 4행의 `<table>`로 대체했다. 기존 상단 공식 YES24 지역별 예매 링크 네 개와 STEP 2 안내, FAQ, 공식 출처를 유지했다. 새 가격·공연 시간·좌석·할인·실시간 판매 가능 여부는 넣지 않았다.

## 공식 출처와 검증 범위

YES24 공식 목록: <https://m.ticket.yes24.com/Genre/GenreBridge.aspx?genre=15456&id=1560>. 2026-09-21에 `fetch_sources()`의 실제 HTML 텍스트에서 다음 네 일자·장소를 직접 대조했다.

| 지역 | 공연 날짜 | 공연장 | 공식 목록에 있는 개별 상품 |
| --- | --- | --- | --- |
| 대구 | 2026.10.10 | 대구 엑스코 동관 6홀 | `Perf/59876` |
| 전주 | 2026.10.31 | 한국소리문화의전당 야외공연장 | `Perf/59992` |
| 광주 | 2026.12.05 | 광주여대 유니버시아드 체육관 | `Perf/60111` |
| 고양 | 2026.12.26 | 킨텍스 2전시장 9A홀 | `Perf/60238` |

공식 목록 요청 HTTP 200, HTML 안의 네 상품 URL을 모두 확인했다. 과거 bundle 원문에는 실제 최신 HTML에서 재확인되지 않는 `예매상태: 예매중` 및 예매·공연 기간 라벨이 수동 추가되어 있었다. 과거 원문 SHA256은 `044829f3b89c8829718c55563701722c0697f3cfa7534cda15aa387760a04e42`, 실제 새 수집 원문 SHA256은 `b33e1004a45ace611d64000f806cf817e37708e4dbaa1fd1fa411ac036ef705f`로 불일치했다. 해당 라벨과 기존 의미 검토 기록을 재사용하지 않았다.

대신 목록의 지역·공연일·공연장·예매 진입 링크만 증명하는 `schedule_listing_only`를 추가했다. 공식 원문에서 추출한 실제 공연 행과 표의 전체 행을 일치시켜 검사하며, 공연 종료일을 판매 종료일로 대체하지 않는다. 구매 가능성은 검증된 사실이 아니므로 단정하지 않는다. 새 원문 출처 해시 재검증과 독립 모델 의미 검토는 그대로 수행한다.

## 실행과 검증

- 기준 커밋: `22275fc`. 작업 이전부터 수정돼 있던 `curator.py`, `publisher.py`, `test_editorial_system.py`, `test_ticket_validation.py`, 미추적 최적화 감사 문서는 편집·커밋하지 않았다.
- 로컬 `unittest discover -s agent-publisher/tests -q`: **179개 테스트 통과**. 표 렌더·행 근거·HTML escaping·빈 문단의 표 섹션 및 YES24 목록 일치/위변조/판매 상태 오인 방지 테스트 포함.
- 서버 런타임 코드 `agents/editorial.py`, `agents/editorial_writer.py`, `agents/temporal_validation.py` 및 공통 편집 지침을 적용했다. 이전 파일 사본은 `/home/ubuntu/agent-publisher/data/editorial_runs/staging349-20260921/backup/`에 보관했다. 서버 venv 문법 검사 통과.
- WordPress 목록 실조회에서 대상 #349가 `publish`임을 확인한 뒤 나머지 게시물 39개만 포함한 중복 점검 인벤토리로 새 bundle을 독립 모델 검토했다. `editorial_cli.py review` 최종 보고서 `status=ready`, `reasons=[]`.
- 수정 전 WordPress 본문 SHA256: `4110ce3369478313f589573d2dd4323ed4499600b68dd44da528120672a1529b`. 해당 해시와 대상 ID를 지정하여 **`editorial_cli.py update-existing --post-id 349 --expected-content-sha256 ... --confirm-update`** 경로로 적용했다. 결과 `Updated public post ID: 349`.
- WordPress 원본 전체 백업: `/home/ubuntu/agent-publisher/data/editorial_runs/public-edit-349-20260921T180420.json` (서버 로컬만, Git 제외). 기존 복원 기록으로 보유하며 **복원 실행은 하지 않았다**. 배포 이후 WP 수정 시각 `2026-09-21 18:04:24`, 제목·슬러그·`publish` 상태 동일, 편집 잠금 해제 확인.
- WP 실제 `post_content` 및 공개 웹페이지 `https://lifeinfo24.org/?p=349`에서 독립 확인: 공개 HTTP 200, 정확한 3열/4행 표, 예매 링크 4개, FAQ 1개, 공식 출처 링크 1개, `overflow-x:auto` 가로 스크롤 모두 일치. 원본과 갱신 본문 모두 이미지 `<img>` 0개였으므로 기존 본문 이미지 손실 없음. 실제 모바일 기기의 시각적 사용성은 별도 실기기 시험을 하지 않았다.

## 운영·보존 메모

이번 개선은 #349의 본문만 갱신한 것이며 #218이나 기타 게시물은 수정하지 않았다. `tmp/kim349_20260921/` 및 서버 `data/editorial_runs/`의 원고·백업·검토 기록은 런타임 자료로 Git에 올리지 않는다. 문제가 발생하면 원본 백업과 현행 해시를 대조하고 새 승인·검토를 거쳐 안전한 갱신 경로로 복구한다. 직접 WP-CLI 수정으로 검증을 우회하지 않는다.
