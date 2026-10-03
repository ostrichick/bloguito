"""Deterministic content-cluster recommendations and explicit-link orphan audit."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
CLUSTERS = ROOT / "data" / "content_clusters.json"


class ContentClusterError(ValueError):
    pass


def load_clusters(path: str | Path = CLUSTERS) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ContentClusterError("content_clusters_unreadable") from None
    validate_clusters(payload)
    return payload


def validate_clusters(payload: dict) -> None:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ContentClusterError("invalid_content_clusters_schema")
    clusters = payload.get("clusters")
    if not isinstance(clusters, dict):
        raise ContentClusterError("invalid_content_clusters")
    seen_posts: set[int] = set()
    for cluster_id, cluster in clusters.items():
        if (not isinstance(cluster_id, str) or not cluster_id.strip()
                or not isinstance(cluster, dict)
                or set(cluster) != {"name", "posts"}
                or not isinstance(cluster.get("name"), str)
                or not cluster["name"].strip()
                or not isinstance(cluster.get("posts"), list)):
            raise ContentClusterError("invalid_content_cluster_entry")
        posts = cluster["posts"]
        if (any(type(post_id) is not int or post_id <= 0 for post_id in posts)
                or len(posts) != len(set(posts))):
            raise ContentClusterError("invalid_content_cluster_posts")
        overlap = seen_posts.intersection(posts)
        if overlap:
            raise ContentClusterError("content_cluster_post_overlap")
        seen_posts.update(posts)


def _cluster(brief: dict, clusters: dict) -> tuple[str, dict] | None:
    cluster_id = brief.get("cluster_id") if isinstance(brief, dict) else None
    if cluster_id is None:
        return None
    if not isinstance(cluster_id, str) or not cluster_id.strip():
        raise ContentClusterError("invalid_brief_cluster_id")
    cluster = clusters["clusters"].get(cluster_id)
    if not isinstance(cluster, dict):
        raise ContentClusterError("unknown_brief_cluster_id")
    return cluster_id, cluster


def _inventory_posts(inventory: dict) -> list[dict]:
    posts = inventory.get("posts") if isinstance(inventory, dict) else None
    if not isinstance(posts, list) or any(not isinstance(row, dict) for row in posts):
        raise ContentClusterError("invalid_cluster_inventory")
    return posts


def _label(title: str) -> str:
    clean = " ".join(title.split())
    if len(clean) <= 60:
        return clean
    return clean[:59].rstrip() + "…"


def related_post_candidates(brief: dict, inventory: dict, clusters: dict, *,
                            max_results: int = 2) -> list[dict]:
    """Return curated same-cluster published posts using the reviewed ?p=ID contract."""
    validate_clusters(clusters)
    selected = _cluster(brief, clusters)
    if selected is None:
        return []
    if type(max_results) is not int or not 1 <= max_results <= 2:
        raise ContentClusterError("invalid_cluster_related_limit")
    _, cluster = selected
    posts = {row.get("ID"): row for row in _inventory_posts(inventory)}
    existing_post_id = brief.get("existing_post_id")
    result = []
    for post_id in cluster["posts"]:
        if post_id == existing_post_id:
            continue
        row = posts.get(post_id)
        if (not row or row.get("post_status") != "publish"
                or not isinstance(row.get("post_title"), str)
                or len(row["post_title"].strip()) < 4):
            continue
        result.append({
            "post_id": post_id,
            "label": _label(row["post_title"]),
            "url": f"https://lifeinfo24.org/?p={post_id}",
        })
        if len(result) >= max_results:
            break
    return result


def apply_cluster_related_posts(plan: dict, brief: dict, inventory: dict,
                                clusters: dict) -> dict:
    """Bind generated related navigation to curated cluster membership before review."""
    if not isinstance(plan, dict):
        raise ContentClusterError("invalid_cluster_plan")
    if brief.get("cluster_id") is None:
        return plan
    updated = dict(plan)
    updated["related_posts"] = related_post_candidates(brief, inventory, clusters)
    return updated


def _explicit_post_id(url: str) -> int | None:
    if not isinstance(url, str):
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "lifeinfo24.org":
        return None
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) != {"p"} or len(query["p"]) != 1:
        return None
    value = query["p"][0]
    return int(value) if value.isascii() and value.isdecimal() and int(value) > 0 else None


def cluster_link_report(inventory: dict, clusters: dict) -> dict:
    """Audit only explicit ?p=ID links; missing content_urls never implies orphan status."""
    validate_clusters(clusters)
    posts = _inventory_posts(inventory)
    by_id = {row.get("ID"): row for row in posts}
    published = {
        post_id: row for post_id, row in by_id.items()
        if type(post_id) is int and row.get("post_status") == "publish"
    }
    incoming: dict[int, set[int]] = {post_id: set() for post_id in published}
    outgoing: dict[int, set[int]] = {post_id: set() for post_id in published}
    complete_link_state = all(isinstance(row.get("content_urls"), list)
                              for row in published.values())
    if complete_link_state:
        for source_id, row in published.items():
            for url in row["content_urls"]:
                target_id = _explicit_post_id(url)
                if target_id in published and target_id != source_id:
                    outgoing[source_id].add(target_id)
                    incoming[target_id].add(source_id)

    rows = []
    for cluster_id, cluster in clusters["clusters"].items():
        members = set(cluster["posts"])
        for post_id in cluster["posts"]:
            row = published.get(post_id)
            if not row:
                continue
            incoming_count = len(incoming[post_id]) if complete_link_state else None
            outgoing_cluster_count = (len(outgoing[post_id].intersection(members))
                                      if complete_link_state else None)
            rows.append({
                "cluster_id": cluster_id,
                "cluster_name": cluster["name"],
                "post_id": post_id,
                "title": row.get("post_title", ""),
                "incoming_explicit_links": incoming_count,
                "outgoing_cluster_links": outgoing_cluster_count,
                "orphan_candidate": bool(
                    complete_link_state and incoming_count == 0 and outgoing_cluster_count == 0),
            })
    return {
        "schema_version": 1,
        "link_state_complete": complete_link_state,
        "clusters": len(clusters["clusters"]),
        "published_cluster_members": len(rows),
        "orphan_candidates": sum(1 for row in rows if row["orphan_candidate"]),
        "posts": rows,
    }
