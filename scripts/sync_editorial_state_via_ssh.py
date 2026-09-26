"""One-time import of legacy editorial index state from the production host.

New editorial work keeps these ignored runtime indexes locally and talks to the
server only through restricted WordPress commands.  This helper exists for the
transition: it imports the old server-side draft/published index only when the
local files do not already exist.  It never overwrites local canonical state.
"""

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent-publisher'))

from config import DRAFTS_INDEX_FILE, POSTS_INDEX_FILE  # noqa: E402


_RUN = subprocess.run
_FILES = {
    'draft_posts.json': DRAFTS_INDEX_FILE,
    'published_posts.json': POSTS_INDEX_FILE,
}


def _safe_identifier(value, label):
    if value is not None and not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
        raise ValueError(f'invalid_{label}')


def _ssh_argv(host, user, distro, remote):
    destination = f'{user}@{host}' if user else host
    command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', destination, remote]
    return ['wsl.exe', '-d', distro, '--', *command] if distro else command


def _validate_index(payload, filename):
    rows = json.loads(payload)
    if not isinstance(rows, list):
        raise ValueError(f'invalid_remote_{filename}')
    ids = []
    for row in rows:
        if not isinstance(row, dict) or not str(row.get('id', '')).isdigit():
            raise ValueError(f'invalid_remote_{filename}')
        ids.append(int(row['id']))
    if len(ids) != len(set(ids)):
        raise ValueError(f'duplicate_remote_{filename}_ids')
    return rows


def sync_state(host='bloguito', *, ssh_user=None, wsl_distro=None,
               remote_data_dir='/home/ubuntu/agent-publisher/data'):
    _safe_identifier(host, 'ssh_host')
    _safe_identifier(ssh_user, 'ssh_user')
    _safe_identifier(wsl_distro, 'wsl_distro')
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', remote_data_dir) or '..' in remote_data_dir.split('/'):
        raise ValueError('invalid_remote_data_dir')
    existing = [str(path) for path in _FILES.values() if path.exists()]
    if existing:
        raise FileExistsError('local_editorial_state_already_exists:' + ','.join(existing))

    diagnosed = False

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

    downloaded = {}
    for filename in _FILES:
        remote_path = remote_data_dir.rstrip('/') + '/' + filename
        remote = 'cat -- ' + shlex.quote(remote_path)
        try:
            result = _RUN(
                _ssh_argv(host, ssh_user, wsl_distro, remote),
                capture_output=True, text=True, encoding='utf-8', timeout=30, check=True)
        except (OSError, subprocess.SubprocessError):
            diagnose_once()
            raise
        downloaded[filename] = _validate_index(result.stdout, filename)

    written = []
    try:
        for filename, rows in downloaded.items():
            target = _FILES[filename]
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix(target.suffix + '.import-tmp')
            temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            if target.exists():
                temp.unlink(missing_ok=True)
                raise FileExistsError('local_editorial_state_created_during_import:' + str(target))
            temp.replace(target)
            written.append(target)
    except Exception:
        # A partial import must not silently become the new canonical state.
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return {name: len(downloaded[name]) for name in downloaded}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh-host', default='bloguito')
    parser.add_argument('--ssh-user')
    parser.add_argument('--wsl-distro')
    parser.add_argument('--remote-data-dir', default='/home/ubuntu/agent-publisher/data')
    args = parser.parse_args()
    result = sync_state(
        args.ssh_host, ssh_user=args.ssh_user, wsl_distro=args.wsl_distro,
        remote_data_dir=args.remote_data_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
