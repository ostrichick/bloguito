"""Private, read-only growth opportunity analysis for Bloguito.

This module consumes already-collected Search Console/GA4 snapshots and a
WordPress catalog snapshot. It never writes WordPress, changes editorial
review state, or treats GA4 all-channel page views as organic traffic.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unicodedata
from urllib.parse import parse_qs, unquote, urlparse


class GrowthAnalysisError(ValueError):
    """Fail-closed growth analysis input or storage error."""


RECOMMENDED_ACTIONS = {
    "winner": "expand_related_demand",
    "quick_win": "inspect_title_snippet_and_search_intent",
    "growth_candidate": "strengthen_content_and_internal_links",
    "seasonal_decay": "review_archive_redirect_or_next_cycle_update",
    "low_signal": "defer_or_consider_consolidation_after_manual_review",
    "too_early": "wait_for_more_data",
    "observed": "monitor",
}


def load_policy(path: str | Path) -> dict:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or policy.get("version") != 1:
        raise GrowthAnalysisError("invalid_growth_policy")
    required = {
        "fresh_post_days", "confidence", "winner", "quick_win",
        "growth_candidate", "low_signal", "classification_order",
    }
    if not required.issubset(policy):
        raise GrowthAnalysisError("invalid_growth_policy")
    return policy


def _parse_date(value, *, code: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise GrowthAnalysisError(code) from None


def _normal_path(path: str) -> str:
    decoded = unicodedata.normalize("NFC", unquote(path or "/"))
    if not decoded.startswith("/"):
        decoded = "/" + decoded
    if decoded != "/":
        decoded = decoded.rstrip("/")
    return decoded.casefold()


def _url_aliases(url: str) -> set[str]:
    if not isinstance(url, str) or not url.strip():
        return set()
    parsed = urlparse(url.strip())
    aliases = set()
    query = parse_qs(parsed.query)
    post_ids = query.get("p", [])
    if len(post_ids) == 1 and str(post_ids[0]).isdigit():
        aliases.add("post_id:" + str(int(post_ids[0])))
    path = _normal_path(parsed.path)
    aliases.add("path:" + path)
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "p" and parts[1].isdigit():
        aliases.add("post_id:" + str(int(parts[1])))
    return aliases


def _post_aliases(post: dict) -> set[str]:
    post_id = post.get("ID")
    if type(post_id) is not int:
        raise GrowthAnalysisError("invalid_catalog_post_id")
    aliases = {"post_id:" + str(post_id), "path:/p/" + str(post_id)}
    for field in ("permalink", "url"):
        aliases.update(_url_aliases(post.get(field, "")))
    post_name = post.get("post_name")
    if isinstance(post_name, str) and post_name.strip():
        aliases.add("path:" + _normal_path("/" + post_name))
    return aliases


def _build_alias_index(posts: list[dict]) -> dict[str, int | None]:
    index: dict[str, int | None] = {}
    for post in posts:
        for alias in _post_aliases(post):
            if alias in index and index[alias] != post["ID"]:
                index[alias] = None
            else:
                index[alias] = post["ID"]
    return index


def _match_post_id(value: str, alias_index: dict[str, int | None]) -> int | None:
    matches = {alias_index.get(alias) for alias in _url_aliases(value)}
    matches.discard(None)
    return next(iter(matches)) if len(matches) == 1 else None


def _confidence(impressions: int, policy: dict) -> str:
    thresholds = policy["confidence"]
    if impressions >= int(thresholds["high_impressions"]):
        return "high"
    if impressions >= int(thresholds["medium_impressions"]):
        return "medium"
    return "low"


def _classify(*, metrics: dict, age_days: int, expires_at, period_end: date,
              policy: dict) -> tuple[str, str, list[str]]:
    impressions = int(metrics.get("impressions") or 0)
    clicks = int(metrics.get("clicks") or 0)
    ctr = float(metrics.get("ctr") or 0.0)
    position = metrics.get("position")
    position = float(position) if position is not None else None

    if expires_at:
        expiry = _parse_date(expires_at, code="invalid_growth_expires_at")
        if expiry < period_end:
            return "seasonal_decay", "high", ["explicit_useful_until_before_report_end"]

    if age_days < 0:
        return "too_early", "high", ["published_after_reporting_period"]

    fresh = age_days < int(policy["fresh_post_days"])

    def signal_reasons(reason: str) -> list[str]:
        return [reason, "fresh_post_but_signal_threshold_reached"] if fresh else [reason]

    winner = policy["winner"]
    if clicks >= int(winner["click_override"]):
        return "winner", _confidence(impressions, policy), signal_reasons("click_override_reached")
    if (clicks >= int(winner["min_clicks"])
            and impressions >= int(winner["min_impressions"])
            and position is not None and position <= float(winner["max_position"])
            and ctr >= float(winner["min_ctr"])):
        return "winner", _confidence(impressions, policy), signal_reasons("click_ctr_position_signal")

    quick = policy["quick_win"]
    if (impressions >= int(quick["min_impressions"])
            and position is not None
            and float(quick["min_position"]) <= position <= float(quick["max_position"])
            and ctr < float(quick["max_ctr"])):
        return "quick_win", _confidence(impressions, policy), signal_reasons("page_one_visibility_low_ctr")

    growth = policy["growth_candidate"]
    if (impressions >= int(growth["min_impressions"])
            and position is not None
            and float(growth["min_position_exclusive"]) < position <= float(growth["max_position"])):
        return "growth_candidate", _confidence(impressions, policy), signal_reasons("page_two_or_three_visibility")

    if fresh:
        return "too_early", "high", ["post_too_new_for_growth_judgment"]

    low = policy["low_signal"]
    if age_days >= int(low["min_age_days"]) and impressions <= int(low["max_impressions"]):
        return "low_signal", "low", ["mature_post_with_little_search_visibility"]

    reason = ("sample_too_small_for_strong_action"
              if impressions < int(policy["confidence"]["medium_impressions"])
              else "search_signal_observed_without_action_threshold")
    return "observed", _confidence(impressions, policy), [reason]


def _validate_snapshot(snapshot: dict) -> None:
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 2:
        raise GrowthAnalysisError("unsupported_analytics_snapshot")
    if not isinstance(snapshot.get("search_console"), dict) or not isinstance(snapshot.get("ga4"), dict):
        raise GrowthAnalysisError("invalid_analytics_snapshot")
    for key in ("pages", "queries"):
        if not isinstance(snapshot["search_console"].get(key), list):
            raise GrowthAnalysisError("invalid_analytics_snapshot")
    if not isinstance(snapshot["ga4"].get("pages"), list):
        raise GrowthAnalysisError("invalid_analytics_snapshot")


def analyze_growth(snapshot: dict, catalog_posts: list[dict], policy: dict, *,
                   provenance_by_id: dict[int, dict] | None = None) -> dict:
    """Join private performance data to published WordPress posts without mutation."""
    _validate_snapshot(snapshot)
    if not isinstance(catalog_posts, list):
        raise GrowthAnalysisError("invalid_catalog_inventory")
    published = [post for post in catalog_posts if post.get("post_status") == "publish"]
    if any(type(post.get("ID")) is not int for post in published):
        raise GrowthAnalysisError("invalid_catalog_inventory")

    period_end = _parse_date(snapshot.get("period", {}).get("end"), code="invalid_report_period")
    alias_index = _build_alias_index(published)
    by_id = {post["ID"]: post for post in published}

    gsc_by_id: dict[int, dict] = {}
    unmatched_gsc_pages = []
    for row in snapshot["search_console"]["pages"]:
        page = row.get("page")
        post_id = _match_post_id(page, alias_index) if isinstance(page, str) else None
        if post_id is None or post_id not in by_id:
            unmatched_gsc_pages.append({
                "page": page,
                "clicks": row.get("clicks"),
                "impressions": row.get("impressions"),
                "position": row.get("position"),
            })
            continue
        if post_id in gsc_by_id:
            raise GrowthAnalysisError("duplicate_gsc_page_mapping")
        gsc_by_id[post_id] = row

    ga4_by_id: dict[int, dict] = {}
    unmatched_ga4_paths = []
    for row in snapshot["ga4"]["pages"]:
        path = row.get("pagePath")
        post_id = _match_post_id(path, alias_index) if isinstance(path, str) else None
        if post_id is None or post_id not in by_id:
            unmatched_ga4_paths.append({
                "pagePath": path,
                "screenPageViews": row.get("screenPageViews"),
                "activeUsers": row.get("activeUsers"),
            })
            continue
        existing = ga4_by_id.setdefault(post_id, {"screenPageViews": 0, "activeUsers": 0})
        existing["screenPageViews"] += int(row.get("screenPageViews") or 0)
        existing["activeUsers"] += int(row.get("activeUsers") or 0)

    provenance_by_id = provenance_by_id if isinstance(provenance_by_id, dict) else {}
    pages = []
    for post in published:
        published_on = _parse_date(post.get("post_date"), code="invalid_catalog_post_date")
        age_days = (period_end - published_on).days
        gsc = gsc_by_id.get(post["ID"])
        metrics = {
            "clicks": int(gsc.get("clicks", 0)) if gsc else 0,
            "impressions": int(gsc.get("impressions", 0)) if gsc else 0,
            "ctr": float(gsc.get("ctr", 0.0)) if gsc else 0.0,
            "position": float(gsc["position"]) if gsc and gsc.get("position") is not None else None,
            "gsc_row_observed": gsc is not None,
        }
        classification, confidence, reasons = _classify(
            metrics=metrics,
            age_days=age_days,
            expires_at=post.get("expires_at"),
            period_end=period_end,
            policy=policy,
        )
        ga4 = ga4_by_id.get(post["ID"], {"screenPageViews": 0, "activeUsers": 0})
        provenance = provenance_by_id.get(post["ID"])
        if not isinstance(provenance, dict):
            provenance = {
                "classification": "provenance_unavailable",
                "auto_adoptable": False,
            }
        pages.append({
            "post_id": post["ID"],
            "title": post.get("post_title", ""),
            "permalink": post.get("permalink") or post.get("url"),
            "category_slugs": post.get("category_slugs", []),
            "categories": post.get("categories", []),
            "post_date": post.get("post_date"),
            "age_days_at_report_end": age_days,
            "search_console": metrics,
            "ga4_all_channels": {
                "screenPageViews": ga4["screenPageViews"],
                "activeUsers": ga4["activeUsers"],
                "note": "Not organic-only; do not use this field as search traffic.",
            },
            "classification": classification,
            "confidence": confidence,
            "reasons": reasons,
            "recommended_action": RECOMMENDED_ACTIONS[classification],
            "editorial_provenance": {
                key: provenance.get(key)
                for key in (
                    "classification", "auto_adoptable", "live_status",
                    "live_content_sha256", "review_digest", "bundle_digest",
                    "provenance_variant", "canonical_category_key",
                )
            },
        })

    order = {name: idx for idx, name in enumerate(policy["classification_order"])}
    pages.sort(key=lambda item: (
        order.get(item["classification"], len(order)),
        -int(item["search_console"]["impressions"]),
        item["post_id"],
    ))
    counts: dict[str, int] = {}
    for page in pages:
        counts[page["classification"]] = counts.get(page["classification"], 0) + 1

    top_queries = sorted(
        snapshot["search_console"]["queries"],
        key=lambda row: (float(row.get("clicks", 0)), float(row.get("impressions", 0))),
        reverse=True,
    )[:50]
    return {
        "schema_version": 1,
        "provenance_contract_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": snapshot["period"],
        "policy_version": policy["version"],
        "summary": {
            "published_posts": len(published),
            "mapped_gsc_pages": len(gsc_by_id),
            "unmatched_gsc_pages": len(unmatched_gsc_pages),
            "mapped_ga4_pages": len(ga4_by_id),
            "classifications": counts,
        },
        "pages": pages,
        "top_queries_global": top_queries,
        "unmatched_gsc_pages": unmatched_gsc_pages,
        "unmatched_ga4_paths": unmatched_ga4_paths,
        "limitations": [
            "Search Console query rows are global and are not attributed to a page in this collector schema.",
            "GA4 page metrics in this report include all channels and are not treated as organic traffic.",
            "Low impression counts yield low confidence; classifications are workflow triage, not ranking predictions.",
            "Unmatched legacy or alternate URLs are reported instead of guessed onto a current post.",
        ],
    }


def save_opportunities(report: dict, output_dir: str | Path) -> Path:
    """Atomically save private growth state; never follow symlink targets."""
    directory = Path(output_dir).absolute()
    if directory.is_symlink():
        raise GrowthAnalysisError("growth_output_directory_symlink_not_allowed")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix" and directory.stat().st_mode & 0o077:
        raise GrowthAnalysisError("growth_output_directory_permissions_too_open")
    target = directory / "latest-opportunities.json"
    if target.is_symlink():
        raise GrowthAnalysisError("growth_output_target_symlink_not_allowed")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, prefix=".growth-",
                suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            if os.name == "posix":
                os.chmod(temp, 0o600)
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return target
