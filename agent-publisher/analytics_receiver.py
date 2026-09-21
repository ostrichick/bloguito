"""Restricted SSH endpoint for private Google analytics snapshots.

The dedicated SSH key is forced to execute this program and cannot run an
arbitrary remote command. No Google credentials are needed on the VPS.
"""

from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
import sys

from analytics_collector import CollectionError, DEFAULT_OUTPUT, markdown_report, save_report, save_snapshot


MAX_INPUT = 4 * 1024 * 1024
GSC_FIELDS = {
    "queries": ("query",),
    "pages": ("page",),
    "daily": ("date",),
}
GA4_FIELDS = {
    "daily": ("date", "activeUsers", "sessions", "screenPageViews"),
    "channels": ("sessionDefaultChannelGroup", "sessions", "activeUsers"),
    "pages": ("pagePath", "screenPageViews", "activeUsers"),
}
GA4_IDENTITY_FIELDS = ("sessionManualSourceMedium", "sessionDefaultChannelGroup", "sessions")


def _valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise CollectionError("invalid_report_date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise CollectionError("invalid_report_date") from None


def validate_snapshot(snapshot, now=None):
    """Fail closed on oversized, malformed, stale, or non-report input."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "schema_version", "collected_at_utc", "period", "search_console", "ga4", "limitations"
    } or snapshot["schema_version"] not in (1, 2):
        raise CollectionError("invalid_snapshot_schema")
    try:
        generated = datetime.fromisoformat(snapshot["collected_at_utc"])
    except (TypeError, ValueError):
        raise CollectionError("invalid_collection_time") from None
    if generated.tzinfo is None or not now - timedelta(hours=24) <= generated <= now + timedelta(minutes=10):
        raise CollectionError("stale_or_future_snapshot")
    period = snapshot["period"]
    if not isinstance(period, dict) or set(period) != {"start", "end", "timezone"}:
        raise CollectionError("invalid_report_period")
    end = _valid_date(period["end"])
    start = _valid_date(period["start"])
    if (end - start).days != 27 or end > now.date() - timedelta(days=1):
        raise CollectionError("invalid_report_period")
    if period["timezone"] != "Google-property-specific":
        raise CollectionError("invalid_report_timezone")
    if not isinstance(snapshot["limitations"], list) or len(snapshot["limitations"]) > 10:
        raise CollectionError("invalid_report_limitations")
    if not all(isinstance(item, str) and len(item) <= 512 for item in snapshot["limitations"]):
        raise CollectionError("invalid_report_limitations")

    for section, groups in (
        ("search_console", GSC_FIELDS),
        ("ga4", GA4_FIELDS if snapshot["schema_version"] == 1 else {
            **GA4_FIELDS, "traffic_identity": GA4_IDENTITY_FIELDS,
        }),
    ):
        data = snapshot[section]
        if not isinstance(data, dict) or set(data) != set(groups):
            raise CollectionError("invalid_report_section")
        for label, rows in data.items():
            if not isinstance(rows, list) or len(rows) > 250:
                raise CollectionError("invalid_report_rows")
            expected = set(groups[label])
            for row in rows:
                if not isinstance(row, dict) or not expected.issubset(row):
                    raise CollectionError("invalid_report_row")
                if len(row) > 10:
                    raise CollectionError("invalid_report_row")
                if not all(isinstance(value, (str, int, float)) and not isinstance(value, bool)
                           and len(str(value)) <= 2048 for value in row.values()):
                    raise CollectionError("invalid_report_value")
                if section == "search_console" and not set(row).issubset(
                    expected | {"clicks", "impressions", "ctr", "position"}
                ):
                    raise CollectionError("invalid_report_row")
                if section == "ga4" and set(row) != expected:
                    raise CollectionError("invalid_report_row")
                dimension_count = 2 if section == "ga4" and label == "traffic_identity" else 1
                if not all(isinstance(row[field], str) for field in groups[label][:dimension_count]):
                    raise CollectionError("invalid_report_label")
                if section == "search_console":
                    for field in ("clicks", "impressions", "ctr", "position"):
                        value = row.get(field)
                        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                                or not math.isfinite(value) or value < 0):
                            raise CollectionError("invalid_search_metrics")
                    if row["ctr"] > 1:
                        raise CollectionError("invalid_search_metrics")
                else:
                    for field in groups[label][dimension_count:]:
                        value = row[field]
                        if not isinstance(value, str) or not re.fullmatch(r"\d{1,20}", value):
                            raise CollectionError("invalid_ga4_metrics")
    # Validate the entire human-readable rendering before writing any file.
    markdown_report(snapshot)
    return snapshot


def receive(data, output_dir=DEFAULT_OUTPUT, now=None):
    if len(data) > MAX_INPUT:
        raise CollectionError("snapshot_too_large")
    try:
        snapshot = json.loads(data)
    except (ValueError, UnicodeError):
        raise CollectionError("invalid_snapshot_json") from None
    validate_snapshot(snapshot, now=now)
    # Write the human view first; the canonical JSON snapshot is the last
    # published file and is never replaced by an incomplete ingestion.
    save_report(snapshot, output_dir)
    save_snapshot(snapshot, output_dir)
    return snapshot["period"]["end"]


def main():
    if os.environ.get("SSH_ORIGINAL_COMMAND", ""):
        print("analytics_ingest_failed:remote_commands_disabled", file=sys.stderr)
        return 1
    data = sys.stdin.buffer.read(MAX_INPUT + 1)
    try:
        end = receive(data)
    except (CollectionError, OSError, TypeError, KeyError, OverflowError):
        print("analytics_ingest_failed:invalid_or_unwritable_report", file=sys.stderr)
        return 1
    print("analytics_ingest_ok end=" + end)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
