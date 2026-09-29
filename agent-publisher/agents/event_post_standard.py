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
    r"편집자\s*메모|확인\s*불가"
)
_COMMA_SPACING = re.compile(r"(?<=[가-힣A-Za-z]),(?=[가-힣A-Za-z])")
_PERIOD_SPACING = re.compile(r"(?<=[가-힣])\.(?=[가-힣])")
_YEAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_VAGUE_OVERVIEW_HEADER = re.compile(
    r"확인된\s*실전\s*조건|실전\s*조건|실전\s*정보|판단\s*포인트|"
    r"추천\s*/?\s*핵심|핵심\s*관전\s*포인트"
)
_IMAGE_RIGHTS = {"generated_original", "site_owned", "open_license", "permission_granted"}


def event_post_standard_enabled(bundle: dict | None) -> bool:
    """Return whether a bundle explicitly opts into the event-post standard."""
    if not isinstance(bundle, dict):
        return False
    brief = bundle.get("brief") or {}
    return brief.get("event_post_standard_version") is not None


def _visible_strings(plan: dict, sources: list[dict]) -> list[str]:
    """Reader-facing strings only; evidence/source raw text is deliberately excluded."""
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


def _overview_valid(section: dict | None) -> bool:
    if not isinstance(section, dict) or section.get("kind") != "overview":
        return False
    table = section.get("table")
    if not isinstance(table, dict) or table.get("mobile_cards") is not True:
        return False
    headers = table.get("headers")
    rows = table.get("rows")
    if not isinstance(headers, list) or not isinstance(rows, list) or len(rows) < 2:
        return False
    text = " ".join(value for value in headers if isinstance(value, str))
    if _VAGUE_OVERVIEW_HEADER.search(text):
        return False
    has_date = any(token in text for token in ("날짜", "기간", "일정"))
    has_event = any(token in text for token in ("행사", "축제", "프로그램"))
    has_place = any(token in text for token in ("장소", "행사장", "지역"))
    has_decision = any(
        token in text
        for token in ("볼거리", "체험", "관람", "프로그램", "비용", "가격", "티켓", "예매", "신청", "예약", "운영시간")
    )
    return has_date and has_event and has_place and has_decision


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
        return False
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
    if not event_post_standard_enabled(bundle):
        return []

    brief = bundle.get("brief") or {}
    plan = bundle.get("plan") or {}
    sources = bundle.get("sources") or []
    temporal = bundle.get("temporal_source") or {}
    reasons: list[str] = []

    if (brief.get("event_post_standard_version") != EVENT_POST_STANDARD_VERSION
            or brief.get("content_type") != "dated"
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
    overview_header_text = " ".join(
        value for value in ((sections[0].get("table") or {}).get("headers", []) if sections and isinstance(sections[0], dict) else [])
        if isinstance(value, str)
    )
    if not sections or not _overview_valid(sections[0]):
        reasons.append("event_standard_overview_missing")
    if _VAGUE_OVERVIEW_HEADER.search(overview_header_text):
        reasons.append("event_standard_overview_header_vague")

    if (brief.get("allow_selection_guide") is not True
            and any(isinstance(section, dict)
                    and section.get("kind") == "comparison"
                    and section.get("event_name") is None
                    for section in sections)):
        reasons.append("event_standard_unrequested_selection_guide")

    entries = temporal.get("event_entries") or []
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

    source_map = {source.get("id"): source for source in sources if isinstance(source, dict)}
    decision_missing = False
    prior_year_missing = False
    section_assets_missing = False
    image_rights_missing = False
    entry_map = {entry.get("name"): entry for entry in entries if isinstance(entry, dict)}
    for name, section in bound.items():
        body, support = _section_support_text(section)
        if (not body.strip() or not _ACTIVITY.search(body) or not _DECISION.search(support)):
            decision_missing = True
        image = section.get("image")
        location = section.get("location")
        if not isinstance(image, dict) or not isinstance(location, dict):
            section_assets_missing = True
        if isinstance(image, dict):
            rights = image.get("rights")
            rights_url = image.get("rights_url")
            if (rights not in _IMAGE_RIGHTS
                    or (rights in {"open_license", "permission_granted"}
                        and (not isinstance(rights_url, str) or not rights_url.startswith("https://")))):
                image_rights_missing = True
            if rights == "generated_original" and not re.search(r"제작|바탕|일러스트|이미지", image.get("caption", "")):
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
    if prior_year_missing:
        reasons.append("event_standard_previous_year_image_disclosure_missing")

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

    visible = _visible_strings(plan, sources)
    if any(_COMMA_SPACING.search(value) or _PERIOD_SPACING.search(value) for value in visible):
        reasons.append("event_standard_reader_punctuation_spacing")
    if any(_EDITOR_NOTE.search(value) for value in visible):
        reasons.append("event_standard_editor_note_exposed")

    return sorted(set(reasons))


def event_writer_instruction(brief: dict, temporal_source: dict | None = None) -> str:
    """Extra writer contract only for explicitly standardized event roundups."""
    if brief.get("event_post_standard_version") != EVENT_POST_STANDARD_VERSION:
        return ""
    if (temporal_source or {}).get("multi_event_schedule") is not True:
        return ""
    return (
        " 이 원고는 행사 일정형 v1이다. 첫 section은 kind=overview 비교표로 만들고 mobile_cards=true를 사용해 "
        "날짜, 행사, 실제 볼거리와 체험, 필요할 때 티켓과 예약 또는 비용, 장소처럼 독자가 뜻을 바로 이해하는 열을 사용하라. "
        "'확인된 실전 조건', '판단 포인트', '추천/핵심'처럼 추상적인 열 이름은 쓰지 마라. "
        "temporal_source.event_entries의 각 name마다 상세 section 하나를 만들고 section.event_name에 그 name을 정확히 넣어라. "
        "각 상세 section은 날짜·장소 반복으로 끝내지 말고 공식 프로그램에 근거해 무엇을 보고·해볼 수 있는지와 어떤 방문 목적에 맞는지, "
        "비용·신청·운영시간 등 확인된 조건을 설명하라. 각 event section에는 검증된 대표 이미지와 위치 카드를 모두 넣고, "
        "이미지는 재사용 권리 상태를 기록하라. 안전한 공식 활동 사진을 확보하지 못하면 공식 프로그램을 근거로 직접 제작한 이미지를 사용하고 실제 현장 사진처럼 표현하지 마라. "
        "booking/apply/purchase action은 해당 event section.actions에만 배치하라. 독자가 행사별 설명만으로 선택할 수 있으면 별도의 선택·추천 비교 section을 만들지 마라. "
        "이전 회차 프로그램이나 사진은 현재 확정 내용처럼 쓰지 말고 연도와 참고 성격을 명시하라. "
        "primary_keyword는 SEO title, meta description, lead와 관련 소제목 하나에 자연스럽게 exact match로 사용하되 반복하지 마라."
    )


def event_review_instruction(bundle: dict) -> str:
    """Extra semantic-review checklist for standardized event roundups."""
    if not event_post_standard_enabled(bundle):
        return ""
    return (
        " 행사 일정형 v1 추가 검토: 각 event_name section만 읽어도 독자가 실제로 무엇을 보고·체험할지와 방문 목적, "
        "비용·신청·운영시간 중 확인된 실전 조건을 판단할 수 있는지 확인하라. 프로그램에서 추론할 수 없는 연령·가족·커플 선호를 "
        "임의로 일반화하지 마라. 이전 연도 프로그램·사진을 현재 회차로 오인하게 만들면 실패시켜라. 행사 전용 신청·예약·구매 CTA가 "
        "그 행사 section에 붙어 있는지, 소개/홍보 페이지가 행동 버튼으로 둔갑하지 않았는지 확인하라. 각 행사에 대표 이미지와 위치 카드가 있고, "
        "이미지의 재사용 권리 또는 직접 제작 provenance가 기록됐는지 확인하라. 독자가 이미 행사별 정보로 판단할 수 있는데 별도 추천·선택 조언 section을 덧붙이지 않았는지도 확인하라. 이미지가 활동 장면인지·화질이 충분한지는 "
        "최종 browser/visual QA 대상이므로 텍스트 메타데이터만으로 검증했다고 추정하지 마라."
    )
