"""Editorially reviewed search briefs; never infer search volume from RSS."""
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

BRIEFS = Path(__file__).resolve().parents[1] / 'data' / 'search_briefs.json'
INVENTORY = BRIEFS.with_name('wordpress_inventory.json')


def duplicate_posts(brief, posts):
    import re
    def norm(value):
        return re.sub(r'[^가-힣a-z0-9]', '', value.casefold()).replace('앙코르', '앵콜')
    terms = brief.get('required_title_terms', [])
    official = set(brief.get('official_urls', []))
    return [p for p in posts if p.get('post_status') in {'publish', 'draft', 'pending', 'future', 'private'}
            and ((terms and all(norm(t) in norm(p.get('post_title', '')) for t in terms))
                 or any(url in p.get('post_content', '') for url in official))]


def load_briefs(category, today=None):
    today = today or date.today()
    briefs = json.loads(BRIEFS.read_text(encoding='utf-8'))
    try:
        inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
        if inventory['checked_on'] != today.isoformat():
            return []
        posts = inventory['posts']
        if not isinstance(posts, list):
            return []
    except (OSError, ValueError, KeyError):
        return []  # An unavailable inventory is not evidence that no duplicate exists.
    result = []
    for brief in briefs:
        if brief.get('category_key') != category or not brief.get('approved'):
            continue
        if duplicate_posts(brief, posts):
            continue
        try:
            if not date.fromisoformat(brief['reviewed_at']) <= today <= date.fromisoformat(brief['review_until']):
                continue
        except (KeyError, ValueError):
            continue
        if not all(brief.get(k) for k in ('entity', 'primary_keyword', 'question', 'angle', 'official_urls', 'serp_urls', 'queries')):
            continue
        if brief['entity'] not in brief['primary_keyword']:
            continue
        if not all(urlparse(url).scheme == 'https' and urlparse(url).hostname for url in brief['official_urls'] + brief['serp_urls']):
            continue
        result.append(brief)
    return result


def matches_brief(title, brief):
    return all(token in title for token in brief['required_title_terms'])
