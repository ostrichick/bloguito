"""Run selected canonical editorial_cli actions locally against remote WordPress.

Usage keeps editorial/review/policy code in the current local checkout while SSH
is used only as a restricted transport for the WordPress/Docker commands emitted
by those actions::

    python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- \
        publish tmp/article/bundle.json

    python scripts/editorial_cli_via_ssh.py --ssh-host 100.x.y.z \
        --ssh-user ubuntu --wsl-distro Ubuntu-24.04 -- \
        revise-draft tmp/article/bundle.json --post-id 463 \
        --expected-content-sha256 <sha> --confirm-update

The adapter is deliberately not a general remote shell.  Each supported action
has a fixed WP-CLI allowlist, and Tailscale diagnostics run only after SSH fails.
"""

import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent-publisher'))

import editorial_cli  # noqa: E402


_RUN = subprocess.run
_WP_PREFIX = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
_LIST_ARGS = [
    'post', 'list', '--post_type=post',
    '--post_status=publish,draft,pending,future,private', '--posts_per_page=-1',
    '--fields=ID,post_title,post_status,post_content', '--format=json', '--allow-root',
]
_REMOTE_HTML = re.compile(r'/tmp/editorial_[A-Za-z0-9_.-]+\.html')
_SUPPORTED_ACTIONS = {
    'publish', 'revise-draft', 'update-draft', 'replace-legacy-draft',
    'promote-draft', 'reformat', 'fix-excerpt',
}
_UPDATE_FIELDS = {
    'revise-draft': {'post_content', 'post_excerpt'},
    'update-draft': {'post_content'},
    'replace-legacy-draft': {'post_content', 'post_excerpt'},
    'promote-draft': {'post_status'},
    'reformat': {'post_content'},
    'fix-excerpt': {'post_excerpt'},
}
_PERMALINK_ACTIONS = {'publish', 'replace-legacy-draft', 'promote-draft', 'reformat'}


def _safe_identifier(value, label):
    if value is not None and not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
        raise ValueError(f'invalid_{label}')


def _target_ids(action, cli_args):
    ids = set()
    for index, value in enumerate(cli_args):
        if value == '--post-id' and index + 1 < len(cli_args) and cli_args[index + 1].isdigit():
            ids.add(int(cli_args[index + 1]))
    if action == 'reformat' and len(cli_args) > 1 and cli_args[1].isdigit():
        ids.add(int(cli_args[1]))
    if action == 'promote-draft':
        if len(cli_args) > 1 and not cli_args[1].startswith('--'):
            for item in cli_args[1].split(','):
                if item.strip().isdigit():
                    ids.add(int(item.strip()))
        if '--ids' in cli_args:
            start = cli_args.index('--ids') + 1
            for value in cli_args[start:]:
                if value.startswith('--'):
                    break
                if value.isdigit():
                    ids.add(int(value))
    return ids


