"""Read-only inventory of public WordPress article structure and review candidates.

This script is a triage tool, not a fact checker. Full HTML snapshots stay in an
ignored local directory; the Markdown report contains only public post metadata.
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent-publisher'))
from agents.critical_facts import published_content_risks


KST = timezone(timedelta(hours=9))
FIELDS = 'id,date,modified,slug,link,status,title,excerpt,content,categories,featured_media'
SCHEMA_VERSION = 2
PAGE_SIZE = 100
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
DEFLECTION = re.compile(
    r'(?:첨부(?:자료|파일)|참고\s*\d+).{0,75}(?:찾아|확인하|참고하|대조하)'
    r'|(?:공식\s*(?:자료|안내|사이트|홈페이지|공고)|보도자료).{0,50}'
    r'(?:직접\s*)?(?:찾아보|확인하세|참고하세|읽어보)',
    re.IGNORECASE,
)


def site_url(base_url):
    parsed = urlparse(base_url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise ValueError('A public HTTPS site root without credentials is required')
    return base_url.rstrip('/')


def _header_int(headers, name):
    try:
        value = int(headers[name])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f'Missing or invalid WordPress header: {name}') from exc
    if value < 0:
        raise ValueError(f'Negative WordPress header: {name}')
    return value


def _validate_post(post, host):
    if not isinstance(post, dict) or type(post.get('id')) is not int or post['id'] <= 0:
        raise ValueError('Invalid WordPress post ID')
    if post.get('status') != 'publish':
        raise ValueError('Non-public post in public inventory')
    link = post.get('link')
    if (not isinstance(link, str) or urlparse(link).scheme != 'https' or
            urlparse(link).hostname != host or urlparse(link).username is not None
            or urlparse(link).password is not None or any(char.isspace() for char in link)):
        raise ValueError(f'Invalid canonical public link for post {post["id"]}')
    if not isinstance(post.get('title'), dict) or not isinstance(post['title'].get('rendered'), str):
        raise ValueError(f'Missing title for post {post["id"]}')
    if not isinstance(post.get('content'), dict) or not isinstance(post['content'].get('rendered'), str):
        raise ValueError(f'Missing rendered content for post {post["id"]}')
    if not isinstance(post.get('date'), str) or not isinstance(post.get('modified'), str):
        raise ValueError(f'Missing dates for post {post["id"]}')
    try:
        datetime.fromisoformat(post['date'])
        datetime.fromisoformat(post['modified'])
    except ValueError as exc:
        raise ValueError(f'Invalid dates for post {post["id"]}') from exc


def fetch_public_posts(base_url, opener=urlopen, *, with_metadata=False):
    """Read every REST page, requiring matching headers and exact page sizes.

    No partial list is returned on HTTP, parsing, pagination or schema errors.
    """
    base = site_url(base_url)
    results = []
    expected = pages = None
    page = 1
    while True:
        query = urlencode({'per_page': PAGE_SIZE, 'page': page, '_fields': FIELDS})
        req = Request(f'{base}/wp-json/wp/v2/posts?{query}',
                      headers={'User-Agent': 'BloguitoContentQA/1.0'})
        with opener(req, timeout=30) as response:
            batch = json.loads(response.read().decode('utf-8'))
            total_header = _header_int(response.headers, 'X-WP-Total')
            pages_header = _header_int(response.headers, 'X-WP-TotalPages')
            if page == 1:
                expected, pages = total_header, pages_header
                required_pages = (expected + PAGE_SIZE - 1) // PAGE_SIZE
                if pages != required_pages:
                    raise ValueError('WordPress total and page headers disagree')
            elif (total_header, pages_header) != (expected, pages):
                raise ValueError('WordPress totals changed during pagination')
        if not isinstance(batch, list):
            raise ValueError('WordPress response is not a list')
        size = min(PAGE_SIZE, max(0, expected - PAGE_SIZE * (page - 1)))
        if len(batch) != size:
            raise ValueError(f'WordPress page {page} has {len(batch)} posts, expected {size}')
        for post in batch:
            _validate_post(post, urlparse(base).hostname)
        results.extend(batch)
        if page >= max(1, pages):
            break
        page += 1
    ids = [post['id'] for post in results]
    if len(results) != expected or len(ids) != len(set(ids)):
        raise ValueError('Incomplete or duplicate WordPress inventory')
    if with_metadata:
        return {'posts': results, 'expected_total': expected, 'total_pages': pages,
                'site': base, 'complete': True, 'schema_version': SCHEMA_VERSION}
    return results


def inspect_post(post, today=None, site_host='lifeinfo24.org'):
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
    known_risks = published_content_risks(title, markup, today=today or datetime.now(KST).date())
    external = [a.get('href', '') for a in body.select('a[href]')
                if urlparse(a.get('href', '')).hostname not in (None, site_host)]
    source_heading = any(re.search(r'출처|참고\s*자료|근거\s*자료', h.get_text(' ', strip=True))
                         for h in body.select('h2, h3'))
    source_candidates = []
    if not source_heading and not body.select('.source-list, .source-links'):
        source_candidates.append('source_section_missing_candidate')
    if not external:
        source_candidates.append('external_source_link_missing_candidate')
    link_candidates = []
    for anchor in body.select('a'):
        href = (anchor.get('href') or '').strip()
        reason = None
        if not href or href == '#' or href.lower().startswith(('javascript:', 'data:')):
            reason = 'non_actionable_href_candidate'
        elif urlparse(href).scheme == 'http':
            reason = 'plain_http_link_candidate'
        elif urlparse(href).scheme and urlparse(href).scheme not in ('https', 'mailto', 'tel'):
            reason = 'unsupported_link_scheme_candidate'
        if reason:
            # URL queries may contain access tokens; report a host, never raw href.
            link_candidates.append({'reason': reason, 'host': urlparse(href).hostname})
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
    flags.extend(source_candidates)
    if link_candidates:
        flags.append('link_target_candidate')
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
        'external_link_count': len(external),
        'source_link_candidates': source_candidates, 'link_candidates': link_candidates[:12],
        'flags': flags,
    }


def load_previous(path, site):
    """Accept only a complete prior snapshot produced by this version of the CLI."""
    previous = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(previous, dict) or previous.get('schema_version') != SCHEMA_VERSION
            or previous.get('complete') is not True or previous.get('site') != site
            or not isinstance(previous.get('posts'), list)):
        raise ValueError('Previous snapshot is unverified, legacy format or from another site; create a new baseline')
    posts = previous['posts']
    expected = previous.get('expected_total')
    pages = previous.get('total_pages')
    if (type(expected) is not int or type(pages) is not int or expected != len(posts)
            or pages != (expected + PAGE_SIZE - 1) // PAGE_SIZE):
        raise ValueError('Previous snapshot has inconsistent totals')
    ids = []
    for post in posts:
        _validate_post(post, urlparse(site).hostname)
        ids.append(post['id'])
    if len(set(ids)) != len(ids):
        raise ValueError('Previous snapshot has duplicate IDs')
    host = urlparse(site).hostname
    return {row['id']: row for row in (inspect_post(post, site_host=host) for post in posts)}


def load_review_register(path, site, audited_at):
    """Read manually attested provenance; never infer it from post text or a crawl."""
    data = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or data.get('schema_version') != 1
            or data.get('site') != site or not isinstance(data.get('entries'), list)):
        raise ValueError('Review register has an invalid schema or site')
    entries = {}
    now = datetime.fromisoformat(audited_at)
    for entry in data['entries']:
        if not isinstance(entry, dict):
            raise ValueError('Invalid review register entry')
        post_id = entry.get('id')
        digest = entry.get('rendered_sha256')
        reviewer = entry.get('verified_by')
        urls = entry.get('source_urls')
        if (type(post_id) is not int or post_id <= 0 or post_id in entries
                or not isinstance(digest, str) or not SHA256.fullmatch(digest)
                or entry.get('verification_status') != 'human_verified'
                or not isinstance(reviewer, str) or not reviewer.strip()
                or not isinstance(urls, list) or not urls or any(
                    not isinstance(url, str) or urlparse(url).scheme != 'https'
                    or not urlparse(url).hostname or urlparse(url).username is not None
                    or urlparse(url).password is not None
                    for url in urls)):
            raise ValueError(f'Invalid review provenance for post {post_id}')
        try:
            verified_at = datetime.fromisoformat(entry['verified_at'])
            review_until = date.fromisoformat(entry['review_until'])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f'Invalid review dates for post {post_id}') from exc
        if (verified_at.tzinfo is None or verified_at > now
                or review_until < verified_at.astimezone(KST).date()):
            raise ValueError(f'Inconsistent review dates for post {post_id}')
        entries[post_id] = entry
    return entries


def annotate_review(rows, register, today):
    """A registry provides only a review deadline, never a fact-pass label."""
    for row in rows:
        entry = register.get(row['id']) if register is not None else None
        if register is None:
            row['review_register_status'], row['review_due'] = 'not_supplied', None
        elif entry is None:
            row['review_register_status'], row['review_due'] = 'unregistered', None
            row['flags'].append('review_register_missing_candidate')
        elif entry['rendered_sha256'] != row['rendered_sha256']:
            row['review_register_status'], row['review_due'] = 'content_changed', True
            row['flags'].append('review_evidence_content_changed')
        else:
            due = date.fromisoformat(entry['review_until']) <= today
            row['review_register_status'], row['review_due'] = 'due' if due else 'scheduled', due
            if due:
                row['flags'].append('review_due')


def compare_previous(rows, previous):
    """Report public inventory differences without guessing why a post vanished."""
    new, changed, unchanged = [], [], []
    current = {row['id']: row for row in rows}
    for row in rows:
        before = previous.get(row['id']) if previous is not None else None
        if previous is None:
            row['change_status'], row['change_fields'] = 'baseline_unavailable', []
        elif before is None:
            row['change_status'], row['change_fields'] = 'new', []
            row['flags'].append('new_public_post_candidate')
            new.append(row['id'])
        else:
            fields = [field for field in ('rendered_sha256', 'modified', 'title', 'url')
                      if row[field] != before[field]]
            row['change_status'], row['change_fields'] = ('changed' if fields else 'unchanged'), fields
            if fields:
                row['flags'].append('changed_public_post_candidate')
                changed.append({'id': row['id'], 'fields': fields})
            else:
                unchanged.append(row['id'])
    return {'baseline_available': previous is not None, 'new_post_ids': sorted(new),
            'changed_posts': sorted(changed, key=lambda item: item['id']),
            'missing_from_public_snapshot_ids': sorted(set(previous or {}) - set(current)),
            'unchanged_post_ids': sorted(unchanged),
            'review_due_ids': sorted(row['id'] for row in rows if row['review_due'] is True),
            'review_unknown_ids': sorted(row['id'] for row in rows if row['review_due'] is None)}


def markdown_report(rows, base_url, audited_at, changes=None):
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
    if changes is not None:
        lines.extend(['', '## 반복 감사 변경 및 검토기한', '',
                      f'- 이전의 완전한 스냅샷 사용: {changes["baseline_available"]}',
                      f'- 새 공개 글 ID: {changes["new_post_ids"]}',
                      f'- 메타데이터 또는 공개 HTML 변경 ID: {[r["id"] for r in changes["changed_posts"]]}',
                      f'- 이전 공개 목록에서 사라진 ID(원인 미확인): {changes["missing_from_public_snapshot_ids"]}',
                      f'- 검토기한 도래/원고 변경으로 재검토할 ID: {changes["review_due_ids"]}',
                      f'- 검토기한 미등록·미확인 ID: {changes["review_unknown_ids"]}',
                      '- 검토기한은 별도 사람 검증 기록을 제공했을 때만 판정하며, 모든 본문 사실·시각·링크 상태는 계속 unverified다.'])
    lines.extend(['', '## 글별 검사 결과', '',
                  '| ID | 제목 | 구조 | 글자 수 | 목차 | 표 | FAQ | 변경 | 재검토 | 검토 후보 |',
                  '| ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |'])
    for row in sorted(rows, key=lambda r: r['id']):
        title = (row['title'].replace('\\', '\\\\').replace('|', '\\|')
                 .replace('[', '\\[').replace(']', '\\]').replace('\n', ' '))
        flags = ', '.join(row['flags']) or '자동 구조 이상 미탐지'
        layout = '구형' if 'legacy_layout' in row['flags'] else '최신형'
        change = row.get('change_status', 'baseline_unavailable')
        due = ('필요' if row.get('review_due') is True else
               '기한 전' if row.get('review_due') is False else '미확인')
        lines.append(f'| [{row["id"]}]({row["url"]}) | {title} | {layout} | '
                     f'{row["text_characters"]} | {row["toc_count"]} | {row["table_count"]} | '
                     f'{row["faq_cards"]} | {change} | {due} | {flags} |')
    lines.extend(['', '## 다음 검토 시 필수', '',
                  '1. 글별 공식 발표·개정·시행 연도, 첨부자료의 실제 표와 본문 수치 대조.',
                  '2. 독자 질문에 대한 즉답·대상별 차이·제외·실제 메뉴/행동 링크 제공 여부.',
                  '3. 최신 구조 미적용 글의 서식을 새 원고로 이관할 때 사실 근거와 조건 재검증.',
                  '4. 백업·원본 WordPress 본문 해시·검토 bundle·글별 승인 후 전용 update-existing 사용.',
                  '5. 모바일 360/390px·200% 확대·실제 링크 및 접근성 검사.'])
    return '\n'.join(lines) + '\n'


def write_atomic(path, contents):
    """Only publish complete local reports; a collection failure writes nothing."""
    from uuid import uuid4
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{uuid4().hex}.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as handle:
            handle.write(contents)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://lifeinfo24.org')
    parser.add_argument('--snapshot-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--previous-snapshot', type=Path,
                        help='Complete public-rest-snapshot.json from an earlier v2 run')
    parser.add_argument('--review-register', type=Path,
                        help='Separately human-verified review deadlines; optional JSON schema in docs')
    args = parser.parse_args()
    site = site_url(args.url)
    raw_path = args.snapshot_dir / 'public-rest-snapshot.json'
    triage_path = args.snapshot_dir / 'triage.json'
    output_paths = [path.resolve() for path in (raw_path, triage_path, args.report)]
    if len(output_paths) != len(set(output_paths)):
        parser.error('Snapshot, triage and Markdown output files must be distinct')
    for input_path in (args.previous_snapshot, args.review_register):
        if input_path is not None and input_path.resolve() in output_paths:
            parser.error('Input snapshot/register cannot be overwritten by this run')
    # A malformed prior baseline or register must fail before writing output.
    previous = load_previous(args.previous_snapshot, site) if args.previous_snapshot else None
    audited_at = datetime.now(KST).isoformat(timespec='seconds')
    register = load_review_register(args.review_register, site, audited_at) if args.review_register else None
    inventory = fetch_public_posts(site, with_metadata=True)
    rows = [inspect_post(post, today=date.fromisoformat(audited_at[:10]),
                         site_host=urlparse(site).hostname)
            for post in inventory['posts']]
    annotate_review(rows, register, date.fromisoformat(audited_at[:10]))
    changes = compare_previous(rows, previous)
    changes['orphan_review_register_ids'] = sorted(set(register or {}) - {row['id'] for row in rows})
    inventory['audited_at'] = audited_at
    report = {'schema_version': SCHEMA_VERSION, 'site': site, 'audited_at': audited_at,
              'complete': True, 'expected_total': inventory['expected_total'],
              'total_pages': inventory['total_pages'], 'posts': rows, 'changes': changes,
              'scope': 'public REST rendered HTML only; facts, browser layout and link behavior unverified'}
    # The complete snapshot is written last and serves as the baseline marker.
    write_atomic(triage_path, json.dumps(report, ensure_ascii=False, indent=2))
    write_atomic(args.report, markdown_report(rows, site, audited_at, changes))
    write_atomic(raw_path, json.dumps(inventory, ensure_ascii=False, indent=2))
    print(json.dumps({'published': len(rows), 'flags': dict(Counter(
        flag for row in rows for flag in row['flags'])), 'changes': changes,
        'snapshot': str(raw_path), 'report': str(args.report)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
