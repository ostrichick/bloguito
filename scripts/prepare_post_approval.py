"""Read-only, fail-closed WordPress public-post approval package.

Read the live *stored* post and complete status inventory over the configured
SSH alias. Write private originals and reviewable diffs locally under ignored
tmp/ only. This script cannot update WordPress or deploy a server file.
"""

import argparse
import difflib
import hashlib
import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent-publisher'))

from agents.editorial import render, validate_bundle  # noqa: E402
from agents.related_links import missing_internal_post_ids  # noqa: E402
from agents.editorial_writer import fetch_sources  # noqa: E402
from agents.temporal_validation import KST  # noqa: E402


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_wp_json(host, arguments):
    """Only a fixed wp post get/list READ path; never forward arbitrary commands."""
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+', host):
        raise ValueError('invalid_ssh_alias')
    safe_list = ['post', 'list', '--post_type=post',
        '--post_status=publish,draft,pending,future,private', '--posts_per_page=-1',
        '--fields=ID,post_title,post_status,post_content', '--format=json']
    safe_get = (len(arguments) == 4 and arguments[:2] == ['post', 'get']
                and re.fullmatch(r'[1-9][0-9]*', arguments[2])
                and arguments[3] == '--format=json')
    if arguments != safe_list and not safe_get:
        raise ValueError('read_only_wp_commands_only')
    cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', host,
           'sudo docker exec wordpress_app wp ' + ' '.join(arguments) + ' --allow-root']
    result = subprocess.run(cmd, check=True, capture_output=True, timeout=90)
    return json.loads(result.stdout.decode('utf-8-sig'))


def live_post_and_inventory(host, post_id):
    if type(post_id) is not int or post_id <= 0:
        raise ValueError('invalid_post_id')
    inventory = read_wp_json(host, ['post', 'list', '--post_type=post',
        '--post_status=publish,draft,pending,future,private', '--posts_per_page=-1',
        '--fields=ID,post_title,post_status,post_content', '--format=json'])
    post = read_wp_json(host, ['post', 'get', str(post_id), '--format=json'])
    if not isinstance(inventory, list) or not inventory:
        raise ValueError('live_inventory_missing')
    ids = [row['ID'] for row in inventory]
    if (len(ids) != len(set(ids)) or any(type(item) is not int for item in ids)
            or not all(row.get('post_status') in {'publish', 'draft', 'pending',
                                                  'future', 'private'} for row in inventory)):
        raise ValueError('invalid_live_inventory')
    match = [row for row in inventory if row['ID'] == post_id]
    if (len(match) != 1 or match[0]['post_status'] != 'publish'
            or post.get('ID') != post_id or post.get('post_status') != 'publish'
            or match[0]['post_content'] != post.get('post_content')
            or match[0]['post_title'] != post.get('post_title')):
        raise ValueError('live_post_inventory_disagree')
    return post, inventory


def text_blocks(markup):
    soup = BeautifulSoup(markup, 'html.parser')
    for item in soup(['script', 'style', 'iframe', 'form', 'noscript']):
        item.decompose()
    blocks = []
    for item in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'tr']):
        if item.find_parent(['li', 'tr']) and item.name not in {'li', 'tr'}:
            continue
        value = ' '.join(item.get_text(' ', strip=True).split())
        if value:
            blocks.append(f'{item.name.upper()} | {value}')
    # Content-only text comparison misses standalone CTAs and href-only changes.
    # Keep link destinations visible in the reviewable diff without executing them.
    for anchor in soup.select('a[href]'):
        href = anchor.get('href', '').strip()
        if href and not href.startswith('#'):
            label = ' '.join(anchor.get_text(' ', strip=True).split())
            blocks.append(f'LINK | {label} -> {href}')
    return blocks


def private_json(path, value):
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write('\n')
    os.chmod(path, 0o600)


