# -*- coding: utf-8 -*-
"""Synchronize WordPress posts with local docs/POST_CATALOG.md via Direct SSH."""
import json
import hashlib
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

for _stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if callable(_reconfigure):
        try:
            _reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

ROOT = Path(__file__).resolve().parents[1]
SSH_HOST = "bloguito"
CATALOG_MD = ROOT / "docs" / "POST_CATALOG.md"
CATALOG_INVENTORY_JSON = ROOT / "agent-publisher" / "data" / "catalog_inventory.json"
EDITORIAL_DATA_DIR = ROOT / "agent-publisher" / "data"
BACKLOG_HEADING = "## 3. 🎯 추진 예정 백로그 (Topic Backlog)"

DEFAULT_BACKLOG_ROWS = [
    "| **1순위** | **만 65세 이상 임플란트 건강보험 적용 기준** | 1인당 평생 2개(30% 본인부담), 뼈이식 비급여 팩트, 2027 완전 무치악 적용 확대 안내 | `임플란트 건강보험` | 국민건강보험공단 |",
    "| **2순위** | **2026 국민연금 조기노령연금 vs 연기연금 비교** | 조기수령 감액률(연 6%) vs 연기연금 가산율(연 7.2%), 건강보험 피부양자 탈락 기준 | `국민연금 조기노령연금` | 국민연금공단 |",
    "| **3순위** | **2026 국가건강검진 짝수년도 연말 연장 신청법** | 짝수년도 대상자 조회, 연말 검진 대란 대비 전년도 미수검자 이월 신청 방법 | `국가건강검진` | 국민건강보험공단 건강iN |",
    "| **4순위** | **노인장기요양보험 등급 신청 및 혜택** | 1~5등급 판정 기준, 재가급여(방문요양) vs 시설급여, 가족요양비 지원 요건 | `노인장기요양보험` | 국민건강보험공단 |",
    "| **5순위** | **만 65세 이상 시니어 숨은 복지 혜택 5종** | 지하철 무임승차, KTX 30% 할인, 통신비 감면(월 최대 12,100원), 국공립 무료입장 | `65세 이상 혜택` | 복지로, 과기정통부 |",
]

CATALOG_PHP = """<?php
$q = new WP_Query(array(
    'post_type' => 'post',
    'post_status' => array('publish', 'draft', 'pending', 'future', 'private'),
    'posts_per_page' => -1,
    'orderby' => 'ID',
    'order' => 'ASC'
));
$o = array();
foreach ($q->posts as $p) {
    $id = $p->ID;
    $content = (string)$p->post_content;
    $categories = wp_get_post_categories($id, array('fields' => 'names'));
    $o[] = array(
        'ID' => (int)$id,
        'post_title' => (string)$p->post_title,
        'post_status' => (string)$p->post_status,
        'post_name' => (string)$p->post_name,
        'permalink' => (string)get_permalink($id),
        'post_date' => (string)$p->post_date,
        'content_sha256' => hash('sha256', $content),
        'content_urls' => array_values(array_unique(wp_extract_urls(html_entity_decode($content, ENT_QUOTES|ENT_HTML5, 'UTF-8')))),
        'category_slugs' => wp_get_post_terms($id, 'category', array('fields' => 'slugs')),
        'categories' => array_values($categories),
        'rank_math_focus_keyword' => (string)get_post_meta($id, 'rank_math_focus_keyword', true),
        'rank_math_seo_score' => (string)get_post_meta($id, 'rank_math_seo_score', true)
    );
}
echo wp_json_encode($o);
"""

def run_ssh_inventory() -> list:
    temp_php = ROOT / "agent-publisher" / "data" / "catalog_inventory.php"
    temp_php.write_text(CATALOG_PHP, encoding="utf-8")

    # 1. SCP to server
    scp_cmd = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", str(temp_php), f"{SSH_HOST}:/tmp/catalog_inventory.php"]
    subprocess.run(scp_cmd, check=True)

    # 2. Docker cp and wp eval-file
    eval_cmd = (
        "sudo docker cp /tmp/catalog_inventory.php wordpress_app:/tmp/catalog_inventory.php && "
        "sudo docker exec wordpress_app wp eval-file /tmp/catalog_inventory.php --allow-root && "
        "sudo docker exec wordpress_app rm -f /tmp/catalog_inventory.php && rm -f /tmp/catalog_inventory.php"
    )
    full_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", SSH_HOST, eval_cmd]
    res = subprocess.run(full_cmd, capture_output=True, text=True, encoding="utf-8", check=True)

    # Clean up local temp file
    temp_php.unlink(missing_ok=True)
    return json.loads((res.stdout or "").lstrip("\ufeff"))

