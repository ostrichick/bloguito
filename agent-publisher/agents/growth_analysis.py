"""Private, read-only growth opportunity analysis for Bloguito.

This module consumes already-collected Search Console/GA4 snapshots and a
WordPress catalog snapshot. It never writes WordPress, changes editorial
review state, or treats GA4 all-channel page views as organic traffic.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import parse_qs, unquote, urlparse

from agents.wordpress_transport import run_wordpress


class GrowthAnalysisError(ValueError):
    """Fail-closed growth analysis input or storage error."""


_WP_BASE = ["sudo", "docker", "exec", "wordpress_app", "wp"]
_CATALOG_PHP = (
    "$q=new WP_Query(array('post_type'=>'post','post_status'=>array('publish','draft','pending','future','private'),"
    "'posts_per_page'=>-1,'orderby'=>'ID','order'=>'ASC','fields'=>'ids'));$o=array();"
    "foreach($q->posts as $id){$p=get_post($id);$c=(string)$p->post_content;"
    "$o[]=array('ID'=>(int)$id,'post_title'=>(string)$p->post_title,'post_status'=>(string)$p->post_status,"
    "'post_name'=>(string)$p->post_name,'permalink'=>(string)get_permalink($id),"
    "'post_date'=>(string)$p->post_date,'content_sha256'=>hash('sha256',$c),"
    "'category_slugs'=>wp_get_post_terms($id,'category',array('fields'=>'slugs')),'categories'=>"
    "array_values(wp_get_post_categories($id,array('fields'=>'names'))));}echo wp_json_encode($o);"
)
_CATALOG_ARGS = ["eval", _CATALOG_PHP, "--allow-root"]
_ANALYTICS_RE = re.compile(r"google-analytics-(\d{4}-\d{2}-\d{2})\.json\Z")


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


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_digest(payload) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(raw)


def _load_private_json(path: Path, code: str):
    try:
        if path.is_symlink():
            raise GrowthAnalysisError(code + "_symlink_not_allowed")
        return json.loads(path.read_text(encoding="utf-8"))
    except GrowthAnalysisError:
        raise
    except (OSError, ValueError, TypeError):
        raise GrowthAnalysisError(code) from None


def latest_analytics_snapshot(analytics_dir: Path, *, now=None) -> tuple[Path, dict, str]:
    """Return the newest intended private snapshot, or fail closed.

    The newest matching filename is selected *before* validation.  A malformed
    newest snapshot must never make scheduled automation silently fall back to
    an older valid file.
    """
    from analytics_collector import CollectionError
    from analytics_receiver import validate_snapshot

    directory = Path(analytics_dir)
    if directory.is_symlink() or not directory.is_dir():
        raise GrowthAnalysisError("growth_analytics_directory_unavailable")
    candidates = []
    for path in directory.iterdir():
        match = _ANALYTICS_RE.fullmatch(path.name)
        if match is None:
            continue
        try:
            filename_date = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        candidates.append((filename_date, path.name, path))
    if not candidates:
        raise GrowthAnalysisError("growth_analytics_snapshot_unavailable")
    filename_date, _name, path = max(candidates, key=lambda row: (row[0], row[1]))
    if path.is_symlink() or not path.is_file():
        raise GrowthAnalysisError("growth_latest_analytics_snapshot_invalid")
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("schema_version") != 2:
            raise GrowthAnalysisError("growth_latest_analytics_snapshot_unsupported")
        validate_snapshot(payload, now=now)
        period_end = date.fromisoformat(str(payload["period"]["end"]))
        if period_end != filename_date:
            raise GrowthAnalysisError("growth_latest_analytics_filename_period_mismatch")
    except GrowthAnalysisError:
        raise
    except (OSError, UnicodeDecodeError, ValueError, TypeError, KeyError, CollectionError) as exc:
        raise GrowthAnalysisError("growth_latest_analytics_snapshot_invalid") from exc
    checksum = _sha256_bytes(raw)
    return path, payload, checksum


def fetch_current_catalog() -> list[dict]:
    """Read the current WordPress post catalog without mutating WordPress."""
    try:
        result = run_wordpress(
            _WP_BASE + _CATALOG_ARGS,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=60,
        )
        rows = json.loads((result.stdout or "").lstrip("\ufeff"))
    except Exception as exc:
        raise GrowthAnalysisError("growth_wordpress_catalog_unavailable") from exc
    allowed = {"publish", "draft", "pending", "future", "private"}
    if (not isinstance(rows, list)
            or any(
                not isinstance(row, dict)
                or type(row.get("ID")) is not int
                or not isinstance(row.get("post_title"), str)
                or row.get("post_status") not in allowed
                or not isinstance(row.get("post_name"), str)
                or not isinstance(row.get("permalink"), str)
                or not isinstance(row.get("post_date"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", row.get("content_sha256", ""))
                or not isinstance(row.get("category_slugs"), list)
                or not isinstance(row.get("categories"), list)
                for row in rows
            )):
        raise GrowthAnalysisError("growth_wordpress_catalog_invalid")
    ids = [row["ID"] for row in rows]
    if len(ids) != len(set(ids)):
        raise GrowthAnalysisError("growth_wordpress_catalog_duplicate_id")
    return rows


def _canonical_live_category(live: dict):
    from config import CATEGORIES
    slugs = live.get("category_slugs")
    names = live.get("categories")
    if (not isinstance(slugs, list) or len(slugs) != 1
            or not isinstance(names, list) or len(names) != 1):
        return None
    matches = [
        (key, value)
        for key, value in CATEGORIES.items()
        if value.get("slug") == slugs[0] and value.get("name") == names[0]
    ]
    return matches[0] if len(matches) == 1 else None


def audit_reviewed_provenance(posts: list[dict], data_dir: Path) -> dict[int, dict]:
    """Return only current exact reviewed bindings; ambiguous state stays non-adoptable."""
    from agents.editorial import digest, recognized_reviewed_content_hashes
    from agents.post_manifest_store import load_records

    live_by_id = {int(row["ID"]): row for row in posts}
    tracked: dict[int, tuple[str, dict]] = {}
    duplicate_ids: set[int] = set()
    for indexed_status, name in (("draft", "draft_posts.json"), ("publish", "published_posts.json")):
        index = Path(data_dir) / name
        if not index.is_file():
            continue
        try:
            records = load_records(index)
        except (OSError, ValueError, TypeError) as exc:
            raise GrowthAnalysisError("growth_reviewed_index_invalid") from exc
        for record in records:
            post_id = int(record["id"])
            if post_id in tracked:
                duplicate_ids.add(post_id)
            else:
                tracked[post_id] = (indexed_status, record)

    output: dict[int, dict] = {}
    for post_id, live in live_by_id.items():
        base = {
            "classification": "provenance_unavailable",
            "auto_adoptable": False,
            "live_status": live.get("post_status"),
        }
        if post_id in duplicate_ids:
            output[post_id] = {**base, "classification": "duplicate_reviewed_record"}
            continue
        tracked_row = tracked.get(post_id)
        if tracked_row is None:
            output[post_id] = {**base, "classification": "no_reviewed_record"}
            continue
        indexed_status, record = tracked_row
        bundle = (record.get("fact_manifest") or {}).get("editorial_bundle")
        if not isinstance(bundle, dict):
            output[post_id] = {**base, "classification": "legacy_inline_no_bundle"}
            continue
        try:
            reviewed_title = bundle["plan"]["title"]
            hashes = recognized_reviewed_content_hashes(bundle, post_id=post_id)
        except ValueError as exc:
            classification = (
                "review_unbound" if str(exc) == "reviewed_content_review_not_bound"
                else "reviewed_bundle_invalid"
            )
            output[post_id] = {**base, "classification": classification}
            continue
        except (KeyError, TypeError):
            output[post_id] = {**base, "classification": "reviewed_bundle_invalid"}
            continue
        if live.get("post_title") != reviewed_title:
            output[post_id] = {**base, "classification": "live_title_changed"}
            continue
        variant = next(
            (name for name, content_hash in hashes.items()
             if content_hash == live.get("content_sha256")),
            None,
        )
        if variant is None:
            output[post_id] = {**base, "classification": "live_content_changed"}
            continue
        category = _canonical_live_category(live)
        if category is None:
            output[post_id] = {
                **base,
                "classification": "reviewed_exact_category_unbound",
                "provenance_variant": variant,
            }
            continue
        category_key, _category_value = category
        output[post_id] = {
            "classification": "reviewed_exact",
            "auto_adoptable": True,
            "live_status": live.get("post_status"),
            "live_content_sha256": live.get("content_sha256"),
            "review_digest": bundle.get("review", {}).get("digest"),
            "bundle_digest": digest(bundle),
            "provenance_variant": variant,
            "canonical_category_key": category_key,
        }
    return output


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


def _merge_gsc_rows(left: dict, right: dict) -> dict:
    """Aggregate distinct Search Console URL variants mapped to one WordPress post."""
    left_impressions = int(left.get("impressions") or 0)
    right_impressions = int(right.get("impressions") or 0)
    impressions = left_impressions + right_impressions
    clicks = int(left.get("clicks") or 0) + int(right.get("clicks") or 0)
    weighted_positions = []
    if left.get("position") is not None and left_impressions > 0:
        weighted_positions.append((float(left["position"]), left_impressions))
    if right.get("position") is not None and right_impressions > 0:
        weighted_positions.append((float(right["position"]), right_impressions))
    position = (
        sum(value * weight for value, weight in weighted_positions)
        / sum(weight for _value, weight in weighted_positions)
        if weighted_positions else None
    )
    return {
        "page": left.get("page") or right.get("page"),
        "clicks": clicks,
        "impressions": impressions,
        "ctr": (clicks / impressions) if impressions else 0.0,
        "position": position,
        "mapped_url_variants": int(left.get("mapped_url_variants") or 1)
            + int(right.get("mapped_url_variants") or 1),
    }


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
            gsc_by_id[post_id] = _merge_gsc_rows(gsc_by_id[post_id], row)
        else:
            gsc_by_id[post_id] = dict(row, mapped_url_variants=1)

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


def _atomic_json(path: Path, payload: dict) -> None:
    path = Path(path)
    if path.is_symlink():
        raise GrowthAnalysisError("growth_output_symlink_not_allowed")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix" and path.parent.stat().st_mode & 0o077:
        raise GrowthAnalysisError("growth_output_directory_permissions_too_open")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=path.parent, prefix=".growth-runtime-",
                suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            if os.name == "posix":
                os.chmod(temp, 0o600)
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def opportunity_payload_digest(report: dict) -> str:
    """Digest the exact Opportunity payload, excluding self-referential binding fields."""
    if not isinstance(report, dict):
        raise GrowthAnalysisError("growth_opportunity_digest_invalid")
    payload = {
        key: value for key, value in report.items()
        if key not in {"opportunity_payload_sha256", "refresh_id"}
    }
    return _canonical_digest(payload)


def refresh_growth_inputs(*, analytics_dir: Path, growth_dir: Path, data_dir: Path,
                          policy_path: Path, as_of: date, validation_now=None) -> dict:
    """Refresh scheduled Opportunity/Topic inputs from the newest proven data.

    A changed analytics snapshot triggers one read-only WordPress catalog query.
    Topic candidates are re-scored every run so evidence aging cannot stay
    silently eligible. Both live derived files are staged before either is
    replaced; callers additionally verify their shared ``refresh_id``.
    """
    from agents.topic_scoring import TopicScoringError, score_candidates

    analytics_path, snapshot, analytics_sha = latest_analytics_snapshot(
        analytics_dir, now=validation_now)
    policy = load_policy(policy_path)
    opportunities_path = Path(growth_dir) / "latest-opportunities.json"
    scores_path = Path(growth_dir) / "topic-candidate-scores.json"
    candidates_path = Path(growth_dir) / "topic_candidates.json"

    # Recompute every scheduled run from the fully validated newest analytics
    # snapshot plus the current read-only WordPress catalog.  Reusing a previous
    # Opportunity body based only on metadata would let body corruption or live
    # catalog drift influence unattended draft selection.
    catalog = fetch_current_catalog()
    provenance = audit_reviewed_provenance(catalog, data_dir)
    try:
        opportunities = analyze_growth(
            snapshot, catalog, policy, provenance_by_id=provenance)
    except (GrowthAnalysisError, ValueError, TypeError) as exc:
        raise GrowthAnalysisError("growth_opportunity_refresh_failed") from exc
    opportunities["analytics_snapshot"] = analytics_path.name
    opportunities["analytics_snapshot_sha256"] = analytics_sha
    opportunities["wordpress_catalog_checked_at_utc"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds")

    candidates = _load_private_json(candidates_path, "topic_candidates_unreadable")
    try:
        scores = score_candidates(candidates, opportunities, policy, as_of=as_of)
    except (TopicScoringError, GrowthAnalysisError, ValueError, TypeError) as exc:
        raise GrowthAnalysisError("topic_score_refresh_failed") from exc
    candidate_digest = _canonical_digest(candidates)
    opportunity_digest = opportunity_payload_digest(opportunities)
    opportunities["opportunity_payload_sha256"] = opportunity_digest
    refresh_id = _canonical_digest({
        "analytics_snapshot_sha256": analytics_sha,
        "opportunity_payload_sha256": opportunity_digest,
        "topic_candidates_sha256": candidate_digest,
        "policy_version": policy.get("version"),
        "as_of_date": as_of.isoformat(),
    })
    opportunities = dict(opportunities)
    opportunities["refresh_id"] = refresh_id
    scores["analytics_snapshot_sha256"] = analytics_sha
    scores["opportunity_payload_sha256"] = opportunity_digest
    scores["topic_candidates_sha256"] = candidate_digest
    scores["refresh_id"] = refresh_id

    growth_dir = Path(growth_dir).absolute()
    if growth_dir.is_symlink():
        raise GrowthAnalysisError("growth_output_directory_symlink_not_allowed")
    growth_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix" and growth_dir.stat().st_mode & 0o077:
        raise GrowthAnalysisError("growth_output_directory_permissions_too_open")
    with tempfile.TemporaryDirectory(prefix=".growth-refresh-", dir=growth_dir) as temp_name:
        temp_dir = Path(temp_name)
        if os.name == "posix":
            os.chmod(temp_dir, 0o700)
        staged_opportunities = temp_dir / opportunities_path.name
        staged_scores = temp_dir / scores_path.name
        _atomic_json(staged_opportunities, opportunities)
        _atomic_json(staged_scores, scores)
        os.replace(staged_opportunities, opportunities_path)
        os.replace(staged_scores, scores_path)

    return {
        "analytics_snapshot": analytics_path.name,
        "analytics_snapshot_sha256": analytics_sha,
        "refresh_id": refresh_id,
        "opportunities_refreshed": True,
        "topic_scores_refreshed": True,
        "growth_period_end": (opportunities.get("period") or {}).get("end"),
        "topic_candidates": len(scores.get("candidates", [])),
        "eligible_topic_candidates": int((scores.get("summary") or {}).get(
            "eligible_for_automation", 0)),
    }
