"""Deterministic KST availability policy using labelled source evidence only."""
import re
from datetime import date, datetime, time, timedelta, timezone

KST = timezone(timedelta(hours=9))
STAMP = re.compile(r"(?<!\d)(?:(\d{4})\s*(?:년\s*|[./-]\s*))?(\d{1,2})\s*(?:월\s*|[./-]\s*)(\d{1,2})\s*일?(?:\s*\([^)]*\))?(?:\s*(오전|오후)?\s*(\d{1,2})(?:시|:)(?:(\d{1,2})\s*분?)?)?")
LABELS = {
    "event": r"공연일시|행사일시|행사기간|공연기간",
    "application": r"신청기간|접수기간|신청마감|접수마감",
    "sale": r"예매기간|판매기간|예매오픈|티켓오픈",
    "status": r"판매상태|예매상태|접수상태|신청상태",
}

YES24_LISTING = re.compile(
    r'(?m)^\[(?P<region>[가-힣]{2,12})\] (?P<title>[^\n]{4,130})\n'
    r'(?P<start>\d{4}\.\d{2}\.\d{2}) ~ (?P<end>\d{4}\.\d{2}\.\d{2})ㅣ'
    r'(?P<venue>[^\n]{3,120})\n예매(?=\n|$)'
)


def extract_yes24_schedule(text: str, artist: str) -> list[dict]:
    """Read only dated venue rows with an actual booking button on a YES24 listing.

    A visible booking link is not evidence of tickets remaining or a sale deadline.
    No estimated sale period is derived from the last concert date.
    """
    if not isinstance(artist, str) or len(artist.strip()) < 2:
        return []
    rows = []
    for match in YES24_LISTING.finditer(text):
        if artist not in match['title'] or match['start'] != match['end']:
            continue
        try:
            date.fromisoformat(match['start'].replace('.', '-'))
        except ValueError:
            continue
        rows.append({'region': match['region'], 'date': match['start'],
                     'venue': match['venue']})
    return rows


def extract_evidence(text: str, url: str) -> list[dict]:
    # A field ends at a newline, sentence boundary or the next recognised label.
    labels = "|".join(LABELS.values())
    pattern = re.compile(r"(?P<label>" + labels + r")\s*[:：]\s*(?P<value>.*?)(?=\n|[。]|[.!?]\s|(?:" + labels + r")\s*[:：]|$)")
    return [{"kind": kind, "label": m["label"], "value": m["value"].strip(), "source_url": url}
            for m in pattern.finditer(text)
            for kind, expression in LABELS.items() if re.fullmatch(expression, m["label"])]


def _bounds(field: dict) -> tuple[datetime | None, datetime | None]:
    value = field["value"]
    matches = list(STAMP.finditer(value))
    if not matches or len(matches) > 2:
        raise ValueError("missing_or_ambiguous_dates")
    year = None
    parsed = []
    for i, m in enumerate(matches):
        y, month, day, period, hour, minute = m.groups()
        year = int(y) if y else year
        if year is None:
            raise ValueError("year_missing")
        h = int(hour) if hour else None
        if period:
            if not 1 <= h <= 12:
                raise ValueError("invalid_hour")
            h = h % 12 + (12 if period == "오후" else 0)
        # Date-only deadlines include the full day in Korea.
        end = i == len(matches) - 1 and not re.search(r"오픈", field["label"])
        clock = time(h, int(minute or 0)) if h is not None else (time.max if end else time.min)
        parsed.append(datetime(int(year), int(month), int(day), clock.hour, clock.minute, clock.second, clock.microsecond, tzinfo=KST))
    if len(parsed) == 2:
        if not re.search(r"~|∼|～|부터|–|—|\s-\s", value[matches[0].end():matches[1].start()]):
            raise ValueError("range_separator_missing")
        if parsed[0] > parsed[1]:
            raise ValueError("reversed_range")
        return parsed[0], parsed[1]
    if "오픈" in field["label"]:
        return parsed[0], None
    if "기간" in field["label"]:
        raise ValueError("period_requires_both_bounds")
    return None, parsed[0]


def validate_availability(source: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(KST)
    if now.tzinfo is None:
        raise ValueError("reference time must be timezone-aware")
    now = now.astimezone(KST)
    evidence = source.get("evidence", [])
    result = {"status": "needs_review", "reasons": [], "checked_at": now.isoformat(), "evidence": evidence, "expires_at": None}
    reasons = result["reasons"]
    deadlines = []
    kinds = set()
    states = []
    bounds_by_kind = {}
    for field in evidence:
        if not field.get("source_url", "").startswith(("https://", "http://")):
            reasons.append("source_url_missing")
            continue
        kind = field.get("kind")
        if source.get("requires_sale") and kind in {"sale", "status"} and field["source_url"] != source.get("sale_source_url"):
            reasons.append("sale_evidence_not_from_verified_product")
            continue
        kinds.add(kind)
        if kind == "status":
            state = field.get("value", "").strip()
            if state in {"판매중", "예매중", "접수중", "신청가능"}:
                states.append("active")
            elif state in {"판매종료", "예매마감", "접수마감", "신청마감", "매진", "취소"}:
                states.append("closed")
            else:
                reasons.append("status_unknown")
            continue
        try:
            start, end = _bounds(field)
            bounds = (start, end)
            if kind in bounds_by_kind and bounds_by_kind[kind] != bounds:
                reasons.append("conflicting_dates")
            bounds_by_kind[kind] = bounds
            if start and now < start and kind in {"application", "sale"}:
                reasons.append("not_open_yet")
            if end:
                deadlines.append(end)
                if now > end:
                    reasons.append("deadline_passed")
        except (ValueError, TypeError, KeyError):
            reasons.append("date_missing_invalid_or_ambiguous")
    if "closed" in states:
        reasons.append("explicitly_closed")
    if len(set(states)) > 1:
        reasons.append("conflicting_status")
    if source.get("requires_sale") and ("active" not in states or "sale" not in kinds):
        reasons.append("sale_status_or_period_unconfirmed")
    if source.get("requires_sale") and not bounds_by_kind.get("sale", (None, None))[1]:
        reasons.append("sale_deadline_unconfirmed")
    if not deadlines:
        reasons.append("deadline_unconfirmed")
    if deadlines:
        result["expires_at"] = min(deadlines).isoformat()
    result["reasons"] = list(dict.fromkeys(reasons))
    if not reasons:
        result["status"] = "active"
    elif any(reason in reasons for reason in ("deadline_passed", "explicitly_closed")):
        result["status"] = "closed"
    return result
