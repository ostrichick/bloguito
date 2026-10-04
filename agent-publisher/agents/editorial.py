"""Shared editorial contract. Deterministic checks are not semantic fact proof."""
import base64
import hashlib
import html
import json
import math
import re
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote

from config import CATEGORIES, KAKAO_MAP_JAVASCRIPT_KEY
from agents.temporal_validation import (KST, validate_availability, extract_evidence,
                                        extract_yes24_schedule, extract_ticketlink_bridge_schedule,
                                        validate_multi_event_schedule,
                                        validate_legacy_followup,
                                        validate_legacy_reference_period,
                                        validate_reference_period,
                                        validate_current_value_period)
from agents.search_intent import duplicate_posts
from agents.critical_facts import critical_fact_reasons
from agents.event_post_standard import overview_event_date_labels, validate_event_post_standard
from agents.policy_exceptions import get_policy_exception
from agents.reader_tools import validate_reader_tools
from agents.volatility import explicit_contract, lifecycle_reasons, temporal_contract_reasons

ROOT = Path(__file__).resolve().parents[1]
RENDERER_PROVENANCE_FILE = ROOT / 'data' / 'renderer_provenance.json'
REVIEWED_CONTENT_PROVENANCE_FILE = ROOT / 'data' / 'reviewed_content_provenance.json'


