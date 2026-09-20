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
        # Version-specific official policy evidence is separate from a fresh fetch and a valid quote.
        reasons.extend(critical_fact_reasons(brief, sources, plan))
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


def render(plan, sources, category_key=None):
    """Presentation is deterministic: retain every reviewed sentence and condition."""
    source_map = {s['id']: s for s in sources}
    def paragraph(block):
        return f'<p style="margin:14px 0;line-height:1.85;color:#2d3748;font-size:16.5px">{html.escape(block["text"])}</p>'

    # 1. 3초 핵심 요약 박스
    result = ('<div class="bloguito-article" style="line-height:1.85;font-size:17px;color:#2d3748;overflow-wrap:anywhere;word-break:keep-all">'
              '<div class="bloguito-summary" style="padding:22px 24px;margin:24px 0 36px;background:#f0f8f5;border:1px solid #d1e7dd;border-left:6px solid #0d7d59;border-radius:10px;box-shadow:0 2px 8px rgba(13,125,89,0.06)">'
              '<div style="display:flex;align-items:center;margin-bottom:10px"><span style="background:#0d7d59;color:#ffffff;font-size:12px;font-weight:700;padding:3px 8px;border-radius:4px;margin-right:8px;letter-spacing:0.5px">3초 요약</span><strong style="font-size:20px;color:#134e4a">핵심요약</strong></div>'
              + f'<p style="margin:10px 0 0;line-height:1.85;color:#1f2937;font-size:16.5px;font-weight:500">{html.escape(plan["lead"]["text"])}</p></div>')

    # 2. 공식 신청 및 조회 대형 CTA 바로가기 박스 (공식 출처가 있을 경우 자동 생성)
    official_sources = [s for s in sources if s.get('source_type') == 'official' and s.get('url')]
    if official_sources:
        buttons = []
        for idx, s in enumerate(official_sources[:3]):
            label = s.get('cta_label')
            if not label:
                title_short = s.get('title', '공식 바로가기').splitlines()[0][:35]
                label = re.sub(r'^[^\w가-힣]+', '', title_short).strip()
            if not label.endswith('바로가기'):
                label = f"{label} 바로가기"
            mb = '0' if idx == min(len(official_sources), 3) - 1 else '10px'
            buttons.append(
                f'<a href="{html.escape(s["url"], quote=True)}" target="_blank" rel="noopener noreferrer" '
                f'style="display:flex;align-items:center;justify-content:space-between;padding:16px 22px;background:#0d7d59;color:#ffffff !important;text-decoration:none !important;border-radius:12px;font-size:16px;font-weight:700;box-shadow:0 4px 12px rgba(13,125,89,0.3);letter-spacing:0.2px;margin-bottom:{mb}">'
                f'<span style="font-size:20px;margin-right:8px">🏛️</span>'
                f'<span style="flex-grow:1;text-align:center">{html.escape(label)}</span>'
                f'<span style="font-size:18px;margin-left:8px">➔</span></a>'
            )
        result += ('<div class="bloguito-cta" style="margin:28px 0 36px;padding:22px 20px;background:#f8fafc;border:1.5px solid #0d7d59;border-radius:14px;text-align:center;box-shadow:0 6px 16px rgba(13,125,89,0.08)">'
                   '<div style="font-size:17px;font-weight:800;color:#0f172a;margin-bottom:6px">🚨 공식 신청 및 조회 서비스 바로가기</div>'
                   '<p style="font-size:14px;color:#475569;margin:0 0 16px;line-height:1.5">아래 공식 링크를 누르시면 정부·공공기관 누리집으로 안전하게 연결됩니다.</p>'
                   f'<div style="max-width:500px;margin:0 auto">{"".join(buttons)}</div></div>')

    # 3. 경량 네이티브 목차 (Table of Contents - 구글 사이트링크 및 모바일 UX 최적화)
    toc_items = []
    for number, section in enumerate(plan['sections'], 1):
        clean_heading = re.sub(r'^\s*(\d+[.)]\s*)?(STEP\s*\d+[.)]?\s*)?', '', section['heading'], flags=re.IGNORECASE).strip()
        toc_items.append(f'<li style="margin:6px 0"><a href="#step-{number}" style="color:#0d7d59;text-decoration:none;font-weight:500">STEP {number}. {html.escape(clean_heading)}</a></li>')
    if plan.get('faq'):
        toc_items.append('<li style="margin:6px 0"><a href="#faq" style="color:#0d7d59;text-decoration:none;font-weight:500">자주 묻는 질문 (FAQ)</a></li>')
    toc_items.append('<li style="margin:6px 0"><a href="#sources" style="color:#0d7d59;text-decoration:none;font-weight:500">공식 출처 및 사실 검증 자료</a></li>')

    result += ('<div class="bloguito-toc" style="padding:18px 22px;margin:24px 0 36px;background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid #0d7d59;border-radius:8px">'
               '<div style="font-weight:700;font-size:16px;color:#1e293b;margin-bottom:10px;display:flex;align-items:center">'
               '<span style="margin-right:8px">📋</span>핵심 목차 한눈에 보기</div>'
               '<ul style="margin:0;padding-left:22px;line-height:1.75;color:#475569;font-size:15px">'
               + ''.join(toc_items) + '</ul></div>')

    # 4. 본문 섹션 (각 소제목에 점프 링크 앵커 ID 매핑)
    for number, section in enumerate(plan['sections'], 1):
        clean_heading = re.sub(r'^\s*(\d+[.)]\s*)?(STEP\s*\d+[.)]?\s*)?', '', section['heading'], flags=re.IGNORECASE).strip()
        result += (f'<h2 id="step-{number}" style="font-size:24px;line-height:1.45;margin:42px 0 18px;padding-bottom:12px;border-bottom:2px solid #e2e8f0;color:#1a202c;display:flex;align-items:center;flex-wrap:wrap">'
                   f'<span style="background:#e6f4ea;color:#0d7d59;font-size:13px;font-weight:700;padding:4px 10px;border-radius:20px;margin-right:10px;letter-spacing:0.5px">STEP {number}</span>'
                   f'{html.escape(clean_heading)}</h2>'
                   + ''.join(paragraph(b) for b in section['paragraphs']))

    # 4. 자주 묻는 질문 (FAQ)
    if plan.get('faq'):
        result += '<h2 id="faq" style="font-size:24px;margin:42px 0 20px;padding-bottom:12px;border-bottom:2px solid #e2e8f0;color:#1a202c">자주 묻는 질문</h2>'
        for faq in plan['faq']:
            result += ('<div class="bloguito-faq" style="padding:20px 22px;margin:18px 0;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px">'
                       '<div style="display:flex;align-items:flex-start;margin-bottom:12px"><span style="background:#2563eb;color:#ffffff;font-weight:800;font-size:13px;padding:3px 9px;border-radius:4px;margin-right:10px;flex-shrink:0;margin-top:2px">Q</span>'
                       f'<h3 style="font-size:19px;line-height:1.5;margin:0;color:#1e293b;font-weight:700">{html.escape(faq["question"])}</h3></div>'
                       '<div style="display:flex;align-items:flex-start;padding-left:2px"><span style="background:#059669;color:#ffffff;font-weight:800;font-size:13px;padding:3px 9px;border-radius:4px;margin-right:10px;flex-shrink:0;margin-top:2px">A</span>'
                       f'<div style="flex-grow:1;color:#334155;line-height:1.8">{html.escape(faq["answer"]["text"])}</div></div></div>')

    # 5. 내부 링크 추천 카드 (체류시간 증대 & 카테고리 연관성 기반 매칭)
    interlink_html = ''
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

    # 6. 공식 출처 및 사실 검증 자료
    ids = []
    for block in [plan['lead']] + [b for s in plan['sections'] for b in s['paragraphs']] + [f['answer'] for f in plan.get('faq', [])]:
        ids.extend(e['source_id'] for e in block['evidence'])
    ids = list(dict.fromkeys(ids))
    links = ''.join(f'<li style="margin:8px 0"><a href="{html.escape(source_map[i]["url"], quote=True)}" rel="noopener noreferrer" style="color:#0d7d59;text-decoration:underline;word-break:break-all">{html.escape(source_map[i]["title"].splitlines()[0][:100])}</a></li>' for i in ids)
    return (result + interlink_html + '<div style="margin-top:44px;padding:22px 24px;background:#fcfdfd;border:1px dashed #cbd5e1;border-radius:10px">'
            '<h2 id="sources" style="font-size:20px;margin:0 0 14px;color:#334155;display:flex;align-items:center"><span style="margin-right:8px">🏛️</span>공식 출처 및 사실 검증 자료</h2>'
            '<ul class="source-list" style="padding-left:22px;margin:0;color:#64748b">' + links + '</ul></div></div>')


def save_report(bundle, report):
    """Internal audit only; source snapshots and failed prose never enter the public post."""
    from uuid import uuid4
    folder = ROOT / 'data' / 'editorial_runs'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (datetime.now(KST).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8]+'.json')
    target.write_text(json.dumps({'bundle': bundle, 'report': report}, ensure_ascii=False, indent=2), encoding='utf-8')
    return target
