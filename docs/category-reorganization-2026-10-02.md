# 카테고리 개편 작업 기록 (2026-10-02)

## 기준 상태

- 실서버 WordPress 직접 조회 기준 총 61편.
- 공개 59편, 임시글 2편(`#592`, `#817`).
- 기존 카테고리: `공연/콘서트 예매`, `정부 복지/지원금`, `생활/건강 정보`, `생활 세금/절세 정보`.
- 한 글에는 기본 카테고리 하나만 지정한다.
- 기존 공개 글의 permalink는 변경하지 않는다.

## 새 8개 카테고리

| key | 표시명 | slug | 처리 |
|---|---|---|---|
| `events` | 지역 축제·행사 | `local-events` | 신규 |
| `concert` | 공연·콘서트 예매 | `concert` | 기존 term 이름만 정리, slug 보존 |
| `welfare` | 정부 복지·지원금 | `welfare` | 기존 term 이름만 정리, slug 보존 |
| `tax` | 생활 세금·절세 | `tax` | 기존 term 이름만 정리, slug 보존 |
| `health` | 건강·의료 | `health` | 신규 |
| `transport` | 교통·자동차 | `transport` | 신규 |
| `life-admin` | 생활 행정·서비스 | `life-admin` | 신규 |
| `finance` | 생활경제·금융 | `finance` | 신규 |

`생활/건강 정보` (`life-health`, term 4)는 신규 글의 선택지에서 제거한다. 기존 검토 번들 호환을 위해 코드상 legacy 정의만 유지하고, 신규 분류의 fallback으로 사용하지 않는다.

## 61편 최종 재분류표

### 지역 축제·행사 — 7편

| ID | 상태 | 제목 |
|---:|---|---|
| 239 | 공개 | 2026 추석 궁궐, 종묘, 왕릉 무료개방 |
| 621 | 공개 | 2026 전주 10월 축제 일정 총정리 |
| 641 | 공개 | 2026년 10월 대전 행사 총정리 |
| 648 | 공개 | 2026 부산 10월 축제 일정 총정리 |
| 657 | 공개 | 2026 대구 10월 축제 행사 7곳 총정리 |
| 665 | 공개 | 2026 세종 10월 축제 6곳 |
| 666 | 공개 | 2026 광주 10월 축제 일정 총정리 |

### 공연·콘서트 예매 — 7편

| ID | 상태 | 제목 |
|---:|---|---|
| 70 | 공개 | 2026 무명전설 수원앵콜 크리스마스 콘서트 |
| 99 | 공개 | 2026 로이킴 R:O:Y 서울 콘서트 |
| 349 | 공개 | 김건모 콘서트 예매: 35주년 투어 |
| 463 | 공개 | 2026 남진 데뷔 60주년 전국투어 |
| 464 | 공개 | 2026 이승철 40주년 콘서트 THE VOICE |
| 465 | 공개 | 2026~2027 조용필 콘서트 예매 |
| 466 | 공개 | 주현미 데뷔 40주년 The Queen 용인 콘서트 |

### 정부 복지·지원금 — 7편

| ID | 상태 | 제목 |
|---:|---|---|
| 55 | 공개 | 2026 기초연금 신청 |
| 79 | 공개 | 기초연금 소득인정액 확인 순서 |
| 85 | 공개 | 놓친 복지혜택 찾는 순서 |
| 101 | 공개 | 2026년 기초연금 수급자격 |
| 474 | 공개 | 2026 도시가스 요금 경감 대상과 신청방법 |
| 724 | 공개 | 국민연금 조기수령 vs 연기연금 |
| 727 | 공개 | 실업급여 모의계산 |

### 생활 세금·절세 — 5편

| ID | 상태 | 제목 |
|---:|---|---|
| 125 | 공개 | 국세청 세금포인트 조회, 사용처, 유효기간 |
| 127 | 공개 | 미수령 국세환급금 찾기 |
| 137 | 공개 | 2026년 상반기 근로장려금 지급일, 심사 조회 |
| 139 | 공개 | 국세, 지방세, 건강보험, 통신 미환급금 4종 조회 |
| 144 | 공개 | 2026년 9월 재산세 납부 |

