"""Read-only, unattended Google Search Console and GA4 reporting.

Credentials are obtained from Google Application Default Credentials (ADC).
Never write credentials, tokens, API responses from failures, or query data to logs.
"""

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import quote


SCOPES = (
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
)
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = BASE_DIR / "data" / "analytics"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
QA_SOURCE_MEDIUM = {
    "bloguito_qa_agent / internal_test": "agent",
    "bloguito_qa_owner / internal_test": "owner",
}


class CollectionError(Exception):
    """A sanitized, operator-actionable failure without request/response secrets."""


def validate_configuration(site_url, property_id):
    if not isinstance(site_url, str) or not (
        re.fullmatch(r"https://[a-zA-Z0-9.-]+/", site_url)
        or re.fullmatch(r"sc-domain:[a-zA-Z0-9.-]+", site_url)
    ):
        raise CollectionError("invalid_search_console_property")
    if not isinstance(property_id, str) or not re.fullmatch(r"[0-9]{1,24}", property_id):
        raise CollectionError("invalid_ga4_property_id")


def date_window(end_date, days=28, today=None):
    today = today or datetime.now(timezone.utc).date()
    if not isinstance(end_date, date) or end_date > today - timedelta(days=1):
        raise CollectionError("report_end_date_must_be_before_today")
    if days < 1 or days > 90:
        raise CollectionError("invalid_report_window")
    return (end_date - timedelta(days=days - 1)).isoformat(), end_date.isoformat()


def google_requester():
    """Create a client that authenticates once and uses only fixed Google endpoints."""
    try:
        import google.auth
        from google.auth.transport.requests import Request
        import requests

        credentials, _ = google.auth.default(scopes=SCOPES)
        credentials.refresh(Request())
    except Exception:
        raise CollectionError("google_credentials_unavailable_or_expired") from None

    session = requests.Session()

    def request(url, payload):
        if not url.startswith((
            "https://www.googleapis.com/webmasters/v3/sites/",
            "https://analyticsdata.googleapis.com/v1beta/properties/",
        )):
            raise CollectionError("unexpected_google_api_endpoint")
        for attempt in range(3):
            try:
                response = session.post(
                    url,
                    headers={"Authorization": "Bearer " + credentials.token},
                    json=payload,
                    timeout=(5, 25),
                    allow_redirects=False,
                )
                if response.status_code in RETRYABLE_STATUSES and attempt < 2:
                    continue
                if response.status_code != 200:
                    raise CollectionError("google_api_http_" + str(response.status_code))
                data = response.json()
                if not isinstance(data, dict):
                    raise CollectionError("google_api_invalid_response")
                return data
            except CollectionError:
                raise
            except Exception:
                raise CollectionError("google_api_network_or_response_error") from None
        raise CollectionError("google_api_retry_exhausted")

    return request


def _rows(response, *, dimensions, metrics):
    rows = response.get("rows", [])
    if not isinstance(rows, list):
        raise CollectionError("google_api_invalid_rows")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise CollectionError("google_api_invalid_row")
        # Search Console's rows carry keys + metric fields; GA4 rows carry
        # dimensionValues + metricValues. Never fabricate missing measurements.
        if metrics is None:
            keys = row.get("keys")
            if not isinstance(keys, list) or len(keys) != len(dimensions):
                raise CollectionError("search_console_invalid_dimensions")
            result.append({**dict(zip(dimensions, keys)), **{
                m: row[m] for m in ("clicks", "impressions", "ctr", "position") if m in row
            }})
        else:
            vals = row.get("dimensionValues", [])
            nums = row.get("metricValues", [])
            if (not isinstance(vals, list) or not isinstance(nums, list)
                    or len(vals) != len(dimensions) or len(nums) != len(metrics)):
                raise CollectionError("ga4_invalid_dimensions_or_metrics")
            if not all(isinstance(v, dict) and "value" in v for v in vals + nums):
                raise CollectionError("ga4_invalid_values")
            result.append({**dict(zip(dimensions, (v["value"] for v in vals))),
                           **dict(zip(metrics, (v["value"] for v in nums)))})
    return result


