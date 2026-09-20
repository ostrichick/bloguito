"""Read-only public WordPress audit of a narrow set of confirmed policy regression patterns.

Run before publication and after revisions. Zero findings is NOT a fact-check pass.
"""
import argparse
import html
import json
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent-publisher'))
from agents.critical_facts import published_content_risks


def scan(base_url):
    results = []
    page = 1
    while True:
        url = f"{base_url.rstrip('/')}/wp-json/wp/v2/posts?per_page=100&page={page}&_fields=id,title,content,link,status"
        try:
            with urlopen(url, timeout=20) as response:
                posts = json.loads(response.read().decode('utf-8'))
        except Exception as exc:
            if page > 1 and '404' in str(exc):
                break
            raise
        if not isinstance(posts, list):
            raise ValueError('Expected posts list')
        for post in posts:
            title = html.unescape(post['title']['rendered'])
            flags = published_content_risks(title, post['content']['rendered'])
            if flags:
                results.append({'id': post['id'], 'title': title, 'issues': flags, 'url': post.get('link', '')})
        if len(posts) < 100:
            break
        page += 1
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='https://lifeinfo24.org')
    parser.add_argument('--strict', action='store_true', help='exit 2 if any known stale claims found')
    args = parser.parse_args()
    results = scan(args.url)
    print(json.dumps({'known-risk-findings': len(results), 'findings': results,
                      'scope': 'narrow regression patterns only; absence is not verification'},ensure_ascii=False,indent=2))
    if args.strict and results:
        sys.exit(2)

if __name__ == '__main__':
    main()