### 건강·의료 — 7편

| ID | 상태 | 제목 |
|---:|---|---|
| 63 | 공개 | 2026~2027 독감 무료 예방접종 |
| 81 | 공개 | 2026~2027 65세 이상 독감 무료접종 일정 |
| 163 | 공개 | 2026 추석 연휴 문 여는 병원, 약국 찾기 |
| 220 | 공개 | 2026 본인부담상한제 환급금 |
| 233 | 공개 | 휴일 편의점 안전상비의약품과 야간 약국 찾기 |
| 598 | 공개 | 만 65세 이상 임플란트 건강보험 |
| 730 | 공개 | 2026 국가건강검진 대상자 조회 |

### 교통·자동차 — 11편

| ID | 상태 | 제목 |
|---:|---|---|
| 119 | 공개 | 기후동행패스 혜택 |
| 145 | 공개 | 2026 추석 고속도로 통행료 무료 |
| 217 | 공개 | 2026 추석 KTX 취소표 확인, 예매 |
| 219 | 공개 | 2026 추석 전기차 충전 할인 |
| 227 | 공개 | 교통민원24 이파인 과태료, 범칙금 조회 |
| 235 | 공개 | 2026 운전면허 적성검사, 갱신, 재발급 |
| 237 | 공개 | 2026 추석 무료 공공주차장 찾기 |
| 345 | 공개 | 추석, 설 고속버스 취소표 예매 방법 |
| 393 | 공개 | 인천공항 출국장 대기시간 확인 |
| 470 | 공개 | 자동차검사 기간 조회와 예약 |
| 560 | 공개 | 하이패스 미납통행료 조회, 납부 |

### 생활 행정·서비스 — 9편

| ID | 상태 | 제목 |
|---:|---|---|
| 105 | 공개 | 서초구 소형폐가전 무료 배출 |
| 113 | 공개 | 우체국 주거이전 우편물 전송서비스 연장 |
| 121 | 공개 | 주민등록등본 인터넷 무료 발급 |
| 140 | 공개 | 온라인 여권 재발급 후 수령 |
| 229 | 공개 | 2026 추석 서울 쓰레기 배출일 |
| 304 | 공개 | 전국 폐가전 무료수거 |
| 471 | 공개 | 안심상속 원스톱서비스 신청 |
| 475 | 공개 | 전입신고 온라인 신청 |
| 559 | 공개 | 모바일 주민등록증 발급 |

### 생활경제·금융 — 8편

| ID | 상태 | 제목 |
|---:|---|---|
| 218 | 공개 | 내보험 찾아줌 숨은 보험금 조회 |
| 225 | 공개 | 추석 은행 탄력점포, 이동점포 찾기 |
| 231 | 공개 | 어카운트인포 휴면계좌, 휴면예금 찾기 |
| 241 | 공개 | 명절 교대운전 보험 확인 |
| 243 | 공개 | 통신 미환급액 조회, 환급 신청 |
| 592 | 임시글 | 카드포인트 통합조회 |
| 609 | 공개 | 2027 최저시급 10,700원 |
| 817 | 임시글 | 주택연금 예상수령액 조회 |

## 목표 분포

| 카테고리 | 글 수 |
|---|---:|
| 지역 축제·행사 | 7 |
| 공연·콘서트 예매 | 7 |
| 정부 복지·지원금 | 7 |
| 생활 세금·절세 | 5 |
| 건강·의료 | 7 |
| 교통·자동차 | 11 |
| 생활 행정·서비스 | 9 |
| 생활경제·금융 | 8 |
| **합계** | **61** |

## 마이그레이션 원칙