def determine_type_and_category(title: str, categories=None, category_slugs=None):
    """Classify post into category and Evergreen vs Seasonal."""
    clean_categories = [str(c).strip() for c in (categories or []) if str(c).strip()]
    seasonal_keywords = ["추석", "9월", "10월", "콘서트", "예매", "독감", "축제"]
    seasonal_categories = {"지역 축제/행사", "공연/콘서트"}
    is_seasonal = (any(k in title for k in seasonal_keywords)
                   or bool(set(clean_categories) & seasonal_categories)
                   or bool(set(category_slugs or []) & {'local-events', 'concert'}))
    post_type = "시즌형" if is_seasonal else "에버그린"

    if clean_categories:
        category = ", ".join(clean_categories)
    elif any(k in title for k in ["상속", "주민등록", "여권", "전입", "폐가전", "우편물"]):
        category = "행정/생활서비스"
    elif any(k in title for k in ["약국", "병원", "독감", "의약품", "건강", "본인부담상한제"]):
        category = "건강/의료"
    elif any(k in title for k in ["기초연금", "복지", "도시가스", "경감", "지원"]):
        category = "복지/지원금"
    elif any(k in title for k in ["세금", "재산세", "연말정산", "소득공제", "세액공제"]):
        category = "세금/절세"
    elif any(k in title for k in ["계좌", "보험", "포인트", "은행", "주택연금", "최저시급"]):
        category = "금융/경제"
    elif any(k in title for k in ["고속도로", "교통", "통행료", "KTX", "기후동행패스", "전기차"]):
        category = "교통/자동차"
    elif any(k in title for k in ["축제", "지역 행사"]):
        category = "지역 축제/행사"
    elif any(k in title for k in ["콘서트", "공연", "뮤지컬", "예매"]):
        category = "공연/콘서트"
    else:
        category = "행정/생활서비스"

    return post_type, category


def catalog_type(post, reviewed_bundle=None):
    """Use lifecycle metadata only when its reviewed HTML matches the live post."""
    if isinstance(reviewed_bundle, dict) and isinstance(reviewed_bundle.get('review'), dict):
        try:
            from agents.editorial import digest, render, recognized_reviewed_content_hashes
            from agents.volatility import lifecycle_reasons
            body = {key: reviewed_bundle[key] for key in ('brief', 'sources', 'plan', 'temporal_source') if key in reviewed_bundle}
            review = reviewed_bundle['review']
            if (review.get('digest') != digest(body) or review.get('issues') != []
                    or not review.get('checks') or any(value is not True for value in review['checks'].values())
                    or lifecycle_reasons(reviewed_bundle['brief'])):
                raise ValueError('catalog_review_not_bound')
            post_id = post.get('ID')
            if type(post_id) is int and post_id > 0:
                content_hashes = recognized_reviewed_content_hashes(
                    reviewed_bundle, post_id=post_id)
            else:
                content = render(reviewed_bundle['plan'], reviewed_bundle['sources'])
                content_hashes = {
                    'current': hashlib.sha256(content.encode('utf-8')).hexdigest(),
                }
            if post.get('content_sha256') in set(content_hashes.values()):
                brief = reviewed_bundle['brief']
                labels = {'timeless-procedure': '상시 절차', 'policy-current': '현행 제도',
                          'annual-policy': '연간 기준', 'seasonal': '시즌형', 'one-off': '단일 행사'}
                if brief.get('volatility') in labels:
                    return labels[brief['volatility']] + ' (저장 원고 기준)'
                if brief.get('content_type') in {'evergreen', 'dated'}:
                    return ('에버그린' if brief['content_type'] == 'evergreen' else '기간형') + ' (저장 원고 기준)'
        except (KeyError, TypeError, ValueError):
            pass
    inferred, _ = determine_type_and_category(post['post_title'], post.get('categories'), post.get('category_slugs'))
    return inferred + ' (추정)'


def _restore_index_bytes(path: Path, raw: bytes | None) -> None:
    """Restore one reviewed-state index exactly after a failed local reconciliation."""
    if raw is None:
        path.unlink(missing_ok=True)
    else:
        temporary = path.with_name(path.name + '.reconcile-restore')
        temporary.write_bytes(raw)
        os.replace(temporary, path)


