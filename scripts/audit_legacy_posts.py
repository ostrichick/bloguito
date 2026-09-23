"""Read-only inventory of public WordPress article structure and review candidates.

This script is a triage tool, not a fact checker. Full HTML snapshots stay in an
ignored local directory; the Markdown report contains only public post metadata.
"""

import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
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
RUN_NAME = re.compile(r'\d{8}T\d{6}Z-[0-9a-f]{8}\Z')
RECURRING_SCHEMA = 1
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


def _read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _linked_path(path):
    """Reject symlinks and Windows junctions before reading/writing audit runs."""
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def _runs_directory(state):
    runs = state / 'runs'
    if _linked_path(runs) or (runs.exists() and
                             (not runs.is_dir() or runs.resolve() != state.resolve() / 'runs')):
        raise ValueError('Audit runs directory is linked or unsafe')
    return runs


def _safe_state_dir(directory, site, *, dry_run=False):
    """A marked, dedicated local directory is mandatory; never adopt other files."""
    path = directory.resolve()
    project = Path(__file__).resolve().parents[1]
    if path == project or path == path.parent or any(
            path == project / name or (project / name) in path.parents
            for name in ('wordpress', 'agent-publisher', 'docs', 'scripts', '.git')):
        raise ValueError('Refusing a state directory overlapping project or runtime files')
    marker = path / '.bloguito-read-only-audit.json'
    if path.exists():
        if not path.is_dir() or path.is_symlink():
            raise ValueError('Audit state must be an ordinary directory')
        if marker.is_file():
            info = _read_json(marker)
            if info != {'schema_version': RECURRING_SCHEMA, 'site': site,
                         'purpose': 'public-rest-read-only-audit'}:
                raise ValueError('Audit state marker does not match this site and schema')
        elif any(path.iterdir()):
            raise ValueError('Refusing an occupied directory without the audit ownership marker')
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)
        if not marker.is_file():
            write_atomic(marker, json.dumps({'schema_version': RECURRING_SCHEMA,
                'site': site, 'purpose': 'public-rest-read-only-audit'}))
    return path


def _read_checkpoint(state, site):
    """A single validated pointer is the only successful-run baseline."""
    checkpoint = state / 'latest.json'
    runs = _runs_directory(state)
    if runs.exists() and any(item.name.startswith('.pending-') for item in runs.iterdir()):
        raise ValueError('Incomplete previous audit run; inspect pending directory manually')
    if not checkpoint.exists():
        if runs.exists() and any(runs.iterdir()):
            raise ValueError('Uncheckpointed audit run exists; manual inspection required')
        return None, None
    data = _read_json(checkpoint)
    run_id = data.get('run_id') if isinstance(data, dict) else None
    if (not isinstance(run_id, str) or not RUN_NAME.fullmatch(run_id)
            or data.get('schema_version') != RECURRING_SCHEMA or data.get('site') != site
            or not isinstance(data.get('snapshot_sha256'), str)
            or not SHA256.fullmatch(data['snapshot_sha256'])):
        raise ValueError('Invalid recurring audit checkpoint')
    run = runs / run_id
    if (_linked_path(run) or not run.is_dir() or
            run.resolve().parent != runs.resolve()):
        raise ValueError('Checkpoint run directory is linked or unsafe')
    source = run / 'public-rest-snapshot.json'
    if source.is_symlink() or not source.is_file():
        raise ValueError('Checkpoint snapshot is missing or unsafe')
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != data['snapshot_sha256']:
        raise ValueError('Checkpoint snapshot hash mismatch')
    previous = load_previous(source, site)
    stamp = datetime.fromisoformat(data['audited_at'])
    if stamp.tzinfo is None:
        raise ValueError('Checkpoint timestamp has no timezone')
    return previous, data