def prepare(post_id, bundle_path, out_dir, host='bloguito'):
    root_tmp = (ROOT / 'tmp').resolve()
    out_dir = out_dir.resolve()
    if out_dir == root_tmp or root_tmp not in out_dir.parents:
        raise ValueError('approval_output_must_be_inside_gitignored_tmp')
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError('approval_package_must_use_new_empty_directory')
    bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
    if bundle.get('brief', {}).get('existing_post_id') != post_id:
        raise ValueError('bundle_target_post_id_mismatch')
    post, rows = live_post_and_inventory(host, post_id)
    current = post['post_content']
    proposed = render(bundle['plan'], bundle['sources'])
    other_posts = [p for p in rows if p['ID'] != post_id]
    report = validate_bundle(bundle, {'checked_on': datetime.now(KST).date().isoformat(),
                                      'posts': other_posts})
    reasons = list(report['reasons'])
    lost_related_ids = missing_internal_post_ids(current, proposed)
    if lost_related_ids:
        reasons.append('original_internal_post_navigation_missing')
    if post['post_title'] != bundle['plan']['title']:
        reasons.append('reviewed_plan_would_not_preserve_current_title')
    try:
        reread = fetch_sources(bundle['brief'])
        first = {s['url']: s['sha256'] for s in bundle['sources']}
        second = {s['url']: s['sha256'] for s in reread}
        if first != second:
            reasons.append('official_sources_changed_since_review')
    except Exception as error:
        second = None
        reasons.append('official_source_refetch_failed:' + type(error).__name__)

    # Exclude non-public title/content of other draft/private posts from the
    # package; the inventory is used transiently for the full duplicate check.
    out_dir.mkdir(parents=True, exist_ok=True)
    backup = out_dir / 'post-original.PRIVATE.json'
    private_json(backup, post)
    before = text_blocks(current)
    after = text_blocks(proposed)
    delta = list(difflib.unified_diff(before, after,
                fromfile='original-published-text', tofile='reviewed-proposed-text',
                lineterm=''))
    (out_dir / 'content-diff.txt').write_text('\n'.join(delta) + '\n', encoding='utf-8')
    (out_dir / 'proposed-reviewed.html').write_text(proposed, encoding='utf-8')
    doc = ('<!doctype html><html lang="ko"><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>게시물 승인 전 비교 — 미적용</title>'
           '<style>body{font:16px/1.7 system-ui,sans-serif;margin:20px;max-width:1450px}'
           '.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr));gap:20px}'
           'section{min-width:0;border:1px solid #ccd;padding:18px;border-radius:8px}'
           'iframe{width:100%;height:850px;border:1px solid #ccd}'
           'pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
           '<h1>게시물 수정 승인 전 비교 — 공개 사이트 미적용</h1>'
           '<p>왼쪽은 WordPress 원본의 공개 텍스트를 안전하게 추출한 비교본입니다. '
           '오른쪽은 독립 정적 렌더러 HTML이며 운영 테마 화면이 아닙니다.</p>'
           '<div class="cols"><section><h2>기존 게시물 텍스트</h2><pre>'
           + html.escape('\n\n'.join(before)) + '</pre></section>'
           '<section><h2>검토한 변경안</h2><iframe title="승인 전 변경안" sandbox="" srcdoc="'
           + html.escape(proposed, quote=True) + '"></iframe></section></div></html>')
    (out_dir / 'compare-preview.html').write_text(doc, encoding='utf-8')
    manifest = {
        'post_id': post_id, 'captured_at': datetime.now(KST).isoformat(),
        'approval_status': 'prepared_not_authorized',
        'preflight_status': 'ready' if not reasons else 'blocked',
        'reasons': sorted(set(reasons)), 'validation_report': report,
        'original_stored_content_sha256': sha(current),
        'original_full_backup_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(),
        'proposed_rendered_content_sha256': sha(proposed),
        'published_status': post['post_status'], 'original_title': post['post_title'],
        'original_slug': post.get('post_name'),
        'original_published_at': post.get('post_date'),
        'original_modified_at': post.get('post_modified'),
        'original_excerpt_sha256': sha(post.get('post_excerpt', '')),
        'source_hashes_match_live': second == first if second is not None else None,
        'lost_internal_post_ids': lost_related_ids,
        'before_text_blocks': len(before), 'after_text_blocks': len(after),
        'changed_text_diff_lines': len(delta),
        'changes_allowed_if_later_approved': ['post_content', 'post_excerpt_only_if_empty_or_generated'],
        'must_recheck_at_apply': ['fresh_full_wp_inventory', 'stored_content_sha256',
            'post_title', 'post_status', 'official_source_sha256', 'editorial_review_freshness'],
        'restore_source': backup.name,
        'rollback_not_executed': True, 'wordpress_write_performed': False,
    }
    (out_dir / 'approval-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--post-id', type=int, required=True)
    arg.add_argument('--bundle', type=Path, required=True)
    arg.add_argument('--out-dir', type=Path, required=True)
    arg.add_argument('--ssh-host', default='bloguito')
    args = arg.parse_args()
    manifest = prepare(args.post_id, args.bundle, args.out_dir, args.ssh_host)
    print(json.dumps({key: manifest[key] for key in (
        'post_id', 'preflight_status', 'reasons', 'original_stored_content_sha256',
        'proposed_rendered_content_sha256', 'source_hashes_match_live')},
        ensure_ascii=False, indent=2))
    if manifest['preflight_status'] != 'ready':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
