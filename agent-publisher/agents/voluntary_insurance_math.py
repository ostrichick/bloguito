"""Evidence-bound 2026 voluntary-continuation *illustration*, not an NHIS bill.

The regional premium is a fictional input already INCLUDING long-term-care
insurance. Do not infer it from salary, property or family composition.
"""
import re


def validate_voluntary_insurance_example(item, text, quote_text, shared_context=''):
    keys = {
        'operation', 'average_remuneration_won', 'regional_total_won',
        'health_won', 'long_term_care_won', 'voluntary_total_won',
        'advantage', 'monthly_gap_won', 'twelve_month_gap_won',
    }
    if (not isinstance(item, dict) or set(item) != keys
            or item.get('operation') != 'voluntary_insurance_2026_example'):
        return set(), ['invalid_derived_calculation']
    integers = keys - {'operation', 'advantage'}
    if any(type(item[k]) is not int for k in integers):
        return set(), ['invalid_derived_calculation']
    salary = item['average_remuneration_won']
    regional = item['regional_total_won']
    # Restrict to ordinary illustrative cases where the statutory health
    # insurance minimum and maximum do not alter the salary-based expression.
    if (not 1_000_000 <= salary <= 10_000_000 or salary % 10_000
            or not 20_000 <= regional <= 2_000_000 or regional % 10
            or item['advantage'] not in {'voluntary', 'regional', 'equal'}):
        return set(), ['invalid_derived_calculation']

    # 2026: health 7.19%, 50% reduction under insurance premium reduction
    # notice Article 9. LTC = health premium * (0.9448% / 7.19%).
    # NHIS Act 107, LTC Act 64, Treasury Funds Management Act 47:
    # each premium discards remainders smaller than 10 won.
    health = (salary * 719 // 20_000) // 10 * 10
    long_term = (health * 9_448 // 71_900) // 10 * 10
    total = health + long_term
    diff = regional - total
    expected_advantage = 'voluntary' if diff > 0 else 'regional' if diff < 0 else 'equal'
    if (item['health_won'] != health
            or item['long_term_care_won'] != long_term
            or item['voluntary_total_won'] != total
            or item['advantage'] != expected_advantage
            or item['monthly_gap_won'] != abs(diff)
            or item['twelve_month_gap_won'] != abs(diff) * 12):
        return set(), ['invalid_derived_calculation']

    visible_context = text + ' ' + shared_context
    # The rates and reduction must be explicitly present in linked evidence,
    # and the comparison's assumptions/caveats must be reader-visible. These
    # markers deliberately cannot be supplied only through hidden metadata.
    if (not all(marker in quote_text for marker in ('2026', '7.19', '0.9448'))
            or '장기요양' not in quote_text
            or '임의계속' not in quote_text
            or not re.search(r'10\s*원\s*미만', quote_text)
            or not re.search(r'(?:100\s*분의\s*50|50\s*%)', quote_text)
            or not all(marker in visible_context for marker in (
                '가정', '보수월액', '지역보험료', '장기요양 포함',
                '10원 미만 버림', '보수 외 소득', '실제 고지', '12개월 동일'))
            or not re.search(r'(?<!\d)12\s*개월', visible_context)):
        return set(), ['invalid_derived_calculation']

    # All amounts, including invented inputs, must actually be printed in the
    # same row/paragraph, expressed in won. Shared table captions cannot
    # substitute another row's hypothetical values.
    plain_row = text.replace(',', '')
    values = {
        salary, regional, health, long_term, total,
        item['monthly_gap_won'], item['twelve_month_gap_won'],
    }
    if any(not re.search(rf'(?<!\d){value}\s*원(?!\d)', plain_row) for value in values):
        return set(), ['invalid_derived_calculation']
    if not re.search(rf'보수월액[^.。\n]*?(?<!\d){salary}\s*원', plain_row):
        return set(), ['invalid_derived_calculation']
    if not re.search(rf'지역보험료[^.。\n]*?(?<!\d){regional}\s*원', plain_row):
        return set(), ['invalid_derived_calculation']
    return {str(x) for x in values} | {'12'}, []
