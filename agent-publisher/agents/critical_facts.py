"""Fail-closed version checks for a small set of frequently changing public-benefit topics.

A fresh HTTP fetch is not evidence that the source *content* is current. This
module checks years, official publisher domains, canonical current-year facts,
and a handful of known misleading claims before Gemini review or WP draft.
It is intentionally narrow; it does not certify the rest of an article.
"""
import re
from urllib.parse import urlparse


def _flat(value):
    return re.sub(r"[\s,]", "", value or "")


def _article_text(plan):
    parts = [plan.get("title", ""), plan.get("lead", {}).get("text", "")]
    for section in plan.get("sections", []):
        parts.append(section.get("heading", ""))
        parts.extend(block.get("text", "") for block in section.get("paragraphs", []))
    for faq in plan.get("faq", []):
        parts.append(faq.get("question", ""))
        parts.append(faq.get("answer", {}).get("text", ""))
    return " ".join(parts)


def _official(sources, hosts):
    return " ".join(
        source.get("text", "") for source in sources
        if source.get("source_type") == "official" and
        any((urlparse(source.get("url", "")).hostname or "").lower() == h or
            (urlparse(source.get("url", "")).hostname or "").lower().endswith("."+h)
            for h in hosts)
    )


def critical_fact_reasons(brief, sources, plan):
    """Return blocking reasons only for specifically verified 2026 policies."""
    name = " ".join([brief.get("entity", ""), brief.get("primary_keyword", ""), plan.get("title", "")])
    body = _article_text(plan)
    t = _flat(body)
    reasons = []
    if "2026" in name and "기초연금" in name:
        source = _flat(_official(sources, {"mohw.go.kr", "law.go.kr"}))
        if not all(token in source for token in ("2026", "247만", "395만", "349700")):
            reasons.append("pension_2026_authoritative_baseline_missing")
        old_values = ("213만원", "340만8천", "343510원", "549610원", "274805원", "110만원", "2130000원", "3408000원")
        if any(v in t for v in old_values):
            reasons.append("pension_2026_stale_annual_figures")
        if "근로소득" in body and "116만" not in t:
            reasons.append("pension_2026_work_income_allowance_missing")
        if re.search(r"(?:월급|근로소득)[^.。\n]{0,100}(?:전액\s*(?:수령|지급)|수급\s*(?:확정|보장))", body):
            reasons.append("pension_unwarranted_entitlement_claim")
    if "2026" in name and "세금포인트" in name:
        source = _flat(_official(sources, {"nts.go.kr"}))
        if not ("2025" in source and "1000" in source and "5년" in source):
            reasons.append("tax_points_2026_authoritative_version_missing")
        if re.search(r"(?:연간|최대|한해|부여한도)[^.。\n]{0,35}50(?:점|포인트)|50(?:점|포인트)까지", t):
            reasons.append("tax_points_2026_stale_50_point_cap")
        if "5년" in body and not ("2025" in body and "부여" in body):
            reasons.append("tax_points_2026_expiry_cohort_missing")
        if "환급금" in body and re.search(r"세금포인트.{0,30}(?:현금환급|현금으로환급)", t):
            reasons.append("tax_points_misclassified_as_cash_refund")
    if "2026" in name and any(w in name for w in ("인플루엔자", "독감")):
        source = _flat(_official(sources, {"kdca.go.kr", "korea.kr"}))
        if not ("2026" in source and "3가" in source and any(d in source for d in ("9월21", "9.21")) and any(d in source for d in ("10월6", "10.6"))):
            reasons.append("influenza_2026_revised_schedule_source_missing")
        if "4가백신" in t or "4가백신" in t.replace("(4가)", "4가"):
            reasons.append("influenza_2026_outdated_vaccine_type")
        if any(v in t for v in ("9월20일부터", "10월2일부터", "10월11일부터", "10월18일부터", "2026.09.20", "2026.10.02", "2026.10.11", "2026.10.18")):
            reasons.append("influenza_2026_outdated_schedule")
    # Financial/medical claims found in the 2026-09-20 live-publication audit.
    # These guards deliberately stop unsupported sales-like guarantees, rather
    # than claiming comprehensive natural-language truth verification.
    if "2026" in name and any(token in name for token in ("숨은 보험금", "숨은보험금", "내보험 찾아줌", "내보험찾아줌")):
        if any(token in t for token in ("매년12조원", "12조원이상", "1000만원이하즉시", "1분만에일괄조회", "즉시계좌입금")):
            reasons.append("insurance_2026_unverified_guarantee_or_amount")
    if "2026" in name and "본인부담상한" in name:
        old_health_claims = ("평균약130만원", "1분위약87만원", "2026년1분위87만원", "안내를받은날로부터3년")
        if any(token in t for token in old_health_claims):
            reasons.append("health_refund_2026_unverified_year_or_amount")
        if re.search(r"2026년.{0,45}상한액.{0,60}\d+(?:만|원)", t):
            source = _flat(_official(sources, {"nhis.or.kr", "mohw.go.kr"}))
            if "2026" not in source or not any(token in body for token in ("진료 연도", "진료연도", "귀속 연도", "귀속연도")):
                reasons.append("health_refund_2026_service_year_source_missing")
    if "2026" in name and ("전기차" in name or "급속충전" in name):
        if any(token in t for token in ("무료급속충전", "무료이동형충전", "20kW무료", "20kW전액무료")):
            source = _flat(_official(sources, {"me.go.kr", "ev.or.kr", "ex.co.kr", "roadplus.co.kr"}))
            if not all(token in source for token in ("2026", "무료", "휴게소")):
                reasons.append("ev_2026_free_charging_event_unverified")
        if "20kw" in t.lower() and any(token in t for token in ("충전량", "제공량", "주행분")):
            reasons.append("ev_charging_energy_unit_kwh_required")
    return sorted(set(reasons))


