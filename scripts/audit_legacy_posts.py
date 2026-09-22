"""Read-only inventory of public WordPress article structure and review candidates.

This script is a triage tool, not a fact checker. Full HTML snapshots stay in an
ignored local directory; the Markdown report contains only public post metadata.
"""

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent-publisher'))
from agents.critical_facts import published_content_risks


KST = timezone(timedelta(hours=9))
FIELDS = 'id,date,modified,slug,link,status,title,excerpt,content,categories,featured_media'
DEFLECTION = re.compile(
    r'(?:첨부(?:자료|파일)|참고\s*\d+).{0,75}(?:찾아|확인하|참고하|대조하)'
    r'|(?:공식\s*(?:자료|안내|사이트|홈페이지|공고)|보도자료).{0,50}'
    r'(?:직접\s*)?(?:찾아보|확인하세|참고하세|읽어보)',
    re.IGNORECASE,
)


def fetch_public_posts(base_url, opener=urlopen):
    """Fetch every published REST page and fail on incomplete or duplicate data."""
    base = base_url.rstrip('/')
    results = []
    expected = None
    page = 1
    while True:
        query = urlencode({'per_page': 100, 'page': page, '_fields': FIELDS})
        req = Request(f'{base}/wp-json/wp/v2/posts?{query}',
                      headers={'User-Agent': 'BloguitoContentQA/1.0'})
        with opener(req, timeout=30) as response:
            batch = json.loads(response.read().decode('utf-8'))
            if page == 1:
                expected = int(response.headers['X-WP-Total'])
                pages = int(response.headers['X-WP-TotalPages'])
        if not isinstance(batch, list):
            raise ValueError('WordPress response is not a list')
        results.extend(batch)
        if page >= pages:
            break
        page += 1
    ids = [post['id'] for post in results]
    if len(results) != expected or len(ids) != len(set(ids)) or any(
            post.get('status') != 'publish' for post in results):
        raise ValueError('Incomplete, duplicate or non-public WordPress inventory')
    return results


def inspect_post(post):
    markup = post['content']['rendered']
    soup = BeautifulSoup(markup, 'html.parser')
    body = soup.select_one('.bloguito-article') or soup
    text = body.get_text(' ', strip=True)
    toc = body.select('.bloguito-toc, .lwptoc, nav[aria-label="본문 목차"]')
    targets = {tag.get('id') for tag in body.select('[id]')}
    broken_toc = sorted({link.get('href') for element in toc
                         for link in element.select('a[href^="#"]')
                         if link.get('href')[1:] not in targets})
    boxes = []
    for element in body.find_all(['div', 'section']):
        style = (element.get('style') or '').lower()
        if not ('background:' in style or 'background-color:' in style or
                'padding:' in style or element.get('class') and
                any(term in ' '.join(element.get('class')) for term in ('summary', 'faq', 'callout'))):
            continue
        children = [child for child in element.find_all(recursive=False)
                    if child.name not in {'script', 'style'}]
        if children and any(child.name == 'p' and 'margin' not in (child.get('style') or '').lower()
                            for child in (children[0], children[-1])):
            boxes.append(' '.join(element.get('class', [])) or element.name)
    matches = [match.group(0)[:130] for match in DEFLECTION.finditer(text)]
    excerpt = BeautifulSoup(post.get('excerpt', {}).get('rendered', ''), 'html.parser').get_text(' ', strip=True)
    title = html.unescape(BeautifulSoup(post['title']['rendered'], 'html.parser').get_text(' ', strip=True))
    known_risks = published_content_risks(title, markup, today=datetime.now(KST).date())
    flags = []
    if body is soup:
        flags.append('legacy_layout')
    if len(toc) == 0 and len(body.select('h2')) >= 3:
        flags.append('missing_toc_candidate')
    if len(toc) > 1:
        flags.append('duplicate_toc')
    if broken_toc:
        flags.append('broken_toc_anchor')
    if boxes:
        flags.append('box_paragraph_spacing_candidate')
    if matches:
        flags.append('reader_deflection_candidate')
    if not excerpt:
        flags.append('empty_excerpt')
    if known_risks:
        flags.append('known_factual_pattern_candidate')
    return {
        'id': post['id'],
        'title': title,
        'url': post['link'], 'published': post['date'], 'modified': post['modified'],
        'rendered_sha256': hashlib.sha256(markup.encode('utf-8')).hexdigest(),
        'text_characters': len(text), 'h2': len(body.select('h2')),
        'toc_count': len(toc), 'toc_broken_anchors': broken_toc,
        'table_count': len(body.select('table')), 'faq_cards': len(body.select('.bloguito-faq')),
        'summary_count': len(body.select('.bloguito-summary')),
        'box_spacing_candidates': boxes[:12], 'deflection_snippets': matches[:8],
        'known_risk_flags': known_risks,
        'fact_review_status': 'unverified', 'visual_review_status': 'unverified',
        'link_behavior_review_status': 'unverified',
        'external_link_count': len([a for a in body.select('a[href]')
                                    if urlparse(a.get('href', '')).hostname not in (None, 'lifeinfo24.org')]),
        'flags': flags,
    }


