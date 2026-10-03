"""Safe, deterministic reader tools rendered from reviewed structured data only."""

from __future__ import annotations

import html
import math
import re


MINIMUM_WAGE_TOOL_KIND = "minimum_wage_monthly"
MINIMUM_WAGE_FORMULA_VERSION = "moel_weekly_holiday_v1"


def _round_positive(value: float) -> int:
    return int(math.floor(float(value) + 0.5))


def minimum_wage_monthly_projection(hourly_wage: int, weekly_hours: float,
                                    weekly_holiday: bool) -> dict:
    """Return the pilot gross monthly estimate for up to 40 contracted hours/week."""
    if type(hourly_wage) is not int or not 1 <= hourly_wage <= 1_000_000:
        raise ValueError("invalid_reader_tool_hourly_wage")
    if (isinstance(weekly_hours, bool) or not isinstance(weekly_hours, (int, float))
            or not math.isfinite(float(weekly_hours)) or not 0 <= float(weekly_hours) <= 40):
        raise ValueError("invalid_reader_tool_weekly_hours")
    if type(weekly_holiday) is not bool:
        raise ValueError("invalid_reader_tool_weekly_holiday")
    weekly = float(weekly_hours)
    holiday_hours = weekly / 40 * 8 if weekly_holiday and weekly >= 15 else 0.0
    monthly_hours = _round_positive((weekly + holiday_hours) * 365 / 7 / 12)
    return {
        "weekly_holiday_hours": holiday_hours,
        "monthly_hours": monthly_hours,
        "monthly_wage": hourly_wage * monthly_hours,
    }


def _validated_shape(tool: dict) -> dict:
    required = {
        "kind", "title", "formula_version", "hourly_wage_default",
        "weekly_hours_default", "weekly_holiday_default", "evidence",
    }
    if not isinstance(tool, dict) or set(tool) != required:
        raise ValueError("invalid_reader_tool")
    if tool.get("kind") != MINIMUM_WAGE_TOOL_KIND:
        raise ValueError("unsupported_reader_tool")
    if tool.get("formula_version") != MINIMUM_WAGE_FORMULA_VERSION:
        raise ValueError("unsupported_reader_tool_formula")
    title = tool.get("title")
    if (not isinstance(title, str) or not 4 <= len(title.strip()) <= 80
            or re.search(r"[<>\r\n]", title)):
        raise ValueError("invalid_reader_tool_title")
    result = minimum_wage_monthly_projection(
        tool.get("hourly_wage_default"),
        tool.get("weekly_hours_default"),
        tool.get("weekly_holiday_default"),
    )
    evidence = tool.get("evidence")
    if (not isinstance(evidence, list) or not 1 <= len(evidence) <= 3
            or any(not isinstance(row, dict) or set(row) != {"source_id", "quote"}
                   or not isinstance(row.get("source_id"), str) or not row["source_id"].strip()
                   or not isinstance(row.get("quote"), str) or len(row["quote"].strip()) < 8
                   for row in evidence)):
        raise ValueError("invalid_reader_tool_evidence")
    return result


def validate_reader_tools(plan: dict, sources: list[dict], brief: dict) -> list[str]:
    """Validate pilot scope and bind formula evidence to reviewed official source text."""
    tools = plan.get("reader_tools", []) if isinstance(plan, dict) else None
    if not isinstance(tools, list) or len(tools) > 1:
        return ["invalid_reader_tools"]
    if not tools:
        return []
    tool = tools[0]
    try:
        _validated_shape(tool)
    except ValueError:
        return ["invalid_reader_tools"]
    keyword = " ".join(str(brief.get(key, "")) for key in ("entity", "primary_keyword"))
    if (brief.get("intent_type") != "calculator"
            or "calculator" not in brief.get("added_value", [])
            or "최저임금" not in keyword):
        return ["reader_tool_outside_brief_scope"]
    source_map = {row.get("id"): row for row in sources if isinstance(row, dict)}
    for evidence in tool["evidence"]:
        source = source_map.get(evidence["source_id"])
        if not source or source.get("source_type") != "official":
            return ["invalid_reader_tool_evidence"]
        quote = " ".join(evidence["quote"].split())
        source_text = " ".join(str(source.get("text", "")).split())
        if quote not in source_text:
            return ["invalid_reader_tool_evidence"]
    return []


