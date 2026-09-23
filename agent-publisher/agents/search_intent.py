"""Editorially reviewed search briefs; never infer search volume from RSS."""
import json
from html import unescape
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

BRIEFS = Path(__file__).resolve().parents[1] / 'data' / 'search_briefs.json'
INVENTORY = BRIEFS.with_name('wordpress_inventory.json')


def _url_outside_verified_source_footer(content, url):
    """An evidence citation shared by distinct articles is not a duplicate topic.

    Keep the existing strong URL check for legacy/unstructured articles and for
    action links or body links outside the known rendered source footer.
    """
    if url not in unescape(content):
        return False
    if 'source-list' not in content and '공식 근거 및 확인 경로' not in content:
        return True
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')
    for source_list in soup.select('ul.source-list'):
        heading = source_list.find_previous_sibling('h2')
        if heading and heading.get('id') == 'sources':
            source_list.decompose()
    # Three pre-renderer flu posts have an explicit citation list without the
    # modern class/id. Only a KDCA attachment in that exact list is exempt:
    # a PDF linked in the article body or an action card still counts.
    parsed = urlparse(url)
    if (parsed.hostname in {'kdca.go.kr', 'www.kdca.go.kr'}
            and parsed.path.startswith('/bbs/kdca/')
            and parsed.path.endswith('/download.do')):
        for heading in soup.select('h2'):
            if heading.get_text(' ', strip=True) != '공식 근거 및 확인 경로':
                continue
            source_list = heading.find_next_sibling()
            if not source_list or source_list.name != 'ul':
                continue
            for item in source_list.find_all('li', recursive=False):
                anchors = item.find_all('a', recursive=False)
                if len(anchors) == 1 and anchors[0].get('href') == url:
                    item.decompose()
    return url in unescape(str(soup))


def duplicate_posts(brief, posts):
    import re
    def norm(value):
        return re.sub(r'[^가-힣a-z0-9]', '', value.casefold()).replace('앙코르', '앵콜')
    terms = brief.get('required_title_terms', [])
    official = set(brief.get('official_urls', []))
    # Editing an existing article can cite the same broad official policy page
    # as a distinct article. New-post discovery still rejects any source URL
    # overlap, including source-only citations, as its conservative safeguard.
    updating_existing = isinstance(brief.get('existing_post_id'), int)
    return [p for p in posts if p.get('post_status') in {'publish', 'draft', 'pending', 'future', 'private'}
            and ((terms and all(norm(t) in norm(p.get('post_title', '')) for t in terms))
                 or any((_url_outside_verified_source_footer(p.get('post_content', ''), url)
                         if updating_existing else url in unescape(p.get('post_content', '')))
                        for url in official))]


def load_briefs(category, today=None):
    from agents.editorial import topic_reasons
    from agents.temporal_validation import KST
    from datetime import datetime
    today = today or datetime.now(KST).date()
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
        if topic_reasons(brief, today):
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
