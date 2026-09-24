"""Shared editorial contract. Deterministic checks are not semantic fact proof."""
import hashlib
import html
import json
import re
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from agents.temporal_validation import (KST, validate_availability, extract_evidence,
                                        extract_yes24_schedule, validate_legacy_followup,
                                        validate_legacy_reference_period)
from agents.search_intent import duplicate_posts
from agents.critical_facts import critical_fact_reasons

ROOT = Path(__file__).resolve().parents[1]


def policy():
    return json.loads((ROOT / 'editorial_policy.json').read_text(encoding='utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def policy_fingerprint():
    instructions = (ROOT.parent / 'docs' / 'EDITORIAL_SYSTEM.md').read_text(encoding='utf-8')
    return digest({'rules': policy(), 'instructions': instructions, 'contract_version': 1})


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
    exception = policy().get('dated_post_exceptions', {}).get(brief.get('id'), {})
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
    exception = policy().get('legacy_welfare_procedural_exceptions', {}).get(brief.get('id'))
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
    cfg = policy()['legacy_welfare_procedural_exceptions'][brief['id']]
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
    reasons = []
    required = ('entity', 'primary_keyword', 'question', 'angle', 'official_urls', 'required_title_terms', 'reader_questions')
    if not all(brief.get(k) for k in required):
        reasons.append('topic_incomplete')
    try:
        if not brief.get('approved') or not date.fromisoformat(brief['reviewed_at']) <= today <= date.fromisoformat(brief['review_until']):
            reasons.append('topic_not_currently_approved')
        if brief.get('content_type') == 'evergreen':
            if brief.get('useful_until') is not None or not brief.get('evergreen_reason'):
                reasons.append('evergreen_reason_missing_or_deadline_present')
            if (brief.get('category_key') in {'concert', 'welfare'}
                    and not (brief.get('category_key') == 'welfare'
                             and legacy_85_welfare_navigation_exception(brief))):
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
            *[{'text': ' '.join(row['cells']), 'evidence': row['evidence'],
               'answers': row.get('answers', []), 'calculations': row.get('calculations', [])}
              for s in plan['sections'] for row in (s.get('table') or {}).get('rows', [])],
            *[f['answer'] for f in plan.get('faq', [])]]


def supported_currency_sums(text, quote_text, calculations):
    """Allow only explicit KRW sums whose operands are all present in evidence.

    This is intentionally narrow. It supports reader-useful reference prices
    derived by adding official won amounts, while still rejecting inferred
    dates, rates, averages, multiplication, subtraction and arbitrary math.
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
        if (not isinstance(item, dict)
                or set(item) != {'operation', 'unit', 'operands', 'result'}
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
    for item in plan.get('official_navigation', []):
        values.extend((item.get('label', ''), item.get('note', '')))
    for source in sources:
        for action in source.get('actions', []):
            values.append(action.get('label', ''))
        values.append(source.get('citation_label') or source.get('title', ''))
    return [value for value in values if isinstance(value, str)]


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
    if len(links) > 4:
        raise ValueError('too_many_action_links')
    return links


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


def validate_bundle(bundle, inventory, now=None, require_review=True):
    now = now or datetime.now(KST)
    rules = policy()
    reasons = []
    details = []
    try:
        brief, sources, plan = bundle['brief'], bundle['sources'], bundle['plan']
        reasons.extend(topic_reasons(brief, now.date()))
        if any('·' in value for value in reader_visible_strings(plan, sources)):
            reasons.append('reader_middle_dot_disallowed')
            details.append('독자 문구의 가운데점 문자를 쉼표 또는 자연스러운 연결 표현으로 바꿀 것')
        if inventory.get('checked_on') != now.date().isoformat() or not isinstance(inventory.get('posts'), list):
            reasons.append('fresh_inventory_required')
        elif duplicate_posts(brief, inventory['posts']):
            reasons.append('duplicate_topic')
        if not sources or len({s['id'] for s in sources}) != len(sources):
            reasons.append('sources_missing_or_duplicate_ids')
        source_map = {s['id']: s for s in sources}
        for s in sources:
            if s['url'] not in brief['official_urls'] or s.get('source_type') != 'official':
                reasons.append('source_not_official_brief_url')
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
        if legacy_85_welfare_navigation_exception(brief):
            reasons.extend(legacy_85_welfare_navigation_reasons(brief, sources, plan))
        related = plan.get('related_posts', [])
        if not isinstance(related, list) or len(related) > 2:
            reasons.append('invalid_related_post_links')
        else:
            seen_related = set()
            for item in related:
                if not isinstance(item, dict) or set(item) != {'post_id', 'label', 'url'}:
                    reasons.append('invalid_related_post_links')
                    continue
                target, label, url = (item[key] for key in ('post_id', 'label', 'url'))
                if (type(target) is not int or target <= 0 or target in seen_related
                        or target == brief.get('existing_post_id') or not isinstance(label, str)
                        or not 4 <= len(label.strip()) <= 60 or re.search(r'[<>\r\n]', label)
                        or not isinstance(url, str) or url != f'https://lifeinfo24.org/?p={target}'
                        or not any(row.get('ID') == target and row.get('post_status') == 'publish'
                                   for row in inventory.get('posts', []))):
                    reasons.append('invalid_related_post_links')
                seen_related.add(target)
        if brief.get('content_type') == 'dated':
            temporal = bundle.get('temporal_source', {})
            available = [field for s in sources for field in extract_evidence(s['text'], s['url'])]
            seasonal_exception = dated_post_exception(brief, now.date())
            if seasonal_exception:
                exception = rules['dated_post_exceptions'][brief['id']]
                if exception.get('official_urls'):
                    required_urls = exception['official_urls']
                else:
                    required_urls = [exception['official_url']]
                    if exception.get('required_attachment_url'):
                        required_urls.append(exception['required_attachment_url'])
                event_source = next((source for source in sources
                                     if source['url'] == exception.get('source_event_url', required_urls[0])), None)
                if ([source['url'] for source in sources] != required_urls
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
            if temporal.get('evidence') != available:
                reasons.append('temporal_source_not_bound')
            if listing_only:
                # For an event schedule and booking *destinations*, evidence of an
                # actual sale deadline is not available from the public listing.
                # This mode cannot certify ticket availability or sale periods.
                listing_url = temporal.get('listing_source_url')
                listing_source = next((s for s in sources if s['url'] == listing_url), None)
                if (brief.get('category_key') != 'concert' or temporal.get('requires_sale') is not False
                        or not listing_source or urlparse(listing_url).hostname != 'm.ticket.yes24.com'):
                    reasons.append('schedule_listing_provenance_missing')
                else:
                    rows = extract_yes24_schedule(listing_source['text'], brief['entity'].split()[0])
                    table_rows = [row['cells'] for section in plan['sections']
                                  for row in (section.get('table') or {}).get('rows', [])]
                    if (not rows or rows != temporal.get('listing_entries')
                            or any([item['region'], item['date'], item['venue']] not in table_rows for item in rows)):
                        reasons.append('schedule_listing_not_bound')
                    elif max(date.fromisoformat(item['date'].replace('.', '-')) for item in rows) < now.date():
                        reasons.append('availability_not_verified')
                    elif (max(date.fromisoformat(item['date'].replace('.', '-')) for item in rows)
                          - now.date()).days < rules['min_remaining_days']:
                        reasons.append('source_deadline_too_close')
                    public_text = ' '.join([plan['lead']['text'], *[p['text'] for sec in plan['sections']
                                                                   for p in sec['paragraphs']],
                                            *[faq['answer']['text'] for faq in plan.get('faq', [])]])
                    if re.search(r'예매\s*중|판매\s*중|예매\s*기간|판매\s*기간|매진|잔여\s*좌석', public_text):
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
                elif not seasonal_exception:
                    if not available:
                        reasons.append('temporal_source_not_bound')
                    decision = validate_availability(temporal, now=now)
                    if decision['status'] != 'active':
                        reasons.append('availability_not_verified')
                    if decision.get('expires_at') and (datetime.fromisoformat(decision['expires_at']).date()-now.date()).days < rules['min_remaining_days']:
                        reasons.append('source_deadline_too_close')
        # Version-specific official policy evidence is separate from a fresh fetch and a valid quote.
        reasons.extend(critical_fact_reasons(brief, sources, plan))
        title = plan['title']
        if not all(normalized(t) in normalized(title) for t in brief['required_title_terms']):
            reasons.append('title_missing_entity_or_region')
        if not plan['sections'] or not all(s['heading'] and (s['paragraphs'] or s.get('table')) for s in plan['sections']):
            reasons.append('article_structure_incomplete')
        for section in plan['sections']:
            if section.get('kind') is not None and section['kind'] not in {
                    'overview', 'eligibility', 'comparison', 'procedure', 'exceptions', 'schedule', 'general'}:
                reasons.append('invalid_section_kind')
            table = section.get('table')
            if table is None:
                continue
            headers, rows = table.get('headers'), table.get('rows')
            if (not isinstance(table.get('caption'), str) or not table['caption'].strip()
                    or not isinstance(headers, list) or not 2 <= len(headers) <= 5
                    or not isinstance(rows, list) or not 1 <= len(rows) <= 20
                    or any(not isinstance(h, str) or not 1 <= len(h.strip()) <= 60 for h in headers)
                    or any(not isinstance(row, dict) or not isinstance(row.get('cells'), list)
                           or len(row['cells']) != len(headers)
                           or any(not isinstance(cell, str) or not 1 <= len(cell.strip()) <= 160
                                  for cell in row['cells']) for row in rows)):
                reasons.append('invalid_information_table')
        blocks = all_blocks(plan)
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
        if re.search(r'이\s*(?:초안|원고)(?:에서는|은|와|를)|독립적인\s*검색\s*질문이\s*확인되지\s*않으면|(?:자료\s*검토|내용\s*재검토|최종\s*검토일|검토·수정)\s*[:：]|공식\s*출처\s*및\s*검토\s*기록|링크된\s*자료의\s*적용\s*시점과\s*실제\s*안내\s*화면을\s*확인|정정\s*안내|기존\s*수치의\s*정정|(?:기존|과거|종전)\s*(?:글|본문|게시물|공지|안내)[^.。\n]{0,130}(?:삭제|수정|정정|바로잡|폐기)', visible):
            reasons.append('internal_editorial_note_in_prose')
        if re.search(r'<[^>]+>|https?://', visible):
            reasons.append('raw_markup_or_url_in_prose')
        if require_review:
            review = bundle.get('review', {})
            body = {k: bundle[k] for k in ('brief', 'sources', 'plan', 'temporal_source') if k in bundle}
            if review.get('digest') != digest(body) or review.get('policy_digest') != policy_fingerprint():
                reasons.append('review_not_bound_to_current_content')
            if not fresh(review.get('checked_at'), now, rules['review_max_age_hours']):
                reasons.append('review_stale')
            if any(review.get('checks', {}).get(k) is not True for k in rules['review_checks']) or review.get('issues') != []:
                reasons.append('semantic_review_failed')
    except (KeyError, TypeError, ValueError, AttributeError):
        reasons.append('malformed_editorial_bundle')
    return {'status': 'ready' if not reasons else 'needs_review', 'reasons': sorted(set(reasons)), 'details': details}


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
            r"(?<!\d)(20\d{2}|[’‘'ʼ]\d{2})\.(\d{1,2})\.(\d{0,2})", quote_text):
        full = str(2000 + int(year[1:])) if not year.isdigit() else year
        month_number = str(int(month))
        day_number = str(int(day)) if day else None
        prefix = r'(?<!\d)' + full + r'년\s*0?' + month_number + r'월'
        if re.search(prefix, text):
            supported.update({full, month_number} & candidates)
            if day_number and re.search(prefix + r'\s*0?' + day_number + r'일', text):
                supported.update({day_number} & candidates)
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


def excerpt_from_lead(lead, limit=240):
    """Create the archive preview from reviewed answer text, never HTML chrome."""
    text = normalized(lead['text'])
    if len(text) <= limit:
        return text
    shortened = text[:limit].rsplit(' ', 1)[0]
    return (shortened or text[:limit]).rstrip('., ') + '…'


def render(plan, sources, category_key=None):
    """Presentation is deterministic: retain every reviewed sentence and condition."""
    source_map = {s['id']: s for s in sources}
    def inline_text(block):
        text = block['text']
        emphasis = block.get('emphasis') or []
        if not emphasis:
            return html.escape(text)
        # Match the longest phrase first when reviewed emphasis phrases overlap.
        pattern = re.compile('(' + '|'.join(re.escape(item) for item in sorted(emphasis, key=len, reverse=True)) + ')')
        emphasized = set(emphasis)
        return ''.join(
            (f'<strong style="font-weight:700;color:#1f2937">{html.escape(part)}</strong>'
             if part in emphasized else html.escape(part))
            for part in pattern.split(text) if part
        )

    def paragraph(block):
        return (f'<p style="margin:0 0 16px;line-height:1.8;color:#2d3748;'
                f'font-size:16px;font-weight:400;letter-spacing:normal">{inline_text(block)}</p>')

    # 1. Immediate answer, with one heading and no repeated decorative badges.
    result = ('<div class="bloguito-article" style="line-height:1.8;font-size:16px;color:#2d3748;'
              'font-family:-apple-system,BlinkMacSystemFont,\'Malgun Gothic\',\'Apple SD Gothic Neo\',\'Noto Sans KR\',sans-serif;'
              'font-weight:400;letter-spacing:normal;overflow-wrap:anywhere;word-break:keep-all">'
              '<div class="bloguito-summary" style="padding:18px 20px;margin:16px 0 24px;background:#f0f8f5;border:1px solid #d1e7dd;border-left:5px solid #0d7d59;border-radius:10px">'
              '<div style="font-size:18px;font-weight:700;color:#134e4a">핵심 답변</div>'
              + f'<p style="margin:8px 0 0;line-height:1.75;color:#1f2937;font-size:16px">{inline_text(plan["lead"])}</p></div>')

    # A source-reviewed overview table belongs immediately after the answer.
    sections = plan['sections']
    overview_first = bool(sections and section_kind(sections[0]) == 'overview')
    procedure_number = 0
    # One isolated procedure is not a sequence. A lonely STEP 1 confuses the
    # heading hierarchy and was mistakenly included in the table of contents.
    numbered_procedures = sum(section_kind(section) == 'procedure' for section in sections) > 1

    def section_markup(number, section):
        nonlocal procedure_number
        clean_heading = re.sub(r'^\s*(\d+[.)]\s*)?(STEP\s*\d+[.)]?\s*)?', '', section['heading'], flags=re.IGNORECASE).strip()
        procedural = numbered_procedures and section_kind(section) == 'procedure'
        if procedural:
            procedure_number += 1
        badge = (f'<span style="background:#e6f4ea;color:#0d7d59;font-size:13px;font-weight:700;padding:4px 9px;border-radius:20px;margin-right:9px">STEP {procedure_number}</span>'
                 if procedural else '')
        body = (f'<h2 id="step-{number}" style="font-family:inherit;font-size:clamp(20px,2.5vw,23px);'
                f'font-weight:700;font-style:normal;letter-spacing:normal;text-align:left;'
                f'line-height:1.45;margin:32px 0 14px;padding-bottom:10px;border-bottom:2px solid #e2e8f0;color:#1a202c">'
                f'{badge}{html.escape(clean_heading)}</h2>')
        table = section.get('table')
        if table:
            headers = ''.join(f'<th scope="col" style="padding:10px;border-bottom:2px solid #cbd5e1;text-align:left">{html.escape(h)}</th>'
                              for h in table['headers'])
            rows = ''.join('<tr>' + ''.join(
                (f'<th scope="row" style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:left;font-weight:700">{html.escape(cell)}</th>'
                 if index == 0 else
                 f'<td style="padding:10px;border-bottom:1px solid #e2e8f0;vertical-align:top">{html.escape(cell)}</td>')
                for index, cell in enumerate(row['cells'])) + '</tr>' for row in table['rows'])
            scrolling = len(table['headers']) >= 3
            hint = ('<p class="bloguito-table-hint" style="font-size:13px;color:#475569;margin:0 0 6px">작은 화면에서는 표를 좌우로 밀어 확인할 수 있습니다.</p>'
                    if scrolling else '')
            body += (hint + '<div class="bloguito-info-table" role="region" aria-label="'
                     + html.escape(table['caption'], quote=True)
                     + '" tabindex="0" style="overflow-x:auto;margin:8px 0 24px;max-width:100%">'
                     + '<table style="border-collapse:collapse;width:100%;min-width:'
                     + ('580px' if scrolling else '0')
                     + ';font-size:15px;line-height:1.6;overflow-wrap:anywhere;word-break:keep-all">'
                     + '<caption style="text-align:left;font-weight:700;margin-bottom:8px">'
                     + html.escape(table['caption']) + '</caption><thead style="background:#edf7f3"><tr>'
                     + headers + '</tr></thead><tbody>' + rows + '</tbody></table></div>')
        return body + ''.join(paragraph(b) for b in section['paragraphs'])

    if overview_first:
        result += section_markup(1, sections[0])

    # 2. Only confirmed booking/apply/lookup/purchase/install destinations are actions.
    # Informational sources remain in the citations below, never in the CTA.
    actions = actionable_links(sources)
    if actions:
        buttons = []
        for idx, action in enumerate(actions):
            primary = idx == 0 and len(actions) <= 2
            background = '#0d7d59' if primary or len(actions) > 2 else '#ffffff'
            color = '#ffffff' if primary or len(actions) > 2 else '#0d7d59'
            buttons.append(
                f'<a href="{html.escape(action["url"], quote=True)}" target="_blank" rel="noopener noreferrer" '
                f'style="display:flex;align-items:center;justify-content:center;gap:10px;min-width:0;padding:13px 16px;background:{background};color:{color} !important;border:1px solid #0d7d59;text-decoration:none !important;border-radius:10px;font-size:16px;font-weight:700;overflow-wrap:anywhere">'
                f'<span style="flex-grow:1;text-align:center">{html.escape(action["label"])}</span>'
                f'<span aria-hidden="true">↗</span></a>'
            )
        result += ('<div class="bloguito-cta" style="margin:20px 0 26px;padding:16px;background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px">'
                   '<div style="font-size:17px;font-weight:700;color:#0f172a;margin-bottom:12px">공식 서비스 바로가기</div>'
                   f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));gap:10px">{"".join(buttons)}</div></div>')

    # Navigation is visibly distinct from verified direct-service actions.
    navigation = official_navigation_links(plan, sources)
    if navigation:
        items = ''.join(
            '<li style="margin:10px 0 14px"><a href="'
            + html.escape(item['url'], quote=True)
            + '" target="_blank" rel="noopener noreferrer" '
            + 'style="color:#0d7d59;text-decoration:underline;font-weight:600">'
            + html.escape(item['label']) + '</a><div style="font-size:14px;color:#475569">'
            + html.escape(item['note']) + '</div></li>' for item in navigation)
        result += ('<aside class="bloguito-official-navigation" style="margin:18px 0 26px;'
                   'padding:12px 20px;background:#f8fafc;border:1px solid #cbd5e1;'
                   'border-radius:10px"><h2 style="font-size:17px;color:#334155;'
                   'margin:4px 0 8px">공식 사이트에서 메뉴 찾기</h2>'
                   + '<ul style="padding-left:20px;margin:0">' + items + '</ul></aside>')

    # 3. 경량 네이티브 목차 (Table of Contents - 구글 사이트링크 및 모바일 UX 최적화)
    toc_items = []
    toc_procedure_number = 0
    for number, section in enumerate(sections, 1):
        if number == 1 and overview_first:
            continue
        clean_heading = re.sub(r'^\s*(\d+[.)]\s*)?(STEP\s*\d+[.)]?\s*)?', '', section['heading'], flags=re.IGNORECASE).strip()
        if numbered_procedures and section_kind(section) == 'procedure':
            toc_procedure_number += 1
            heading_label = f'STEP {toc_procedure_number}. {clean_heading}'
        else:
            heading_label = clean_heading
        toc_items.append(f'<li style="margin:6px 0"><a href="#step-{number}" style="color:#0d7d59;text-decoration:none;font-weight:500">{html.escape(heading_label)}</a></li>')
    if plan.get('faq'):
        toc_items.append('<li style="margin:6px 0"><a href="#faq" style="color:#0d7d59;text-decoration:none;font-weight:500">자주 묻는 질문 (FAQ)</a></li>')
    # The evidence list is a footer, not an additional article section.

    result += ('<nav class="bloguito-toc" aria-label="본문 목차" style="padding:16px 20px;margin:20px 0 28px;background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #0d7d59;border-radius:8px">'
               '<div style="font-weight:700;font-size:16px;color:#1e293b;margin-bottom:8px">목차</div>'
               '<ul style="margin:0;padding-left:22px;line-height:1.75;color:#475569;font-size:15px">'
               + ''.join(toc_items) + '</ul></nav>')

    # 4. 본문 섹션 (각 소제목에 점프 링크 앵커 ID 매핑)
    for number, section in enumerate(sections, 1):
        if number == 1 and overview_first:
            continue
        result += section_markup(number, section)

    # 4. 자주 묻는 질문 (FAQ)
    if plan.get('faq'):
        result += ('<h2 id="faq" style="font-family:inherit;font-size:clamp(20px,2.5vw,23px);'
                   'font-weight:700;letter-spacing:normal;line-height:1.45;'
                   'margin:36px 0 16px;padding-bottom:10px;border-bottom:2px solid #e2e8f0;color:#1a202c">자주 묻는 질문</h2>')
        for faq in plan['faq']:
            result += ('<div class="bloguito-faq" style="padding:20px 22px;margin:18px 0;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px">'
                       '<div style="display:flex;align-items:flex-start;margin-bottom:12px"><span style="background:#2563eb;color:#ffffff;font-weight:800;font-size:13px;padding:3px 9px;border-radius:4px;margin-right:10px;flex-shrink:0;margin-top:2px">Q</span>'
                       f'<h3 style="font-family:inherit;font-size:18px;line-height:1.5;margin:0;color:#1e293b;font-weight:700;letter-spacing:normal">{html.escape(faq["question"])}</h3></div>'
                       '<div style="display:flex;align-items:flex-start;padding-left:2px"><span style="background:#059669;color:#ffffff;font-weight:800;font-size:13px;padding:3px 9px;border-radius:4px;margin-right:10px;flex-shrink:0;margin-top:2px">A</span>'
                       f'<div style="flex-grow:1;color:#334155;line-height:1.8">{inline_text(faq["answer"])}</div></div></div>')

    # 5. Explicit, reviewed related-post links take precedence over volatile
    # local recommendations. Never promote an internal article to an official CTA.
    interlink_html = ''
    related = plan.get('related_posts', [])
    if related:
        items = ''.join(
            '<li style="margin-bottom:10px"><a href="'
            + html.escape(item['url'], quote=True)
            + '" style="color:#0d7d59;text-decoration:underline;font-weight:600;font-size:15.5px">'
            + html.escape(item['label']) + '</a></li>' for item in related)
        interlink_html = (
            '<div class="bloguito-interlink" style="padding:20px 24px;margin:40px 0 20px;'
            'background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid #0d7d59;border-radius:10px">'
            '<h3 style="margin:0 0 12px;font-size:18px;color:#1e293b;font-weight:700">관련 글</h3>'
            '<ul style="margin:0;padding-left:22px;line-height:1.8">' + items + '</ul></div>')
    else:
      try:
        posts_file = ROOT / 'data' / 'published_posts.json'
        if posts_file.exists():
            posts = json.loads(posts_file.read_text(encoding='utf-8'))
            today = datetime.now(KST).date()

            # 현재 글의 카테고리 결정
            cur_cat = category_key or plan.get('category_key')
            if not cur_cat:
                t = plan.get('title', '')
                if any(w in t for w in ['콘서트', '티켓', '앵콜', '뮤지컬', '공연', '페스티벌']):
                    cur_cat = 'concert'
                elif any(w in t for w in ['세금', '연말정산', '종합소득세', '자동차세', '취득세']):
                    cur_cat = 'tax'
                elif any(w in t for w in ['지원금', '기초연금', '바우처', '장려금', '환급금']):
                    cur_cat = 'welfare'
                else:
                    cur_cat = 'life-health'

            # 카테고리 상호 호환 그룹 정의 (공연/콘서트와 생활/복지/세무 철저 분리)
            is_concert = (cur_cat == 'concert' or cur_cat == 2 or cur_cat == '공연/콘서트 예매')

            candidates = []
            for p in posts:
                if not p.get('url') or p.get('title') == plan.get('title'):
                    continue
                # The local post index may contain legacy IP/HTTP links. Only link
                # canonical public HTTPS posts, and never treat category alone as relevance.
                parsed = urlparse(p['url'])
                if parsed.scheme != 'https' or parsed.hostname != 'lifeinfo24.org':
                    continue
                generic = {'2026', '2027', '안내', '정보', '방법', '총정리', '가이드',
                           '무료', '신청', '조회', '기간', '혜택', '이용', '확인',
                           '전국', '서울', '2026년', '2027년', '기준', '절차',
                           '관련', '대상', '공식', '받는', '찾기', '오늘', '예약'}
                words = lambda title: {t for t in re.findall(r'[가-힣a-zA-Z]{2,}', title.casefold())
                                       if t not in generic and not t.endswith('년')}
                current_terms = words(plan.get('title', ''))
                candidate_terms = words(p.get('title', ''))
                if not any(len(a) >= 3 and (a in b or b in a) for a in current_terms for b in candidate_terms):
                    continue
                if p.get('status') == 'draft' or p.get('is_closed') is True:
                    continue
                exp_str = p.get('expires_at')
                if exp_str:
                    try:
                        exp_date = datetime.strptime(str(exp_str)[:10], '%Y-%m-%d').date()
                        if exp_date < today:
                            continue
                    except Exception:
                        pass

                p_cat_id = p.get('category_id')
                p_cat_name = p.get('category_name', '')

                # 공연 글 여부 판별
                p_is_concert = (p_cat_id == 2 or '공연' in p_cat_name or '콘서트' in p_cat_name)

                # 상호 배타성 검사: 공연 글은 공연 글끼리만, 비공연(생활/복지/세무) 글은 비공연 글끼리만 추천!
                if is_concert != p_is_concert:
                    continue

                # 점수 부여 (동일 카테고리 최우선)
                score = 0
                if cur_cat in {'life-health', 4, '생활/건강 정보'} and (p_cat_id == 4 or '생활' in p_cat_name or '건강' in p_cat_name):
                    score = 2
                elif cur_cat in {'welfare', 3, '정부 복지/지원금'} and (p_cat_id == 3 or '복지' in p_cat_name or '지원금' in p_cat_name):
                    score = 2
                elif cur_cat in {'tax', 102, '생활 세금/절세 정보'} and (p_cat_id == 102 or '세금' in p_cat_name or '절세' in p_cat_name):
                    score = 2
                elif is_concert and p_is_concert:
                    score = 2
                else:
                    score = 1

                candidates.append((score, p))

            if candidates:
                # 점수 높은 순(동일 카테고리 우선) 정렬 후 최대 2개 선택
                candidates.sort(key=lambda x: x[0], reverse=True)
                selected = [x[1] for x in candidates[:2]]

                header_title = '함께 보면 좋은 추천 공연·티켓 정보' if is_concert else '함께 보면 유익한 생활 정보 추천'
                items = ''.join(
                    f'<li style="margin-bottom:10px"><a href="{html.escape(item["url"], quote=True)}" target="_blank" rel="noopener noreferrer" style="color:#0d7d59;text-decoration:underline;font-weight:600;font-size:15.5px">👉 [{html.escape(item.get("category_name", "생활정보"))}] {html.escape(item["title"])}</a></li>'
                    for item in selected
                )
                interlink_html = (
                    '<div class="bloguito-interlink" style="padding:20px 24px;margin:40px 0 20px;background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid #0d7d59;border-radius:10px">'
                    f'<h3 style="margin:0 0 12px;font-size:18px;color:#1e293b;display:flex;align-items:center"><span style="margin-right:8px">{"🎵" if is_concert else "🔗"}</span>{header_title}</h3>'
                    f'<ul style="margin:0;padding-left:22px;line-height:1.8">{items}</ul></div>'
                )
      except Exception:
          interlink_html = ''

    # 6. 공식 출처 및 사실 검증 자료.
    # Exact action destinations already have a prominent reader-facing CTA, so
    # do not repeat those same URLs in the evidence footer. The footer is for
    # distinct evidence/reference pages only.
    ids = []
    for block in all_blocks(plan):
        ids.extend(e['source_id'] for e in block['evidence'])
    ids = list(dict.fromkeys(ids))
    action_urls = {action['url'] for action in actions}
    citation_ids = [i for i in ids if source_map[i]['url'] not in action_urls]
    links = ''.join(
        '<li style="margin:8px 0"><a href="'
        + html.escape(source_map[i].get('citation_url') or source_map[i]['url'], quote=True)
        + '" rel="noopener noreferrer" style="color:#0d7d59;text-decoration:underline;word-break:break-all">'
        + html.escape((source_map[i].get('citation_label')
                       or source_map[i]['title'].splitlines()[0])[:100])
        + '</a></li>'
        for i in citation_ids)
    source_footer = (
        '<div style="margin-top:44px;padding:22px 24px;background:#fcfdfd;border:1px dashed #cbd5e1;border-radius:10px">'
        '<h2 id="sources" style="font-family:inherit;font-size:20px;font-weight:700;letter-spacing:normal;line-height:1.45;margin:0 0 14px;color:#334155;display:flex;align-items:center"><span style="margin-right:8px">🏛️</span>공식 출처 및 사실 검증 자료</h2>'
        '<ul class="source-list" style="padding-left:22px;margin:0;color:#64748b">'
        + links + '</ul></div>'
        if links else '')
    return result + interlink_html + source_footer + '</div>'


def save_report(bundle, report):
    """Internal audit only; source snapshots and failed prose never enter the public post."""
    from uuid import uuid4
    folder = ROOT / 'data' / 'editorial_runs'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (datetime.now(KST).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8]+'.json')
    target.write_text(json.dumps({'bundle': bundle, 'report': report}, ensure_ascii=False, indent=2), encoding='utf-8')
    return target