def reconcile_reviewed_statuses(posts: list, data_dir: Path = EDITORIAL_DATA_DIR) -> dict:
    """Align reviewed draft/publish indexes with live WordPress without touching WordPress.

    A row moves only when its reviewed renderer output and reviewed title still match
    the live post exactly.  This repairs status-only changes made by WordPress UI row
    actions while refusing to adopt reader-visible edits that bypassed editorial review.
    """
    agent_root = ROOT / 'agent-publisher'
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    from agents.editorial import recognized_reviewed_content_hashes
    from agents.post_manifest_store import load_records, remove_record, upsert_record
    from config import CATEGORIES

    data_dir = Path(data_dir)
    draft_index = data_dir / 'draft_posts.json'
    public_index = data_dir / 'published_posts.json'
    indexes = {'draft': draft_index, 'publish': public_index}
    live_by_id = {
        int(row['ID']): row
        for row in posts
        if isinstance(row, dict) and str(row.get('ID', '')).isdigit()
    }
    tracked = {}
    duplicate_ids = set()
    for indexed_status, index in indexes.items():
        if not index.is_file():
            continue
        for record in load_records(index):
            post_id = int(record['id'])
            if post_id in tracked:
                duplicate_ids.add(post_id)
                continue
            tracked[post_id] = (indexed_status, record)

    moved = []
    metadata_updated = []
    skipped = []
    for post_id, (indexed_status, record) in sorted(tracked.items()):
        if post_id in duplicate_ids:
            skipped.append({'post_id': post_id, 'reason': 'present_in_both_reviewed_indexes'})
            continue
        live = live_by_id.get(post_id)
        if not live:
            continue
        live_status = live.get('post_status')
        if live_status not in indexes:
            continue
        bundle = (record.get('fact_manifest') or {}).get('editorial_bundle')
        if not isinstance(bundle, dict):
            if live_status == indexed_status:
                continue
            skipped.append({'post_id': post_id, 'reason': 'reviewed_bundle_missing'})
            continue
        try:
            reviewed_title = bundle['plan']['title']
            reviewed_hashes = recognized_reviewed_content_hashes(bundle, post_id=post_id)
        except (KeyError, TypeError, ValueError):
            skipped.append({'post_id': post_id, 'reason': 'reviewed_bundle_invalid'})
            continue
        if live.get('post_title') != reviewed_title:
            if live_status == indexed_status:
                continue
            skipped.append({'post_id': post_id, 'reason': 'live_title_changed'})
            continue
        provenance_variant = next(
            (name for name, digest in reviewed_hashes.items()
             if live.get('content_sha256') == digest),
            None,
        )
        if provenance_variant is None:
            if live_status == indexed_status:
                continue
            skipped.append({'post_id': post_id, 'reason': 'live_content_changed'})
            continue

        source_index = indexes[indexed_status]
        target_index = indexes[live_status]
        updated = dict(record)
        updated['status'] = live_status
        updated['title'] = reviewed_title
        if isinstance(live.get('permalink'), str) and live['permalink'].startswith('https://lifeinfo24.org/'):
            updated['url'] = live['permalink']
        slugs = live.get('category_slugs')
        names = live.get('categories')
        if isinstance(slugs, list) and len(slugs) == 1 and isinstance(names, list) and len(names) == 1:
            category = next(
                (value for value in CATEGORIES.values()
                 if value.get('slug') == slugs[0] and value.get('name') == names[0]),
                None,
            )
            if category is not None:
                updated['category_id'] = category['id']
                updated['category_name'] = category['name']

        if live_status == indexed_status:
            if updated != record:
                upsert_record(source_index, updated)
                metadata_updated.append({
                    'post_id': post_id,
                    'status': live_status,
                    'fields': sorted(
                        key for key in updated
                        if updated.get(key) != record.get(key)
                    ),
                })
            continue

        source_raw = source_index.read_bytes() if source_index.exists() else None
        target_raw = target_index.read_bytes() if target_index.exists() else None
        try:
            upsert_record(target_index, updated)
            if not remove_record(source_index, post_id):
                raise ValueError('reviewed_status_source_record_missing')
        except Exception:
            _restore_index_bytes(source_index, source_raw)
            _restore_index_bytes(target_index, target_raw)
            raise
        moved_row = {
            'post_id': post_id,
            'from_status': indexed_status,
            'to_status': live_status,
        }
        if provenance_variant != 'current':
            if provenance_variant.startswith('completed-full-review-'):
                moved_row['provenance_variant'] = provenance_variant
            else:
                moved_row['renderer_variant'] = provenance_variant
        moved.append(moved_row)
    return {'moved': moved, 'metadata_updated': metadata_updated, 'skipped': skipped}