def _summary(report, checkpoint, prior_attempt, now, expected_hours):
    changes = report['changes']
    previously_flagged = checkpoint.get('flag_map', {}) if checkpoint else {}
    new_flags = {}
    if checkpoint is not None:
        for row in report['posts']:
            before = set(previously_flagged.get(str(row['id']), []))
            introduced = sorted(set(row['flags']) - before)
            if introduced:
                new_flags[str(row['id'])] = introduced
    elapsed = None
    missed = 0
    if checkpoint:
        last = datetime.fromisoformat(checkpoint['audited_at'])
        elapsed = round((now - last).total_seconds() / 3600, 2)
        if elapsed < -0.1:
            raise ValueError('System clock precedes the last successful audit')
        missed = max(0, math.ceil(max(0, elapsed) / expected_hours) - 1)
    recovered_failure = bool(prior_attempt and prior_attempt.get('status') == 'failed')
    codes = []
    if changes['new_post_ids'] or changes['changed_posts'] or changes['missing_from_public_snapshot_ids']:
        codes.append('public_inventory_changed')
    if changes['review_due_ids']:
        codes.append('review_due')
    if new_flags:
        codes.append('new_layout_source_or_review_candidates')
    if missed:
        codes.append('missed_expected_runs')
    if recovered_failure:
        codes.append('recovered_prior_failure')
    return {
        'status': 'complete', 'audited_at': report['audited_at'],
        'public_post_count': report['expected_total'],
        'baseline_available': changes['baseline_available'],
        'new_post_ids': changes['new_post_ids'],
        'changed_posts': changes['changed_posts'],
        'missing_from_public_snapshot_ids': changes['missing_from_public_snapshot_ids'],
        'review_due_ids': changes['review_due_ids'],
        'review_unknown_count': len(changes['review_unknown_ids']),
        'flag_counts': dict(Counter(flag for row in report['posts'] for flag in row['flags'])),
        'new_flags_by_post_id': new_flags,
        'hours_since_previous_success': elapsed,
        'missed_expected_runs': missed, 'recovered_prior_failure': recovered_failure,
        'alert_codes': codes, 'attention_required': bool(codes),
        'scope': 'public WordPress REST only; facts, visual behavior and links unverified',
    }


def _read_prior_attempt(state):
    path = state / 'last-attempt.json'
    if not path.exists():
        return None
    attempt = _read_json(path)
    if not isinstance(attempt, dict) or attempt.get('status') not in ('failed', 'complete'):
        raise ValueError('Invalid previous audit attempt record')
    return attempt


_RUN_FILES = frozenset({'public-rest-snapshot.json', 'triage.json', 'report.md',
                        'alert-summary.json', 'run-manifest.json'})
_RUN_DIGESTS = ('public-rest-snapshot.json', 'triage.json', 'report.md')


