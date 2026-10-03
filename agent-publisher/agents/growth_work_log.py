"""Private completion log for Bloguito growth work.

This state never edits WordPress. It records completed planner-selected
existing-page improvements and successful scheduled new drafts. The log lets
the planner avoid reusing stale signals or the same brief and maintain an
intentional work mix without treating a mere plan selection as completion.
"""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile


class GrowthWorkLogError(ValueError):
    """Fail-closed work-log validation or storage error."""


def empty_work_log() -> dict:
    return {"schema_version": 1, "entries": []}


def _parse_date(value, code: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise GrowthWorkLogError(code) from None


def validate_work_log(log: dict, *, as_of: date | None = None) -> dict:
    if (not isinstance(log, dict) or log.get("schema_version") != 1
            or not isinstance(log.get("entries"), list)):
        raise GrowthWorkLogError("invalid_growth_work_log")
    seen = set()
    for row in log["entries"]:
        if not isinstance(row, dict):
            raise GrowthWorkLogError("invalid_growth_work_log_entry")
        action = row.get("action")
        if action not in {"existing_improvement", "new_draft"} or row.get("outcome") != "completed":
            raise GrowthWorkLogError("invalid_growth_work_log_entry")
        if type(row.get("post_id")) is not int or row["post_id"] <= 0:
            raise GrowthWorkLogError("invalid_growth_work_log_post_id")
        completed = _parse_date(row.get("completed_on"), "invalid_growth_work_log_completed_on")
        if action == "existing_improvement":
            recheck = _parse_date(row.get("recheck_after"), "invalid_growth_work_log_recheck_after")
            period_end = _parse_date(
                row.get("opportunity_period_end"), "invalid_growth_work_log_opportunity_period_end")
            if completed < period_end or recheck < completed:
                raise GrowthWorkLogError("invalid_growth_work_log_date_order")
        else:
            if not isinstance(row.get("brief_id"), str) or not row["brief_id"].strip():
                raise GrowthWorkLogError("invalid_growth_work_log_brief_id")
        if as_of is not None and completed > as_of:
            raise GrowthWorkLogError("future_growth_work_completion")
        event_id = row.get("event_id")
        if not isinstance(event_id, str) or len(event_id) != 64 or event_id in seen:
            raise GrowthWorkLogError("invalid_growth_work_log_event_id")
        seen.add(event_id)
    return log


def suppressed_post_ids(log: dict, *, opportunity_period_end: date, as_of: date) -> set[int]:
    """Return posts whose completed work still lacks enough post-change GSC time."""
    validate_work_log(log, as_of=as_of)
    latest: dict[int, dict] = {}
    for row in log["entries"]:
        if row.get("action") != "existing_improvement":
            continue
        current = latest.get(row["post_id"])
        if current is None or row["completed_on"] > current["completed_on"]:
            latest[row["post_id"]] = row
    return {
        post_id
        for post_id, row in latest.items()
        if opportunity_period_end < _parse_date(
            row["recheck_after"], "invalid_growth_work_log_recheck_after")
    }


def completed_new_brief_ids(log: dict, *, as_of: date) -> set[str]:
    """Return scheduler brief IDs that already produced a WordPress draft."""
    validate_work_log(log, as_of=as_of)
    return {
        row["brief_id"]
        for row in log["entries"]
        if row.get("action") == "new_draft"
    }


def recent_work_mix(log: dict, *, as_of: date, limit: int) -> dict:
    """Summarize the most recent completed scheduler growth actions."""
    validate_work_log(log, as_of=as_of)
    if type(limit) is not int or limit < 1:
        raise GrowthWorkLogError("invalid_growth_work_mix_limit")
    rows = sorted(
        log["entries"],
        key=lambda row: _parse_date(row["completed_on"], "invalid_growth_work_log_completed_on"),
    )[-limit:]
    existing = sum(1 for row in rows if row.get("action") == "existing_improvement")
    new = sum(1 for row in rows if row.get("action") == "new_draft")
    return {
        "lookback": limit,
        "observed": len(rows),
        "existing_improvement": existing,
        "new_draft": new,
        "last_action": rows[-1]["action"] if rows else None,
    }


def record_existing_completion(log: dict, daily_plan: dict, policy: dict, *,
                               post_id: int, completed_on: date, note: str = "") -> dict:
    """Idempotently append a completion bound to the current planner-selected target."""
    from agents.growth_planner import daily_planner_digest

    validate_work_log(log, as_of=completed_on)
    if not isinstance(daily_plan, dict) or daily_plan.get("schema_version") != 1:
        raise GrowthWorkLogError("invalid_daily_growth_plan")
    if daily_plan.get("daily_planner_digest") != daily_planner_digest(policy):
        raise GrowthWorkLogError("daily_growth_plan_policy_mismatch")
    plan_day = _parse_date(
        daily_plan.get("as_of_date"), "invalid_daily_growth_plan_as_of_date")
    if plan_day != completed_on:
        raise GrowthWorkLogError("daily_growth_plan_not_current_for_completion")
    if daily_plan.get("action") != "existing_improvement":
        raise GrowthWorkLogError("daily_growth_plan_not_existing_improvement")
    target = daily_plan.get("target")
    if not isinstance(target, dict) or target.get("post_id") != post_id:
        raise GrowthWorkLogError("daily_growth_plan_post_mismatch")
    inputs = daily_plan.get("inputs") if isinstance(daily_plan.get("inputs"), dict) else {}
    period_end = _parse_date(
        inputs.get("opportunity_period_end"), "invalid_daily_growth_plan_opportunity_period")
    if completed_on < period_end:
        raise GrowthWorkLogError("growth_completion_before_observation_period")
    planner = policy.get("daily_planner") if isinstance(policy, dict) else None
    recheck_days = planner.get("existing_recheck_days") if isinstance(planner, dict) else None
    if type(recheck_days) is not int or recheck_days < 1:
        raise GrowthWorkLogError("invalid_existing_recheck_days")
    recheck_after = completed_on + timedelta(days=recheck_days)
    payload = {
        "action": "existing_improvement",
        "outcome": "completed",
        "post_id": post_id,
        "title": target.get("title"),
        "classification": target.get("classification"),
        "recommended_action": target.get("recommended_action"),
        "completed_on": completed_on.isoformat(),
        "opportunity_period_end": period_end.isoformat(),
        "recheck_after": recheck_after.isoformat(),
        "note": note.strip(),
    }
    event_raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    payload["event_id"] = hashlib.sha256(event_raw).hexdigest()
    if any(row.get("event_id") == payload["event_id"] for row in log["entries"]):
        return log
    return {"schema_version": 1, "entries": [*log["entries"], payload]}


def record_new_draft_completion(log: dict, daily_plan: dict, policy: dict, *,
                                post_id: int, completed_on: date, title: str = "") -> dict:
    """Idempotently record one scheduler-selected new draft after verified creation."""
    from agents.growth_planner import daily_planner_digest

    validate_work_log(log, as_of=completed_on)
    if not isinstance(daily_plan, dict) or daily_plan.get("schema_version") != 1:
        raise GrowthWorkLogError("invalid_daily_growth_plan")
    if daily_plan.get("daily_planner_digest") != daily_planner_digest(policy):
        raise GrowthWorkLogError("daily_growth_plan_policy_mismatch")
    plan_day = _parse_date(
        daily_plan.get("as_of_date"), "invalid_daily_growth_plan_as_of_date")
    if plan_day != completed_on:
        raise GrowthWorkLogError("daily_growth_plan_not_current_for_completion")
    if daily_plan.get("action") != "new_draft":
        raise GrowthWorkLogError("daily_growth_plan_not_new_draft")
    target = daily_plan.get("target")
    if not isinstance(target, dict):
        raise GrowthWorkLogError("invalid_daily_growth_plan_target")
    brief_id = target.get("brief_id")
    if not isinstance(brief_id, str) or not brief_id.strip():
        raise GrowthWorkLogError("invalid_daily_growth_plan_brief_id")
    if type(post_id) is not int or post_id <= 0:
        raise GrowthWorkLogError("invalid_growth_work_log_post_id")
    payload = {
        "action": "new_draft",
        "outcome": "completed",
        "post_id": post_id,
        "brief_id": brief_id,
        "candidate_id": target.get("candidate_id"),
        "category_key": target.get("category_key"),
        "title": title.strip(),
        "completed_on": completed_on.isoformat(),
    }
    event_raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    payload["event_id"] = hashlib.sha256(event_raw).hexdigest()
    if any(row.get("event_id") == payload["event_id"] for row in log["entries"]):
        return log
    if any(row.get("action") == "new_draft" and row.get("brief_id") == brief_id
           for row in log["entries"]):
        raise GrowthWorkLogError("growth_new_brief_already_completed")
    return {"schema_version": 1, "entries": [*log["entries"], payload]}


def save_work_log(log: dict, path: str | Path) -> Path:
    target = Path(path).absolute()
    directory = target.parent
    if directory.is_symlink() or target.is_symlink():
        raise GrowthWorkLogError("growth_work_log_symlink_not_allowed")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix" and directory.stat().st_mode & 0o077:
        raise GrowthWorkLogError("growth_work_log_directory_permissions_too_open")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, prefix=".growth-work-",
                suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            if os.name == "posix":
                os.chmod(temp, 0o600)
            json.dump(log, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return target
