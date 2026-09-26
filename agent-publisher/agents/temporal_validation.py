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

TICKETLINK_BRIDGE = re.compile(
    r'(?m)^지역/제목\n(?P<region>[^\n]{1,20})\n(?P<title>[^\n]{4,160})\n'
    r'기간\n(?P<start>\d{4}\.\d{2}\.\d{2})\s*~\n(?P<end>\d{4}\.\d{2}\.\d{2})\n'
    r'장소\n(?P<venue>[^\n]{2,140})\n(?P<status>예매하기|판매 예정|판매 종료)(?=\n|$)'
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


def extract_ticketlink_bridge_schedule(text: str, artist: str) -> list[dict]:
    """Read current single-day tour rows with a booking action from Ticketlink."""
    if not isinstance(artist, str) or len(artist.strip()) < 2:
        return []
    rows = []
    for match in TICKETLINK_BRIDGE.finditer(text):
        if (artist not in match['title'] or match['status'] != '예매하기'
                or match['start'] != match['end']):
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


def validate_legacy_followup(brief: dict, sources: list[dict], temporal: dict,
                             plan: dict, now: datetime) -> list[str]:
    """Check cited past and future dates in a *specific existing* welfare article.

    This does not certify that applications are open. It permits an article about
    a completed application and officially documented future routes to undergo
    independent review. No uncited calendar fields or model-generated evidence
    can satisfy it. New articles still use validate_availability().
    """
    reasons = []
    lifecycle = temporal.get('legacy_followup')
    if (not isinstance(lifecycle, dict) or brief.get('category_key') != 'welfare'
            or brief.get('content_type') != 'dated'
            or not isinstance(brief.get('existing_post_id'), int)
            or brief['existing_post_id'] <= 0):
        return ['legacy_followup_not_for_existing_welfare_post']
    source_map = {s.get('id'): s for s in sources if isinstance(s, dict)}

    def cited_date(item, field):
        if not isinstance(item, dict):
            reasons.append('legacy_followup_invalid_item')
            return None
        try:
            day = date.fromisoformat(item[field])
            evidence = item['evidence']
            source = source_map[evidence['source_id']]
            quote = evidence['quote']
            if (not isinstance(quote, str) or not 16 <= len(quote) <= 600
                    or quote not in source['text']
                    or source.get('source_type') != 'official'
                    or source.get('url') not in brief['official_urls']):
                raise ValueError('unbound')
            year2 = str(day.year)[-2:]
            year = re.search(r'(?<!\d)(?:'+str(day.year)+r'|[’\']?'+year2
                             +r')\s*(?:년|[./-])', quote)
            month_day = re.search(r'(?<!\d)0?'+str(day.month)+r'\s*(?:월|[./-])\s*0?'
                                  +str(day.day)+r'\s*(?:일|[.\s~∼～)\-]|$)', quote)
            if not year or not month_day:
                raise ValueError('date_not_in_quote')
            return day
        except (KeyError, TypeError, ValueError):
            reasons.append('legacy_followup_date_or_evidence_unverified')
            return None

    ended = lifecycle.get('ended')
    ended_day = cited_date(ended, 'end_date')
    if ended_day is not None and ended_day >= now.date():
        reasons.append('legacy_followup_original_application_not_closed')
    if not isinstance(ended, dict) or '종료' not in plan.get('lead', {}).get('text', ''):
        reasons.append('legacy_followup_closed_status_missing_from_answer')
    next_windows = lifecycle.get('next_windows')
    if not isinstance(next_windows, list) or not next_windows or len(next_windows) > 4:
        reasons.append('legacy_followup_future_windows_missing')
        next_windows = []
    last_end = None
    for window in next_windows:
        end = cited_date(window, 'end_date')
        if not isinstance(window, dict):
            continue
        start = cited_date(window, 'start_date') if window.get('start_date') else None
        if end is not None:
            if (end <= now.date() or (ended_day is not None and end <= ended_day)
                    or (start is not None and (start > end or
                        (ended_day is not None and start <= ended_day)))):
                reasons.append('legacy_followup_window_not_future')
            last_end = max(last_end, end) if last_end else end
        if window.get('start_date') and start is None:
            reasons.append('legacy_followup_start_unverified')
    try:
        if not last_end or date.fromisoformat(brief['useful_until']) > last_end:
            reasons.append('legacy_followup_useful_after_last_official_window')
    except (ValueError, TypeError, KeyError):
        reasons.append('legacy_followup_useful_until_invalid')
    if re.search(r'현재\s*(?:신청|접수)\s*(?:가능|중)|(?:접수|신청)\s*진행\s*중',
                 ' '.join([plan.get('title', ''), plan.get('lead', {}).get('text', '')])):
        reasons.append('legacy_followup_misleading_open_claim')
    return sorted(set(reasons))


def validate_legacy_reference_period(brief: dict, sources: list[dict], temporal: dict,
                                     plan: dict, now: datetime, minimum_days=30) -> list[str]:
    """Verify a *published historical ID's* annual rules or vaccination season.

    Annual pension criteria do not have an application closing time. A flu
    season is likewise not a single general application period for every age
    group. The older availability validator expects an active labelled sale/
    application and cannot model either. This tightly limited path validates
    explicitly cited applicability dates *without certifying applications,
    vaccine stock, any person's eligibility or a service's real-time status*.
    New posts, unrelated categories and unsupported time windows fail closed.
    """
    info = temporal.get('legacy_reference_period')
    if not isinstance(info, dict):
        return ['legacy_reference_period_invalid']
    allowed = {55: ('welfare', 'annual_pension'),
               79: ('welfare', 'annual_pension'),
               101: ('welfare', 'annual_pension'),
               220: ('welfare', 'annual_health_ceiling'),
               103: ('life-health', 'flu_season'),
               63: ('life-health', 'national_flu_season'),
               81: ('life-health', 'national_flu_season')}
    post_id = brief.get('existing_post_id')
    if (type(post_id) is not int or allowed.get(post_id) !=
            (brief.get('category_key'), info.get('kind'))
            or brief.get('content_type') != 'dated'):
        return ['legacy_reference_period_not_for_this_existing_post']
    reasons = []
    try:
        start = date.fromisoformat(info['start_date'])
        end = date.fromisoformat(info['end_date'])
        useful = date.fromisoformat(brief['useful_until'])
        item = info['evidence']
        source = next(s for s in sources if s['id'] == item['source_id'])
        quote = item['quote']
        if (not isinstance(quote, str) or not 24 <= len(quote) <= 800
                or quote not in source['text'] or source.get('source_type') != 'official'
                or source['url'] not in brief['official_urls']):
            raise ValueError('reference_quote_unbound')
    except (TypeError, ValueError, KeyError, StopIteration):
        return ['legacy_reference_period_dates_or_source_unverified']
    if not start <= now.date() <= end or (end - now.date()).days < minimum_days:
        reasons.append('legacy_reference_period_not_current_or_too_short')
    if useful > end or useful < now.date():
        reasons.append('legacy_reference_period_useful_until_invalid')
    if info['kind'] == 'annual_pension':
        # The ministry explicitly labels the 2026 monthly *benefit amount*
        # 2026 January through December. This is a cutoff for a 2026 guide,
        # not a claim that the underlying entitlement expires on Dec 31.
        if (start != date(2026, 1, 1) or end != date(2026, 12, 31)
                or useful != end or not re.search(
                    r'2026\s*년\s*1\s*월\s*~\s*2026\s*년\s*12\s*월', quote)
                or '기초연금' not in (' '.join([brief.get('entity', ''),
                                               brief.get('primary_keyword', '')]))):
            reasons.append('legacy_pension_annual_range_not_officially_bound')
    elif info['kind'] == 'annual_health_ceiling':
        expected_url = 'https://www.nhis.or.kr/nhis/minwon/wbhapa01000m01.do?mode=view&articleNo=10946900'
        values = info.get('values_evidence')
        try:
            values_source = next(s for s in sources if s['id'] == values['source_id'])
            values_quote = values['quote']
            compact = re.sub(r'[\s,]', '', values_quote)
            required = ('2026년', '90만원', '112만원', '173만원', '326만원',
                        '446만원', '536만원', '843만원', '143만원', '181만원',
                        '245만원', '404만원', '580만원', '698만원', '1096만원')
            public = re.sub(r'\s+', '', ' '.join([
                plan.get('title', ''), plan.get('lead', {}).get('text', ''),
                *(s.get('heading', '') for s in plan.get('sections', [])),
                *(p.get('text', '') for s in plan.get('sections', [])
                  for p in s.get('paragraphs', [])),
            ]))
            if (start != date(2026, 1, 1) or end != date(2026, 12, 31)
                    or useful != end or source['url'] != expected_url
                    or values_source is not source
                    or source.get('source_type') != 'official'
                    or expected_url not in brief.get('official_urls', [])
                    or not isinstance(values_quote, str) or not 40 <= len(values_quote) <= 900
                    or values_quote not in source['text']
                    or not all(token in compact for token in required)
                    or '연간(1.1.~12.31.)' not in quote.replace('∼', '~')
                    or '2026' not in public or '진료연도' not in public
                    or '본인부담상한' not in public):
                raise ValueError('health_ceiling_reference_mismatch')
        except (KeyError, TypeError, ValueError, StopIteration):
            reasons.append('legacy_health_ceiling_annual_range_not_officially_bound')
    elif info['kind'] == 'national_flu_season':
        # The August KDCA announcement established the overall season, but its
        # per-group start dates were superseded on September 16. Both official
        # originals are required; the earlier schedule alone is insufficient.
        expected_period = 'https://www.kdca.go.kr/bbs/kdca/42/312308/artclView.do'
        expected_revision = 'https://www.kdca.go.kr/bbs/kdca/42/309764/download.do'
        schedule = info.get('schedule_evidence')
        try:
            latest = next(s for s in sources if s['url'] == expected_revision
                          and s['source_type'] == 'official'
                          and expected_revision in brief['official_urls'])
            child, elder = (schedule['child'], schedule['elder'])
            if (not isinstance(child, dict) or not isinstance(elder, dict)
                    or any(item.get('source_id') != latest['id']
                           or not isinstance(item.get('quote'), str)
                           or not 40 <= len(item['quote']) <= 800
                           or item['quote'] not in latest['text']
                           for item in (child, elder))):
                raise ValueError('missing_revision_quotes')
            child_text = re.sub(r'\s+', '', child['quote'])
            elder_text = re.sub(r'\s+', '', elder['quote'])
            lead = re.sub(r'\s+', '', plan.get('lead', {}).get('text', ''))
            if (start != date(2026, 9, 21) or end != date(2027, 4, 30)
                    or useful != end or source['url'] != expected_period
                    or '2026.08.25' not in source['text']
                    or '2026. 9. 16.' not in latest['text']
                    or not re.search(r'9월21일.*2027년4월30일',
                                     re.sub(r'\s+', '', quote))
                    or not re.search(r'1회접종어린이9월28일에서21일로조정', child_text)
                    or not re.search(r'모든어린이와임신부접종21일시작', child_text)
                    or not re.search(r'75세이상10월6일.*70~74세10월12일.*65~69세10월15일',
                                     elder_text)
                    or not all(day in lead for day in ('10월6일', '10월12일', '10월15일'))
                    or (post_id == 63 and '9월21일' not in lead)):
                raise ValueError('national_season_or_revision_mismatch')
        except (KeyError, TypeError, ValueError, StopIteration):
            reasons.append('legacy_national_flu_season_not_officially_bound')
    else:
        # Only the city's season-wide national program notice can establish
        # BOTH dates; historical KDCA August start dates were superseded in
        # September. Individual eligibility start dates need semantic review.
        if (start != date(2026, 9, 21) or end != date(2027, 4, 30)
                or useful != end or 'mokpo.go.kr' not in source['url']
                or '접종일정' not in quote
                or not re.search(r'2026\s*[.년]\s*0?9\s*[.월]\s*21', quote)
                or not re.search(r'2027\s*[.년]\s*0?4\s*[.월]\s*30', quote)):
            reasons.append('legacy_flu_season_range_not_officially_bound')
    # A period reference is never evidence that all groups can act today,
    # applications are open, or that a particular provider has inventory.
    headline = ' '.join([plan.get('title', ''), plan.get('lead', {}).get('text', '')])
    if re.search(r'현재\s*(?:누구나|모든\s*대상|전\s*연령|전원)\s*(?:신청|접종|수령)\s*(?:가능|중)|'
                 r'(?:신청|접수)\s*진행\s*중', headline):
        reasons.append('legacy_reference_period_misleading_current_status')
    return sorted(set(reasons))


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