def make_transport(action, target_ids, host, *, ssh_user=None, wsl_distro=None):
    if action not in _SUPPORTED_ACTIONS:
        raise ValueError('unsupported_editorial_ssh_action')
    _safe_identifier(host, 'ssh_host')
    _safe_identifier(ssh_user, 'ssh_user')
    _safe_identifier(wsl_distro, 'wsl_distro')
    allowed_ids = set(int(value) for value in target_ids)
    diagnosed = False

    def ssh_argv(remote):
        destination = f'{ssh_user}@{host}' if ssh_user else host
        command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', destination, remote]
        return ['wsl.exe', '-d', wsl_distro, '--', *command] if wsl_distro else command

    def diagnose_once():
        nonlocal diagnosed
        if diagnosed or not wsl_distro:
            return
        diagnosed = True
        for command in (
            ['wsl.exe', '-d', wsl_distro, '--', 'tailscale', 'status'],
            ['wsl.exe', '-d', wsl_distro, '--', 'tailscale', 'ping', '-c', '1', host],
        ):
            try:
                _RUN(command, capture_output=True, text=True, timeout=12, check=False)
            except (OSError, subprocess.SubprocessError):
                pass

    def remote_run(remote, **kwargs):
        options = dict(kwargs)
        if options.get('text') or options.get('universal_newlines'):
            options.setdefault('encoding', 'utf-8')
        options.setdefault('timeout', 120)
        try:
            result = _RUN(ssh_argv(remote), **options)
        except (OSError, subprocess.SubprocessError):
            diagnose_once()
            raise
        if getattr(result, 'returncode', 0) == 255:
            diagnose_once()
        return result

    def parse_update(wp):
        if len(wp) < 5 or wp[:2] != ['post', 'update'] or not wp[2].isdigit():
            return None
        post_id = int(wp[2])
        if post_id not in allowed_ids or wp[-1] != '--allow-root':
            raise ValueError('unexpected_wordpress_update_target')
        fields = {}
        for item in wp[3:-1]:
            if not item.startswith('--') or '=' not in item:
                raise ValueError('unexpected_wordpress_update_flags')
            key, value = item[2:].split('=', 1)
            if key in fields:
                raise ValueError('unexpected_wordpress_update_flags')
            fields[key] = value
        expected = _UPDATE_FIELDS.get(action, set())
        if set(fields) != expected:
            raise ValueError('unexpected_wordpress_update_flags')
        if action == 'promote-draft' and fields.get('post_status') != 'publish':
            raise ValueError('unexpected_wordpress_update_flags')
        return post_id

    def validate_wp(wp):
        if wp == _LIST_ARGS:
            return
        if any(not isinstance(item, str) or '\x00' in item for item in wp):
            raise ValueError('unsafe_wordpress_argument')
        if action == 'publish' and wp[:2] == ['post', 'create']:
            if len(wp) < 10 or not _REMOTE_HTML.fullmatch(wp[2]):
                raise ValueError('unexpected_wordpress_draft_create')
            flags = wp[3:]
            required = {'--post_type=post', '--post_status=draft', '--comment_status=closed',
                        '--allow-root', '--porcelain'}
            categories = [item for item in flags if item.startswith('--post_category=')]
            if (not required.issubset(flags)
                    or sum(item.startswith('--post_title=') for item in flags) != 1
                    or sum(item.startswith('--post_excerpt=') for item in flags) != 1
                    or len(categories) != 1 or not categories[0].split('=', 1)[1].isdigit()):
                raise ValueError('unexpected_wordpress_draft_create')
            allowed = required | set(categories)
            if any(item not in allowed and not item.startswith(('--post_title=', '--post_excerpt='))
                   for item in flags):
                raise ValueError('unexpected_wordpress_draft_create')
            return 'create'
        if wp[:2] == ['post', 'get'] and len(wp) in {5, 6} and wp[2].isdigit():
            post_id = int(wp[2])
            if post_id not in allowed_ids:
                raise ValueError('unexpected_wordpress_get_target')
            tail = wp[3:]
            if tail not in (["--format=json", "--allow-root"],
                            ['--fields=post_status,post_content', '--format=json', '--allow-root']):
                raise ValueError('unexpected_wordpress_get_flags')
            return
        if parse_update(wp) is not None:
            return
        if (action in _PERMALINK_ACTIONS and len(wp) == 3 and wp[0] == 'eval'
                and re.fullmatch(r'echo get_permalink\(([1-9][0-9]*)\);', wp[1])
                and int(re.fullmatch(r'echo get_permalink\(([1-9][0-9]*)\);', wp[1]).group(1)) in allowed_ids
                and wp[2] == '--allow-root'):
            return
        if (action == 'publish' and len(wp) == 7 and wp[:3] == ['post', 'meta', 'set']
                and wp[3].isdigit() and int(wp[3]) in allowed_ids
                and wp[4] in {'rank_math_focus_keyword', 'rank_math_description'}
                and wp[6] == '--allow-root'):
            return
        raise ValueError('unexpected_wordpress_command_during_editorial_ssh')

    def run(command, *args, **kwargs):
        if args or not isinstance(command, (list, tuple)):
            raise ValueError('unexpected_subprocess_call_during_editorial_ssh')
        command = list(command)
        if command[:5] == _WP_PREFIX:
            wp = command[5:]
            kind = validate_wp(wp)
            remote = 'sudo docker exec wordpress_app wp ' + ' '.join(shlex.quote(item) for item in wp)
            result = remote_run(remote, **kwargs)
            if kind == 'create' and getattr(result, 'returncode', 0) == 0:
                raw = result.stdout.decode() if isinstance(result.stdout, bytes) else str(result.stdout or '')
                created = raw.strip()
                if not created.isdigit() or int(created) <= 0:
                    raise ValueError('invalid_created_wordpress_post_id')
                allowed_ids.add(int(created))
            return result

        if action == 'publish' and command[:3] == ['sudo', 'docker', 'cp'] and len(command) == 5:
            source = Path(command[3])
            target = command[4]
            prefix = 'wordpress_app:'
            if not source.is_file() or source.suffix.lower() != '.html' or not target.startswith(prefix):
                raise ValueError('unexpected_docker_copy_during_draft_publish')
            remote_path = target[len(prefix):]
            if not _REMOTE_HTML.fullmatch(remote_path):
                raise ValueError('unexpected_docker_copy_during_draft_publish')
            payload = source.read_bytes()
            remote = 'sudo docker exec -i wordpress_app sh -c ' + shlex.quote('cat > ' + remote_path)
            options = dict(kwargs)
            options.pop('text', None)
            options.pop('universal_newlines', None)
            options['input'] = payload
            return remote_run(remote, **options)

        if (action == 'publish' and command[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'rm']
                and len(command) == 7 and command[5] == '-f' and _REMOTE_HTML.fullmatch(command[6])):
            return remote_run('sudo docker exec wordpress_app rm -f ' + shlex.quote(command[6]), **kwargs)

        raise ValueError('unexpected_subprocess_command_during_editorial_ssh')

    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh-host', default='bloguito')
    parser.add_argument('--ssh-user')
    parser.add_argument('--wsl-distro')
    parser.add_argument('cli_args', nargs=argparse.REMAINDER,
                        help='Pass -- followed by editorial_cli.py arguments')
    args = parser.parse_args()
    cli_args = list(args.cli_args)
    if cli_args and cli_args[0] == '--':
        cli_args.pop(0)
    if not cli_args or cli_args[0] not in _SUPPORTED_ACTIONS:
        parser.error('use -- followed by a supported editorial_cli action')
    action = cli_args[0]
    targets = _target_ids(action, cli_args)
    if action != 'publish' and not targets:
        parser.error('a concrete target post ID is required for this action')
    transport = make_transport(
        action, targets, args.ssh_host, ssh_user=args.ssh_user, wsl_distro=args.wsl_distro)
    with patch('subprocess.run', side_effect=transport), \
            patch.object(sys, 'argv', ['editorial_cli.py', *cli_args]):
        editorial_cli.main()


if __name__ == '__main__':
    main()