def _validate_owned_run(folder, runs, site):
    """Treat unexpected files, unmarked history and invalid run contents as foreign."""
    if (not RUN_NAME.fullmatch(folder.name) or _linked_path(folder) or
            not folder.is_dir() or folder.parent.resolve() != runs.resolve() or
            folder.resolve().parent != runs.resolve()):
        raise ValueError('Unsafe or unowned audit run directory')
    entries = list(folder.iterdir())
    if {entry.name for entry in entries} != _RUN_FILES or any(
            _linked_path(entry) or not entry.is_file() or
            entry.resolve().parent != folder.resolve() for entry in entries):
        raise ValueError('Audit run has foreign, linked or incomplete files')
    manifest = _read_json(folder / 'run-manifest.json')
    if (not isinstance(manifest, dict) or set(manifest) != {
            'schema_version', 'site', 'run_id', 'audited_at', 'sha256'} or
            manifest['schema_version'] != RECURRING_SCHEMA or
            manifest['site'] != site or manifest['run_id'] != folder.name or
            not isinstance(manifest['audited_at'], str) or
            not isinstance(manifest['sha256'], dict) or
            set(manifest['sha256']) != set(_RUN_DIGESTS)):
        raise ValueError('Audit run ownership manifest is invalid')
    stamp = datetime.fromisoformat(manifest['audited_at'])
    if (stamp.tzinfo is None or
            stamp.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ') != folder.name[:16]):
        raise ValueError('Audit run timestamp does not match directory')
    for name in _RUN_DIGESTS:
        claimed = manifest['sha256'][name]
        if (not isinstance(claimed, str) or not SHA256.fullmatch(claimed) or
                hashlib.sha256((folder / name).read_bytes()).hexdigest() != claimed):
            raise ValueError('Audit run immutable content hash mismatch')
    snapshot = _read_json(folder / 'public-rest-snapshot.json')
    # Reuse the exact schema, complete count and public-post checks applied to
    # previous checkpoints. This is not an endorsement of article factuality.
    load_previous(folder / 'public-rest-snapshot.json', site)
    report = _read_json(folder / 'triage.json')
    alert = _read_json(folder / 'alert-summary.json')
    post_ids = [post['id'] for post in snapshot['posts']]
    if (snapshot.get('audited_at') != manifest['audited_at'] or
            not isinstance(report, dict) or report.get('schema_version') != SCHEMA_VERSION or
            report.get('site') != site or report.get('complete') is not True or
            report.get('audited_at') != manifest['audited_at'] or
            report.get('expected_total') != snapshot['expected_total'] or
            report.get('total_pages') != snapshot['total_pages'] or
            not isinstance(report.get('posts'), list) or
            [row.get('id') for row in report['posts'] if isinstance(row, dict)] != post_ids or
            not isinstance(alert, dict) or alert.get('status') != 'complete' or
            alert.get('audited_at') != manifest['audited_at']):
        raise ValueError('Audit run outputs disagree with ownership manifest')
    return manifest


def _prune_owned_runs(state, keep, current_id):
    """Only remove this tool's old complete runs after checkpoint publication."""
    runs = _runs_directory(state)
    checkpoint = _read_json(state / 'latest.json')
    if (checkpoint.get('run_id') != current_id or
            checkpoint.get('site') is None or not RUN_NAME.fullmatch(current_id)):
        raise ValueError('Audit retention checkpoint does not match current run')
    folders = sorted(runs.iterdir())
    # Validate every entry before even deciding which runs to delete. Old runs
    # without manifests are preserved for deliberate manual migration.
    manifests = {item.name: _validate_owned_run(item, runs, checkpoint['site'])
                 for item in folders}
    if current_id not in manifests or checkpoint.get('snapshot_sha256') != (
            manifests[current_id]['sha256']['public-rest-snapshot.json']):
        raise ValueError('Audit retention current run does not match checkpoint')
    # The run name contains a UTC second followed by a RANDOM suffix, so
    # sorting names may delete a newer run when several runs share a second.
    # The source timestamp has microsecond precision for newly created runs.
    older = sorted((item for item in folders if item.name != current_id),
                   key=lambda item: datetime.fromisoformat(manifests[item.name]['audited_at']))
    slots = keep - 1
    if len(older) > slots and datetime.fromisoformat(
            manifests[older[-slots - 1].name]['audited_at']) == datetime.fromisoformat(
            manifests[older[-slots].name]['audited_at']):
        # Historical same-second runs cannot be reliably ordered by their
        # random suffix; preserve all until a human decides which to retain.
        raise ValueError('Ambiguous audit retention timestamps; no runs deleted')
    keep_ids = {current_id} | {item.name for item in older[-slots:]}
    candidates = [item for item in folders if item.name not in keep_ids]
    # Validate the whole deletion set again before any removal, including
    # unexpected children added after the initial manifest check.
    for item in candidates:
        _validate_owned_run(item, runs, checkpoint['site'])
    for item in candidates:
        shutil.rmtree(item)
    return len(candidates)


def recurring_audit(state_dir, site, *, opener=urlopen, review_register=None,
                    expected_hours=24, retain=14, dry_run=False, now=None):
    """One manual scheduler-ready iteration. Never installs a timer or sends alerts.

    Complete run directories are immutable; the atomic latest.json pointer changes
    only after every snapshot and report is durable. Failed fetches retain baseline.
    """
    if not 1 <= expected_hours <= 24 * 31 or type(retain) is not int or not 2 <= retain <= 365:
        raise ValueError('Expected hours must be 1..744 and retention 2..365 complete runs')
    site = site_url(site)
    state = _safe_state_dir(Path(state_dir), site, dry_run=dry_run)
    checkpoint, previous = None, None
    previous, checkpoint = _read_checkpoint(state, site)
    prior_attempt = _read_prior_attempt(state)
    current = now or datetime.now(KST)
    if current.tzinfo is None:
        raise ValueError('Audit clock must contain a timezone')
    run_id = current.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    lock = state / '.audit.lock'
    locked = False
    pending = None
    stage = 'lock'
    try:
        if dry_run:
            if lock.exists():
                raise ValueError('Audit lock exists; dry-run cannot race a live iteration')
        else:
            try:
                lock.mkdir()
            except FileExistsError as exc:
                raise ValueError('Audit already locked; inspect owner before manual recovery') from exc
            locked = True
            write_atomic(lock / 'owner.json', json.dumps({
                'pid': os.getpid(), 'started_at': current.isoformat(), 'run_id': run_id}))
        stage = 'collect'
        inventory = fetch_public_posts(site, opener=opener, with_metadata=True)
        audited_at = current.isoformat(timespec='microseconds')
        rows = [inspect_post(post, today=current.astimezone(KST).date(),
                             site_host=urlparse(site).hostname) for post in inventory['posts']]
        register = load_review_register(review_register, site, audited_at) if review_register else None
        annotate_review(rows, register, current.astimezone(KST).date())
        changes = compare_previous(rows, previous)
        changes['orphan_review_register_ids'] = sorted(set(register or {}) - {row['id'] for row in rows})
        inventory['audited_at'] = audited_at
        report = {'schema_version': SCHEMA_VERSION, 'site': site, 'audited_at': audited_at,
                  'complete': True, 'expected_total': inventory['expected_total'],
                  'total_pages': inventory['total_pages'], 'posts': rows, 'changes': changes,
                  'scope': 'public REST only; facts, browser layout and links unverified'}
        summary = _summary(report, checkpoint, prior_attempt, current, expected_hours)
        summary['dry_run'] = dry_run
        if dry_run:
            return summary
        stage = 'commit'
        runs = _runs_directory(state)
        runs.mkdir(exist_ok=True)
        pending = runs / ('.pending-' + uuid4().hex)
        pending.mkdir()
        raw_json = json.dumps(inventory, ensure_ascii=False, indent=2)
        write_atomic(pending / 'triage.json', json.dumps(report, ensure_ascii=False, indent=2))
        write_atomic(pending / 'report.md', markdown_report(rows, site, audited_at, changes))
        write_atomic(pending / 'alert-summary.json', json.dumps(summary, ensure_ascii=False, indent=2))
        write_atomic(pending / 'public-rest-snapshot.json', raw_json)
        write_atomic(pending / 'run-manifest.json', json.dumps({
            'schema_version': RECURRING_SCHEMA, 'site': site,
            'run_id': run_id, 'audited_at': audited_at,
            # alert-summary.json is rewritten after retention and cannot carry
            # an immutable digest without making genuine runs self-invalidating.
            'sha256': {name: hashlib.sha256((pending / name).read_bytes()).hexdigest()
                       for name in _RUN_DIGESTS}}, ensure_ascii=False, indent=2))
        destination = runs / run_id
        pending.rename(destination)
        pending = None
        marker = {'schema_version': RECURRING_SCHEMA, 'site': site, 'run_id': run_id,
                  'audited_at': audited_at,
                  # Text-mode newline conversion on Windows changes on-disk bytes.
                  'snapshot_sha256': hashlib.sha256(
                      (destination / 'public-rest-snapshot.json').read_bytes()).hexdigest(),
                  'post_ids': [row['id'] for row in rows],
                  'flag_map': {str(row['id']): row['flags'] for row in rows}}
        write_atomic(state / 'latest.json', json.dumps(marker, ensure_ascii=False, indent=2))
        write_atomic(state / 'last-attempt.json', json.dumps({
            'status': 'complete', 'audited_at': audited_at, 'run_id': run_id}))
        stage = 'retention'
        try:
            summary['pruned_runs'] = _prune_owned_runs(state, retain, run_id)
        except (OSError, ValueError) as exc:
            summary['retention_warning'] = type(exc).__name__
            summary['attention_required'] = True
            summary['alert_codes'].append('retention_requires_attention')
        # Keep the public-facing on-disk summary consistent with post-commit
        # retention outcome. The complete snapshot/checkpoint is unaffected.
        write_atomic(destination / 'alert-summary.json', json.dumps(
            summary, ensure_ascii=False, indent=2))
        return summary
    except Exception as exc:
        if not dry_run and locked:
            try:
                write_atomic(state / 'last-attempt.json', json.dumps({
                    'status': 'failed', 'audited_at': current.isoformat(timespec='seconds'),
                    'stage': stage, 'error_type': type(exc).__name__}))
            except OSError:
                pass
        raise
    finally:
        if pending is not None and pending.exists():
            shutil.rmtree(pending)
        if locked:
            # Never clear a preexisting/stale lock belonging to another process.
            (lock / 'owner.json').unlink(missing_ok=True)
            lock.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://lifeinfo24.org')
    parser.add_argument('--snapshot-dir', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--previous-snapshot', type=Path,
                        help='Complete public-rest-snapshot.json from an earlier v2 run')
    parser.add_argument('--review-register', type=Path,
                        help='Separately human-verified review deadlines; optional JSON schema in docs')
    parser.add_argument('--recurring-state-dir', type=Path,
                        help='Dedicated local state directory; one iteration, NEVER registers a schedule')
    parser.add_argument('--dry-run', action='store_true',
                        help='Read public REST and compare checkpoint, but do not change local state')
    parser.add_argument('--expected-hours', type=float, default=24,
                        help='Expected frequency for missed-run detection (default: 24)')
    parser.add_argument('--retain', type=int, default=14,
                        help='Keep this many complete local snapshots (2..365; default: 14)')
    parser.add_argument('--strict-alert', action='store_true',
                        help='Exit 2 for attention_required, without sending notifications')
    args = parser.parse_args()
    if args.recurring_state_dir:
        if args.snapshot_dir or args.report or args.previous_snapshot:
            parser.error('Recurring state mode cannot be combined with individual snapshot/report paths')
        try:
            summary = recurring_audit(args.recurring_state_dir, args.url,
                review_register=args.review_register, expected_hours=args.expected_hours,
                retain=args.retain, dry_run=args.dry_run)
        except Exception as exc:
            # URL and raw exception strings might contain credentials. Report a type only.
            print(json.dumps({'status': 'failed', 'attention_required': True,
                              'alert_codes': ['audit_failed'],
                              'error_type': type(exc).__name__}))
            raise SystemExit(3) from None
        print(json.dumps(summary, ensure_ascii=False))
        if args.strict_alert and summary['attention_required']:
            raise SystemExit(2)
        return
    if args.dry_run or args.strict_alert or args.expected_hours != 24 or args.retain != 14:
        parser.error('Recurring flags require --recurring-state-dir')
    if args.snapshot_dir is None or args.report is None:
        parser.error('One-shot mode requires both --snapshot-dir and --report')
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
