"""Run the normal *local* editorial updater against the known remote WP host.

The production checkout can be older than the review checkout. This adapter
changes only the subprocess transport: all existing validation, source refresh,
backup, compare-and-swap and read-after-write checks stay in editorial_updater.
It cannot be used for arbitrary remote shell or WordPress commands.
"""

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent-publisher'))

from agents.editorial import render  # noqa: E402
from agents.editorial_updater import update_existing_public_post  # noqa: E402

_RUN = subprocess.run
_PREFIX = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
_LIST_ARGS = [
    'post', 'list', '--post_type=post',
    '--post_status=publish,draft,pending,future,private',
    '--posts_per_page=-1', '--fields=ID,post_title,post_status,post_content',
    '--format=json', '--allow-root',
]


def make_transport(host, post_id, rendered_content, expected_title=None):
    """Translate only WP list/get/update performed by the canonical updater."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', host):
        raise ValueError('invalid_ssh_alias')

    def run(command, *args, **kwargs):
        if args or not isinstance(command, (list, tuple)) or list(command[:5]) != _PREFIX:
            raise ValueError('unexpected_subprocess_command_during_public_post_update')
        wp = list(command[5:])
        get = ['post', 'get', str(post_id), '--format=json', '--allow-root']
        expected_update = ['post', 'update', str(post_id), '--post_content=' + rendered_content]
        if wp != _LIST_ARGS and wp != get:
            if wp[:4] != expected_update:
                raise ValueError('unexpected_wordpress_write_arguments')
            trailing = wp[4:]
            if not trailing or trailing[-1] != '--allow-root':
                raise ValueError('unexpected_wordpress_write_flags')
            flags = trailing[:-1]
            title_flags = [item for item in flags if item.startswith('--post_title=')]
            excerpt_flags = [item for item in flags if item.startswith('--post_excerpt=')]
            if len(title_flags) > 1 or len(excerpt_flags) > 1 or len(flags) != len(title_flags) + len(excerpt_flags):
                raise ValueError('unexpected_wordpress_write_flags')
            if expected_title is None and title_flags:
                raise ValueError('unexpected_wordpress_title_change')
            if expected_title is not None and title_flags and title_flags != ['--post_title=' + expected_title]:
                raise ValueError('unexpected_wordpress_title_change')
        if any(not isinstance(item, str) or '\x00' in item for item in wp):
            raise ValueError('unsafe_wordpress_argument')
        remote = 'sudo docker exec wordpress_app wp ' + ' '.join(shlex.quote(x) for x in wp)
        ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', host, remote]
        options = dict(kwargs)
        if options.get('text') or options.get('universal_newlines'):
            options.setdefault('encoding', 'utf-8')
        options.setdefault('timeout', 120)
        return _RUN(ssh, **options)

    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--post-id', type=int, required=True)
    parser.add_argument('--expected-content-sha256', required=True)
    parser.add_argument('--ssh-host', default='bloguito')
    parser.add_argument('--confirm-update', action='store_true')
    parser.add_argument('--confirm-title-change', action='store_true')
    args = parser.parse_args()
    if not args.confirm_update:
        parser.error('explicit --confirm-update required')
    if not re.fullmatch('[0-9a-f]{64}', args.expected_content_sha256):
        parser.error('actual current stored content SHA256 required')
    bundle = json.loads(args.bundle.read_text(encoding='utf-8'))
    if bundle.get('brief', {}).get('existing_post_id') != args.post_id:
        parser.error('reviewed bundle targets a different post')
    content = render(bundle['plan'], bundle['sources'])
    expected_title = bundle.get('plan', {}).get('title') if args.confirm_title_change else None
    transport = make_transport(args.ssh_host, args.post_id, content, expected_title=expected_title)
    with patch('subprocess.run', side_effect=transport):
        updated = update_existing_public_post(
            args.post_id, bundle, args.expected_content_sha256, confirmed=True,
            confirm_title_change=args.confirm_title_change)
    print(json.dumps({'updated_public_post_id': updated,
                      'expected_rendered_content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest()},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