def policy():
    return json.loads((ROOT / 'editorial_policy.json').read_text(encoding='utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def policy_profile(bundle=None):
    """Return the reader-content policy profile that applies to one bundle."""
    bundle = bundle if isinstance(bundle, dict) else {}
    brief = bundle.get('brief') if isinstance(bundle.get('brief'), dict) else bundle
    temporal = bundle.get('temporal_source') if isinstance(bundle.get('temporal_source'), dict) else {}
    if (brief.get('event_post_standard_version') == 1
            or temporal.get('multi_event_schedule') is True):
        return 'event'
    return 'general'


def policy_document_names(bundle=None):
    """Policy documents relevant to semantic writing/review for this bundle."""
    specific = 'EVENT_POST_STANDARD.md' if policy_profile(bundle) == 'event' else 'GENERAL_POST_STANDARD.md'
    return ('EDITORIAL_SYSTEM.md', specific)


def _policy_document_text(name):
    return (ROOT.parent / 'docs' / name).read_text(encoding='utf-8')


def policy_instructions(bundle=None):
    """Load only the common policy plus the current post-type policy."""
    return '\n\n'.join(_policy_document_text(name) for name in policy_document_names(bundle))


def applicable_policy_rules(bundle=None):
    """Select only machine rules that can affect this bundle's semantic approval.

    Image-generation settings, model preferences and exceptions for unrelated
    posts intentionally do not invalidate an otherwise identical text review.
    Deterministic freshness gates continue to read the live full policy directly.
    """
    rules = policy()
    selected = {
        key: rules[key]
        for key in ('version', 'min_remaining_days', 'review_checks', 'blocked_patterns')
        if key in rules
    }
    bundle = bundle if isinstance(bundle, dict) else {}
    brief = bundle.get('brief') if isinstance(bundle.get('brief'), dict) else bundle
    brief_id = brief.get('id') if isinstance(brief, dict) else None
    dated = get_policy_exception('dated_post', brief_id, on_date=datetime.now(KST).date())
    if dated is not None:
        selected['dated_post_exception'] = {brief_id: dated}
    legacy = get_policy_exception('legacy_procedure', brief_id)
    if legacy is not None:
        selected['legacy_welfare_procedural_exception'] = {brief_id: legacy}
    volatility_contract = explicit_contract(brief)
    if volatility_contract is not None:
        selected['volatility_contract'] = volatility_contract
    temporal = bundle.get('temporal_source') if isinstance(bundle.get('temporal_source'), dict) else {}
    if temporal.get('current_value_period') is not None:
        selected['current_value_period_contract_version'] = 1
    return selected


def policy_fingerprint(bundle=None):
    documents = {
        name: _policy_document_text(name)
        for name in policy_document_names(bundle)
    }
    return digest({
        'profile': policy_profile(bundle),
        'rules': applicable_policy_rules(bundle),
        'instructions': documents,
        'contract_version': 2,
    })


def normalized(text):
    return ' '.join(text.split())


def supported_counts(text, quote_text, candidates):
    """Only positive integer item counts inside an explicit quoted upper bound.

    Units, applicability and exceptions still require semantic review. Never infer money/dates.
    """
    result = set()
    bounds = re.findall(r'(\d+)\s*개\s*(미만|이하)', quote_text)
    for number in candidates:
        if not number.isdigit() or int(number) < 1:
            continue
        occurrences = list(re.finditer(r'(?<![\d.])'+re.escape(number)+r'(?![\d.])', text))
        if not occurrences or not all(re.match(r'\s*개', text[m.end():]) for m in occurrences):
            continue
        if any(int(number) < int(limit) if relation == '미만' else int(number) <= int(limit) for limit, relation in bounds):
            result.add(number)
    return result


def dated_post_exception(brief, today):
    """A narrowly scoped, expiring exception for an authorized existing post."""
    exception = get_policy_exception('dated_post', brief.get('id'), on_date=today) or {}
    try:
        if exception.get('official_urls'):
            required_urls = exception['official_urls']
        else:
            required_urls = [exception['official_url']]
            if exception.get('required_attachment_url'):
                required_urls.append(exception['required_attachment_url'])
        return bool(exception and brief.get('content_type') == 'dated'
                    and brief.get('existing_post_id') == exception['existing_post_id']
                    and brief.get('useful_until') == exception['useful_until']
                    and brief.get('official_urls') == required_urls
                    and today <= date.fromisoformat(exception['useful_until']))
    except (TypeError, ValueError, KeyError):
        return False


def legacy_85_welfare_navigation_exception(brief):
    """Permit only the user-approved, exact existing #85 timeless MENU guide.

    No new welfare post, different ID, date, title/question, URL substitution or
    generic evergreen declaration can inherit this exception. Full source,
    semantic and preservation validation remains mandatory in validate_bundle.
    """
    if not isinstance(brief, dict):
        return False
    exception = get_policy_exception('legacy_procedure', brief.get('id'))
    if not isinstance(exception, dict):
        return False
    return (type(brief.get('existing_post_id')) is int
            and brief['existing_post_id'] == exception.get('existing_post_id') == 85
            and all(brief.get(key) == exception.get(key) for key in (
                'category_key', 'content_type', 'entity', 'question',
                'required_title_terms', 'official_urls', 'evergreen_reason'))
            and brief.get('useful_until') is None)


def legacy_85_welfare_navigation_reasons(brief, sources, plan):
    """Fail closed before model review for the sole existing welfare menu guide.

    Lock reader-facing menu targets and preserved service/checklist structure;
    historical or future outages and operational availability do NOT turn this
    guide into a validated live welfare application route.
    """
    if not legacy_85_welfare_navigation_exception(brief):
        return ['legacy_85_welfare_exception_scope_invalid']
    cfg = get_policy_exception('legacy_procedure', brief['id'])
    if cfg is None:
        return ['legacy_85_welfare_exception_scope_invalid']
    reasons = []
    if (plan.get('title') != cfg['title']
            or plan.get('official_navigation') != cfg['official_navigation']
            or any(s.get('actions') for s in sources)):
        reasons.append('legacy_85_navigation_or_action_contract_invalid')

    if ([s.get('url') for s in sources] != cfg['official_urls']
            or any(s.get('source_type') != 'official' for s in sources)):
        reasons.append('legacy_85_official_source_scope_invalid')
    else:
        by_url = {s['url']: s.get('text', '') for s in sources}
        required = {
            cfg['official_urls'][0]: (
                '나의 혜택 | 혜택알리미 | 정부24', '로그인이 필요한 메뉴입니다.'),
            cfg['official_urls'][1]: (
                '맞춤형급여안내(복지멤버십)', '이용 방법',
                '복지급여 신청', '서비스 신청 현황'),
            cfg['official_urls'][2]: (
                '받을 가능성이 있는', '실제 조사 결과',
                '읍면동 주민센터'),
            cfg['official_urls'][3]: (
                '보조금24', '2022.12.16'),
        }
        if any(any(phrase not in by_url[url] for phrase in phrases)
               for url, phrases in required.items()):
            reasons.append('legacy_85_official_role_evidence_missing')

    sections = plan.get('sections')
    tables = [section.get('table') for section in sections
              if section.get('table')] if isinstance(sections, list) else []
    if (len(tables) != 2
            or any(len(table.get('headers', [])) != 3 for table in tables)
            or [[row['cells'][0] for row in table.get('rows', [])]
                for table in tables] != [
                    cfg['service_rows'], cfg['checklist_rows']]):
        reasons.append('legacy_85_original_tables_not_preserved')

    # These are required reader tasks, not claims of any individual's benefit.
    blocks = ([plan.get('lead', {}).get('text', '')]
              + [block.get('text', '') for section in (sections or [])
                 for block in section.get('paragraphs', [])]
              + [faq.get('answer', {}).get('text', '') for faq in plan.get('faq', [])])
    visible = ' '.join([plan.get('title', ''), *blocks,
                        *[cell for table in tables for row in table.get('rows', [])
                          for cell in row.get('cells', [])]])
    if not all(phrase in visible for phrase in (
            '과거', '보조금24', '혜택알리미', '로그인',
            '실제 가입 양식', '개별', '조사', '주민센터',
            '사업명', '담당 기관', '공고 링크', '대상 조건',
            '마감 날짜와 시각', '준비서류', '제출처',
            '문의한 날짜', '제출 완료 여부', '접수번호')):
        reasons.append('legacy_85_original_explanations_or_fallback_missing')
    # No time-window announcements in an evergreen guide. The 2026-09-27/30
    # outage is separately verified but has under 30 days of remaining value.
    # A text/source-only exception cannot make that event a permanent deadline.
    if (re.search(r'(?<!\d)20\d{2}\s*(?:년|[./-])', visible)
            or re.search(r'(?<!\d)\d{1,2}\s*월\s*\d{1,2}\s*일', visible)
            or re.search(r'(?:로그인|서비스|전송)\s*(?:중단|점검)', visible)
            or re.search(r'현재\s*(?:신청|접수|가입)\s*(?:가능|중)|'
                         r'언제든\s*(?:신청|접수|가입)\s*가능|'
                         r'(?:누구나|모두)\s*(?:신청|수급|지원)\s*가능|'
                         r'(?:급여|지원)\s*(?:확정|보장)', visible)):
        reasons.append('legacy_85_time_or_availability_claim_not_allowed')

    return sorted(set(reasons))


def topic_reasons(brief, today=None):
    if not isinstance(brief, dict):
        return ['malformed_topic']
    today = today or datetime.now(KST).date()
    reasons = list(lifecycle_reasons(brief))
    required = ('entity', 'primary_keyword', 'question', 'angle', 'official_urls', 'required_title_terms', 'reader_questions')
    if not all(brief.get(k) for k in required):
        reasons.append('topic_incomplete')
    try:
        if not brief.get('approved') or not date.fromisoformat(brief['reviewed_at']) <= today <= date.fromisoformat(brief['review_until']):
            reasons.append('topic_not_currently_approved')
        if brief.get('content_type') == 'evergreen':
            if brief.get('useful_until') is not None or not brief.get('evergreen_reason'):
                reasons.append('evergreen_reason_missing_or_deadline_present')
            explicit_policy_current_welfare = (
                brief.get('category_key') == 'welfare'
                and brief.get('volatility') == 'policy-current'
                and 'requires_live_state' in brief
                and type(brief.get('requires_live_state')) is bool
            )
            if (brief.get('category_key') in {'events', 'concert', 'welfare'}
                    and not (brief.get('category_key') == 'welfare'
                             and (legacy_85_welfare_navigation_exception(brief)
                                  or explicit_policy_current_welfare))):
                reasons.append('dated_category_cannot_bypass_time_check')
        elif brief.get('content_type') == 'dated':
            if ((date.fromisoformat(brief['useful_until']) - today).days < policy()['min_remaining_days']
                    and not dated_post_exception(brief, today)):
                reasons.append('insufficient_useful_lifetime')
        else:
            reasons.append('content_type_missing')
    except (KeyError, ValueError, TypeError):
        reasons.append('invalid_topic_dates')
    urls = brief.get('official_urls', [])
    if not isinstance(urls, list) or any(urlparse(u).scheme != 'https' or not urlparse(u).hostname or urlparse(u).username for u in urls):
        reasons.append('invalid_official_urls')
    reference_urls = brief.get('reference_urls', [])
    if (not isinstance(reference_urls, list)
            or any(urlparse(u).scheme != 'https' or not urlparse(u).hostname or urlparse(u).username
                   for u in reference_urls)
            or set(urls) & set(reference_urls)):
        reasons.append('invalid_reference_urls')
    return reasons


def fresh(value, now, hours):
    try:
        stamp = datetime.fromisoformat(value)
        return stamp.tzinfo is not None and 0 <= (now-stamp).total_seconds() <= hours*3600
    except (ValueError, TypeError):
        return False


def all_blocks(plan):
    return [plan['lead'],
            *[b for s in plan['sections'] for b in s['paragraphs']],
            *[{'text': fact['value'], 'evidence': fact['evidence'],
               'answers': fact.get('answers', []), 'calculations': fact.get('calculations', [])}
              for s in plan['sections'] for fact in s.get('facts', [])],
            *[{'text': ' '.join(row['cells']), 'evidence': row['evidence'],
               'answers': row.get('answers', []), 'calculations': row.get('calculations', [])}
              for s in plan['sections'] for row in (s.get('table') or {}).get('rows', [])],
            *[{'text': f"{s['location']['venue']} {s['location']['address']}",
               'evidence': s['location']['evidence'], 'answers': []}
              for s in plan['sections'] if s.get('location')],
            *[f['answer'] for f in plan.get('faq', [])]]


def supported_currency_sums(text, quote_text, calculations):
    """Allow only narrowly defined derived values whose inputs are in evidence.

    Supported operations are reader-useful KRW sums, exact thousand-won to won
    unit conversions, and a scheduled end time derived from an explicit Korean
    start time plus an official running time.
    A pension projection is also allowed when it is bound to a cited official
    monthly amount and cited official early/delayed percentage, and only shows
    deterministic cumulative totals at explicitly labelled fixed horizons.
    Other rates, averages and arbitrary date math remain rejected.
    """
    if calculations in (None, []):
        return set(), []
    if not isinstance(calculations, list) or not 1 <= len(calculations) <= 8:
        return set(), ['invalid_derived_calculation']

    numbers = lambda value: set(re.findall(r'\d+(?:[.,]\d+)*', value.replace(',', '')))
    quoted_numbers = numbers(quote_text)
    visible_numbers = numbers(text)
    supported = set()
    errors = []
    plain_text = text.replace(',', '')
    for item in calculations:
        if not isinstance(item, dict):
            errors.append('invalid_derived_calculation')
            continue
        if item.get('operation') == 'thousand_won_to_won':
            if (set(item) != {'operation', 'source_thousand_won', 'result_won'}
                    or type(item.get('source_thousand_won')) is not int
                    or item['source_thousand_won'] <= 0
                    or type(item.get('result_won')) is not int
                    or item['result_won'] != item['source_thousand_won'] * 1000
                    or str(item['source_thousand_won']) not in quoted_numbers
                    or not re.search(r'천\s*원', quote_text)
                    or str(item['result_won']) not in visible_numbers
                    or not re.search(
                        r'(?<!\d)' + re.escape(str(item['result_won'])) + r'\s*원(?!\d)',
                        plain_text,
                    )):
                errors.append('invalid_derived_calculation')
                continue
            supported.add(str(item['result_won']))
            continue
        if item.get('operation') == 'illustrative_input':
            required_keys = {'operation', 'age', 'monthly_salary', 'employment_months'}
            if (set(item) != required_keys
                    or type(item.get('age')) is not int or not 15 <= item['age'] <= 100
                    or type(item.get('monthly_salary')) is not int
                    or not 100_000 <= item['monthly_salary'] <= 100_000_000
                    or item['monthly_salary'] % 10_000 != 0
                    or type(item.get('employment_months')) is not int
                    or not 1 <= item['employment_months'] <= 600):
                errors.append('invalid_derived_calculation')
                continue
            age = str(item['age'])
            salary_man = str(item['monthly_salary'] // 10_000)
            months = str(item['employment_months'])
            patterns = {
                age: r'(?<!\d)' + re.escape(age) + r'\s*세(?!\d)',
                salary_man: r'(?<!\d)' + re.escape(salary_man) + r'\s*만원(?!\d)',
                months: r'(?<!\d)' + re.escape(months) + r'\s*개월(?!\d)',
            }
            if any(value not in visible_numbers or not re.search(pattern, text)
                   for value, pattern in patterns.items()):
                errors.append('invalid_derived_calculation')
                continue
            supported.update(patterns)
            continue
        if item.get('operation') == 'days_to_months':
            if (set(item) != {'operation', 'days', 'months'}
                    or type(item.get('days')) is not int or not 30 <= item['days'] <= 365
                    or type(item.get('months')) is not int or not 1 <= item['months'] <= 12
                    or item['days'] % 30 != 0 or item['months'] != item['days'] // 30
                    or str(item['days']) not in quoted_numbers
                    or not re.search(r'(?<!\d)' + str(item['days']) + r'\s*일(?!\d)', text)
                    or not re.search(r'(?<!\d)' + str(item['months']) + r'\s*개월(?!\d)', text)):
                errors.append('invalid_derived_calculation')
                continue
            supported.add(str(item['months']))
            continue
        if item.get('operation') == 'pension_projection':
            required_keys = {
                'operation', 'unit', 'base_monthly', 'direction', 'change_percent',
                'start_offset_years', 'monthly_result', 'horizons',
            }
            if (set(item) != required_keys or item.get('unit') != '원'
                    or type(item.get('base_monthly')) is not int or item['base_monthly'] <= 0
                    or item.get('direction') not in {'decrease', 'none', 'increase'}
                    or type(item.get('change_percent')) is not int
                    or not 0 <= item['change_percent'] <= 100
                    or type(item.get('start_offset_years')) is not int
                    or not -5 <= item['start_offset_years'] <= 5
                    or type(item.get('monthly_result')) is not int or item['monthly_result'] <= 0
                    or not isinstance(item.get('horizons'), list)
                    or len(item['horizons']) > 4):
                errors.append('invalid_derived_calculation')
                continue

            base = item['base_monthly']
            direction = item['direction']
            change = item['change_percent']
            if direction == 'none':
                if change != 0 or item['start_offset_years'] != 0:
                    errors.append('invalid_derived_calculation')
                    continue
                expected_monthly = base
            else:
                if change <= 0:
                    errors.append('invalid_derived_calculation')
                    continue
                numerator = base * ((100 - change) if direction == 'decrease' else (100 + change))
                if numerator % 100:
                    errors.append('invalid_derived_calculation')
                    continue
                expected_monthly = numerator // 100
                if (str(change) not in quoted_numbers
                        or str(abs(item['start_offset_years'])) not in quoted_numbers):
                    errors.append('invalid_derived_calculation')
                    continue

            if str(base) not in quoted_numbers or item['monthly_result'] != expected_monthly:
                errors.append('invalid_derived_calculation')
                continue

            derived = set()
            monthly_visible = str(item['monthly_result']) in visible_numbers
            if monthly_visible:
                derived.add(str(item['monthly_result']))
            horizon_error = False
            for horizon in item['horizons']:
                if (not isinstance(horizon, dict)
                        or set(horizon) != {'years_after_normal', 'cumulative_result'}
                        or type(horizon.get('years_after_normal')) is not int
                        or not 1 <= horizon['years_after_normal'] <= 40
                        or type(horizon.get('cumulative_result')) is not int
                        or horizon['cumulative_result'] < 0):
                    horizon_error = True
                    break
                years_receiving = horizon['years_after_normal'] - item['start_offset_years']
                if years_receiving < 0:
                    horizon_error = True
                    break
                expected_total = item['monthly_result'] * years_receiving * 12
                if horizon['cumulative_result'] != expected_total:
                    horizon_error = True
                    break
                if not re.search(r'(?<!\d)' + str(horizon['years_after_normal']) + r'\s*년', text):
                    horizon_error = True
                    break
                derived.add(str(horizon['years_after_normal']))
                derived.add(str(horizon['cumulative_result']))
            if horizon_error:
                errors.append('invalid_derived_calculation')
                continue

            if any(value not in visible_numbers for value in derived):
                errors.append('invalid_derived_calculation')
                continue
            won_values = {
                *([str(item['monthly_result'])] if monthly_visible else []),
                *[str(horizon['cumulative_result']) for horizon in item['horizons']],
            }
            if any(not re.search(r'(?<!\d)' + re.escape(value) + r'\s*원', plain_text)
                   for value in won_values):
                errors.append('invalid_derived_calculation')
                continue
            supported.update(derived)
            continue
        if item.get('operation') == 'monthly_from_total_days':
            if (set(item) != {'operation', 'total', 'days', 'monthly'}
                    or type(item.get('total')) is not int or item['total'] <= 0
                    or type(item.get('days')) is not int or not 30 <= item['days'] <= 365
                    or type(item.get('monthly')) is not int or item['monthly'] <= 0
                    or item['total'] % item['days'] != 0
                    or item['monthly'] != (item['total'] // item['days']) * 30
                    or str(item['total']) not in quoted_numbers
                    or str(item['days']) not in quoted_numbers
                    or str(item['monthly']) not in visible_numbers
                    or not re.search(r'(?<!\d)' + str(item['monthly']) + r'\s*원(?!\d)', plain_text)):
                errors.append('invalid_derived_calculation')
                continue
            supported.add(str(item['monthly']))
            continue
        if item.get('operation') == 'add_duration':
            if (set(item) != {'operation', 'unit', 'start', 'duration', 'result'}
                    or item.get('unit') != '분'
                    or type(item.get('duration')) is not int
                    or not 1 <= item['duration'] <= 24 * 60
                    or not isinstance(item.get('start'), str)
                    or not isinstance(item.get('result'), str)):
                errors.append('invalid_derived_calculation')
                continue

            clock = re.compile(r'^(오전|오후)\s*(\d{1,2})시\s*(\d{1,2})분$')
            start_match = clock.fullmatch(item['start'])
            result_match = clock.fullmatch(item['result'])
            if not start_match or not result_match:
                errors.append('invalid_derived_calculation')
                continue

            def minute_of_day(match):
                period, hour, minute = match.groups()
                hour, minute = int(hour), int(minute)
                if not 1 <= hour <= 12 or not 0 <= minute <= 59:
                    raise ValueError('invalid_clock')
                return (hour % 12 + (12 if period == '오후' else 0)) * 60 + minute

            try:
                expected = (minute_of_day(start_match) + item['duration']) % (24 * 60)
                actual = minute_of_day(result_match)
            except ValueError:
                errors.append('invalid_derived_calculation')
                continue
            if (expected != actual
                    or item['start'] not in quote_text
                    or not re.search(r'(?<!\d)' + str(item['duration']) + r'\s*분', quote_text)
                    or item['result'] not in text):
                errors.append('invalid_derived_calculation')
                continue
            supported.update(numbers(item['result']))
            continue

        if (set(item) != {'operation', 'unit', 'operands', 'result'}
                or item.get('operation') != 'sum'
                or item.get('unit') != '원'):
            errors.append('invalid_derived_calculation')
            continue
        operands, result = item.get('operands'), item.get('result')
        if (not isinstance(operands, list) or not 2 <= len(operands) <= 8
                or any(type(value) is not int or value <= 0 for value in operands)
                or type(result) is not int or result <= 0
                or sum(operands) != result
                or any(str(value) not in quoted_numbers for value in operands)):
            errors.append('invalid_derived_calculation')
            continue
        result_text = str(result)
        if (result_text not in visible_numbers
                or not re.search(r'(?<!\d)' + re.escape(result_text) + r'\s*원', plain_text)):
            errors.append('invalid_derived_calculation')
            continue
        supported.add(result_text)
    return supported, errors


def reader_visible_strings(plan, sources):
    """Collect text that can be rendered to readers; source snapshots stay untouched."""
    values = [plan.get('title', '')]
    lead = plan.get('lead') or {}
    values.append(lead.get('text', ''))
    for section in plan.get('sections', []):
        values.append(section.get('heading', ''))
        values.extend((p or {}).get('text', '') for p in section.get('paragraphs', []))
        for fact in section.get('facts', []):
            values.extend((fact.get('label', ''), fact.get('value', '')))
        image = section.get('image') or {}
        values.extend((image.get('alt', ''), image.get('caption', '')))
        location = section.get('location') or {}
        values.extend((location.get('venue', ''), location.get('address', '')))
        table = section.get('table') or {}
        values.append(table.get('caption', ''))
        values.extend(table.get('headers', []))
        for row in table.get('rows', []):
            values.extend(row.get('cells', []))
    for faq in plan.get('faq', []):
        values.append(faq.get('question', ''))
        values.append((faq.get('answer') or {}).get('text', ''))
    for item in plan.get('related_posts', []):
        values.append(item.get('label', ''))
    for item in plan.get('reader_tools', []):
        if isinstance(item, dict):
            values.append(item.get('title', ''))
    for item in plan.get('official_navigation', []):
        values.extend((item.get('label', ''), item.get('note', '')))
    for source in sources:
        for action in source.get('actions', []):
            values.append(action.get('label', ''))
        values.append(source.get('citation_label') or source.get('title', ''))
    return [value for value in values if isinstance(value, str)]


def validated_section_assets(plan, sources):
    """Validate optional event image and location blocks bound to reviewed sources."""
    source_map = {source.get('id'): source for source in sources if isinstance(source, dict)}
    assets = []
    for section in plan.get('sections', []):
        image = section.get('image')
        if image is not None:
            if (not isinstance(image, dict)
                    or set(image) - {'url', 'alt', 'caption', 'source_id', 'year', 'rights', 'rights_url'}
                    or not {'url', 'alt', 'caption', 'source_id'}.issubset(image)):
                raise ValueError('invalid_section_image')
            url, alt, caption, source_id = (
                image.get('url'), image.get('alt'), image.get('caption'), image.get('source_id'))
            parsed = urlparse(url) if isinstance(url, str) else None
            source = source_map.get(source_id)
            if (not parsed or parsed.scheme != 'https' or not parsed.hostname
                    or parsed.username or parsed.password or parsed.fragment
                    or re.search(r'[<>\r\n]', url)
                    or not isinstance(alt, str) or not 4 <= len(alt.strip()) <= 200
                    or re.search(r'[<>\r\n]', alt)
                    or not isinstance(caption, str) or not 2 <= len(caption.strip()) <= 180
                    or re.search(r'[<>\r\n]', caption)
                    or (image.get('rights') is not None
                        and image.get('rights') not in {
                            'generated_original', 'site_owned', 'open_license', 'permission_granted', 'source_attributed'})
                    or (image.get('rights_url') is not None and (
                        not isinstance(image.get('rights_url'), str)
                        or not image['rights_url'].startswith('https://')
                        or re.search(r'[<>\r\n]', image['rights_url'])))
                    or (image.get('year') is not None
                        and (type(image.get('year')) is not int or not 2000 <= image['year'] <= 2100))
                    or not source or source.get('source_type') != 'official'):
                raise ValueError('invalid_section_image')

        location = section.get('location')
        if location is not None:
            if (not isinstance(location, dict)
                    or set(location) - {'venue', 'address', 'query', 'evidence', 'latitude', 'longitude'}
                    or not {'venue', 'address', 'query', 'evidence'}.issubset(location)):
                raise ValueError('invalid_section_location')
            venue, address, query, evidence = (
                location.get('venue'), location.get('address'), location.get('query'), location.get('evidence'))
            latitude, longitude = location.get('latitude'), location.get('longitude')
            if (not all(isinstance(value, str) for value in (venue, address, query))
                    or not 2 <= len(venue.strip()) <= 120
                    or (address.strip() and not 4 <= len(address.strip()) <= 180)
                    or not 2 <= len(query.strip()) <= 180
                    or re.search(r'[<>\r\n]', venue + address + query)
                    or ((latitude is None) != (longitude is None))
                    or (latitude is not None and (
                        type(latitude) not in {int, float} or type(longitude) not in {int, float}
                        or not math.isfinite(float(latitude)) or not math.isfinite(float(longitude))
                        or not -90 <= float(latitude) <= 90 or not -180 <= float(longitude) <= 180))
                    or not isinstance(evidence, list) or not 1 <= len(evidence) <= 4):
                raise ValueError('invalid_section_location')
            for item in evidence:
                if (not isinstance(item, dict) or set(item) != {'source_id', 'quote'}
                        or item.get('source_id') not in source_map
                        or source_map[item['source_id']].get('source_type') != 'official'
                        or not isinstance(item.get('quote'), str)
                        or len(normalized(item['quote'])) < 8
                        or normalized(item['quote']) not in normalized(source_map[item['source_id']].get('text', ''))):
                    raise ValueError('invalid_section_location')
        if image or location:
            assets.append({'image': image, 'location': location})
    return assets


def actionable_links(sources):
    """Return explicitly verified action destinations; evidence URLs are never CTAs."""
    links = []
    for source in sources:
        if source.get('actions') and source.get('source_type') != 'official':
            raise ValueError('action_source_must_be_official')
        for action in source.get('actions', []):
            if not isinstance(action, dict):
                raise ValueError('invalid_action_link')
            label, url, kind = (action.get(key) for key in ('label', 'url', 'kind'))
            if (not isinstance(label, str) or not 4 <= len(label.strip()) <= 60
                    or re.search(r'[<>\r\n]', label)
                    or re.search(r'소개|홍보|보도자료|기사|사업\s*영역', label)
                    or kind not in {'booking', 'install', 'lookup', 'apply', 'purchase'}
                    or not isinstance(url, str)):
                raise ValueError('invalid_action_link')
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                    or parsed.password or parsed.fragment or any(ch.isspace() for ch in url)):
                raise ValueError('invalid_action_link')
            if kind == 'install' and not (
                (parsed.hostname == 'play.google.com' and parsed.path == '/store/apps/details' and re.search(r'(?:^|&)id=[a-zA-Z0-9._]+(?:&|$)', parsed.query))
                or (parsed.hostname == 'apps.apple.com' and re.search(r'/app/(?:[^/]+/)?id\d+$', parsed.path))
            ):
                raise ValueError('invalid_action_link')
            if any(other['url'] == url for other in links):
                raise ValueError('duplicate_action_link')
            links.append({'label': label.strip(), 'url': url, 'kind': kind})
    # Region-specific event booking can legitimately require more than four
    # distinct official destinations (for example a six-city tour). Keep a
    # finite cap so the CTA area cannot turn into an unbounded link farm.
    if len(links) > 8:
        raise ValueError('too_many_action_links')
    return links


def validated_section_action_links(plan, sources):
    """Bind optional section CTA URLs to already-reviewed official source actions."""
    actions_by_url = {action['url']: action for action in actionable_links(sources)}
    scoped = []
    seen = set()
    for section in plan.get('sections', []):
        references = section.get('actions', [])
        if not isinstance(references, list) or len(references) > 2:
            raise ValueError('invalid_section_actions')
        section_actions = []
        for url in references:
            if (not isinstance(url, str) or url not in actions_by_url or url in seen):
                raise ValueError('invalid_section_actions')
            seen.add(url)
            section_actions.append(actions_by_url[url])
        scoped.append(section_actions)
    return scoped, seen


def validated_section_official_links(plan, sources):
    """Bind section-level informational links only to reviewed official sources.

    These links intentionally remain separate from ``actions``: an event detail
    page can be useful to readers without pretending to be a booking/apply
    destination.
    """
    official_by_url = {
        source['url']: source
        for source in sources
        if isinstance(source, dict) and source.get('source_type') == 'official'
        and isinstance(source.get('url'), str)
    }
    scoped = []
    seen = set()
    for section in plan.get('sections', []):
        entries = section.get('official_links', [])
        if not isinstance(entries, list) or len(entries) > 2:
            raise ValueError('invalid_section_official_links')
        section_links = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {'label', 'url'}:
                raise ValueError('invalid_section_official_links')
            label = entry.get('label')
            url = entry.get('url')
            if (not isinstance(label, str) or not 6 <= len(label.strip()) <= 80
                    or re.search(r'[<>\r\n]', label)
                    or not isinstance(url, str) or url not in official_by_url
                    or url in seen):
                raise ValueError('invalid_section_official_links')
            normalized_label = normalized(label).casefold()
            if normalized_label in {'공식 홈페이지', '공식 사이트', '홈페이지', '공식 페이지'}:
                raise ValueError('invalid_section_official_links')
            seen.add(url)
            section_links.append({'label': label.strip(), 'url': url})
        scoped.append(section_links)
    return scoped, seen


def official_navigation_links(plan, sources):
    """Validate labeled official-site/menu navigation, never direct-service CTAs."""
    entries = plan.get('official_navigation', [])
    if not isinstance(entries, list) or len(entries) > 2:
        raise ValueError('invalid_official_navigation')
    official = {s['url'] for s in sources if s.get('source_type') == 'official'}
    actions = {a['url'] for a in actionable_links(sources)}
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'label', 'url', 'note'}:
            raise ValueError('invalid_official_navigation')
        label, url, note = (entry[key] for key in ('label', 'url', 'note'))
        if (not isinstance(url, str) or url not in official or url in actions or url in seen
                or not isinstance(label, str) or not 8 <= len(label.strip()) <= 80
                or not isinstance(note, str) or not 16 <= len(note.strip()) <= 220
                or re.search(r'[<>\r\n]', label + note)
                or re.search(r'직접\s*(?:조회|신청)|바로\s*(?:조회|신청)|원클릭\s*(?:조회|신청)', label)
                or not re.search(r'메뉴|로그인|진입|첫\s*화면', note)):
            raise ValueError('invalid_official_navigation')
        seen.add(url)
    return entries


VALIDATION_SCOPES = frozenset({'content', 'source', 'site', 'review'})


def validate_bundle(bundle, inventory, now=None, require_review=True, scopes=None):
    now = now or datetime.now(KST)
    rules = policy()
    scopes = set(VALIDATION_SCOPES if scopes is None else scopes)
    unknown_scopes = scopes - VALIDATION_SCOPES
    if unknown_scopes:
        raise ValueError('unknown_validation_scope:' + ','.join(sorted(unknown_scopes)))
    if not require_review:
        scopes.discard('review')
    reasons = []
    details = []
    try:
        brief, sources, plan = bundle['brief'], bundle['sources'], bundle['plan']
        if 'content' in scopes:
            reasons.extend(topic_reasons(brief, now.date()))
            reasons.extend(temporal_contract_reasons(bundle))
            reasons.extend(validate_current_value_period(
                brief, sources, bundle.get('temporal_source', {}), now))
            reasons.extend(validate_reader_tools(plan, sources, brief))
            if any('·' in value for value in reader_visible_strings(plan, sources)):
                reasons.append('reader_middle_dot_disallowed')
                details.append('독자 문구의 가운데점 문자를 쉼표 또는 자연스러운 연결 표현으로 바꿀 것')
            try:
                validated_lead_image(plan)
            except ValueError:
                reasons.append('invalid_lead_image')
        related_post_ids = {
            item.get('post_id')
            for item in plan.get('related_posts', [])
            if isinstance(item, dict) and type(item.get('post_id')) is int and item.get('post_id') > 0
        }
        if 'site' in scopes:
            if inventory.get('checked_on') != now.date().isoformat() or not isinstance(inventory.get('posts'), list):
                reasons.append('fresh_inventory_required')
            elif duplicate_posts(brief, inventory['posts'], related_post_ids=related_post_ids):
                reasons.append('duplicate_topic')
        if 'source' in scopes and (not sources or len({s['id'] for s in sources}) != len(sources)):
            reasons.append('sources_missing_or_duplicate_ids')
        source_map = {s['id']: s for s in sources}
        official_urls = set(brief['official_urls'])
        reference_urls = set(brief.get('reference_urls', []))
        if 'source' in scopes:
            for s in sources:
                source_type = s.get('source_type')
                if not ((source_type == 'official' and s['url'] in official_urls)
                        or (source_type == 'reference' and s['url'] in reference_urls)):
                    reasons.append('source_not_declared_brief_url')
                citation_label = s.get('citation_label')
                if (citation_label is not None
                        and (not isinstance(citation_label, str)
                             or not 4 <= len(citation_label.strip()) <= 100
                             or re.search(r'[<>\r\n]', citation_label))):
                    reasons.append('invalid_source_citation_label')
                citation_url = s.get('citation_url')
                if citation_url is not None:
                    parsed_citation = urlparse(citation_url)
                    if (not isinstance(citation_url, str)
                            or parsed_citation.scheme != 'https'
                            or not parsed_citation.hostname
                            or re.search(r'[<>\r\n]', citation_url)):
                        reasons.append('invalid_source_citation_url')
                if s['sha256'] != hashlib.sha256(s['text'].encode()).hexdigest():
                    reasons.append('source_hash_mismatch')
                if not fresh(s['fetched_at'], now, rules['source_max_age_hours']):
                    reasons.append('source_stale')
            try:
                actionable_links(sources)
            except (TypeError, ValueError):
                reasons.append('invalid_action_links')
            try:
                official_navigation_links(plan, sources)
            except (KeyError, TypeError, ValueError):
                reasons.append('invalid_official_navigation')
        if 'content' in scopes:
            try:
                validated_section_assets(plan, sources)
            except (KeyError, TypeError, ValueError):
                reasons.append('invalid_section_assets')
            try:
                validated_section_action_links(plan, sources)
            except (KeyError, TypeError, ValueError):
                reasons.append('invalid_section_actions')
            try:
                validated_section_official_links(plan, sources)
            except (KeyError, TypeError, ValueError):
                reasons.append('invalid_section_official_links')
            reasons.extend(validate_event_post_standard(bundle))
        if 'content' in scopes and legacy_85_welfare_navigation_exception(brief):
            reasons.extend(legacy_85_welfare_navigation_reasons(brief, sources, plan))
        related = plan.get('related_posts', [])
        if 'content' in scopes and (not isinstance(related, list) or len(related) > 2):
            reasons.append('invalid_related_post_links')
        elif isinstance(related, list):
            seen_related = set()
            for item in related:
                if not isinstance(item, dict) or set(item) != {'post_id', 'label', 'url'}:
                    if 'content' in scopes:
                        reasons.append('invalid_related_post_links')
                    continue
                target, label, url = (item[key] for key in ('post_id', 'label', 'url'))
                structurally_invalid = (
                    type(target) is not int or target <= 0 or target in seen_related
                    or target == brief.get('existing_post_id') or not isinstance(label, str)
                    or not 4 <= len(label.strip()) <= 60 or re.search(r'[<>\r\n]', label)
                    or not isinstance(url, str) or url != f'https://lifeinfo24.org/?p={target}'
                )
                missing_live_target = (
                    'site' in scopes and not structurally_invalid
                    and not any(row.get('ID') == target and row.get('post_status') == 'publish'
                                for row in inventory.get('posts', []))
                )
                if (('content' in scopes and structurally_invalid) or missing_live_target):
                    reasons.append('invalid_related_post_links')
                seen_related.add(target)
        if 'content' in scopes and brief.get('content_type') == 'dated':
            temporal = bundle.get('temporal_source', {})
            available = [field for s in sources for field in extract_evidence(s['text'], s['url'])]
            seasonal_exception = dated_post_exception(brief, now.date())
            if seasonal_exception:
                exception = get_policy_exception('dated_post', brief['id'], on_date=now.date())
                if exception is None:
                    reasons.append('specific_holiday_window_official_evidence_missing')
                    exception = {}
                if exception.get('official_urls'):
                    required_urls = exception['official_urls']
                else:
                    required_urls = [exception['official_url']]
                    if exception.get('required_attachment_url'):
                        required_urls.append(exception['required_attachment_url'])
                event_source = next((source for source in sources
                                     if source['url'] == exception.get('source_event_url', required_urls[0])), None)
                if ([source['url'] for source in sources if source.get('source_type') == 'official'] != required_urls
                        or not event_source
                        or exception['source_event_phrase'] not in event_source['text']
                        or (exception.get('source_date_phrase')
                            and exception['source_date_phrase'] not in event_source['text'])):
                    reasons.append('specific_holiday_window_official_evidence_missing')
                if exception.get('required_attachment_url'):
                    detailed = sources[1]['text'] if len(sources) > 1 else ''
                    schedule_rows = sum(len(section['table']['rows']) for section in plan['sections']
                                        if section.get('kind') == 'schedule' and section.get('table'))
                    if (not all(place in detailed for place in
                                ('하남드림휴게소', '익산미륵사지휴게소', '영광 상사화'))
                            or schedule_rows < 22):
                        reasons.append('specific_holiday_branch_details_missing')
            listing_only = temporal.get('schedule_listing_only') is True
            multi_event = temporal.get('multi_event_schedule') is True
            if temporal.get('reference_period') is None and temporal.get('evidence') != available:
                reasons.append('temporal_source_not_bound')
            if multi_event:
                reasons.extend(validate_multi_event_schedule(
                    brief, sources, temporal, plan, now,
                    minimum_days=0 if seasonal_exception else rules['min_remaining_days']))
            elif listing_only:
                # For an event schedule and booking *destinations*, evidence of an
                # actual sale deadline is not available from the public listing.
                # This mode cannot certify ticket availability or sale periods.
                listing_url = temporal.get('listing_source_url')
                listing_source = next((s for s in sources if s['url'] == listing_url), None)
                host = urlparse(listing_url).hostname if listing_url else None
                generic_listing = (
                    host in {'m.ticket.yes24.com', 'www.ticketlink.co.kr'}
                )
                if (brief.get('category_key') != 'concert' or temporal.get('requires_sale') is not False
                        or not listing_source
                        or not generic_listing):
                    reasons.append('schedule_listing_provenance_missing')
                else:
                    if host == 'm.ticket.yes24.com':
                        rows = extract_yes24_schedule(listing_source['text'], brief['entity'].split()[0])
                    elif host == 'www.ticketlink.co.kr':
                        rows = extract_ticketlink_bridge_schedule(listing_source['text'], brief['entity'].split()[0])
                    schedule_tables = [
                        (table.get('headers', []), row.get('cells', []))
                        for section in plan['sections']
                        for table in [section.get('table') or {}]
                        for row in table.get('rows', [])
                    ]
                    if host == 'www.ticketlink.co.kr':
                        # Ticketlink's bridge uses a broad province label (for
                        # example 경기) while the product/venue names identify
                        # the reader-useful city (for example 평택). Bind the
                        # schedule to the exact date+venue pair instead of
                        # forcing those two different geography levels to match.
                        listing_rows_in_table = all(
                            any(item['date'] in cells
                                and item['venue'] in cells
                                for _, cells in schedule_tables)
                            for item in rows)
                    else:
                        def matches_schedule_row(headers, cells, item):
                            header_sets = {
                                'region': {'지역'},
                                'date': {'날짜', '공연 날짜', '공연일'},
                                'venue': {'공연장', '장소'},
                            }
                            indexes = {}
                            for key, labels in header_sets.items():
                                indexes[key] = next(
                                    (i for i, header in enumerate(headers) if header in labels), None)
                                if indexes[key] is None or indexes[key] >= len(cells):
                                    return False
                            return (
                                cells[indexes['region']] == item['region']
                                and cells[indexes['date']] == item['date']
                                and cells[indexes['venue']] == item['venue']
                            )

                        listing_rows_in_table = all(
                            any(matches_schedule_row(headers, cells, item)
                                for headers, cells in schedule_tables)
                            for item in rows)
                    if (not rows or rows != temporal.get('listing_entries') or not listing_rows_in_table):
                        reasons.append('schedule_listing_not_bound')
                    elif max(date.fromisoformat(item['date'].replace('.', '-')) for item in rows) < now.date():
                        reasons.append('availability_not_verified')
                    elif (max(date.fromisoformat(item['date'].replace('.', '-')) for item in rows)
                          - now.date()).days < rules['min_remaining_days']:
                        reasons.append('source_deadline_too_close')
                    public_text = ' '.join([plan['lead']['text'], *[p['text'] for sec in plan['sections']
                                                                   for p in sec['paragraphs']],
                                            *[faq['answer']['text'] for faq in plan.get('faq', [])]])
                    if re.search(r'예매\s*중|판매\s*중|예매\s*기간|판매\s*기간|매진|품절|'
                                 r'잔여\s*좌석|남은\s*좌석|현재\s*예매\s*가능|바로\s*예매', public_text):
                        reasons.append('sale_status_claim_without_evidence')
            else:
                if brief.get('category_key') == 'concert' and (temporal.get('requires_sale') is not True or temporal.get('sale_source_url') not in brief['official_urls']):
                    reasons.append('concert_sale_evidence_required')
                if temporal.get('legacy_followup') is not None:
                    # Historical *existing* welfare posts may explain a closed
                    # period and a cited future application route. No open
                    # application or sale status is inferred from these dates.
                    reasons.extend(validate_legacy_followup(brief, sources, temporal, plan, now))
                elif temporal.get('legacy_reference_period') is not None:
                    # Existing 2026 pension information and the 2026-27 Mokpo
                    # flu season are information applicability periods, not
                    # evidence of an active application or universal supply.
                    reasons.extend(validate_legacy_reference_period(
                        brief, sources, temporal, plan, now,
                        minimum_days=rules['min_remaining_days']))
                elif temporal.get('reference_period') is not None:
                    reasons.extend(validate_reference_period(
                        brief, sources, temporal, plan, now,
                        minimum_days=rules['min_remaining_days']))
                elif not seasonal_exception:
                    if not available:
                        reasons.append('temporal_source_not_bound')
                    decision = validate_availability(temporal, now=now)
                    if decision['status'] != 'active':
                        reasons.append('availability_not_verified')
                    if decision.get('expires_at') and (datetime.fromisoformat(decision['expires_at']).date()-now.date()).days < rules['min_remaining_days']:
                        reasons.append('source_deadline_too_close')
        # Version-specific official policy evidence is separate from a fresh fetch and a valid quote.
        if 'content' in scopes:
            reasons.extend(critical_fact_reasons(brief, sources, plan))
            title = plan['title']
            if not all(normalized(t) in normalized(title) for t in brief['required_title_terms']):
                reasons.append('title_missing_entity_or_region')
            if not plan['sections'] or not all(s['heading'] and (s['paragraphs'] or s.get('table')) for s in plan['sections']):
                reasons.append('article_structure_incomplete')
        for section in plan['sections'] if 'content' in scopes else []:
            if section.get('kind') is not None and section['kind'] not in {
                    'overview', 'eligibility', 'comparison', 'procedure', 'exceptions', 'schedule', 'general'}:
                reasons.append('invalid_section_kind')
            facts = section.get('facts')
            if facts is not None and (
                    not isinstance(facts, list) or not 1 <= len(facts) <= 8
                    or any(not isinstance(fact, dict)
                           or set(fact) - {'label', 'value', 'evidence', 'answers', 'calculations'}
                           or not isinstance(fact.get('label'), str)
                           or not 1 <= len(fact['label'].strip()) <= 30
                           or not isinstance(fact.get('value'), str)
                           or not 1 <= len(fact['value'].strip()) <= 220
                           or not isinstance(fact.get('evidence'), list)
                           or not 1 <= len(fact['evidence']) <= 4
                           for fact in facts)):
                reasons.append('invalid_section_facts')
            table = section.get('table')
            if table is None:
                continue
            headers, rows = table.get('headers'), table.get('rows')
            mobile_title_index = next(
                (idx for idx, header in enumerate(headers or [])
                 if isinstance(header, str)
                 and any(token in header for token in ('행사', '축제'))),
                1 if isinstance(headers, list) and len(headers) > 1 else 0,
            )
            if (not isinstance(table.get('caption'), str) or not table['caption'].strip()
                    or table.get('mobile_cards', False) not in {True, False}
                    or not isinstance(headers, list) or not 2 <= len(headers) <= 6
                    or not isinstance(rows, list) or not 1 <= len(rows) <= 20
                    or any(not isinstance(h, str) or not 1 <= len(h.strip()) <= 60 for h in headers)
                    or any(not isinstance(row, dict) or not isinstance(row.get('cells'), list)
                           or len(row['cells']) != len(headers)
                           or any(not isinstance(cell, str) or len(cell.strip()) > 160
                                  for cell in row['cells'])
                           or not row['cells'][0].strip()
                           or (table.get('mobile_cards', False)
                               and (mobile_title_index >= len(row['cells'])
                                    or not row['cells'][mobile_title_index].strip()))
                           for row in rows)):
                reasons.append('invalid_information_table')
        blocks = all_blocks(plan) if 'content' in scopes else []
        answered = set()
        for block_index, b in enumerate(blocks):
            if not b['text'].strip() or not b['evidence']:
                reasons.append('paragraph_without_evidence')
            emphasis = b.get('emphasis')
            if emphasis is not None and (
                    not isinstance(emphasis, list) or not 1 <= len(emphasis) <= 5
                    or any(not isinstance(item, str) or not 2 <= len(item.strip()) <= 80
                           or item not in b['text'] for item in emphasis)
                    or len(emphasis) != len(set(emphasis))):
                reasons.append('invalid_inline_emphasis')
            evidence_text = []
            for e in b['evidence']:
                s = source_map[e['source_id']]
                if len(normalized(e['quote'])) < 8 or normalized(e['quote']) not in normalized(s['text']):
                    reasons.append('quote_not_in_source')
                evidence_text.append(e['quote'])
            numbers = lambda t: set(re.findall(r'\d+(?:[.,]\d+)*', t.replace(',', '')))
            unsupported = numbers(b['text']) - numbers(' '.join(evidence_text))
            unsupported -= supported_counts(b['text'], ' '.join(evidence_text), unsupported)
            unsupported -= supported_official_number_notations(
                b['text'], ' '.join(evidence_text), unsupported)
            derived_numbers, calculation_errors = supported_currency_sums(
                b['text'], ' '.join(evidence_text), b.get('calculations', []))
            unsupported -= derived_numbers
            reasons.extend(calculation_errors)
            if unsupported:
                reasons.append('number_without_evidence')
                details.append(f'block[{block_index}]의 수치 {sorted(unsupported)}는 연결된 인용에 없음. 해당 수치를 빼거나 실제 인용에 있는 범위 표현으로 수정할 것.')
            answered.update(b.get('answers', []))
        if 'content' in scopes:
            questions = {q['id'] for q in brief['reader_questions']}
            if not questions.issubset(answered) or not set(plan['lead'].get('answers', [])) & questions:
                reasons.append('reader_question_not_answered')
            if any(f['question_id'] not in questions or f['question_id'] not in f['answer'].get('answers', []) for f in plan.get('faq', [])):
                reasons.append('faq_answer_missing')
                details.append(f'FAQ question_id는 새 ID가 아니라 reader_questions의 ID {sorted(questions)} 중 하나여야 하며 answer.answers에도 같은 ID가 필요함.')
            table_labels = [label for section in plan['sections'] if section.get('table')
                            for label in [section['table']['caption'], *section['table']['headers']]]
            visible = ' '.join([title, *[s['heading'] for s in plan['sections']], *table_labels,
                                *[b['text'] for b in blocks], *[f['question'] for f in plan.get('faq', [])]])
            if any(re.search(p, visible) for p in rules['blocked_patterns']):
                reasons.append('reader_deflection_or_disclaimer')
        # Correction banners, previous-copy change logs and review metadata are
        # internal records. Keep legitimate source publication dates and rules.
        if 'content' in scopes:
            if re.search(r'이\s*(?:초안|원고)(?:에서는|은|와|를)|독립적인\s*검색\s*질문이\s*확인되지\s*않으면|(?:자료\s*검토|내용\s*재검토|최종\s*검토일|검토·수정)\s*[:：]|공식\s*출처\s*및\s*검토\s*기록|링크된\s*자료의\s*적용\s*시점과\s*실제\s*안내\s*화면을\s*확인|정정\s*안내|기존\s*수치의\s*정정|(?:기존|과거|종전)\s*(?:글|본문|게시물|공지|안내)[^.。\n]{0,130}(?:삭제|수정|정정|바로잡|폐기)', visible):
                reasons.append('internal_editorial_note_in_prose')
            if re.search(r'<[^>]+>|https?://', visible):
                reasons.append('raw_markup_or_url_in_prose')
        if 'review' in scopes:
            review = bundle.get('review', {})
            body = {k: bundle[k] for k in ('brief', 'sources', 'plan', 'temporal_source') if k in bundle}
            if review.get('digest') != digest(body) or review.get('policy_digest') != policy_fingerprint(bundle):
                reasons.append('review_not_bound_to_current_content')
            if not fresh(review.get('checked_at'), now, rules['review_max_age_hours']):
                reasons.append('review_stale')
            if any(review.get('checks', {}).get(k) is not True for k in rules['review_checks']) or review.get('issues') != []:
                reasons.append('semantic_review_failed')
    except (KeyError, TypeError, ValueError, AttributeError):
        reasons.append('malformed_editorial_bundle')
    return {'status': 'ready' if not reasons else 'needs_review', 'reasons': sorted(set(reasons)), 'details': details}


def validate_content(bundle, now=None):
    """Validate reader-visible claims/structure against the bound source snapshots."""
    now = now or datetime.now(KST)
    return validate_bundle(
        bundle,
        {'checked_on': now.date().isoformat(), 'posts': []},
        now=now,
        require_review=False,
        scopes={'content'},
    )


def validate_sources(bundle, now=None):
    """Validate source declarations, hashes, freshness and action/navigation metadata."""
    now = now or datetime.now(KST)
    return validate_bundle(
        bundle,
        {'checked_on': now.date().isoformat(), 'posts': []},
        now=now,
        require_review=False,
        scopes={'source'},
    )


def validate_site_context(bundle, inventory, now=None):
    """Validate only duplicate-topic and related-post state requiring site inventory."""
    return validate_bundle(
        bundle,
        inventory,
        now=now,
        require_review=False,
        scopes={'site'},
    )


def validate_review_binding(bundle, now=None):
    """Validate only semantic-review digest, policy digest and freshness."""
    now = now or datetime.now(KST)
    return validate_bundle(
        bundle,
        {'checked_on': now.date().isoformat(), 'posts': []},
        now=now,
        scopes={'review'},
    )


def render_legacy(plan, sources):
    source_map = {s['id']: s for s in sources}
    def paragraph(block):
        urls = list(dict.fromkeys(source_map[e['source_id']]['url'] for e in block['evidence']))
        links = ' '.join(f'<a href="{html.escape(u, quote=True)}" rel="noopener noreferrer">출처</a>' for u in urls)
        return f'<p>{html.escape(block["text"])}</p><p class="source-links">{links}</p>'
    result = paragraph(plan['lead'])
    for section in plan['sections']:
        result += '<h2>'+html.escape(section['heading'])+'</h2>'
        result += ''.join(paragraph(b) for b in section['paragraphs'])
    if plan.get('faq'):
        result += '<h2>자주 묻는 질문</h2>'
        for faq in plan['faq']:
            result += '<h3>'+html.escape(faq['question'])+'</h3>'+paragraph(faq['answer'])
    return result


def supported_official_number_notations(text, quote_text, candidates):
    """Accept exact Korean orthography for explicit years, dates and won amounts.

    This does not infer any other coverage period or replace semantic review.
    """
    supported = set()
    for short in re.findall(r"[’‘'ʼ](\d{2})년", quote_text):
        full = str(2000 + int(short))
        if full in candidates and re.search(r'(?<!\d)' + full + r'년', text):
            supported.add(full)
    for year, month, day in re.findall(
            r"(?<!\d)(20\d{2}|[’‘'ʼ]\d{2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{0,2})", quote_text):
        full = str(2000 + int(year[1:])) if not year.isdigit() else year
        month_number = str(int(month))
        day_number = str(int(day)) if day else None
        prefix = r'(?<!\d)' + full + r'년\s*0?' + month_number + r'월'
        if re.search(prefix, text):
            supported.update({full, month_number} & candidates)
            if day_number and re.search(prefix + r'\s*0?' + day_number + r'일', text):
                supported.update({day_number} & candidates)
        if day_number and re.search(
                r'(?<!\d)0?' + re.escape(month_number) + r'\s*/\s*0?'
                + re.escape(day_number) + r'(?!\d)', text):
            supported.update({month_number, day_number} & candidates)
    # Event sources frequently use compact ``10.9.(금)`` or ISO dates while
    # reader copy deliberately expands them to ``10월 9일(금)``. Treat only
    # the exact month/day pair present in the evidence as equivalent; this is
    # notation normalization, not inference of an unquoted date range.
    for month, day in re.findall(
            r"(?<!\d)(\d{1,2})\s*[./-]\s*(\d{1,2})(?:\s*\.)?(?:\s*\([월화수목금토일]\))?",
            quote_text):
        month_number = str(int(month))
        day_number = str(int(day))
        if (re.search(
                r'(?<!\d)0?' + re.escape(month_number) + r'월\s*0?'
                + re.escape(day_number) + r'일', text)
                or re.search(
                    r'(?<!\d)0?' + re.escape(month_number) + r'\s*/\s*0?'
                    + re.escape(day_number) + r'(?:\s*\([월화수목금토일]\))?(?!\d)', text)):
            supported.update({month_number, day_number} & candidates)
    # Likewise, official prose may say ``오후 2시`` while a schedule table
    # normalizes that exact clock time to ``14:00``. Accept only whole-hour
    # conversions whose AM/PM token is explicitly present in the evidence.
    for time_match in re.finditer(
            r'(오전|오후)\s*(\d{1,2})\s*시(?:\s*(?:와|과|및|,)\s*(\d{1,2})\s*시)?',
            quote_text):
        meridiem = time_match.group(1)
        for raw_hour in filter(None, time_match.groups()[1:]):
            hour = int(raw_hour)
            if not 1 <= hour <= 12:
                continue
            hour24 = hour % 12 + (12 if meridiem == '오후' else 0)
            hour_text = str(hour24)
            if re.search(r'(?<!\d)0?' + re.escape(hour_text) + r':00(?!\d)', text):
                supported.update({hour_text, '00'} & candidates)
    for quantity in re.findall(r'(?<!\d)(\d+)\s*천\s*원', quote_text):
        amount = str(int(quantity) * 1000)
        if amount in candidates and re.search(r'(?<!\d)' + amount + r'\s*원', text.replace(',', '')):
            supported.add(amount)
    return supported


def section_kind(section):
    """Explicit editorial intent wins; infer only clear legacy procedure headings."""
    if section.get('kind'):
        return section['kind']
    heading = section['heading'].strip()
    if re.match(r'^(?:\d+[.)]\s*)?STEP\s*\d+', heading, re.I):
        return 'procedure'
    if re.search(r'(?:신청|조회|청구|예약|배출|수령|접수)\s*(?:방법|절차|순서)$', heading):
        return 'procedure'
    return 'general'


def validated_lead_image(plan):
    """Return a reviewed lead image after enforcing a narrow safe schema."""
    image = plan.get('lead_image')
    if image is None:
        return None
    if not isinstance(image, dict) or set(image) != {'url', 'alt', 'width', 'height'}:
        raise ValueError('invalid_lead_image')
    url, alt = image.get('url'), image.get('alt')
    width, height = image.get('width'), image.get('height')
    if not isinstance(url, str) or not isinstance(alt, str):
        raise ValueError('invalid_lead_image')
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or re.search(r'[<>\r\n]', url)
            or not 1 <= len(alt.strip()) <= 200 or re.search(r'[<>\r\n]', alt)
            or type(width) is not int or type(height) is not int
            or not 1 <= width <= 10000 or not 1 <= height <= 10000):
        raise ValueError('invalid_lead_image')
    return image


def excerpt_from_lead(lead, limit=240):
    """Create the archive preview from reviewed answer text, never HTML chrome."""
    text = normalized(lead['text'])
    if len(text) <= limit:
        return text
    shortened = text[:limit].rsplit(' ', 1)[0]
    return (shortened or text[:limit]).rstrip('., ') + '…'


def render(plan, sources, category_key=None):
    """Keep the public contract while delegating deterministic presentation."""
    from agents.article_renderer import render_article
    return render_article(plan, sources, category_key, helpers={
        'validated_lead_image': validated_lead_image,
        'section_kind': section_kind,
        'actionable_links': actionable_links,
        'validated_section_action_links': validated_section_action_links,
        'validated_section_official_links': validated_section_official_links,
        'normalized': normalized,
        'all_blocks': all_blocks,
        'official_navigation_links': official_navigation_links,
    }, map_key=KAKAO_MAP_JAVASCRIPT_KEY)


def _previous_responsive_layout_variant(current_html):
    """Reproduce the immediately prior renderer layout from current HTML.

    This is intentionally presentation-only.  It removes the responsive CSS
    additions introduced later without changing any reviewed reader text,
    links, evidence, headings or table cells.
    """
    previous = re.sub(
        r'<style id="bloguito-responsive-layout">.*?</style>',
        '',
        current_html,
        count=1,
        flags=re.DOTALL,
    )
    previous = re.sub(
        r'<style>@media\(max-width:640px\)\{\.bloguito-cta-grid\{grid-template-columns:1fr!important\}\}</style>',
        '',
        previous,
    )
    previous = previous.replace(
        '<div class="bloguito-cta-grid" style=',
        '<div style=',
    )
    return previous


def recognized_renderer_outputs(plan, sources, category_key=None):
    """Return exact deterministic renderer outputs accepted as reviewed provenance.

    Never use fuzzy HTML or text similarity here.  A live post is recognized
    only when its body is byte-for-byte equal to one output generated from the
    stored reviewed bundle by a known renderer version.
    """
    current = render(plan, sources, category_key)
    outputs = {
        'current': current,
        'legacy': render_legacy(plan, sources),
    }
    previous = _previous_responsive_layout_variant(current)
    if previous != current:
        outputs['pre-responsive-layout-v1'] = previous
    return outputs


def validate_renderer_provenance_registry(path=None):
    """Validate the complete tracked historical-renderer provenance registry."""
    registry = Path(path) if path is not None else RENDERER_PROVENANCE_FILE
    try:
        payload = json.loads(registry.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid_renderer_provenance_registry') from exc
    if not isinstance(payload, dict):
        raise ValueError('invalid_renderer_provenance_registry')
    entries = payload.get('entries')
    if payload.get('schema_version') != 1 or not isinstance(entries, list):
        raise ValueError('invalid_renderer_provenance_registry')
    seen = set()
    for entry in entries:
        if (not isinstance(entry, dict)
                or set(entry) != {'post_id', 'current_sha256', 'historical_sha256',
                                  'renderer_revision', 'variant'}
                or type(entry.get('post_id')) is not int or entry['post_id'] <= 0
                or not isinstance(entry.get('variant'), str) or not entry['variant']
                or not isinstance(entry.get('renderer_revision'), str)
                or not re.fullmatch(r'[0-9a-f]{7,40}', entry['renderer_revision'])
                or any(not isinstance(entry.get(key), str)
                       or not re.fullmatch(r'[0-9a-f]{64}', entry[key])
                       for key in ('current_sha256', 'historical_sha256'))):
            raise ValueError('invalid_renderer_provenance_registry')
        token = (entry['post_id'], entry['variant'])
        if token in seen:
            raise ValueError('duplicate_renderer_provenance_entry')
        seen.add(token)
    return entries


def recognized_renderer_hashes(plan, sources, category_key=None, *, post_id=None):
    """Return exact renderer SHA bindings, including audited historical outputs.

    Historical compatibility is intentionally post-specific and bound to the
    current reviewed render SHA.  It cannot authorize a different bundle or a
    fuzzy-similar live body.
    """
    outputs = recognized_renderer_outputs(plan, sources, category_key)
    hashes = {
        name: hashlib.sha256(content.encode('utf-8')).hexdigest()
        for name, content in outputs.items()
    }
    if post_id is None or not RENDERER_PROVENANCE_FILE.is_file():
        return hashes
    entries = validate_renderer_provenance_registry()
    current_sha = hashes['current']
    for entry in entries:
        if entry['post_id'] == post_id and entry['current_sha256'] == current_sha:
            hashes[entry['variant']] = entry['historical_sha256']
    return hashes


def validate_reviewed_content_provenance_registry(path=None):
    """Validate the complete tracked reviewed-content provenance registry."""
    registry = Path(path) if path is not None else REVIEWED_CONTENT_PROVENANCE_FILE
    try:
        payload = json.loads(registry.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid_reviewed_content_provenance_registry') from exc
    entries = payload.get('entries') if isinstance(payload, dict) else None
    if payload.get('schema_version') != 1 or not isinstance(entries, list):
        raise ValueError('invalid_reviewed_content_provenance_registry')
    seen = set()
    for entry in entries:
        common_keys = {
            'post_id', 'review_digest', 'reviewed_content_sha256',
            'live_content_sha256', 'kind', 'variant', 'evidence_sha256',
            'bundle_digest',
        }
        if not isinstance(entry, dict):
            raise ValueError('invalid_reviewed_content_provenance_registry')
        kind = entry.get('kind')
        expected_keys = set(common_keys)
        if kind == 'post-review-image-url-substitution':
            expected_keys.update({
                'replacements', 'before_snapshot_sha256',
                'mutation_payload_sha256', 'mutation_script_sha256',
                'transformation_digest',
            })
        if (set(entry) != expected_keys
                or type(entry.get('post_id')) is not int or entry['post_id'] <= 0
                or kind not in {
                    'completed-full-review',
                    'post-review-image-url-substitution',
                }
                or not isinstance(entry.get('variant'), str) or not entry['variant']
                or any(not isinstance(entry.get(key), str)
                       or re.fullmatch(r'[0-9a-f]{64}', entry[key]) is None
                       for key in (
                           'review_digest', 'reviewed_content_sha256',
                           'live_content_sha256', 'evidence_sha256',
                           'bundle_digest',
                       ))):
            raise ValueError('invalid_reviewed_content_provenance_registry')
        if (kind == 'completed-full-review'
                and entry['reviewed_content_sha256'] != entry['live_content_sha256']):
            raise ValueError('invalid_reviewed_content_provenance_registry')
        if kind == 'post-review-image-url-substitution':
            replacements = entry.get('replacements')
            if (not isinstance(replacements, list) or not replacements
                    or len(replacements) > 20
                    or any(not isinstance(entry.get(key), str)
                           or re.fullmatch(r'[0-9a-f]{64}', entry[key]) is None
                           for key in (
                               'before_snapshot_sha256', 'mutation_payload_sha256',
                               'mutation_script_sha256', 'transformation_digest',
                           ))):
                raise ValueError('invalid_reviewed_content_provenance_registry')
            old_urls = []
            new_urls = []
            for replacement in replacements:
                if (not isinstance(replacement, dict)
                        or set(replacement) != {
                            'old_url', 'new_url', 'asset_sha256', 'receipt_sha256',
                        }
                        or any(not isinstance(replacement.get(key), str)
                               or not replacement[key].startswith(
                                   'https://lifeinfo24.org/wp-content/uploads/')
                               for key in ('old_url', 'new_url'))
                        or any(not isinstance(replacement.get(key), str)
                               or re.fullmatch(r'[0-9a-f]{64}', replacement[key]) is None
                               for key in ('asset_sha256', 'receipt_sha256'))
                        or replacement['old_url'] == replacement['new_url']):
                    raise ValueError('invalid_reviewed_content_provenance_registry')
                old_urls.append(replacement['old_url'])
                new_urls.append(replacement['new_url'])
            if (len(old_urls) != len(set(old_urls))
                    or len(new_urls) != len(set(new_urls))
                    or entry['reviewed_content_sha256'] == entry['live_content_sha256']):
                raise ValueError('invalid_reviewed_content_provenance_registry')
            transformation = {
                'reviewed_content_sha256': entry['reviewed_content_sha256'],
                'live_content_sha256': entry['live_content_sha256'],
                'before_snapshot_sha256': entry['before_snapshot_sha256'],
                'mutation_payload_sha256': entry['mutation_payload_sha256'],
                'mutation_script_sha256': entry['mutation_script_sha256'],
                'replacements': replacements,
            }
            if digest(transformation) != entry['transformation_digest']:
                raise ValueError('invalid_reviewed_content_provenance_registry')
        token = (entry['post_id'], entry['variant'])
        if token in seen:
            raise ValueError('duplicate_reviewed_content_provenance_entry')
        seen.add(token)
    return entries


def assert_review_digest_bound(bundle):
    """Require the semantic review to be cryptographically bound to this bundle body."""
    if not isinstance(bundle, dict):
        raise ValueError('invalid_reviewed_content_bundle')
    try:
        review = bundle['review']
    except (KeyError, TypeError):
        raise ValueError('invalid_reviewed_content_bundle') from None
    body = {
        key: bundle[key]
        for key in ('brief', 'sources', 'plan', 'temporal_source')
        if key in bundle
    }
    review_digest = review.get('digest') if isinstance(review, dict) else None
    checks = review.get('checks') if isinstance(review, dict) else None
    review_bound = (
        isinstance(review_digest, str)
        and re.fullmatch(r'[0-9a-f]{64}', review_digest) is not None
        and review_digest == digest(body)
        and review.get('issues') == []
        and isinstance(checks, dict)
        and bool(checks)
        and all(value is True for value in checks.values())
    )
    if not review_bound:
        raise ValueError('reviewed_content_review_not_bound')
    return review_digest


def recognized_reviewed_content_hashes(bundle, *, post_id=None):
    """Return exact content SHAs bound to the current reviewed bundle.

    Renderer provenance remains a separate concept: this helper may additionally
    accept a content SHA that was already saved by a completed full-review
    transaction, but only when the registry is cryptographically bound to the
    exact current bundle review digest.  These entries must never be used to
    authorize renderer migration because they do not reconstruct historical HTML.
    """
    if not isinstance(bundle, dict):
        raise ValueError('invalid_reviewed_content_bundle')
    try:
        brief = bundle['brief']
        sources = bundle['sources']
        plan = bundle['plan']
        review = bundle['review']
    except (KeyError, TypeError):
        raise ValueError('invalid_reviewed_content_bundle') from None
    review_digest = assert_review_digest_bound(bundle)

    hashes = recognized_renderer_hashes(
        plan, sources, brief.get('category_key'), post_id=post_id,
    )
    if post_id is None or not REVIEWED_CONTENT_PROVENANCE_FILE.is_file():
        return hashes

    entries = validate_reviewed_content_provenance_registry()
    for entry in entries:
        if (entry['post_id'] == post_id
                and entry['review_digest'] == review_digest
                and entry['bundle_digest'] == digest(bundle)):
            hashes[entry['variant']] = entry['live_content_sha256']
    return hashes


def save_report(bundle, report):
    """Internal audit only; source snapshots and failed prose never enter the public post."""
    from uuid import uuid4
    folder = ROOT / 'data' / 'editorial_runs'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (datetime.now(KST).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8]+'.json')
    target.write_text(json.dumps({'bundle': bundle, 'report': report}, ensure_ascii=False, indent=2), encoding='utf-8')
    return target