1. 신규 5개 term을 만든 뒤 실제 term ID를 코드에 반영한다.
2. 기존 `concert`, `welfare`, `tax`는 slug를 유지하고 표시명만 변경한다.
3. 모든 글은 위 표의 카테고리 하나만 갖도록 원자적으로 교체한다.
4. 글 제목, 본문, excerpt, slug, 공개 상태, 발행일, 대표이미지, SEO 메타는 변경하지 않는다.
5. `life-health`는 모든 글이 빠진 것을 확인한 뒤 신규 사용을 중단한다. 최초 cutover에서는 rollback을 위해 빈 term을 보존하고, 삭제는 별도 후속 작업으로 한다.
6. `/category/life-health/`의 최종 폐기 시점에는 404로 방치하지 않고 새 분류 안내 경로 또는 적절한 목적지로의 이동 정책을 별도 검토한다. 서로 다른 6개 생활 카테고리로 분할됐으므로 임의의 단일 새 카테고리로 곧바로 301하지 않는다.
7. 적용 전 WordPress term, menu, post-category 매핑을 JSON으로 보관하고 적용 후 동일 범위를 재조회한다.
8. 프로젝트의 신규 분류 resolver는 알 수 없는 key를 임의 카테고리로 보내지 않고 오류로 차단한다.

## 2026-10-02 적용 결과

- 신규 term ID: `events=274`, `health=275`, `transport=276`, `life-admin=277`, `finance=278`.
- 기존 term ID 유지: `concert=2`, `welfare=3`, `tax=102`.
- 61편 전체를 명시적 `post ID → term ID` 매핑으로 이동했고, 각 글은 정확히 카테고리 하나만 갖도록 저장 후 즉시 readback했다.
- 이동 전후 61편의 `post_status`, 제목, `post_name`, 본문 SHA256, permalink를 전수 비교한 결과 변경 0건이었다. 카테고리만 목표 term으로 바뀌었다.
- 공개글 term count는 지역 축제·행사 7, 공연·콘서트 예매 7, 정부 복지·지원금 7, 생활 세금·절세 5, 건강·의료 7, 교통·자동차 11, 생활 행정·서비스 9, 생활경제·금융 6이다. 금융의 임시글 #592, #817까지 포함하면 전체 8편이다.
- 기존 `life-health` term 4는 글 0개, 메뉴 미노출 상태로 남겼다. 신규 코드에서는 active category가 아니며 rollback/과거 reviewed bundle 해석을 위한 legacy 정의만 유지한다.
- WordPress 기본 카테고리는 기존 term 2(공연)에서 term 1(미분류)로 변경했다. 자동화는 명시적 카테고리를 요구하므로 수동 미분류 글이 공연으로 잘못 들어가는 위험을 제거한다.
- permalink 구조는 `/%postname%/`로 확인돼 이번 taxonomy 이동은 개별 글 URL에 영향을 주지 않는다.
- cutover 직전 DB 백업은 서버 `/tmp/bloguito-category-reorg-20261002-pre.sql.gz`에 생성했다. 별도로 61편 무결성, category, menu, option 스냅샷을 작업용 `scratch/category-reorg-20261002/`에 보관했다.

### 메뉴

WordPress taxonomy는 평면으로 유지하고 메인 메뉴에서만 두 그룹으로 묶었다.

- `생활정보` (menu item 825): 정부 복지·지원금, 생활 세금·절세, 건강·의료, 교통·자동차, 생활 행정·서비스, 생활경제·금융
- `문화·행사` (menu item 832): 지역 축제·행사, 공연·콘서트 예매
- 기존 `생활/건강 정보` 메뉴 항목은 제거했다.
- 기존 `사이트 소개` menu item은 DB에 남아 있지만 기존 MU-plugin의 primary-menu 필터가 계속 숨긴다.

변경 직후 공개 홈은 WP Super Cache의 기존 HTML을 한 차례 반환했다. `wp_cache_clear_cache()`로 캐시를 비운 뒤 cache-busting 요청과 실제 HTML에서 새 두 상위 메뉴, 8개 하위 카테고리, `menu-item-has-children` 구조를 확인했고 `생활/건강 정보` 메뉴는 더 이상 노출되지 않았다.

### 로컬 카탈로그

