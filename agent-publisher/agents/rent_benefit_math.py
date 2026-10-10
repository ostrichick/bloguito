"""Auditable *illustrative* rent benefit arithmetic, never an actual refund estimate.

Only fictional inputs and explicit 2026 legal-rate citations may be combined.
Results are in ten-thousand KRW (만원), not tax assessment or guaranteed refunds.
"""
from decimal import Decimal
import re


def _str(value):
    return format(value.normalize(), 'f') if isinstance(value, Decimal) else str(value)


def validate_rent_benefit(item, text, quote_text):
    keys = {'operation','salary_man','monthly_rent_man','months','credit_percent',
            'marginal_percent','standard_credit_man'}
    if not isinstance(item, dict) or set(item) != keys or item.get('operation') != 'rent_benefit_example':
        return set(), ['invalid_derived_calculation']
    if any(type(item[k]) is not int for k in keys - {'operation'}):
        return set(), ['invalid_derived_calculation']
    salary, monthly, months = item['salary_man'],item['monthly_rent_man'],item['months']
    credit, marginal = item['credit_percent'],item['marginal_percent']
    standard = item['standard_credit_man']
    if (not 500 <= salary <= 30000 or not 1 <= monthly <= 500 or not 1 <= months <= 12
            or credit not in {0,15,17} or marginal not in {6,15,24,35,38,40,42,45}
            or standard not in {0,13}
            or (salary > 8000 and credit != 0)
            or (5500 < salary <= 8000 and credit not in {0,15})
            or (salary <= 5500 and credit == 15 and '종합소득' not in text)):
        return set(), ['invalid_derived_calculation']
    # This must be labelled as an assumption and the cited official law must
    # contain each operative statutory number (not merely an unrelated rate).
    markers = ('가정','현금영수증','월세')
    tax_rate_section = quote_text.rsplit('과세표준과 기본세율의 표', 1)
    if (not all(x in text for x in markers)
            or not re.search(rf'(?<!\d){salary}\s*만원',text)
            or not re.search(rf'(?<!\d){monthly}\s*만원',text)
            or not re.search(rf'(?<!\d){months}\s*개월',text)
            or '100분의 25' not in quote_text or '100분의 30' not in quote_text
            or ('100분의 17' if credit == 17 else '100분의 15') not in quote_text
            or len(tax_rate_section) != 2
            or f'{marginal}%' not in tax_rate_section[1]
            or (standard == 13 and not re.search(r'13\s*만원',quote_text))):
        return set(), ['invalid_derived_calculation']
    annual = Decimal(monthly * months)
    rent_credit = min(annual,Decimal(1000))*Decimal(credit)/100
    receipt_deduction = annual*Decimal('0.30')
    receipt_saving = receipt_deduction*Decimal(marginal)/100
    receipt_total = receipt_saving+Decimal(standard)
    gap=abs(rent_credit-receipt_total)
    numbers={_str(x) for x in (salary,monthly,months,credit,marginal,standard,
                annual,rent_credit,receipt_deduction,receipt_saving,receipt_total,gap,30,25)}
    # A case-specific breakpoint is permitted only under the explicitly cited
    # assumption of 17% / 15% marginal / 30% card / full standard credit.
    if (credit,marginal,standard)==(17,15,13):
        numbers.update({'104','8.67'})
    return numbers, []
