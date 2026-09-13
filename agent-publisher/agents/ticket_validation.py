"""Conservative identity checks; no LLM, network calls or guessed dates."""

import re
import unicodedata
from datetime import date

from bs4 import BeautifulSoup
from agents.temporal_validation import extract_evidence
from agents.fact_validation import snapshot


REGIONS = (
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "수원",
    "고양", "성남", "용인", "화성", "안양", "안산", "부천", "남양주", "의정부",
    "평택", "파주", "김포", "광명", "이천", "춘천", "원주", "강릉", "속초",
    "청주", "충주", "천안", "아산", "공주", "전주", "군산", "익산", "목포",
    "여수", "순천", "창원", "진주", "김해", "양산", "포항", "경주", "구미", "안동", "제주",
)
DATE_PATTERN = re.compile(
    r"(?<!\d)(?:(\d{4})\s*(?:년\s*|[./-]\s*))?"
    r"(\d{1,2})\s*(?:월\s*|[./-]\s*)(\d{1,2})\s*일?(?!\d)"
)
BOOKING_WORDS = re.compile(r"예매|티켓|오픈|판매|접수|예약")
EVENT_WORDS = re.compile(r"공연|콘서트|일시|개최|열린|진행|무대")
QUALIFIERS = ("크리스마스", "앵콜", "팬미팅", "뮤지컬")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("앙코르", "앵콜")
    return re.sub(r"[^가-힣a-z0-9]", "", value)


def extract_dates(text: str, year: int | None = None) -> list[str]:
    """Parse explicit dates; an omitted year requires source-provided context."""
    result = []
    context_year = year
    for match in DATE_PATTERN.finditer(text):
        explicit_year, month, day = match.groups()
        if explicit_year:
            context_year = int(explicit_year)
        if context_year is None:
            continue
        try:
            value = date(context_year, int(month), int(day)).isoformat()
        except ValueError:
            continue
        if value not in result:
            result.append(value)
    return result


def regions_in(text: str) -> list[str]:
    # Check a region at a word boundary, or in a venue such as 수원컨벤션센터.
    return [region for region in REGIONS if re.search(r"(?<![가-힣])" + region, text)]


def extract_expectation(entity: str, title: str, body: str) -> dict:
    """Extract only unambiguous article identity. Booking dates are excluded."""
    title_regions = regions_in(title)
    regions = title_regions or regions_in(body)
    years = set(re.findall(r"(?<!\d)(20\d{2})(?:년|[./-]|\s)", title))
    if not years:
        years = set(re.findall(r"(?<!\d)(20\d{2})(?:년|[./-])", body))
    year = int(next(iter(years))) if len(years) == 1 else None
    event_dates = []
    for fragment in re.split(r"\n|(?<=[.!?])\s+|[,;]", title + "\n" + body):
        if BOOKING_WORDS.search(fragment) or not EVENT_WORDS.search(fragment):
            continue
        for value in extract_dates(fragment, year):
            if value not in event_dates:
                event_dates.append(value)
    # Do not enrich an article listing several performances with just one product.
    return {
        "entity": entity if normalize(entity) in normalize(title + " " + body) else "",
        "region": regions[0] if len(regions) == 1 else "",
        "event_dates": event_dates if len(event_dates) == 1 else [],
        "qualifiers": [word for word in QUALIFIERS if word in normalize(title)],
        "venue": _field(body, "장소"),
        "name_tokens": [value.strip() for value in re.findall(r"['\"‘“]([^'\"’”]+)['\"’”]", title)
                        if normalize(value) != normalize(entity)],
    }


def _field(text: str, label: str) -> str:
    match = re.search(r"(?:^|\n)\s*-?\s*" + label + r"\s*[:：]\s*([^\n]+)", text)
    return match.group(1).strip() if match else ""


def parse_product(html: str, product_id: str) -> dict:
    """Use product heading and labelled details, never recommendation text."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    meta = soup.find("meta", property="og:title")
    title = heading.get_text(" ", strip=True) if heading else (meta.get("content", "") if meta else "")
    details = soup.find(id="details")
    text = details.get_text("\n", strip=True) if details else ""
    date_str = _field(text, "일시")
    place_str = _field(text, "장소")
    price_str = _field(text, "티켓")
    # Product title may supply the year for a labelled date that omits it.
    years = set(re.findall(r"(?<!\d)(20\d{2})(?!\d)", title))
    year = int(next(iter(years))) if len(years) == 1 else None
    return {
        "product_id": product_id,
        "product_url": f"https://nol.yanolja.com/ticket/products/{product_id}",
        "title": title,
        "date_str": date_str,
        "place_str": place_str,
        "price_str": price_str or None,
        "event_dates": extract_dates(date_str, year),
        "temporal_evidence": extract_evidence("공연일시: " + date_str + "\n" + text, f"https://nol.yanolja.com/ticket/products/{product_id}"),
        "fact_source": snapshot(f"https://nol.yanolja.com/ticket/products/{product_id}", title, "공연일시: " + date_str + "\n" + text, "ticket_product"),
    }


def check_identity(expected: dict, product: dict, today: date | None = None) -> list[str]:
    today = today or date.today()
    reasons = []
    entity = normalize(expected.get("entity", ""))
    region = expected.get("region", "")
    wanted = expected.get("event_dates", [])
    if len(entity) < 2 or not region or len(wanted) != 1:
        return ["article_identity_incomplete_or_ambiguous"]
    if entity not in normalize(product.get("title", "")):
        reasons.append("performance_name_mismatch")
    for token in expected.get("name_tokens", []):
        if normalize(token) not in normalize(product.get("title", "")):
            reasons.append("performance_subtitle_mismatch")
    for qualifier in expected.get("qualifiers", []):
        if normalize(qualifier) not in normalize(product.get("title", "")):
            reasons.append("performance_qualifier_mismatch")
    # Both product title and venue must support the target region. Unknown is not a match.
    if region not in regions_in(product.get("title", "")) or region not in regions_in(product.get("place_str", "")):
        reasons.append("region_or_venue_mismatch")
    if expected.get("venue") and normalize(expected["venue"]) != normalize(product.get("place_str", "")):
        reasons.append("venue_mismatch")
    actual = product.get("event_dates", [])
    if not actual or set(wanted) != set(actual):
        reasons.append("performance_date_mismatch_or_missing")
    try:
        if any(date.fromisoformat(value) < today for value in wanted):
            reasons.append("performance_already_ended")
    except (ValueError, TypeError):
        reasons.append("invalid_expected_date")
    return reasons


def select_product(expected: dict, products: list[dict], today: date | None = None) -> dict:
    checks = []
    matches = []
    seen = set()
    for product in products:
        if product.get("product_id") in seen:
            continue
        seen.add(product.get("product_id"))
        reasons = check_identity(expected, product, today)
        checks.append({"product_url": product.get("product_url"), "reasons": reasons})
        if not reasons:
            matches.append(product)
    if len(matches) == 1:
        return {"status": "matched", "product": matches[0], "checks": checks}
    return {
        "status": "needs_review",
        "reason": "multiple_matching_products" if matches else "no_verified_product",
        "product": None,
        "checks": checks,
    }