def markdown_report(rows, base_url, audited_at):
    counts = Counter(flag for row in rows for flag in row['flags'])
    lines = [
        '# 기존 공개 게시물 전수 진단 — ' + audited_at[:10], '',
        f'- 조회 시각: {audited_at} (KST)',
        f'- 출처: {base_url.rstrip("/")}/wp-json/wp/v2/posts (공개 게시물 REST)',
        f'- 조회 완료: {len(rows)}편; 공개 REST 본문만 확인. 원본 WordPress 저장 HTML의 해시와 구분.',
        '- 자동 탐지는 구조 및 검토 후보만 표시한다. 누락 플래그는 사실·사용성 통과가 아니다.',
        '- 모든 글의 사실·화면·외부 링크 동작은 별도 검토 전까지 unverified로 기록한다.',
        '- 공식 원문 최신성, 링크의 실제 실행 가능 여부, 모바일 화면은 개별 검토 전까지 미검증.',
        '', '## 구조 검사 집계', '',
    ]
    lines.extend(f'- `{key}`: {value}편' for key, value in sorted(counts.items()))
    lines.extend(['', '## 글별 검사 결과', '', '| ID | 제목 | 구조 | 글자 수 | 목차 | 표 | FAQ | 검토 후보 |',
                  '| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |'])
    for row in sorted(rows, key=lambda r: r['id']):
        title = row['title'].replace('|', '\\|').replace('\n', ' ')
        flags = ', '.join(row['flags']) or '자동 구조 이상 미탐지'
        layout = '구형' if 'legacy_layout' in row['flags'] else '최신형'
        lines.append(f'| [{row["id"]}]({row["url"]}) | {title} | {layout} | '
                     f'{row["text_characters"]} | {row["toc_count"]} | {row["table_count"]} | '
                     f'{row["faq_cards"]} | {flags} |')
    lines.extend(['', '## 다음 검토 시 필수', '',
                  '1. 글별 공식 발표·개정·시행 연도, 첨부자료의 실제 표와 본문 수치 대조.',
                  '2. 독자 질문에 대한 즉답·대상별 차이·제외·실제 메뉴/행동 링크 제공 여부.',
                  '3. 최신 구조 미적용 글의 서식을 새 원고로 이관할 때 사실 근거와 조건 재검증.',
                  '4. 백업·원본 WordPress 본문 해시·검토 bundle·글별 승인 후 전용 update-existing 사용.',
                  '5. 모바일 360/390px·200% 확대·실제 링크 및 접근성 검사.'])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://lifeinfo24.org')
    parser.add_argument('--snapshot-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    posts = fetch_public_posts(args.url)
    audited_at = datetime.now(KST).isoformat(timespec='seconds')
    rows = [inspect_post(post) for post in posts]
    args.snapshot_dir.mkdir(parents=True, exist_ok=True)
    (args.snapshot_dir / 'public-rest-snapshot.json').write_text(
        json.dumps({'audited_at': audited_at, 'posts': posts}, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.snapshot_dir / 'triage.json').write_text(
        json.dumps({'audited_at': audited_at, 'posts': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(markdown_report(rows, args.url, audited_at), encoding='utf-8')
    print(json.dumps({'published': len(rows), 'flags': dict(Counter(
        flag for row in rows for flag in row['flags'])), 'report': str(args.report)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
