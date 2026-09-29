# -*- coding: utf-8 -*-
"""Synchronize WordPress posts with local docs/POST_CATALOG.md via Direct SSH."""
import json
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
INVENTORY_JSON = ROOT / "agent-publisher" / "data" / "wordpress_inventory.json"
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
    $categories = wp_get_post_categories($id, array('fields' => 'names'));
    $o[] = array(
        'ID' => (int)$id,
        'post_title' => (string)$p->post_title,
        'post_status' => (string)$p->post_status,
        'post_name' => (string)$p->post_name,
        'post_date' => (string)$p->post_date,
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

def determine_type_and_category(title: str, categories=None):
    """Classify post into category and Evergreen vs Seasonal."""
    seasonal_keywords = ["추석", "9월", "콘서트", "예매", "독감"]
    is_seasonal = any(k in title for k in seasonal_keywords)
    post_type = "시즌형" if is_seasonal else "에버그린"

    clean_categories = [str(c).strip() for c in (categories or []) if str(c).strip()]
    if clean_categories:
        category = ", ".join(clean_categories)
    elif any(k in title for k in ["상속", "주민등록", "여권", "전입", "폐가전", "우편물"]):
        category = "생활행정"
    elif any(k in title for k in ["약국", "병원", "독감", "의약품", "건강", "본인부담상한제"]):
        category = "보건의료"
    elif any(k in title for k in ["기초연금", "복지", "도시가스", "경감", "지원"]):
        category = "복지혜택"
    elif any(k in title for k in ["계좌", "환급", "세금", "보험금", "포인트"]):
        category = "금융세무"
    elif any(k in title for k in ["고속도로", "교통", "통행료", "KTX", "기후동행패스", "전기차"]):
        category = "교통이동"
    elif "콘서트" in title:
        category = "공연문화"
    else:
        category = "일반생활"

    return post_type, category

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


def generate_catalog_markdown(posts: list, backlog_rows=None) -> str:
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
        p_type, category = determine_type_and_category(title, p.get("categories"))
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
            f"| #{pid} | [{title}]({link}) | {category} | {p_type} | {kw} | {score_str} |"
        )

    draft_rows = []
    for p in draft_posts:
        pid = str(p["ID"])
        title = p["post_title"].replace("|", "/")
        p_type, category = determine_type_and_category(title, p.get("categories"))
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
> **공개글 자동 분류 비중**: 에버그린 {eg_ratio}% ({evergreen_count}편) / 시즌형 {100 - eg_ratio}% ({seasonal_count}편)

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

    existing_backlog = None
    if CATALOG_MD.exists():
        existing_backlog = extract_backlog_rows(CATALOG_MD.read_text(encoding="utf-8"))
    md = generate_catalog_markdown(posts, existing_backlog)

    CATALOG_MD.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_MD.write_text(md, encoding="utf-8")
    print(f"[Sync Catalog] Successfully generated {CATALOG_MD}")

    # Also save json inventory
    INVENTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
    INVENTORY_JSON.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Sync Catalog] Successfully saved {INVENTORY_JSON}")

if __name__ == "__main__":
    sync_catalog()
