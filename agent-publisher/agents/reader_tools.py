"""Safe, deterministic reader tools rendered from reviewed structured data only."""

from __future__ import annotations

import html
import math
import re


MINIMUM_WAGE_TOOL_KIND = "minimum_wage_monthly"
MINIMUM_WAGE_FORMULA_VERSION = "moel_weekly_holiday_v1"
RENT_TAX_TOOL_KIND = "rent_tax_comparison"
RENT_TAX_FORMULA_VERSION = "rent_credit_receipt_2026_v1"
RENT_TAX_RATES = frozenset((6, 15, 24, 35, 38, 40, 42, 45))


def rent_comparison_projection(monthly_gross_man: int, monthly_rent_man: int,
                               months: int, marginal_percent: int,
                               card_deduction_used_man: int,
                               other_card_floor_met: bool,
                               rent_eligible: bool, annual_bonus_man: int = 0) -> dict:
    """Conditional upper-level comparison, deliberately NOT a tax assessment.

    Assumes other card spend already passes salary's 25% threshold and doesn't
    consume the 300/250 basic deduction cap beyond the explicit used amount.
    Statutory rent credit eligibility depends on other legal tests the model
    cannot determine from gross pay alone. No standard 130k credit is added.
    """
    if (any(type(v) is not int for v in (monthly_gross_man, monthly_rent_man,
                                        months, marginal_percent, card_deduction_used_man,
                                        annual_bonus_man))
            or not 1 <= monthly_gross_man <= 10_000
            or not 1 <= monthly_rent_man <= 500
            or not 1 <= months <= 12
            or marginal_percent not in RENT_TAX_RATES
            or not 0 <= card_deduction_used_man <= 400
            or not 0 <= annual_bonus_man <= 100_000
            or type(other_card_floor_met) is not bool or type(rent_eligible) is not bool):
        raise ValueError("invalid_rent_comparison_inputs")
    salary = monthly_gross_man * 12 + annual_bonus_man
    annual_rent = monthly_rent_man * months
    rate = 17 if salary <= 5500 else 15
    base_cap = 250 if salary > 7000 else 300
    card_headroom = max(0, base_cap - card_deduction_used_man)
    deduction = min(annual_rent * 0.30, card_headroom)
    return {
        "salary_man": salary,
        "credit_percent": rate if salary <= 8000 and rent_eligible else None,
        "rent_nominal_man": round(min(annual_rent, 1000) * rate / 100, 4)
                            if salary <= 8000 and rent_eligible else None,
        "credit_ineligible_salary": salary > 8000,
        "receipt_tax_simple_man": round(deduction * marginal_percent / 100, 4)
                                   if other_card_floor_met else None,
        "receipt_deduction_man": round(deduction, 4) if other_card_floor_met else None,
        "base_card_cap_man": base_cap,
    }


def _validate_rent_shape(tool: dict) -> dict:
    required = {"kind", "title", "formula_version", "monthly_gross_default_man",
                "annual_bonus_default_man",
                "monthly_rent_default_man", "months_default", "marginal_percent_default",
                "card_deduction_used_default_man", "other_card_floor_met_default",
                "rent_eligible_default", "evidence"}
    if (not isinstance(tool, dict) or set(tool) != required
            or tool.get("kind") != RENT_TAX_TOOL_KIND
            or tool.get("formula_version") != RENT_TAX_FORMULA_VERSION
            or not isinstance(tool.get("title"), str)
            or not 4 <= len(tool["title"].strip()) <= 80
            or re.search(r"[<>\r\n]", tool["title"])):
        raise ValueError("invalid_rent_reader_tool")
    values = rent_comparison_projection(
        tool.get("monthly_gross_default_man"), tool.get("monthly_rent_default_man"),
        tool.get("months_default"), tool.get("marginal_percent_default"),
        tool.get("card_deduction_used_default_man"),
        tool.get("other_card_floor_met_default"), tool.get("rent_eligible_default"),
        tool.get("annual_bonus_default_man"))
    if (not isinstance(tool.get("evidence"), list) or len(tool["evidence"]) != 4
            or any(not isinstance(row, dict) or set(row) != {"source_id", "quote"}
                   or not isinstance(row.get("source_id"), str)
                   or not isinstance(row.get("quote"), str)
                   for row in tool["evidence"])):
        raise ValueError("invalid_rent_reader_tool_evidence")
    return values



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
    kind = tool.get("kind") if isinstance(tool, dict) else None
    try:
        if kind == RENT_TAX_TOOL_KIND:
            _validate_rent_shape(tool)
        else:
            _validated_shape(tool)
    except ValueError:
        return ["invalid_reader_tools"]
    keyword = " ".join(str(brief.get(key, "")) for key in ("entity", "primary_keyword"))
    rent_scope = (kind == RENT_TAX_TOOL_KIND and "월세" in keyword
                  and brief.get("intent_type") in {"calculator", "comparison", "decision"})
    wage_scope = (kind == MINIMUM_WAGE_TOOL_KIND and "최저임금" in keyword
                  and brief.get("intent_type") == "calculator")
    if (not (rent_scope or wage_scope)
            or "calculator" not in brief.get("added_value", [])):
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
    if kind == RENT_TAX_TOOL_KIND and {e["source_id"] for e in tool["evidence"]} != {
            "s2", "s3", "s5", "s6"}:
        return ["invalid_reader_tool_evidence"]
    return []