def load_reviewed_bundles(data_dir: Path = EDITORIAL_DATA_DIR):
    agent_root = ROOT / 'agent-publisher'
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    from agents.post_manifest_store import load_records
    bundles = {}
    for name in ('published_posts.json', 'draft_posts.json'):
        index = Path(data_dir) / name
        if not index.is_file():
            continue
        try:
            rows = load_records(index)
        except (OSError, ValueError):
            print('[Sync Catalog] WARNING: reviewed state unavailable; use explicitly labeled estimates.')
            continue
        for row in rows:
            bundle = (row.get('fact_manifest') or {}).get('editorial_bundle')
            if isinstance(bundle, dict):
                bundles[int(row['id'])] = bundle
    return bundles

def _markdown_cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def extract_backlog_rows(markdown: str) -> list[str]:
    """Return manually curated topic rows from an existing catalog."""
    if BACKLOG_HEADING not in markdown:
        return []

    section = markdown.split(BACKLOG_HEADING, 1)[1]
    rows = []
    in_table = False
    for line in section.splitlines():
        if line.startswith("| 우선순위 |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|:---"):
            continue
        if line.startswith("|"):
            cells = _markdown_cells(line)
            if len(cells) >= 5:
                rows.append(line.strip())
            continue
        if rows:
            break
    return rows


