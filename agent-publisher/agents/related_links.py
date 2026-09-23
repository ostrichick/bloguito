"""Conservative preservation of explicit internal post navigation on updates."""

from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup


def internal_post_ids(markup, site='https://lifeinfo24.org'):
    """Recognize only WordPress's unambiguous ?p=ID post links, not other URLs."""
    found = set()
    for anchor in BeautifulSoup(markup, 'html.parser').select('a[href]'):
        parsed = urlparse(urljoin(site + '/', anchor['href']))
        if parsed.scheme != 'https' or parsed.hostname != urlparse(site).hostname:
            continue
        query = parse_qs(parsed.query, keep_blank_values=True)
        if set(query) != {'p'} or len(query['p']) != 1:
            continue
        target = query['p'][0]
        if target.isascii() and target.isdecimal() and int(target) > 0:
            found.add(int(target))
    return found


def missing_internal_post_ids(original, proposed):
    """Return deleted explicit internal post targets; no silent approval of loss."""
    return sorted(internal_post_ids(original) - internal_post_ids(proposed))
