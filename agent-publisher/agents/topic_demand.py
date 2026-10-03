"""Measured external-demand enrichment for reviewed private topic candidates.

This module never invents candidate topics or search volume. Its first provider
is Naver DataLab's official search-trend API, whose ``ratio`` values are
relative interest rather than absolute query counts. By default only candidates
with an exact text-normalized match against a fresh Search Console query are
sent to the external provider, preserving the GSC-first discovery policy.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import json
import math
import os
from pathlib import Path
import re
import tempfile
import unicodedata


NAVER_DATALAB_ENDPOINT = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
NAVER_MAX_GROUPS = 5
NAVER_MAX_KEYWORDS_PER_GROUP = 20
NAVER_TIME_UNITS = {"date", "week", "month"}
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class TopicDemandError(ValueError):
    """Fail-closed demand-collection or private-storage error."""


def _normal_text(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value)).casefold()
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def _parse_date(value, *, code: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise TopicDemandError(code) from None


def measurement_window(as_of: date, *, days: int = 90) -> tuple[date, date]:
    """Return a complete trailing window ending yesterday."""
    if not isinstance(as_of, date) or type(days) is not int or not 7 <= days <= 365:
        raise TopicDemandError("invalid_topic_demand_window")
    end = as_of - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    return start, end


def matching_gsc_queries(candidate: dict, growth_report: dict) -> list[dict]:
    """Return only literal normalized GSC query matches for explicit gsc_terms."""
    terms = {
        _normal_text(term)
        for term in candidate.get("gsc_terms", [])
        if isinstance(term, str) and _normal_text(term)
    }
    if not terms:
        return []
    matched = []
    for row in growth_report.get("top_queries_global", []):
        if not isinstance(row, dict) or not isinstance(row.get("query"), str):
            continue
        query_norm = _normal_text(row["query"])
        if any(term in query_norm for term in terms):
            matched.append({
                "query": row["query"],
                "clicks": int(row.get("clicks") or 0),
                "impressions": int(row.get("impressions") or 0),
                "position": row.get("position"),
            })
    return matched


def select_measurement_candidates(candidate_document: dict, growth_report: dict, *,
                                  as_of: date, max_gsc_age_days: int,
                                  require_gsc_seed: bool = True) -> tuple[list[dict], str | None]:
    """Select reviewed candidates for measurement without inventing semantic matches."""
    if (not isinstance(candidate_document, dict)
            or candidate_document.get("schema_version") != 1
            or not isinstance(candidate_document.get("candidates"), list)):
        raise TopicDemandError("invalid_topic_candidates_document")
    if (not isinstance(growth_report, dict)
            or growth_report.get("schema_version") != 1
            or not isinstance(growth_report.get("period"), dict)):
        raise TopicDemandError("invalid_growth_opportunity_report")
    if type(max_gsc_age_days) is not int or max_gsc_age_days < 0:
        raise TopicDemandError("invalid_gsc_seed_freshness")
    end = _parse_date(growth_report["period"].get("end"), code="invalid_growth_report_period")
    age = (as_of - end).days
    if require_gsc_seed and (age < 0 or age > max_gsc_age_days):
        return [], "gsc_seed_report_stale"

    selected = []
    for candidate in candidate_document["candidates"]:
        if not isinstance(candidate, dict):
            raise TopicDemandError("invalid_topic_candidate")
        matches = matching_gsc_queries(candidate, growth_report)
        if require_gsc_seed and not matches:
            continue
        selected.append({"candidate": candidate, "gsc_matches": matches})
    return selected, None


def _candidate_keywords(candidate: dict) -> list[str]:
    values = [candidate.get("primary_keyword"), *candidate.get("gsc_terms", [])]
    result = []
    seen = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        normalized = _normal_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value.strip())
        if len(result) >= NAVER_MAX_KEYWORDS_PER_GROUP:
            break
    if not result:
        raise TopicDemandError("topic_candidate_has_no_measurement_keywords")
    return result


def _chunks(values: list[dict], size: int):
    for offset in range(0, len(values), size):
        yield values[offset:offset + size]


def naver_datalab_requester(client_id: str, client_secret: str):
    """Return a fixed NAVER API HUB requester without logging credentials or bodies."""
    if not isinstance(client_id, str) or not client_id.strip():
        raise TopicDemandError("naver_datalab_credentials_unavailable")
    if not isinstance(client_secret, str) or not client_secret.strip():
        raise TopicDemandError("naver_datalab_credentials_unavailable")
    try:
        import requests
    except Exception:
        raise TopicDemandError("naver_datalab_requests_dependency_unavailable") from None

    session = requests.Session()

    def request(payload: dict) -> dict:
        for attempt in range(3):
            try:
                response = session.post(
                    NAVER_DATALAB_ENDPOINT,
                    headers={
                        "X-NCP-APIGW-API-KEY-ID": client_id,
                        "X-NCP-APIGW-API-KEY": client_secret,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=(5, 25),
                    allow_redirects=False,
                )
                if response.status_code in RETRYABLE_STATUSES and attempt < 2:
                    continue
                if response.status_code != 200:
                    raise TopicDemandError("naver_datalab_http_" + str(response.status_code))
                data = response.json()
                if not isinstance(data, dict):
                    raise TopicDemandError("naver_datalab_invalid_response")
                return data
            except TopicDemandError:
                raise
            except Exception:
                raise TopicDemandError("naver_datalab_network_or_response_error") from None
        raise TopicDemandError("naver_datalab_retry_exhausted")

    return request


def _relative_interest(result: dict) -> float | None:
    data = result.get("data")
    if not isinstance(data, list):
        raise TopicDemandError("naver_datalab_invalid_result_data")
    if not data:
        return None
    ratios = []
    for row in data:
        if not isinstance(row, dict) or "ratio" not in row:
            raise TopicDemandError("naver_datalab_invalid_ratio")
        try:
            ratio = float(row["ratio"])
        except (TypeError, ValueError):
            raise TopicDemandError("naver_datalab_invalid_ratio") from None
        if not math.isfinite(ratio) or not 0 <= ratio <= 100:
            raise TopicDemandError("naver_datalab_invalid_ratio")
        ratios.append(ratio)
    return round(sum(ratios) / len(ratios), 4)


def _validated_response_period(response: dict, payload: dict) -> tuple[str, str]:
    """Validate API HUB's granularity-normalized response window.

    Search Trend can widen weekly/monthly requests to provider period
    boundaries.  Accept only small boundary expansion that still fully covers
    the requested window, rather than requiring an exact date echo.
    """
    if response.get("timeUnit") != payload.get("timeUnit"):
        raise TopicDemandError("naver_datalab_invalid_response")
    if not isinstance(response.get("results"), list):
        raise TopicDemandError("naver_datalab_invalid_response")
    request_start = _parse_date(
        payload.get("startDate"), code="naver_datalab_invalid_request_period")
    request_end = _parse_date(
        payload.get("endDate"), code="naver_datalab_invalid_request_period")
    response_start = _parse_date(
        response.get("startDate"), code="naver_datalab_invalid_response_period")
    response_end = _parse_date(
        response.get("endDate"), code="naver_datalab_invalid_response_period")
    if response_start > request_start or response_end < request_end:
        raise TopicDemandError("naver_datalab_invalid_response_period")
    max_expansion_days = {"date": 0, "week": 6, "month": 31}.get(
        payload.get("timeUnit"))
    if max_expansion_days is None:
        raise TopicDemandError("invalid_naver_datalab_time_unit")
    if ((request_start - response_start).days > max_expansion_days
            or (response_end - request_end).days > max_expansion_days):
        raise TopicDemandError("naver_datalab_invalid_response_period")
    return response_start.isoformat(), response_end.isoformat()


def _replace_provider_evidence(candidate: dict, evidence: dict) -> None:
    existing = candidate.get("demand_evidence")
    if not isinstance(existing, list):
        raise TopicDemandError("invalid_topic_candidate_demand_evidence")
    candidate["demand_evidence"] = [
        row for row in existing
        if not (isinstance(row, dict)
                and row.get("source") == evidence["source"]
                and row.get("metric") == evidence["metric"])
    ] + [evidence]


def collect_naver_datalab(candidate_document: dict, growth_report: dict, requester, *,
                          collected_on: date, max_gsc_age_days: int,
                          require_gsc_seed: bool = True, window_days: int = 90,
                          time_unit: str = "week") -> tuple[dict, dict]:
    """Measure Naver relative interest and return an enriched copy plus summary."""
    if time_unit not in NAVER_TIME_UNITS:
        raise TopicDemandError("invalid_naver_datalab_time_unit")
    start, end = measurement_window(collected_on, days=window_days)
    selected, selection_reason = select_measurement_candidates(
        candidate_document, growth_report, as_of=collected_on,
        max_gsc_age_days=max_gsc_age_days, require_gsc_seed=require_gsc_seed,
    )
    updated = deepcopy(candidate_document)
    by_id = {candidate["id"]: candidate for candidate in updated["candidates"]}
    measured = 0
    unavailable = []
    requests_made = 0
    provider_period = None

    for batch in _chunks(selected, NAVER_MAX_GROUPS):
        groups = []
        labels = {}
        for index, item in enumerate(batch):
            candidate = item["candidate"]
            label = "g" + str(index)
            labels[label] = item
            groups.append({
                "groupName": label,
                "keywords": _candidate_keywords(candidate),
            })
        payload = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "timeUnit": time_unit,
            "keywordGroups": groups,
        }
        response = requester(payload)
        requests_made += 1
        response_period = _validated_response_period(response, payload)
        if provider_period is None:
            provider_period = response_period
        elif provider_period != response_period:
            raise TopicDemandError("naver_datalab_inconsistent_response_period")
        seen_labels = set()
        for result in response["results"]:
            if not isinstance(result, dict) or result.get("title") not in labels:
                raise TopicDemandError("naver_datalab_unexpected_result_group")
            label = result["title"]
            if label in seen_labels:
                raise TopicDemandError("naver_datalab_duplicate_result_group")
            seen_labels.add(label)
            item = labels[label]
            candidate = item["candidate"]
            value = _relative_interest(result)
            if value is None:
                unavailable.append(candidate["id"])
                continue
            evidence = {
                "source": "naver_datalab",
                "metric": "relative_interest",
                "value": value,
                "collected_at": collected_on.isoformat(),
                "measured": True,
                "period_start": response_period[0],
                "period_end": response_period[1],
                "requested_period_start": start.isoformat(),
                "requested_period_end": end.isoformat(),
                "time_unit": time_unit,
                "aggregation": "mean_period_ratio",
                "keywords": _candidate_keywords(candidate),
                "gsc_seed_queries": [row["query"] for row in item["gsc_matches"]],
                "normalization_group_size": len(batch),
            }
            _replace_provider_evidence(by_id[candidate["id"]], evidence)
            measured += 1
        missing = set(labels) - seen_labels
        unavailable.extend(labels[label]["candidate"]["id"] for label in sorted(missing))

    return updated, {
        "provider": "naver_datalab",
        "selected": len(selected),
        "measured": measured,
        "unavailable": sorted(set(unavailable)),
        "requests_made": requests_made,
        "selection_reason": selection_reason,
        "require_gsc_seed": require_gsc_seed,
        "period": {"start": start.isoformat(), "end": end.isoformat(), "time_unit": time_unit},
        "provider_period": ({"start": provider_period[0], "end": provider_period[1]}
                            if provider_period is not None else None),
        "metric_note": "relative interest only; not absolute search volume",
    }


def save_candidate_document(document: dict, path: str | Path) -> Path:
    """Atomically replace a private candidate document without following symlinks."""
    target = Path(path).absolute()
    directory = target.parent
    if directory.is_symlink():
        raise TopicDemandError("topic_candidate_directory_symlink_not_allowed")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix" and directory.stat().st_mode & 0o077:
        raise TopicDemandError("topic_candidate_directory_permissions_too_open")
    if target.is_symlink():
        raise TopicDemandError("topic_candidate_target_symlink_not_allowed")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, prefix=".topic-demand-",
                suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            if os.name == "posix":
                os.chmod(temp, 0o600)
            json.dump(document, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return target
