"""Deterministic v1 contract for monthly multi-event roundup posts.

This module intentionally enforces only low-ambiguity structure and wording
checks.  Whether an event section is genuinely useful, whether an image shows
the right activity, and whether the prose is natural remain semantic/browser
review responsibilities.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date


EVENT_POST_STANDARD_VERSION = 1

_ACTIVITY = re.compile(
    r"체험|전시|공연|관람|참여|구매|시식|게임|산책|걷기|콘서트|퍼레이드|"
    r"부스|마켓|먹거리|드론|영화|공모전|굿즈|토크|워크숍|프로그램|전통문화|"
    r"라이브|버스킹|야간|축제|쇼|투어|놀이|만들기|관찰|탐사"
)
_DECISION = re.compile(
    r"비용|무료|유료|요금|가격|신청|예약|입장|시간|운영|대상|가족|아이|학생|"
    r"방문객|관람객|혼잡|주차|대중교통|오픈|마감|선착순|추천|맞(?:는|고|습니다)|"
    r"좋(?:은|고|습니다)|교통|준비물"
)
_REFERENCE_MARKER = re.compile(r"참고|분위기|이전|지난|회차")
_EDITOR_NOTE = re.compile(
    r"미표기|확인하지\s*못했|찾지\s*못했|자료를\s*찾지\s*못|추가\s*확인\s*필요|"
    r"편집자\s*메모|확인\s*불가|"
    r"공식\s*(?:카드뉴스|자료|출처)\s*(?:기준|에서\s*확인)|"
    r"확인된\s*(?:보조\s*)?(?:자료|출처)|보조\s*자료(?:에는|에\s*따르면)?"
)
_COMMA_SPACING = re.compile(r"(?<=[가-힣A-Za-z]),(?=[가-힣A-Za-z])")
_PERIOD_SPACING = re.compile(r"(?<=[가-힣])\.(?=[가-힣])")
_YEAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_SOURCE_STYLE_DATE = re.compile(
    r"(?<!\d)20\d{2}[-.]\d{1,2}[-.]\d{1,2}(?!\d)|"
    r"(?<!\d)\d{1,2}\.\d{1,2}\.(?:\([월화수목금토일]\))?"
)
_TIME_TOKEN = re.compile(r"(?<!\d)(?:[01]?\d|2[0-3]):[0-5]\d(?!\d)")
_PRICE_TOKEN = re.compile(r"(?<!\d)\d{1,3}(?:,\d{3})+\s*원|(?<!\d)\d+\s*원")
_OVERVIEW_HEADERS = ["날짜", "행사", "주요 볼거리", "장소"]
_WEEKDAY_KO = ("월", "화", "수", "목", "금", "토", "일")
_VAGUE_OVERVIEW_HEADER = re.compile(
    r"확인된\s*실전\s*조건|실전\s*조건|실전\s*정보|판단\s*포인트|"
    r"추천\s*/?\s*핵심|핵심\s*관전\s*포인트"
)
_UNHELPFUL_OVERVIEW_VALUE = re.compile(r"^(?:[-—–]+|미정|상이|별도|주요\s*(?:행사|일정)?별\s*상이|날짜별\s*상이)$")
_IMAGE_RIGHTS = {"site_owned", "open_license", "permission_granted", "source_attributed"}


def event_post_standard_declared(bundle: dict | None) -> bool:
    """Return whether a bundle declares any event-post standard version."""
    if not isinstance(bundle, dict):
        return False
    brief = bundle.get("brief") or {}
    return brief.get("event_post_standard_version") is not None


def event_post_standard_enabled(bundle: dict | None) -> bool:
    """Return whether a bundle opts into the currently supported standard."""
    if not isinstance(bundle, dict):
        return False
    brief = bundle.get("brief") or {}
    return brief.get("event_post_standard_version") == EVENT_POST_STANDARD_VERSION


def _reader_strings(
        plan: dict,
        sources: list[dict] | None = None,
        *,
        include_source_labels: bool = False,
) -> list[str]:
    """Reader-facing strings; raw source/evidence text is deliberately excluded."""
    values = [plan.get("title", ""), (plan.get("lead") or {}).get("text", "")]
    for section in plan.get("sections", []) or []:
        values.append(section.get("heading", ""))
        values.extend((paragraph or {}).get("text", "") for paragraph in section.get("paragraphs", []) or [])
        for fact in section.get("facts", []) or []:
            values.extend((fact.get("label", ""), fact.get("value", "")))
        image = section.get("image") or {}
        values.extend((image.get("alt", ""), image.get("caption", "")))
        location = section.get("location") or {}
        values.extend((location.get("venue", ""), location.get("address", "")))
        table = section.get("table") or {}
        values.append(table.get("caption", ""))
        values.extend(table.get("headers", []) or [])
        for row in table.get("rows", []) or []:
            values.extend(row.get("cells", []) or [])
    for faq in plan.get("faq", []) or []:
        values.extend((faq.get("question", ""), (faq.get("answer") or {}).get("text", "")))
    for item in plan.get("related_posts", []) or []:
        values.append(item.get("label", ""))
    for item in plan.get("official_navigation", []) or []:
        values.extend((item.get("label", ""), item.get("note", "")))
    if include_source_labels:
        for source in sources or []:
            for action in source.get("actions", []) or []:
                values.append(action.get("label", ""))
            values.append(source.get("citation_label") or source.get("title", ""))
    return [value for value in values if isinstance(value, str)]


def _section_support_text(section: dict) -> tuple[str, str]:
    paragraphs = section.get("paragraphs", []) or []
    body = " ".join(
        paragraph.get("text", "") for paragraph in paragraphs if isinstance(paragraph, dict)
    )
    support = [body]
    for fact in section.get("facts", []) or []:
        if isinstance(fact, dict):
            support.extend((fact.get("label", ""), fact.get("value", "")))
    table = section.get("table") or {}
    support.extend(table.get("headers", []) or [])
    for row in table.get("rows", []) or []:
        if isinstance(row, dict):
            support.extend(row.get("cells", []) or [])
    return body, " ".join(value for value in support if isinstance(value, str))


def _closing_summary_valid(sections: list[dict], bound: dict[str, dict]) -> bool:
    """Require one non-event synthesis section after all event sections."""
    if not sections or not bound:
        return False
    positions = {
        id(section): index
        for index, section in enumerate(sections)
        if isinstance(section, dict)
    }
    try:
        last_event_index = max(positions[id(section)] for section in bound.values())
    except (KeyError, ValueError):
        return False
    return any(
        isinstance(section, dict)
        and section.get("event_name") is None
        and section.get("kind") == "general"
        and any(
            isinstance(paragraph, dict) and paragraph.get("text", "").strip()
            for paragraph in section.get("paragraphs", []) or []
        )
        for section in sections[last_event_index + 1:]
    )


def _overview_contract(section: dict | None, entries: list[dict]) -> tuple[bool, bool]:
    """Return (overview_semantically_present, exact_layout_valid)."""
    if not isinstance(section, dict) or section.get("kind") != "overview":
        return False, False
    table = section.get("table")
    if not isinstance(table, dict) or table.get("mobile_cards") is not True:
        return False, False
    headers = table.get("headers")
    rows = table.get("rows")
    if not isinstance(headers, list) or not isinstance(rows, list) or len(rows) < 2:
        return False, False
    text = " ".join(value for value in headers if isinstance(value, str))
    if _VAGUE_OVERVIEW_HEADER.search(text):
        return False, False
    has_date = any(token in text for token in ("날짜", "기간", "일정"))
    has_event = any(token in text for token in ("행사", "축제", "프로그램"))
    has_place = any(token in text for token in ("장소", "행사장", "지역"))
    has_decision = any(
        token in text
        for token in ("볼거리", "체험", "관람", "프로그램", "비용", "가격", "티켓", "예매", "신청", "예약", "운영시간")
    )
    overview_present = has_date and has_event and has_place and has_decision
    if not overview_present or headers != _OVERVIEW_HEADERS:
        return overview_present, False

    entry_map = {
        entry.get("name"): entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    for row in rows:
        cells = row.get("cells") if isinstance(row, dict) else None
        if not isinstance(cells, list) or len(cells) != len(_OVERVIEW_HEADERS):
            return overview_present, False
        event_name = cells[1] if isinstance(cells[1], str) else ""
        entry = entry_map.get(event_name)
        if not entry or not isinstance(cells[0], str):
            return overview_present, False
        try:
            expected_date = readable_event_date_label(entry["start_date"], entry["end_date"])
        except (KeyError, TypeError, ValueError):
            return overview_present, False
        if cells[0].strip() != expected_date:
            return overview_present, False
        if any(not isinstance(cell, str) or not cell.strip() for cell in cells):
            return overview_present, False
        if any(_TIME_TOKEN.search(cell) or _PRICE_TOKEN.search(cell) for cell in cells):
            return overview_present, False
        if any(_UNHELPFUL_OVERVIEW_VALUE.fullmatch(cell.strip()) for cell in cells):
            return overview_present, False
    return overview_present, True


def readable_event_date_label(start_date: str, end_date: str) -> str:
    """Format ISO event dates as the compact reader-facing overview style."""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("event_date_range_invalid")

    def one(value: date, include_year: bool = False) -> str:
        prefix = f"{value.year}/" if include_year else ""
        return f"{prefix}{value.month}/{value.day}({_WEEKDAY_KO[value.weekday()]})"

    if start == end:
        return one(start)
    if start.year == end.year:
        if start.month == end.month:
            return f"{one(start)}~{end.day}({_WEEKDAY_KO[end.weekday()]})"
        return f"{one(start)}~{one(end)}"
    return f"{one(start, True)}~{one(end, True)}"


def overview_event_date_labels(section: dict) -> dict[str, str]:
    """Return exact event-name -> reader-facing date labels from the overview table."""
    table = section.get("table") if isinstance(section, dict) else None
    if not isinstance(table, dict):
        raise ValueError("event_overview_table_required")
    headers = table.get("headers")
    rows = table.get("rows")
    if headers != _OVERVIEW_HEADERS or not isinstance(rows, list):
        raise ValueError("event_overview_table_required")
    date_index, event_index = 0, 1
    labels: dict[str, str] = {}
    for row in rows:
        cells = row.get("cells") if isinstance(row, dict) else None
        if (not isinstance(cells, list)
                or max(event_index, date_index) >= len(cells)
                or not isinstance(cells[event_index], str)
                or not isinstance(cells[date_index], str)):
            raise ValueError("event_overview_map_row_invalid")
        name = cells[event_index].strip()
        label = cells[date_index].strip()
        if not name or not label or name in labels:
            raise ValueError("event_overview_map_row_invalid")
        labels[name] = label
    return labels


def _valid_coordinate(value, minimum: float, maximum: float) -> bool:
    return type(value) in {int, float} and minimum <= value <= maximum


def _section_source_ids(section: dict) -> set[str]:
    source_ids: set[str] = set()
    for paragraph in section.get("paragraphs", []) or []:
        if isinstance(paragraph, dict):
            source_ids.update(
                item.get("source_id") for item in (paragraph.get("evidence", []) or [])
                if isinstance(item, dict) and isinstance(item.get("source_id"), str)
            )
    for fact in section.get("facts", []) or []:
        if isinstance(fact, dict):
            source_ids.update(
                item.get("source_id") for item in (fact.get("evidence", []) or [])
                if isinstance(item, dict) and isinstance(item.get("source_id"), str)
            )
    table = section.get("table") or {}
    for row in table.get("rows", []) or []:
        if isinstance(row, dict):
            source_ids.update(
                item.get("source_id") for item in (row.get("evidence", []) or [])
                if isinstance(item, dict) and isinstance(item.get("source_id"), str)
            )
    location = section.get("location") or {}
    source_ids.update(
        item.get("source_id") for item in (location.get("evidence", []) or [])
        if isinstance(item, dict) and isinstance(item.get("source_id"), str)
    )
    image = section.get("image") or {}
    if isinstance(image.get("source_id"), str):
        source_ids.add(image["source_id"])
    return source_ids


def _prior_year_image_disclosed(section: dict, entry_year: int, source_map: dict[str, dict]) -> bool:
    image = section.get("image")
    if not isinstance(image, dict):
        return True
    caption = image.get("caption", "")
    source = source_map.get(image.get("source_id"), {})
    source_title = source.get("title", "") if isinstance(source, dict) else ""
    image_year = image.get("year")
    if type(image_year) is not int:
        # Some public/archive photos do not expose a reliable capture year.
        # Do not invent one: require the reader-facing caption to disclose that
        # the photo is from a previous/reference edition instead.
        return bool(_REFERENCE_MARKER.search(caption))
    caption_years = {int(value) for value in _YEAR.findall(caption)}
    source_years = {int(value) for value in _YEAR.findall(source_title)}
    prior_caption = {year for year in caption_years if year < entry_year}
    prior_source = {year for year in source_years if year < entry_year}
    if image_year >= entry_year and not prior_caption and not prior_source:
        return True
    if image_year < entry_year:
        prior_caption.add(image_year)
    if not prior_caption and not prior_source:
        return True
    if not _REFERENCE_MARKER.search(caption):
        return False
    if image_year < entry_year and str(image_year) not in caption:
        return False
    # If the official image/source title reveals a previous year, do not hide
    # that year behind a generic "previous event" caption.
    return all(str(year) in caption for year in prior_source)


def validate_event_post_standard(bundle: dict) -> list[str]:
    """Return deterministic v1 event-post violations.

    Legacy bundles are not silently migrated: absence of the version marker
    means this extension does not run.  Once v1 is declared, failures are
    fail-closed and require a Standard revision.
    """
    if not event_post_standard_declared(bundle):
        return []

    brief = bundle.get("brief") or {}
    plan = bundle.get("plan") or {}
    sources = bundle.get("sources") or []
    temporal = bundle.get("temporal_source") or {}
    reasons: list[str] = []

    if (not event_post_standard_enabled(bundle)
            or brief.get("content_type") != "dated"
            or brief.get("category_key") != "events"
            or temporal.get("multi_event_schedule") is not True):
        reasons.append("event_standard_contract_invalid")
        return reasons

    keyword = brief.get("primary_keyword")
    seo = brief.get("seo")
    lead_text = (plan.get("lead") or {}).get("text", "")
    headings = [section.get("heading", "") for section in plan.get("sections", []) or []]
    if (not isinstance(keyword, str) or not keyword.strip()
            or not isinstance(seo, dict)
            or not isinstance(seo.get("title"), str) or not seo["title"].strip()
            or not isinstance(seo.get("description"), str) or not seo["description"].strip()):
        reasons.append("event_standard_seo_missing")
    else:
        keyword = keyword.strip()
        if (keyword not in seo["title"]
                or keyword not in seo["description"]
                or keyword not in lead_text
                or not any(keyword in heading for heading in headings if isinstance(heading, str))):
            reasons.append("event_standard_keyword_alignment_missing")

    sections = plan.get("sections", []) or []
    entries = temporal.get("event_entries") or []
    overview_header_text = " ".join(
        value for value in ((sections[0].get("table") or {}).get("headers", []) if sections and isinstance(sections[0], dict) else [])
        if isinstance(value, str)
    )
    overview_present, overview_layout_valid = _overview_contract(sections[0] if sections else None, entries)
    if not overview_present:
        reasons.append("event_standard_overview_missing")
    if _VAGUE_OVERVIEW_HEADER.search(overview_header_text):
        reasons.append("event_standard_overview_header_vague")

    if (brief.get("allow_selection_guide") is not True
            and any(isinstance(section, dict)
                    and section.get("kind") == "comparison"
                    and section.get("event_name") is None
                    for section in sections)):
        reasons.append("event_standard_unrequested_selection_guide")

    if sections and not overview_layout_valid:
        reasons.append("event_standard_overview_schedule_layout_invalid")
    entry_names = [entry.get("name") for entry in entries if isinstance(entry, dict)]
    if (not entry_names or any(not isinstance(name, str) or not name.strip() for name in entry_names)
            or len(entry_names) != len(set(entry_names))):
        reasons.append("event_standard_event_section_binding_invalid")
        bound: dict[str, dict] = {}
    else:
        bound = {}
        invalid_binding = False
        for section in sections:
            event_name = section.get("event_name") if isinstance(section, dict) else None
            if event_name is None:
                continue
            if event_name not in entry_names or event_name in bound:
                invalid_binding = True
                continue
            bound[event_name] = section
        if invalid_binding or set(bound) != set(entry_names):
            reasons.append("event_standard_event_section_binding_invalid")

    if not _closing_summary_valid(sections, bound):
        reasons.append("event_standard_closing_summary_missing")

    map_invalid = False
    try:
        overview_dates = overview_event_date_labels(sections[0])
        if set(overview_dates) != set(entry_names):
            map_invalid = True
    except (IndexError, TypeError, ValueError):
        map_invalid = True

    source_map = {source.get("id"): source for source in sources if isinstance(source, dict)}
    decision_missing = False
    prior_year_missing = False
    section_assets_missing = False
    image_rights_missing = False
    deferred_generated = brief.get("deferred_generated_event_image_urls", [])
    deferred_generated_valid = (
        isinstance(deferred_generated, list)
        and type(brief.get("existing_post_id")) is int
        and brief.get("existing_post_id") > 0
        and all(isinstance(url, str) and url.startswith("https://") for url in deferred_generated)
        and len(deferred_generated) == len(set(deferred_generated))
    )
    deferred_generated_set = set(deferred_generated) if deferred_generated_valid else set()
    encountered_deferred_generated: set[str] = set()
    entry_map = {entry.get("name"): entry for entry in entries if isinstance(entry, dict)}
    for name, section in bound.items():
        body, support = _section_support_text(section)
        activities = set(_ACTIVITY.findall(body)) - {"축제"}
        if (not body.strip() or not activities
                or (not _DECISION.search(support) and len(activities) < 2)):
            decision_missing = True
        image = section.get("image")
        location = section.get("location")
        if not isinstance(image, dict) or not isinstance(location, dict):
            section_assets_missing = True
        if (not isinstance(location, dict)
                or not _valid_coordinate(location.get("latitude"), -90, 90)
                or not _valid_coordinate(location.get("longitude"), -180, 180)):
            map_invalid = True
        if isinstance(image, dict):
            rights = image.get("rights")
            rights_url = image.get("rights_url")
            image_url = image.get("url")
            generated_deferred = (
                rights == "generated_original"
                and deferred_generated_valid
                and isinstance(image_url, str)
                and image_url in deferred_generated_set
            )
            if generated_deferred:
                encountered_deferred_generated.add(image_url)
            elif (rights not in _IMAGE_RIGHTS
                    or (rights in {"open_license", "permission_granted", "source_attributed"}
                        and (not isinstance(rights_url, str) or not rights_url.startswith("https://")))):
                image_rights_missing = True
        try:
            entry_year = date.fromisoformat(entry_map[name]["start_date"]).year
        except (KeyError, TypeError, ValueError):
            # Temporal validation owns malformed dates.  Do not invent a year.
            continue
        if not _prior_year_image_disclosed(section, entry_year, source_map):
            prior_year_missing = True
    if decision_missing:
        reasons.append("event_standard_decision_support_missing")
    if section_assets_missing:
        reasons.append("event_standard_section_assets_missing")
    if image_rights_missing:
        reasons.append("event_standard_image_rights_missing")
    if deferred_generated and (
            not deferred_generated_valid
            or encountered_deferred_generated != deferred_generated_set):
        reasons.append("event_standard_deferred_generated_image_invalid")
    if prior_year_missing:
        reasons.append("event_standard_previous_year_image_disclosure_missing")
    if map_invalid:
        reasons.append("event_standard_interactive_map_invalid")

    scoped_counts = Counter(
        url
        for section in sections if isinstance(section, dict)
        for url in (section.get("actions", []) or [])
        if isinstance(url, str)
    )
    event_actions = [
        (source.get("id"), action)
        for source in sources if isinstance(source, dict)
        for action in (source.get("actions", []) or []) if isinstance(action, dict)
        if action.get("kind") in {"booking", "apply", "purchase"}
    ]
    if any(scoped_counts[action.get("url")] != 1 for _, action in event_actions):
        reasons.append("event_standard_event_action_not_section_scoped")
    action_source_mismatch = False
    for source_id, action in event_actions:
        url = action.get("url")
        owners = [
            section for section in sections if isinstance(section, dict)
            and url in (section.get("actions", []) or [])
        ]
        if len(owners) == 1 and source_id not in _section_source_ids(owners[0]):
            action_source_mismatch = True
    if action_source_mismatch:
        reasons.append("event_standard_action_source_mismatch")

    official_source_id_by_url = {
        source.get("url"): source.get("id")
        for source in sources if isinstance(source, dict)
        and source.get("source_type") == "official"
    }
    official_link_source_mismatch = False
    official_link_missing = False
    event_facts_present = False
    for section in sections:
        if not isinstance(section, dict) or not section.get("event_name"):
            continue
        if section.get("facts"):
            event_facts_present = True
        official_links = section.get("official_links", []) or []
        if not isinstance(official_links, list) or not official_links:
            official_link_missing = True
            continue
        section_source_ids = _section_source_ids(section)
        for link in official_links:
            if not isinstance(link, dict):
                continue
            source_id = official_source_id_by_url.get(link.get("url"))
            if source_id is not None and source_id not in section_source_ids:
                official_link_source_mismatch = True
    if official_link_missing:
        reasons.append("event_standard_official_link_missing")
    if official_link_source_mismatch:
        reasons.append("event_standard_official_link_source_mismatch")
    if event_facts_present:
        reasons.append("event_standard_event_facts_not_allowed")

    visible = _reader_strings(plan, sources, include_source_labels=True)
    if any(_COMMA_SPACING.search(value) or _PERIOD_SPACING.search(value) for value in visible):
        reasons.append("event_standard_reader_punctuation_spacing")
    if any(_EDITOR_NOTE.search(value) for value in visible):
        reasons.append("event_standard_editor_note_exposed")
    if any(_SOURCE_STYLE_DATE.search(value) for value in _reader_strings(plan)):
        reasons.append("event_standard_reader_date_format_inconsistent")

    return sorted(set(reasons))


def event_writer_instruction(brief: dict, temporal_source: dict | None = None) -> str:
    """Extra writer contract only for explicitly standardized event roundups."""
    if brief.get("event_post_standard_version") != EVENT_POST_STANDARD_VERSION:
        return ""
    if brief.get("category_key") != "events":
        return ""
    if (temporal_source or {}).get("multi_event_schedule") is not True:
        return ""
    return (
        " 이 원고는 도시별 월간 행사 일정형 v1이다. 첫 section은 kind=overview, mobile_cards=true로 만들고 "
        "열은 '날짜, 행사, 주요 볼거리, 장소' 순서로 고정하라. 같은 달 기간은 '10/9(금)~11(일)'처럼 짧게 쓴다. "
        "temporal_source.event_entries의 각 name마다 상세 section 하나를 만들고 section.event_name에 정확히 넣어라. "
        "행사 section은 '제목 → 이미지 → 필요한 경우 사진 출처 → 본문 → 필요한 경우 작은 일정표 → 공식 안내 링크 박스 → 위치' 순서로 구성하고 facts 카드는 넣지 마라. "
        "본문은 날짜·장소 반복이 아니라 실제 볼거리·체험과 확인된 비용·예약·운영 조건처럼 방문 판단에 필요한 내용을 설명하라. "
        "공식 자료에 실제 작품명·출연자·공연명·프로그램명이 있으면 '다양한 공연', '여러 작품'처럼 범주나 개수만 적지 말고 대표 예시를 이름까지 제시하라. "
        "공식 하위 공지·첨부·공식 SNS에 공개된 세부 정보를 독자에게 다시 찾아보라고 넘기지 마라. 가수 대표곡은 공식 세트리스트가 아니면 공연 예정곡처럼 단정하지 마라. 작은 표는 실제 비교 가치가 있을 때만 쓴다. "
        "각 event section에는 재사용 권리를 기록한 실제 행사 사진을 우선한 대표 이미지, 검증된 위치·좌표, 직접 공식 안내페이지를 section.official_links에 최소 1개 넣어라. "
        "사진은 행사의 핵심 활동과 의미적으로 맞아야 하며 공연 행사에 강변 풍경·빈 공연장·연습실처럼 활동이 보이지 않는 이미지를 쓰지 마라. "
        "적합한 실제 사진이 없을 때만 공식 포스터를 쓰고 행사 본문용 AI/Pillow 대체 이미지는 만들지 마라. 이전 회차 사진은 연도와 참고 성격을 caption에 명시하라. "
        "booking/apply/purchase action은 해당 section.actions에만 두고 정보성 공식 링크와 구분하라. "
        "모든 행사 section 뒤에는 event_name이 없는 kind=general 마무리 section을 두고 일정이 몰리는 시기, 하루/다일 행사 차이, 프로그램 성격 차이 등 본문에서 확인한 정보를 종합하라. 단순히 '방문 전 공식 일정을 확인하세요'로 끝내지 마라."
    )


def event_review_instruction(bundle: dict) -> str:
    """Extra semantic-review checklist for standardized event roundups."""
    if not event_post_standard_enabled(bundle):
        return ""
    if (bundle.get("brief") or {}).get("category_key") != "events":
        return ""
    return (
        " 행사 일정형 v1 의미 검토: 각 행사 설명이 실제 볼거리·체험과 방문 판단에 필요한 확인된 조건을 충분히 설명하는지, "
        "문장이 날짜·장소를 되풀이하거나 같은 내용을 overview·상세·FAQ에서 중복하지 않는지 확인하라. 공식 자료에 작품명·출연자·공연명·세부 프로그램이 있는데도 수량·범주만 남겼거나 공개된 하위 자료 확인을 독자에게 떠넘기면 실패시켜라. "
        "가수 대표곡을 공식 세트리스트처럼 오인하게 쓰지 않았는지 확인하고, 공식 자료로 뒷받침되지 않는 연령·가족·커플 등 추천 대상이나 주차 팁을 일반화하지 마라. "
        "이전 회차 사진·프로그램을 현재 회차로 오인하게 만들지 않았는지, 이미지가 해당 행사 활동을 실제로 보여 주는지, 포스터보다 적절한 실제 사진을 놓치지 않았는지 검토하라. "
        "마지막 마무리 section이 일정 분포·행사 성격 등 본문 정보를 실제로 종합하는지 확인하고 재확인 안내만 반복하면 실패시켜라. "
        "소개·홍보 페이지를 예약·신청·구매 행동으로 오인시키지 않았는지 확인하라. 이미지 화질·crop과 지도/section 실제 배치는 최종 browser/visual QA에서 확인한다."
    )