`python scripts/sync_post_catalog.py`를 2026-10-02 12:59에 실행해 실서버 61편을 다시 반영했다. 현재 카탈로그는 공개 59편, 임시글 2편이며 새 8개 표시명을 사용한다. 지역 행사 카테고리를 시즌형으로 인식하도록 분류 보조 로직도 함께 갱신했다.

### 운영 자동발행 런타임

운영 `/home/ubuntu/agent-publisher`는 Git checkout이 아닌 별도 배포 복사본이며 기존 `config.py`가 4개 카테고리만 알고 있었다. 다음 08:00 cron에서 `life-health`를 다시 사용할 수 있어 cutover 당일 최소 런타임 패치를 적용했다.

- 로컬에서 검증한 `config.py`를 배포해 active `CATEGORIES`를 8개 term ID와 일치시켰다.
- 운영 `main.py`는 전체 파일을 교체하지 않고 category CLI choices만 `CATEGORIES` 기반 동적 목록으로 바꿨다. 서버에 아직 배포되지 않은 다른 최신 함수에 대한 불필요한 의존성을 만들지 않았다.
- 운영 `data/search_briefs.json`은 로컬 파일로 통째로 덮지 않았다. 서버에 이미 있던 10개 reviewed brief 중 기존 `life-health` 4개만 `transport` 1개, `life-admin` 3개로 이관했다. 로컬에만 있던 신규 주제 3개는 이번 taxonomy 작업으로 운영 자동발행에 추가하지 않았다.
- 운영 venv에서 `main.py --help`가 `events, concert, welfare, tax, health, transport, life-admin, finance, all`을 노출하는지 확인했다.
- 운영 venv에서 `life-health`가 active `CATEGORIES`에 없고 legacy로만 남는지, 실서버 term ID와 표시명이 일치하는지 확인했다.
- 배포 전 세 파일은 `/home/ubuntu/agent-publisher/backups/category-reorg-20261002T040436Z`에 보관했다. 배포 검증 실패 시 세 파일을 자동 복원하도록 적용했고 실제 검증은 통과했다.

### 2026-10-06 legacy `life-health` 재점검

- WordPress term ID 4 (`life-health`)는 현재 count=0이고 primary menu에 없으며, 기본 카테고리도 term 1이다. 즉 active taxonomy에서는 사용되지 않는다.
- 그러나 `/category/life-health/`는 현재 HTTP 200으로 남아 있어 term을 즉시 삭제하면 기존 archive URL을 처리할 정책 없이 404로 바꿀 수 있다.
- reviewed state에는 `life-health` category key를 가진 historical manifest가 여전히 복수 존재한다. 2026-10-06 로컬 reviewed index와 운영 감사 모두 legacy reference가 남아 있음을 확인했지만, status reconciliation/compact state 시점에 따라 index별 개수는 달라질 수 있으므로 개수를 운영 계약으로 고정하지 않는다. 이 기록은 현재 live category를 다시 `life-health`로 바꾸는 근거가 아니라 과거 reviewed bundle 재생·검사 호환용이다.
- `config.py`의 `LEGACY_CATEGORIES`, `critical_facts.py`, `temporal_validation.py`와 회귀 테스트도 이 historical parsing을 의도적으로 유지한다. 따라서 이번 후속에서는 WordPress term과 legacy resolver를 삭제하지 않는다.
- 향후 제거 순서는 archive URL 처리 정책 결정 → redirect/landing 검증 → historical manifest 호환성 이전 → 백업/readback → term 삭제 → 마지막으로 legacy resolver 제거다.

### 코드 검증

- 카테고리 관련 표적 회귀 220개 통과.
- 추가 회귀 수정 후 source provenance, renderer/interlink, resolver 표적 66개 통과.
- `git diff --check`, strict UTF-8 검사, 변경 Python `py_compile` 통과.
- 전체 Python suite는 786개 중 3 failures, 8 errors, 1 skipped였다. 이번 개편에서 발견한 행사 category fixture와 생활행정 관련글 추론 회귀 2건은 수정 후 사라졌다. 남은 8 designer-safety 오류와 public-fast 3 failures는 작업 전 clean `origin/main`에서도 확인된 기존 baseline 계열이다.

