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
from agents.remote_transport_config import resolve_transport  # noqa: E402
from sync_wordpress_inventory import LIGHTWEIGHT_INVENTORY_ARGS  # noqa: E402

_RUN = subprocess.run
_PREFIX = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
_LIST_ARGS = [
    'post', 'list', '--post_type=post',
    '--post_status=publish,draft,pending,future,private',
    '--posts_per_page=-1', '--fields=ID,post_title,post_status,post_content',
    '--format=json', '--allow-root',
]
_LIGHT_INVENTORY_ARGS = list(LIGHTWEIGHT_INVENTORY_ARGS)


def make_transport(host, post_id, rendered_content, expected_title=None, wsl_distro=None,
                   ssh_user=None, tailscale_ssh=False):
    """Translate only WP list/get/update performed by the canonical updater."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', host):
        raise ValueError('invalid_ssh_alias')
    if ssh_user is not None and not re.fullmatch(r'[A-Za-z0-9_.-]+', ssh_user):
        raise ValueError('invalid_ssh_user')
    if wsl_distro is not None and not re.fullmatch(r'[A-Za-z0-9_.-]+', wsl_distro):
        raise ValueError('invalid_wsl_distro')

    tailscale_diagnosed = False
    readable_ids = {post_id}

    def diagnose_tailscale_once():
        """Best-effort diagnostics that must never replace the original SSH failure."""
        nonlocal tailscale_diagnosed
        if not wsl_distro or tailscale_diagnosed:
            return
        tailscale_diagnosed = True
        diagnostics = [
            ['wsl.exe', '-d', wsl_distro, '--', 'tailscale', 'status'],
            ['wsl.exe', '-d', wsl_distro, '--', 'tailscale', 'ping', '-c', '1', host],
        ]
        for diagnostic in diagnostics:
            try:
                _RUN(
                    diagnostic,
                    capture_output=True,
                    text=True,
                    timeout=12,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                pass

    def run(command, *args, **kwargs):
        if args or not isinstance(command, (list, tuple)) or list(command[:5]) != _PREFIX:
            raise ValueError('unexpected_subprocess_command_during_public_post_update')
        wp = list(command[5:])
        get = ['post', 'get', str(post_id), '--format=json', '--allow-root']
        expected_update = ['post', 'update', str(post_id), '--post_content=' + rendered_content]
        light_inventory = wp == _LIGHT_INVENTORY_ARGS
        candidate_get = (
            len(wp) == 5 and wp[:2] == ['post', 'get'] and wp[2].isdigit()
            and int(wp[2]) in readable_ids and wp[3:] == ['--format=json', '--allow-root']
        )
        if wp != _LIST_ARGS and not light_inventory and wp != get and not candidate_get:
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
        destination = f'{ssh_user}@{host}' if ssh_user else host
        if tailscale_ssh:
            if not wsl_distro:
                raise ValueError('tailscale_ssh_requires_wsl_distro')
            ssh = ['wsl.exe', '-d', wsl_distro, '--', 'tailscale', 'ssh', destination, remote]
        else:
            ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', destination, remote]
        if wsl_distro and not tailscale_ssh:
            # The production Tailscale interface may live only inside WSL.
            # Keep argv structured end-to-end so the reviewed HTML never
            # passes through an extra shell quoting layer.
            ssh = ['wsl.exe', '-d', wsl_distro, '--', *ssh]
        options = dict(kwargs)
        if options.get('text') or options.get('universal_newlines'):
            options.setdefault('encoding', 'utf-8')
        options.setdefault('timeout', 120)
        try:
            result = _RUN(ssh, **options)
        except (OSError, subprocess.SubprocessError):
            diagnose_tailscale_once()
            raise
        if getattr(result, 'returncode', 0) == 255:
            diagnose_tailscale_once()
        if light_inventory and getattr(result, 'returncode', 0) == 0:
            raw = result.stdout.decode() if isinstance(result.stdout, bytes) else str(result.stdout or '')
            rows = json.loads(raw)
            if not isinstance(rows, list):
                raise ValueError('invalid_lightweight_inventory_response')
            for row in rows:
                if isinstance(row, dict) and type(row.get('ID')) is int and row['ID'] > 0:
                    readable_ids.add(row['ID'])
        return result

    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--post-id', type=int, required=True)
    parser.add_argument('--expected-content-sha256', required=True)
    parser.add_argument('--ssh-mode', choices=['direct', 'wsl', 'tailscale'])
    parser.add_argument('--ssh-host')
    parser.add_argument('--ssh-user',
                        help='Optional SSH user, for example ubuntu when using a Tailscale IP.')
    parser.add_argument('--wsl-distro',
                        help='Route the restricted SSH transport through this WSL distro.')
    parser.add_argument('--tailscale-ssh', action='store_true',
                        help='legacy override: use `tailscale ssh` inside the selected WSL distro')
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
    config = resolve_transport(
        ssh_mode=args.ssh_mode,
        ssh_host=args.ssh_host,
        ssh_user=args.ssh_user,
        wsl_distro=args.wsl_distro,
        tailscale_ssh=args.tailscale_ssh,
    )
    transport = make_transport(
        config.host,
        args.post_id,
        content,
        expected_title=expected_title,
        wsl_distro=config.wsl_distro if config.mode in {'wsl', 'tailscale'} else None,
        ssh_user=config.user,
        tailscale_ssh=config.mode == 'tailscale',
    )
    with patch('subprocess.run', side_effect=transport):
        updated = update_existing_public_post(
            args.post_id, bundle, args.expected_content_sha256, confirmed=True,
            confirm_title_change=args.confirm_title_change)
    print(json.dumps({'updated_public_post_id': updated,
                      'expected_rendered_content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest()},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