def published_content_risks(title, content, today=None):
    """Read-only, conservative legacy-content audit; no blanket accuracy claims."""
    from datetime import date
    import html
    today = today or date.today()
    risks = []
    if re.search(r'정정\s*안내|(?:자료\s*검토|내용\s*재검토|최종\s*검토일|검토·수정)\s*[:：]|이\s*초안|공식\s*출처\s*및\s*검토\s*기록', html.unescape(content or '')):
        risks.append('internal_editorial_note_exposed')
    # Correction history may quote a bad *former* value without asserting it.
    # Exclude the explicitly labelled correction note and superseded-date sentence.
    body = re.sub(r'<div\b[^>]*>\s*<strong>정정 안내[^<]*</strong>.*?</div>', ' ', content or '',flags=re.IGNORECASE | re.DOTALL)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    text = re.sub(r'기존의.{0,190}?폐기했습니다\.', ' ', text)
    flat = _flat(text)
    if "기초연금" in title and "2026" in title and any(x in flat for x in ("213만원", "340만8천", "343510원", "549610원", "110만원")):
        risks.append("pension_known_stale_2026")
    if "세금포인트" in title and re.search(r"(?:연간|최대|한해|부여한도)[^.。\n]{0,35}50(?:점|포인트)|50(?:점|포인트)까지", flat):
        risks.append("tax_point_old_cap")
    if "2026" in title and any(w in title for w in ("독감", "인플루엔자")) and ("4가백신" in flat or "2026.09.20" in flat):
        risks.append("influenza_stale_2026")
    if "환급금" in title and "세금포인트" in title and "환급금5종" in flat:
        risks.append("tax_points_refund_category_error")
    if "2026" in title and "전기차" in title and "무료" in title and "20kW" in text:
        risks.append("unverified_free_ev_charging_and_wrong_energy_unit")
    if "오늘" in title and today.year == 2026:
        for month, day in re.findall(r"오늘\s*\(?\s*(?:2026년\s*)?(\d{1,2})월\s*(\d{1,2})일", text):
            if (int(month), int(day)) < (today.month, today.day):
                risks.append("outdated_today_event")
    return sorted(set(risks))