## 2026-10-02 표시명 2차 정리

초기 8개 분류의 범위와 term ID, slug, 글 배치는 유지하면서 중복되는 `생활` 접두어와 `·` 구분자를 정리한다. 이번 후속 작업에서는 글을 다른 term으로 이동하지 않는다.

| key | 기존 표시명 | 새 표시명 | term ID | slug |
|---|---|---|---:|---|
| `events` | 지역 축제·행사 | 지역 축제/행사 | 274 | `local-events` |
| `concert` | 공연·콘서트 예매 | 공연/콘서트 | 2 | `concert` |
| `welfare` | 정부 복지·지원금 | 복지/지원금 | 3 | `welfare` |
| `tax` | 생활 세금·절세 | 세금/절세 | 102 | `tax` |
| `health` | 건강·의료 | 건강/의료 | 275 | `health` |
| `transport` | 교통·자동차 | 교통/자동차 | 276 | `transport` |
| `life-admin` | 생활 행정·서비스 | 행정/생활서비스 | 277 | `life-admin` |
| `finance` | 생활경제·금융 | 금융/경제 | 278 | `finance` |

`행정/생활서비스`는 주민등록·여권 같은 행정 글뿐 아니라 폐가전 수거, 쓰레기 배출, 우편물 전송 같은 현재 글도 함께 포괄하기 위해 선택했다. `행정/민원`으로 좁히지 않는다.

적용 전에는 운영 WordPress의 term, 메뉴, 운영 `config.py`, 전체 post-category 매핑과 각 글의 상태·제목·slug·본문 SHA256·permalink를 다시 스냅샷한다. 적용 후에는 동일 범위를 재조회해 term ID, slug, 글 배치와 글 자체가 보존됐는지 비교한다.

### 표시명 2차 정리 적용 결과

- cutover 직전 운영 글은 총 63편으로 공개 61편, 임시글 2편이었다. 임시글은 #592(`finance`)와 #841(`welfare`)였고 모든 글이 카테고리 하나만 갖고 있었다.
- WordPress term ID와 slug는 그대로 유지하고 8개 표시명과 설명만 갱신했다. 공개글 term count는 `events=7`, `concert=7`, `welfare=7`, `tax=5`, `health=7`, `transport=11`, `life-admin=10`, `finance=7`로 cutover 전후 동일했다.
- 운영 `/home/ubuntu/agent-publisher/config.py`는 전체 파일 교체 없이 8개 표시명만 치환했다. 적용 전 파일은 `/home/ubuntu/agent-publisher/backups/category-name-refresh-20261002T083311Z/config.py`에 보관했다.
- 적용 전후 63편의 `post_status`, 제목, `post_name`, 본문 SHA256, permalink, category term ID/slug를 비교한 결과 변경 0건이었다. 글 이동도 없었다.
- 메인 메뉴의 category taxonomy 항목은 term 이름을 자동 반영해 별도 menu item 수정 없이 새 표시명으로 바뀌었다. 상위 그룹 `생활정보`, `문화·행사` 구조는 유지했다.
- WP Super Cache를 비운 뒤 기본 홈 URL의 실제 HTML에서 새 8개 이름을 모두 확인했고 이전 8개 표시명은 0건이었다. 8개 category archive URL은 모두 HTTP 200이었다.
- `python scripts/sync_post_catalog.py`로 최신 63편을 다시 동기화했고 `docs/POST_CATALOG.md`에서 이전 표시명은 0건이다.
- 최신 `main` 위로 rebase한 최종 상태에서 카테고리 mapping, catalog fallback, editorial/indexing, designer routing 표적 테스트와 `git diff --check`, strict UTF-8, `py_compile`은 통과했다. 유효 형식의 Kakao 테스트 키를 주고 실행한 전체 suite는 822개 전부 통과했고 1개가 skip됐다.