def render_reader_tools(plan: dict) -> str:
    tools = plan.get("reader_tools", []) if isinstance(plan, dict) else []
    if not tools:
        return ""
    if not isinstance(tools, list) or len(tools) != 1:
        raise ValueError("invalid_reader_tools")
    tool = tools[0]
    projection = _validated_shape(tool)
    hourly = tool["hourly_wage_default"]
    weekly = float(tool["weekly_hours_default"])
    checked = " checked" if tool["weekly_holiday_default"] else ""
    title = html.escape(tool["title"])
    weekly_attr = format(weekly, "g")
    initial_wage = f"{projection['monthly_wage']:,}원"
    initial_detail = f"월 환산 {projection['monthly_hours']}시간"
    return (
        '<section class="bloguito-reader-tool" data-reader-tool="minimum_wage_monthly" '
        'style="margin:24px 0 30px;padding:20px;border:1px solid #cbd5e1;border-radius:12px;background:#ffffff">'
        f'<h2 style="margin:0 0 8px;font-size:21px;color:#1e293b">{title}</h2>'
        '<p style="margin:0 0 16px;color:#475569;font-size:14px;line-height:1.65">'
        '세전 단순 환산값입니다. 연장, 야간, 휴일 가산수당과 세금/공제는 포함하지 않습니다.</p>'
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px">'
        '<label style="font-weight:600;color:#334155">시급(원)'
        f'<input data-role="hourly" type="number" inputmode="numeric" min="1" max="1000000" step="10" value="{hourly}" '
        'style="display:block;width:100%;margin-top:6px;padding:10px;border:1px solid #94a3b8;border-radius:8px;font:inherit" /></label>'
        '<label style="font-weight:600;color:#334155">주 소정근로시간'
        f'<input data-role="weekly" type="number" inputmode="decimal" min="0" max="40" step="0.5" value="{weekly_attr}" '
        'style="display:block;width:100%;margin-top:6px;padding:10px;border:1px solid #94a3b8;border-radius:8px;font:inherit" /></label>'
        '</div>'
        '<label style="display:flex;gap:8px;align-items:flex-start;margin:14px 0;color:#334155;font-weight:600">'
        f'<input data-role="holiday" type="checkbox"{checked} style="margin-top:5px" />'
        '<span>주휴 적용 조건을 충족함 <small style="display:block;font-weight:400;color:#64748b">'
        '주 15시간 이상 등 실제 적용 요건은 근로계약과 출근 상황을 확인하세요.</small></span></label>'
        '<div style="padding:16px;background:#f0f8f5;border-radius:10px" aria-live="polite">'
        '<div style="font-size:14px;color:#475569">예상 월 급여</div>'
        f'<output data-role="salary" style="display:block;margin-top:4px;font-size:24px;font-weight:800;color:#0d7d59">{initial_wage}</output>'
        f'<div data-role="detail" style="margin-top:5px;font-size:13px;color:#64748b">{initial_detail}</div>'
        '</div>'
        '<noscript><p style="margin:12px 0 0;color:#7c2d12;font-size:13px">'
        '계산 기능을 사용하려면 JavaScript가 필요합니다. 공식 최저임금 모의계산기로 최종 확인하세요.</p></noscript>'
        '<script>(function(){"use strict";const root=document.currentScript.parentElement;'
        'const hourly=root.querySelector("[data-role=hourly]"),weekly=root.querySelector("[data-role=weekly]"),'
        'holiday=root.querySelector("[data-role=holiday]"),salary=root.querySelector("[data-role=salary]"),'
        'detail=root.querySelector("[data-role=detail]");const fmt=new Intl.NumberFormat("ko-KR");'
        'function update(){const h=Number(hourly.value),w=Number(weekly.value);'
        'if(!Number.isFinite(h)||h<1||h>1000000||!Number.isFinite(w)||w<0||w>40){'
        'salary.textContent="입력값을 확인하세요";detail.textContent="주 소정근로시간은 0~40시간 범위입니다.";return;}'
        'const holidayHours=holiday.checked&&w>=15?(w/40)*8:0;'
        'const monthlyHours=Math.round((w+holidayHours)*365/7/12);'
        'const monthly=Math.round(h*monthlyHours);salary.textContent=fmt.format(monthly)+"원";'
        'detail.textContent="월 환산 "+monthlyHours+"시간"+(holiday.checked&&w<15?" · 주 15시간 미만이라 주휴 0시간 적용":"");}'
        '[hourly,weekly,holiday].forEach(function(el){el.addEventListener("input",update);el.addEventListener("change",update);});update();})();</script>'
        '</section>'
    )