def collect(site_url, property_id, end_date, requester, days=28):
    """Collect all reports or fail without returning a misleading partial snapshot."""
    validate_configuration(site_url, property_id)
    start, end = date_window(end_date, days)
    gsc_url = ("https://www.googleapis.com/webmasters/v3/sites/"
               + quote(site_url, safe="") + "/searchAnalytics/query")
    gsc = {}
    for label, dimensions in (("queries", ["query"]), ("pages", ["page"]),
                              ("daily", ["date"])):
        data = requester(gsc_url, {
            "startDate": start, "endDate": end, "dimensions": dimensions,
            "rowLimit": 250, "dataState": "final",
        })
        gsc[label] = _rows(data, dimensions=dimensions, metrics=None)

    ga_url = ("https://analyticsdata.googleapis.com/v1beta/properties/"
              + property_id + ":runReport")
    ga4 = {}
    for label, dimensions, metrics in (
        ("daily", ["date"], ["activeUsers", "sessions", "screenPageViews"]),
        ("channels", ["sessionDefaultChannelGroup"], ["sessions", "activeUsers"]),
        ("pages", ["pagePath"], ["screenPageViews", "activeUsers"]),
        ("traffic_identity", ["sessionManualSourceMedium", "sessionDefaultChannelGroup"],
         ["sessions"]),
    ):
        data = requester(ga_url, {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": dim} for dim in dimensions],
            "metrics": [{"name": metric} for metric in metrics],
            "limit": "250",
        })
        if label == "traffic_identity" and data.get("rowCount", len(data.get("rows", []))) > len(data.get("rows", [])):
            raise CollectionError("ga4_traffic_identity_report_truncated")
        ga4[label] = _rows(data, dimensions=dimensions, metrics=metrics)
    return {
        "schema_version": 2, "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "period": {"start": start, "end": end, "timezone": "Google-property-specific"},
        "search_console": gsc, "ga4": ga4,
        "limitations": [
            "Search Console omits anonymized queries and may omit low-volume rows.",
            "Search Console clicks and GA4 sessions measure different things.",
            "GA4 reporting timezone is defined by the GA4 property.",
            "QA labels are voluntary URL tags, not bot detection or proof that other visits are human.",
            "Unmarked Direct traffic remains unverified; historical traffic cannot be reclassified.",
        ],
    }


def _private_directory(path):
    path = Path(path).absolute()
    if path.is_symlink():
        raise CollectionError("report_directory_symlink_not_allowed")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        if path.stat().st_mode & 0o077:
            raise CollectionError("report_directory_permissions_too_open")
    return path