def _normalize_topic_text(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", value.lower())


def filter_backlog_rows(backlog_rows: list[str], posts: list) -> list[str]:
    """Remove backlog topics already represented by a current WordPress post."""
    post_haystacks = []
    for post in posts:
        combined = " ".join(
            [
                str(post.get("post_title", "")),
                str(post.get("rank_math_focus_keyword", "")),
            ]
        )
        post_haystacks.append(_normalize_topic_text(combined))

    remaining = []
    for row in backlog_rows:
        cells = _markdown_cells(row)
        if len(cells) < 5:
            continue

        topic = re.sub(r"[*`]", "", cells[1]).strip()
        keyword = re.sub(r"[*`]", "", cells[3]).strip()
        match_terms = [
            _normalize_topic_text(keyword),
            _normalize_topic_text(topic),
        ]
        covered = any(
            term and len(term) >= 4 and term in haystack
            for term in match_terms
            for haystack in post_haystacks
        )
        if covered:
            continue

        cells[0] = f"**{len(remaining) + 1}순위**"
        remaining.append("| " + " | ".join(cells[:5]) + " |")
    return remaining


def generate_catalog_markdown(posts: list, backlog_rows=None, reviewed_bundles=None) -> str:
    reviewed_bundles = reviewed_bundles or {}
    published_posts = [p for p in posts if p.get("post_status") == "publish"]
    draft_posts = [p for p in posts if p.get("post_status") == "draft"]

    # Sort posts descending by ID
    published_posts.sort(key=lambda x: int(x["ID"]), reverse=True)
    draft_posts.sort(key=lambda x: int(x["ID"]), reverse=True)

    evergreen_count = 0
    seasonal_count = 0

    pub_rows = []
    for p in published_posts:
        pid = str(p["ID"])
        title = p["post_title"].replace("|", "/")
        p_type, category = determine_type_and_category(title, p.get("categories"), p.get('category_slugs'))
        type_label = catalog_type(p, reviewed_bundles.get(int(p['ID'])))
        if p_type == "에버그린":
            evergreen_count += 1
        else:
            seasonal_count += 1

        kw = p.get("rank_math_focus_keyword", "").strip() or "-"
        score = p.get("rank_math_seo_score", "").strip()
        score_str = f"{score}점" if score else "미측정"

        # Link to permalink
        link = f"https://lifeinfo24.org/?p={pid}"
        pub_rows.append(
            f"| #{pid} | [{title}]({link}) | {category} | {type_label} | {kw} | {score_str} |"
        )

    draft_rows = []
    for p in draft_posts:
        pid = str(p["ID"])
        title = p["post_title"].replace("|", "/")
        p_type, category = determine_type_and_category(title, p.get("categories"), p.get('category_slugs'))
        kw = p.get("rank_math_focus_keyword", "").strip() or "-"
        draft_rows.append(
            f"| #{pid} | {title} | {category} | Draft 보존 | {kw} |"
        )

    total_pub = len(published_posts)
    eg_ratio = round((evergreen_count / total_pub * 100)) if total_pub > 0 else 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    if backlog_rows is None:
        backlog_rows = DEFAULT_BACKLOG_ROWS
    backlog_rows = filter_backlog_rows(backlog_rows, posts)
    backlog_body = "\n".join(backlog_rows)
    if not backlog_body:
        backlog_body = "_현재 검토 대기 후보가 없습니다. 새 후보 조사가 필요합니다._"

    status_labels = {
        "publish": "공개",
        "draft": "임시글",
        "pending": "검토대기",
        "future": "예약",
        "private": "비공개",
    }
    status_counts = []
    for status, label in status_labels.items():
        count = sum(1 for post in posts if post.get("post_status") == status)
        if count:
            status_counts.append(f"{label}: {count}편")
    status_summary = ", ".join(status_counts)

    md_content = f"""# 📚 Bloguito 콘텐츠 카탈로그 & 주제 관리 대시보드

> **최종 동기화**: {now_str} (Direct SSH)
> **총 포스트**: {len(posts)}편 ({status_summary})
> **공개글 제목/카테고리 추정 비중**: 에버그린 {eg_ratio}% ({evergreen_count}편) / 시즌형 {100 - eg_ratio}% ({seasonal_count}편)
> 유형의 `저장 원고 기준`은 검토 digest와 현재 본문 SHA가 맞는 로컬 metadata이며, 현재 사실·출처의 재검증을 뜻하지 않습니다. metadata가 없거나 본문이 다르면 `추정`으로 표시합니다.

---

## 1. 🟢 발행 완료 글 (Published)

| ID | 제목 | 카테고리 | 유형 | 포커스 키워드 | Rank Math 점수 |
|:---:|---|:---:|:---:|---|:---:|
""" + "\n".join(pub_rows) + """

---

## 2. 🟡 작업 중 / 임시글 (Draft)

| ID | 제목 | 카테고리 | 상태 | 포커스 키워드 |
|:---:|---|:---:|:---:|---|
""" + "\n".join(draft_rows) + f"""

---

## 3. 🎯 추진 예정 백로그 (Topic Backlog)

Bloguito 편집 정책(공식 출처 필수, 유효기간 30일 이상), 4060 중장년 핵심 검색 수요 및 기존 evergreen 조사를 반영한 우선순위 백로그입니다:

동기화 시 현재 공개·임시·예약·비공개 글의 제목과 포커스 키워드가 겹치는 후보는 자동 제외합니다. 새 후보는 공식 출처와 유효기간을 조사한 뒤 이 표에 추가하며, 다음 동기화에서도 그대로 보존합니다.

| 우선순위 | 주제명 | 핵심 타깃 및 검색 의도 | 주요 포커스 키워드 | 공식 출처 |
|:---:|---|---|---|---|
{backlog_body}

---

## 🛠️ 카탈로그 최신화 안내
서버의 최신 상태를 로컬 문서에 반영하려면 터미널에서 다음 명령을 실행합니다:
```powershell
python scripts/sync_post_catalog.py
```
"""
    return md_content

def sync_catalog():
    print("[Sync Catalog] Fetching all posts and metadata via Direct SSH eval-file...")
    posts = run_ssh_inventory()
    print(f"[Sync Catalog] Successfully fetched {len(posts)} posts with full metadata.")

    reconciliation = reconcile_reviewed_statuses(posts)
    for row in reconciliation['moved']:
        print('[Sync Catalog] Reviewed state reconciled: '
              f"#{row['post_id']} {row['from_status']} -> {row['to_status']}")
    for row in reconciliation.get('metadata_updated', []):
        print('[Sync Catalog] Reviewed metadata reconciled: '
              f"#{row['post_id']} fields={','.join(row['fields'])}")
    for row in reconciliation['skipped']:
        print('[Sync Catalog] WARNING: reviewed state not reconciled for '
              f"#{row['post_id']}: {row['reason']}")

    existing_backlog = None
    if CATALOG_MD.exists():
        existing_backlog = extract_backlog_rows(CATALOG_MD.read_text(encoding="utf-8"))
    md = generate_catalog_markdown(posts, existing_backlog, load_reviewed_bundles())

    CATALOG_MD.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_MD.write_text(md, encoding="utf-8")
    print(f"[Sync Catalog] Successfully generated {CATALOG_MD}")

    # Keep the catalog's richer WordPress snapshot separate from the canonical
    # lightweight inventory used by search_intent/scheduled editorial validation.
    CATALOG_INVENTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_INVENTORY_JSON.write_text(
        json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Sync Catalog] Successfully saved {CATALOG_INVENTORY_JSON}")

if __name__ == "__main__":
    sync_catalog()
