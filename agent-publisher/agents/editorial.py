"""Shared editorial contract. Deterministic checks are not semantic fact proof."""
import hashlib
import html
import json
import re
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse

from agents.temporal_validation import KST, validate_availability, extract_evidence
from agents.search_intent import duplicate_posts

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
            if brief.get('category_key') in {'concert', 'welfare'}:
                reasons.append('dated_category_cannot_bypass_time_check')
        elif brief.get('content_type') == 'dated':
            if (date.fromisoformat(brief['useful_until']) - today).days < policy()['min_remaining_days']:
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
    return [plan['lead'], *[b for s in plan['sections'] for b in s['paragraphs']], *[f['answer'] for f in plan.get('faq', [])]]


def validate_bundle(bundle, inventory, now=None, require_review=True):
    now = now or datetime.now(KST)
    rules = policy()
    reasons = []
    details = []
    try:
        brief, sources, plan = bundle['brief'], bundle['sources'], bundle['plan']
        reasons.extend(topic_reasons(brief, now.date()))
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
            if s['sha256'] != hashlib.sha256(s['text'].encode()).hexdigest():
                reasons.append('source_hash_mismatch')
            if not fresh(s['fetched_at'], now, rules['source_max_age_hours']):
                reasons.append('source_stale')
        if brief.get('content_type') == 'dated':
            temporal = bundle.get('temporal_source', {})
            if brief.get('category_key') == 'concert' and (temporal.get('requires_sale') is not True or temporal.get('sale_source_url') not in brief['official_urls']):
                reasons.append('concert_sale_evidence_required')
            available = [field for s in sources for field in extract_evidence(s['text'], s['url'])]
            if not available or temporal.get('evidence') != available:
                reasons.append('temporal_source_not_bound')
            decision = validate_availability(temporal, now=now)
            if decision['status'] != 'active':
                reasons.append('availability_not_verified')
            if decision.get('expires_at') and (datetime.fromisoformat(decision['expires_at']).date()-now.date()).days < rules['min_remaining_days']:
                reasons.append('source_deadline_too_close')
        title = plan['title']
        if not all(normalized(t) in normalized(title) for t in brief['required_title_terms']):
            reasons.append('title_missing_entity_or_region')
        if not plan['sections'] or not all(s['heading'] and s['paragraphs'] for s in plan['sections']):
            reasons.append('article_structure_incomplete')
        blocks = all_blocks(plan)
        answered = set()
        for block_index, b in enumerate(blocks):
            if not b['text'].strip() or not b['evidence']:
                reasons.append('paragraph_without_evidence')
            evidence_text = []
            for e in b['evidence']:
                s = source_map[e['source_id']]
                if len(normalized(e['quote'])) < 8 or normalized(e['quote']) not in normalized(s['text']):
                    reasons.append('quote_not_in_source')
                evidence_text.append(e['quote'])
            numbers = lambda t: set(re.findall(r'\d+(?:[.,]\d+)*', t.replace(',', '')))
            unsupported = numbers(b['text']) - numbers(' '.join(evidence_text))
            unsupported -= supported_counts(b['text'], ' '.join(evidence_text), unsupported)
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
        visible = ' '.join([title, *[s['heading'] for s in plan['sections']], *[b['text'] for b in blocks], *[f['question'] for f in plan.get('faq', [])]])
        if any(re.search(p, visible) for p in rules['blocked_patterns']):
            reasons.append('reader_deflection_or_disclaimer')
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


def render(plan, sources):
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


def save_report(bundle, report):
    """Internal audit only; source snapshots and failed prose never enter the public post."""
    from uuid import uuid4
    folder = ROOT / 'data' / 'editorial_runs'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (datetime.now(KST).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8]+'.json')
    target.write_text(json.dumps({'bundle': bundle, 'report': report}, ensure_ascii=False, indent=2), encoding='utf-8')
    return target