def _render_rent_comparison(tool: dict) -> str:
    result = _validate_rent_shape(tool)
    salary = tool["monthly_gross_default_man"]
    bonus = tool["annual_bonus_default_man"]
    rent = tool["monthly_rent_default_man"]
    months = tool["months_default"]
    rate = tool["marginal_percent_default"]
    used = tool["card_deduction_used_default_man"]
    floor_checked = " checked" if tool["other_card_floor_met_default"] else ""
    eligible_checked = " checked" if tool["rent_eligible_default"] else ""
    title = html.escape(tool["title"])
    credit = (f'{result["rent_nominal_man"]:g}만원'
              if result["rent_nominal_man"] is not None else "요건 확인 필요")
    receipt = (f'{result["receipt_tax_simple_man"]:g}만원'
               if result["receipt_tax_simple_man"] is not None else "25% 사용기준 확인 필요")
    rates = "".join(
        f'<option value="{n}"{" selected" if n == rate else ""}>{n}%</option>'
        for n in sorted(RENT_TAX_RATES))
    # Static, reviewed JS only: input values go to textContent, never innerHTML,
    # and there are no network calls or user-entered script fields.
    script = r"""(function(){
      "use strict";
      // WordPress may wrap this script in a paragraph during the_content filtering.
      // Locate the reviewed single tool by its stable attribute, not the script parent.
      const root=document.querySelector('[data-reader-tool="rent_tax_comparison"]');
      if(!root)return;
      const el=(name)=>root.querySelector('[data-role="'+name+'"]');
      const money=(number)=>(Math.round(number*100)/100).toLocaleString('ko-KR',{maximumFractionDigits:2})+'만원';
      function update(){
        const income=Number(el('income').value),rent=Number(el('rent').value);
        const months=Number(el('months').value),rate=Number(el('rate').value);
        const used=Number(el('used').value),bonus=Number(el('bonus').value);
        // Avoid logical AND characters: WordPress may entity-encode them
        // inside inline scripts and make the real page invalid JavaScript.
        const valid=[
          [income,rent,months,rate,used,bonus].every(Number.isFinite),
          [income,rent,used,bonus].every(Number.isInteger),
          income>=1,income<=10000,rent>=1,rent<=500,
          Number.isInteger(months),months>=1,months<=12,
          [6,15,24,35,38,40,42,45].includes(rate),
          used>=0,used<=400,bonus>=0,bonus<=100000
        ].every(Boolean);
        if(!valid || [el('income'),el('rent'),el('months'),el('used'),el('bonus')].some(x=>!x.value.trim())){
          el('credit').textContent='입력값 확인';el('receipt').textContent='입력값 확인';
          el('detail').textContent='금액과 납부 개월 수를 올바르게 입력하세요.';return;
        }
        const gross=income*12+bonus, annualRent=rent*months;
        const creditRate=gross<=5500?17:15;
        const cardCap=gross>7000?250:300;
        const nominalRent=Math.min(annualRent,1000)*creditRate/100;
        const deductible=Math.min(annualRent*.30,Math.max(0,cardCap-used));
        const saving=deductible*rate/100;
        el('credit').textContent=gross>8000?'총급여 기준 초과'
          :(!el('eligible').checked?'주택·거주 요건 확인 필요':money(nominalRent));
        el('receipt').textContent=el('floor').checked?money(saving):'25% 사용기준 확인 필요';
        el('detail').textContent='가정 연 총급여 '+money(gross)+' · 월세 '+months
          +'개월 · 카드 소득공제 기본한도 '+money(cardCap)
          +' · 현금영수증 가정 한계세율 '+rate+'%'
          +' · 공제율 '+(gross>8000?'대상 아님':creditRate+'%')
          +' (실제 절세·환급액 아님)';
      }
      root.querySelectorAll('input,select').forEach((input)=>{
        input.addEventListener('input',update);input.addEventListener('change',update);
      });
      update();
    })();"""
    return (
        '<section class="bloguito-reader-tool" data-reader-tool="rent_tax_comparison" '
        'style="margin:24px 0 30px;padding:18px;border:1px solid #cbd5e1;border-radius:12px;background:#ffffff">'
        '<style>.bloguito-reader-tool input[type=number],.bloguito-reader-tool select{'
        'min-width:0;max-width:100%;font:inherit;color:#1e293b}'
        '@media(max-width:640px){.bloguito-rent-basic-grid,.bloguito-rent-advanced-grid{'
        'grid-template-columns:minmax(0,1fr)!important}}'
        '</style>'
        f'<h2 style="margin:0 0 8px;font-size:21px">{title}</h2>'
        '<p style="margin:0 0 14px;font-size:14px;line-height:1.6">'
        '금액을 바꿔 두 제도의 <strong>조건부 계산값</strong>을 확인하세요. '
        '연 총급여는 월급 12개월분과 아래 상여금의 합으로 가정하며 실제 환급액은 계산하지 않습니다. '
        '현금영수증 계산에 쓸 가정 세율을 직접 선택하세요(위 비교표의 9천만원 사례는 24% 가정). '
        '<strong>아래 요건을 확인하고 체크하면 계산 결과가 표시됩니다.</strong></p>'
        '<div class="bloguito-rent-basic-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:12px">'
        '<label>월 총급여(세전·만원)'
        f'<input data-role="income" type="number" min="1" max="10000" step="1" value="{salary}" '
        'style="display:block;width:100%;padding:9px;border:1px solid #94a3b8;border-radius:6px"></label>'
        '<label>월세(만원)'
        f'<input data-role="rent" type="number" min="1" max="500" step="1" value="{rent}" '
        'style="display:block;width:100%;padding:9px;border:1px solid #94a3b8;border-radius:6px"></label>'
        '<label>월세 납부 개월 수'
        f'<input data-role="months" type="number" min="1" max="12" step="1" value="{months}" '
        'style="display:block;width:100%;padding:9px;border:1px solid #94a3b8;border-radius:6px"></label>'
        '<label>현금영수증 계산용 가정 한계세율'
        '<select data-role="rate" style="display:block;width:100%;padding:9px;border:1px solid #94a3b8;border-radius:6px">'
        + rates + '</select></label>'
        '</div>'
        '<details style="margin-top:14px"><summary style="cursor:pointer;font-weight:700">'
        '계산 조건 설정 (정확도를 위해 확인)</summary>'
        '<div class="bloguito-rent-advanced-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:12px;margin-top:12px">'
        '<label>연간 상여금 등 추가 총급여(만원)'
        f'<input data-role="bonus" type="number" min="0" max="100000" step="1" value="{bonus}" '
        'style="display:block;width:100%;padding:9px;border:1px solid #94a3b8;border-radius:6px"></label>'
        '<label>이미 사용한 카드 소득공제 한도(만원)'
        f'<input data-role="used" type="number" min="0" max="400" step="1" value="{used}" '
        'style="display:block;width:100%;padding:9px;border:1px solid #94a3b8;border-radius:6px"></label>'
        '</div><p style="font-size:13px;margin:10px 0 0;color:#475569">'
        '종합소득금액 요건도 별도로 충족해야 합니다. 자녀에 따른 카드 공제한도 가산, '
        '다른 소득공제와 세액공제, 남은 소득세, 표준세액공제 13만원의 영향은 반영하지 않았습니다.</p></details>'
        '<fieldset style="border:0;padding:0;margin:12px 0 0">'
        '<legend style="font-weight:700;font-size:14px">계산을 위한 확인사항 (확인 후 체크)</legend>'
        '<label style="display:block;margin-top:8px">'
        f'<input type="checkbox" data-role="floor"{floor_checked}> '
        '월세 외 카드와 현금영수증 사용액이 총급여 25%를 이미 넘음</label>'
        '<label style="display:block;margin-top:8px">'
        f'<input type="checkbox" data-role="eligible"{eligible_checked}> '
        '무주택, 임대차계약, 실거주, 종합소득금액 등 공제 요건을 충족함</label>'
        '</fieldset>'
        '<div aria-live="polite" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-top:16px">'
        '<div style="padding:13px;border:1px solid #dbe5e1;border-radius:8px">'
        '<div style="font-size:13px">월세 세액공제 · 법정 명목액</div>'
        f'<output data-role="credit" style="display:block;font-size:23px;font-weight:800">{credit}</output></div>'
        '<div style="padding:13px;border:1px solid #dbe5e1;border-radius:8px">'
        '<div style="font-size:13px">현금영수증 · 단순 세율 추정</div>'
        f'<output data-role="receipt" style="display:block;font-size:23px;font-weight:800">{receipt}</output></div>'
        '</div>'
        f'<p data-role="detail" style="font-size:13px;margin:12px 0 0;color:#475569">'
        f'가정 연 총급여 {result["salary_man"]}만원 · 실제 환급액 아님</p>'
        '<p style="font-size:13px;color:#7c2d12;margin:7px 0 0">'
        '어느 쪽이 실제 유리한지는 연말정산에서 남은 소득세, 과세표준과 다른 공제를 모두 반영해야 합니다.</p>'
        '<noscript><p style="color:#7c2d12">입력값을 변경하는 계산 기능에는 JavaScript가 필요합니다.</p></noscript>'
        '<script>' + script + '</script></section>'
    )


def render_reader_tools(plan: dict) -> str:
    tools = plan.get("reader_tools", []) if isinstance(plan, dict) else []
    if not tools:
        return ""
    if not isinstance(tools, list) or len(tools) != 1:
        raise ValueError("invalid_reader_tools")
    tool = tools[0]
    if tool.get("kind") == RENT_TAX_TOOL_KIND:
        return _render_rent_comparison(tool)
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