def save_snapshot(snapshot, output_dir):
    """Only publish a complete JSON snapshot; use private, atomic local writes."""
    directory = _private_directory(output_dir)
    filename = "google-analytics-" + snapshot["period"]["end"] + ".json"
    target = directory / filename
    if target.is_symlink():
        raise CollectionError("report_target_symlink_not_allowed")
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory,
                                         prefix=".analytics-", suffix=".tmp",
                                         delete=False) as handle:
            temp = Path(handle.name)
            os.chmod(temp, 0o600)
            json.dump(snapshot, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return target


def markdown_report(snapshot):
    """A source-labelled, bounded human-readable report; not an AI inference."""
    from html import escape

    period = snapshot["period"]
    lines = ["# Bloguito Google 검색·방문 보고서",
             "", "기간: " + period["start"] + " ~ " + period["end"],
             "출처: Google Search Console API / Google Analytics Data API",
             "", "## Search Console 검색어 (클릭수 기준)",
             "", "| 검색어 | 클릭 | 노출 | CTR | 평균 게재순위 |",
             "| --- | ---: | ---: | ---: | ---: |"]
    queries = sorted(snapshot["search_console"]["queries"],
                     key=lambda row: float(row.get("clicks", 0)), reverse=True)
    for row in queries[:20]:
        keyword = str(row["query"]).replace("|", "\\|").replace("\n", " ")[:120]
        lines.append("| " + escape(keyword) + " | " + str(row.get("clicks", "—"))
                     + " | " + str(row.get("impressions", "—"))
                     + " | " + ("{:.1%}".format(row["ctr"]) if "ctr" in row else "—")
                     + " | " + ("{:.1f}".format(row["position"]) if "position" in row else "—")
                     + " |")
    if not queries:
        lines.append("| 조회된 검색어 없음 | — | — | — | — |")

    lines += ["", "## Google Analytics 유입 경로", "",
              "| 경로 | 세션 | 활성 사용자 |", "| --- | ---: | ---: |"]
    for row in sorted(snapshot["ga4"]["channels"],
                      key=lambda entry: int(entry["sessions"]), reverse=True)[:20]:
        channel = escape(str(row["sessionDefaultChannelGroup"]).replace("|", "\\|")[:100])
        lines.append("| " + channel + " | " + row["sessions"] + " | "
                     + row["activeUsers"] + " |")
    if not snapshot["ga4"]["channels"]:
        lines.append("| 조회된 데이터 없음 | — | — |")
    lines += ["", "## 개발·에이전트 방문 구분", ""]
    if snapshot["schema_version"] == 2:
        identity = classify_traffic(snapshot["ga4"])
        lines += [
            "| 구분 | 세션 |", "| --- | ---: |",
            "| QA 태그: 에이전트 | " + str(identity["agent_sessions"]) + " |",
            "| QA 태그: 소유자 비로그인 테스트 | " + str(identity["owner_sessions"]) + " |",
            "| 태그 없는 Direct (사람/봇 미확인) | " + str(identity["unverified_direct_sessions"]) + " |",
            "| QA 태그 없는 기타 유입 (실제 사람 확정 아님) | " + str(identity["unverified_other_sessions"]) + " |",
        ]
        if identity["unaccounted_sessions"]:
            lines.append("| 출처 보고서와 채널 보고서 차이 (미분류) | "
                         + str(identity["unaccounted_sessions"]) + " |")
        if not identity["complete"]:
            lines.append("\n주의: 출처별 세션 합계와 채널별 세션 합계가 달라 분류 결과는 불완전합니다.")
        lines.append("\nQA 수치는 지정된 UTM 링크로 시작한 세션만 의미하며 "
                     "과거 비표시 방문·실제 봇·일반 독자를 자동 판별하지 않습니다.")
    else:
        lines.append("과거 수집 형식: 개발 방문을 식별하지 않았습니다. Direct를 실제 독자로 간주하지 않습니다.")
    lines += ["", "## 해석 범위", "",
              "- Search Console은 익명화된 검색어와 일부 소량 데이터를 제공하지 않을 수 있습니다.",
              "- Search Console 클릭과 GA4 세션은 정의가 달라 직접 비교할 수 없습니다.",
              "- 이 보고서는 API가 반환한 값만 표시하며 증가 원인이나 검색 순위 개선을 추정하지 않습니다.", ""]
    return "\n".join(lines)


def classify_traffic(ga4):
    """Separate explicitly QA-labelled sessions; never infer human identity.

    Both dimensions and the metric are session-scoped. Do not silently claim
    that an incomplete GA4 report is a complete population.
    """
    counts = {"agent_sessions": 0, "owner_sessions": 0,
              "unverified_direct_sessions": 0, "unverified_other_sessions": 0}
    for row in ga4["traffic_identity"]:
        sessions = int(row["sessions"])
        label = QA_SOURCE_MEDIUM.get(row["sessionManualSourceMedium"])
        if label:
            counts[label + "_sessions"] += sessions
        elif row["sessionDefaultChannelGroup"] == "Direct":
            counts["unverified_direct_sessions"] += sessions
        else:
            counts["unverified_other_sessions"] += sessions
    expected = sum(int(row["sessions"]) for row in ga4["channels"])
    actual = sum(counts.values())
    counts["unaccounted_sessions"] = expected - actual
    counts["complete"] = expected == actual
    return counts


def save_report(snapshot, output_dir):
    directory = _private_directory(output_dir)
    target = directory / ("google-analytics-" + snapshot["period"]["end"] + ".md")
    if target.is_symlink():
        raise CollectionError("report_target_symlink_not_allowed")
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory,
                                         prefix=".analytics-", suffix=".tmp",
                                         delete=False) as handle:
            temp = Path(handle.name)
            os.chmod(temp, 0o600)
            handle.write(markdown_report(snapshot))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private read-only Google reports")
    parser.add_argument("--site-url", default=os.environ.get("BLOGUITO_GSC_SITE_URL", ""))
    parser.add_argument("--ga4-property", default=os.environ.get("BLOGUITO_GA4_PROPERTY_ID", ""))
    parser.add_argument("--end-date", default=(datetime.now(timezone.utc).date()
                        - timedelta(days=3)).isoformat())
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        end_date = date.fromisoformat(args.end_date)
        validate_configuration(args.site_url, args.ga4_property)
        date_window(end_date)
        snapshot = collect(args.site_url, args.ga4_property, end_date, google_requester())
        save_snapshot(snapshot, args.output_dir)
        save_report(snapshot, args.output_dir)
    except (ValueError, CollectionError) as exc:
        # Do not print exception chains or Google response bodies, which can
        # contain tokens, headers, URL query parameters, or private metrics.
        code = str(exc) if isinstance(exc, CollectionError) else "invalid_date"
        print("analytics_collection_failed:" + code, file=sys.stderr)
        return 1
    print("analytics_collection_ok end=" + end_date.isoformat()
          + " search_query_rows=" + str(len(snapshot["search_console"]["queries"]))
          + " ga4_day_rows=" + str(len(snapshot["ga4"]["daily"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
