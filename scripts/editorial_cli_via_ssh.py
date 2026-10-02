"""Run selected canonical editorial_cli actions locally against remote WordPress.

Usage keeps editorial/review/policy code in the current local checkout while SSH
is used only as a restricted transport for the WordPress/Docker commands emitted
by those actions::

    python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- \
        prepare-draft scratch/tasks/article/bundle.json --author-model "GPT-5.6 Sol"

    python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- \
        edit-post scratch/tasks/article/bundle.json --post-id 463 \
        --expected-content-sha256 <sha> --confirm-update --edit-intent "문구 정리"

    python scripts/editorial_cli_via_ssh.py --ssh-host bloguito -- \
        replace-featured-image --post-id 463 --image-path cover.webp \
        --alt-text "대표 이미지" --confirm-update

The adapter is deliberately not a general remote shell.  Each supported action
has a fixed WP-CLI allowlist, and Tailscale diagnostics run only after SSH fails.
"""

import argparse
from contextlib import nullcontext
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent-publisher'))

import editorial_cli  # noqa: E402
from agents.editorial_updater import rank_math_meta_from_brief  # noqa: E402
from agents.remote_transport_config import resolve_transport  # noqa: E402
from agents.runtime_stdio import configure_utf8_stdio  # noqa: E402
from agents.section_image import SECTION_IMAGE_SNAPSHOT_SCRIPT  # noqa: E402
from agents.workflow_metrics import timed, workflow_run  # noqa: E402
from agents.wordpress_mutation import GUARDED_POST_MUTATION_SCRIPT  # noqa: E402
from sync_wordpress_inventory import LIGHTWEIGHT_INVENTORY_ARGS  # noqa: E402

configure_utf8_stdio()


_RUN = subprocess.run
_WP_PREFIX = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
_LIST_ARGS = [
    'post', 'list', '--post_type=post',
    '--post_status=publish,draft,pending,future,private', '--posts_per_page=-1',
    '--fields=ID,post_title,post_status,post_content', '--format=json', '--allow-root',
]
_LIGHT_INVENTORY_ARGS = list(LIGHTWEIGHT_INVENTORY_ARGS)
_REMOTE_HTML = re.compile(r'/tmp/editorial_[A-Za-z0-9_.-]+\.html')
_REMOTE_IMAGE = re.compile(r'/tmp/editorial_cover_([1-9][0-9]*)\.(?:jpg|jpeg|png|webp)', re.IGNORECASE)
_REMOTE_SECTION_IMAGE = re.compile(
    r'/tmp/editorial_section_([1-9][0-9]*)_[0-9a-f]{12}\.(?:jpg|jpeg|png|webp)', re.IGNORECASE)


class _CliActionMeta:
    __slots__ = (
        'group', 'target_mode', 'bundle_positional', 'requires_image_path',
        'creates_post', 'update_fields', 'permalink',
    )

    def __init__(self, group, *, target_mode='post-id', bundle_positional=False,
                 requires_image_path=False, creates_post=False, update_fields=(),
                 permalink=False):
        self.group = group
        self.target_mode = target_mode
        self.bundle_positional = bundle_positional
        self.requires_image_path = requires_image_path
        self.creates_post = creates_post
        self.update_fields = frozenset(update_fields)
        self.permalink = permalink


class _CliRequest:
    __slots__ = (
        'action', 'cli_args', 'target_ids', 'bundle_path', 'image_path',
        'image_path_supplied', 'expected_content_sha256', 'confirm_title_change',
        'resume', 'output_path',
    )

    def __init__(self, *, action, cli_args, target_ids, bundle_path, image_path,
                 image_path_supplied, expected_content_sha256, confirm_title_change,
                 resume, output_path):
        self.action = action
        self.cli_args = tuple(cli_args)
        self.target_ids = frozenset(target_ids)
        self.bundle_path = bundle_path
        self.image_path = image_path
        self.image_path_supplied = image_path_supplied
        self.expected_content_sha256 = expected_content_sha256
        self.confirm_title_change = confirm_title_change
        self.resume = resume
        self.output_path = output_path


_CLI_ACTION_METADATA = {
    'prepare-draft': _CliActionMeta(
        'primary', target_mode='none', bundle_positional=True,
        creates_post=True, permalink=True),
    'edit-post': _CliActionMeta('primary', bundle_positional=True),
    'replace-featured-image': _CliActionMeta('primary'),
    'promote-draft': _CliActionMeta(
        'publication', target_mode='promote', update_fields={'post_status'},
        permalink=True),
    'reformat': _CliActionMeta(
        'maintenance', target_mode='positional', update_fields={'post_content'},
        permalink=True),
    'fix-excerpt': _CliActionMeta(
        'maintenance', update_fields={'post_excerpt'}),
    'repair-draft-category': _CliActionMeta(
        'maintenance', update_fields={'post_category'}, permalink=True),
    'import-section-image': _CliActionMeta(
        'maintenance', requires_image_path=True),
}

_CREATE_ACTIONS = {
    action for action, meta in _CLI_ACTION_METADATA.items() if meta.creates_post
}
_PUBLIC_EDIT_ACTIONS = {'public-fast', 'public-standard'}
_DRAFT_EDIT_PROFILES = {'draft-fast', 'draft-standard'}
_IMAGE_EDIT_ACTIONS = {*_DRAFT_EDIT_PROFILES, 'replace-featured-image', *_PUBLIC_EDIT_ACTIONS}
_FEATURED_IMAGE_ACTIONS = _CREATE_ACTIONS | _IMAGE_EDIT_ACTIONS
_PRIMARY_CLI_ACTIONS = {
    action for action, meta in _CLI_ACTION_METADATA.items() if meta.group == 'primary'
}
_PUBLICATION_CLI_ACTIONS = {
    action for action, meta in _CLI_ACTION_METADATA.items() if meta.group == 'publication'
}
_MAINTENANCE_CLI_ACTIONS = {
    action for action, meta in _CLI_ACTION_METADATA.items() if meta.group == 'maintenance'
}
_CLI_ACTIONS = set(_CLI_ACTION_METADATA)
_TRANSPORT_PROFILES = {*_DRAFT_EDIT_PROFILES, 'public-fast', 'public-standard'}
_SUPPORTED_ACTIONS = _CLI_ACTIONS | _TRANSPORT_PROFILES
_UPDATE_FIELDS = {
    action: set(meta.update_fields)
    for action, meta in _CLI_ACTION_METADATA.items() if meta.update_fields
}
_PERMALINK_ACTIONS = {
    action for action, meta in _CLI_ACTION_METADATA.items() if meta.permalink
}

_REQUEST_VALUE_FLAGS = {
    '--post-id', '--image-path', '--expected-content-sha256', '--output',
}


def _safe_identifier(value, label):
    if value is not None and not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
        raise ValueError(f'invalid_{label}')


def _parse_cli_request(cli_args):
    if not cli_args or cli_args[0] not in _CLI_ACTION_METADATA:
        raise ValueError('unsupported_editorial_ssh_action')
    action = cli_args[0]
    meta = _CLI_ACTION_METADATA[action]
    positional = cli_args[1] if len(cli_args) > 1 and not cli_args[1].startswith('--') else None
    ids = set()
    values = {}
    confirm_title_change = False
    resume = False
    promotion_ids_seen = False
    index = 1
    while index < len(cli_args):
        value = cli_args[index]
        if value in _REQUEST_VALUE_FLAGS:
            next_value = cli_args[index + 1] if index + 1 < len(cli_args) else None
            values.setdefault(value, next_value)
            if value == '--post-id' and next_value is not None and next_value.isdigit():
                ids.add(int(next_value))
            index += 1
            continue
        if value == '--confirm-title-change':
            confirm_title_change = True
        elif value == '--resume':
            resume = True
        elif action == 'promote-draft' and value == '--ids' and not promotion_ids_seen:
            promotion_ids_seen = True
            index += 1
            while index < len(cli_args) and not cli_args[index].startswith('--'):
                if cli_args[index].isdigit():
                    ids.add(int(cli_args[index]))
                index += 1
            continue
        index += 1

    if meta.target_mode == 'positional' and positional is not None and positional.isdigit():
        ids.add(int(positional))
    elif meta.target_mode == 'promote' and positional is not None:
        for item in positional.split(','):
            if item.strip().isdigit():
                ids.add(int(item.strip()))

    image_value = values.get('--image-path')
    output_value = values.get('--output')
    return _CliRequest(
        action=action,
        cli_args=cli_args,
        target_ids=ids,
        bundle_path=(Path(positional) if meta.bundle_positional and positional is not None else None),
        image_path=(Path(image_value) if image_value is not None else None),
        image_path_supplied='--image-path' in values,
        expected_content_sha256=values.get('--expected-content-sha256'),
        confirm_title_change=confirm_title_change,
        resume=resume,
        output_path=(Path(output_value) if output_value is not None else None),
    )


def _mark_catalog_sync(request, status, attempts):
    target = request.output_path
    if target is None or not target.is_file():
        return
    try:
        payload = json.loads(target.read_text(encoding='utf-8'))
        if isinstance(payload, dict) and payload.get('action') == 'prepare-draft':
            payload['catalog_sync'] = status
            payload['catalog_sync_attempts'] = attempts
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    except (OSError, ValueError, TypeError):
        pass


def make_transport(action, target_ids, host, *, ssh_user=None, wsl_distro=None,
                   allow_title_change=False, use_tailscale=False,
                   expected_rank_math_meta=None, allow_image=False):
    if action not in _SUPPORTED_ACTIONS:
        raise ValueError('unsupported_editorial_ssh_action')
    if action == 'edit-post':
        raise ValueError('edit_post_requires_preclassified_transport')
    _safe_identifier(host, 'ssh_host')
    _safe_identifier(ssh_user, 'ssh_user')
    _safe_identifier(wsl_distro, 'wsl_distro')
    allowed_ids = set(int(value) for value in target_ids)
    readable_ids = set(allowed_ids)
    diagnosed = False
    control_path = f'/tmp/bloguito-editorial-{os.getpid()}-%C'
    image_mutation_allowed = bool(
        action in _CREATE_ACTIONS or action in {'replace-featured-image', 'import-section-image'} or allow_image
    )
    if expected_rank_math_meta is not None:
        allowed_rank_keys = {'rank_math_focus_keyword', 'rank_math_title', 'rank_math_description'}
        if (not isinstance(expected_rank_math_meta, dict)
                or set(expected_rank_math_meta) != allowed_rank_keys
                or any(not isinstance(value, str) or '\x00' in value
                       for value in expected_rank_math_meta.values())):
            raise ValueError('invalid_expected_rank_math_meta')

    def ssh_argv(remote):
        destination = f'{ssh_user}@{host}' if ssh_user else host
        if use_tailscale:
            if not wsl_distro:
                raise ValueError('tailscale_requires_wsl_distro')
            return ['wsl.exe', '-d', wsl_distro, '--exec', 'tailscale', 'ssh', destination, remote]
        command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']
        if wsl_distro:
            command += [
                '-o', 'ControlMaster=auto',
                '-o', 'ControlPersist=30',
                '-o', f'ControlPath={control_path}',
            ]
        command += [destination, remote]
        return ['wsl.exe', '-d', wsl_distro, '--exec', *command] if wsl_distro else command

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
                _RUN(command, capture_output=True, text=True, encoding='utf-8', errors='strict',
                     timeout=12, check=False)
            except (OSError, subprocess.SubprocessError):
                pass

    def remote_run(remote, *, retry_255=False, **kwargs):
        options = dict(kwargs)
        if options.get('text') or options.get('universal_newlines'):
            options.setdefault('encoding', 'utf-8')
        options.setdefault('timeout', 120)
        argv = ssh_argv(remote)
        try:
            result = _RUN(argv, **options)
        except subprocess.CalledProcessError as exc:
            if exc.returncode != 255:
                raise
            diagnose_once()
            if retry_255:
                return _RUN(argv, **options)
            raise
        except (OSError, subprocess.SubprocessError):
            raise
        if getattr(result, 'returncode', 0) == 255:
            diagnose_once()
            if retry_255:
                return _RUN(argv, **options)
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
        allowed_field_sets = {frozenset(expected)}
        if action == 'draft-standard' and allow_title_change:
            allowed_field_sets.add(frozenset(expected | {'post_title'}))
        if frozenset(fields) not in allowed_field_sets:
            raise ValueError('unexpected_wordpress_update_flags')
        if action == 'promote-draft' and fields.get('post_status') != 'publish':
            raise ValueError('unexpected_wordpress_update_flags')
        if action == 'repair-draft-category' and not fields.get('post_category', '').isdigit():
            raise ValueError('unexpected_wordpress_update_flags')
        return post_id

    def validate_guarded_payload(raw):
        if action not in {'draft-standard', 'draft-fast', 'public-fast', 'public-standard'}:
            raise ValueError('guarded_wordpress_mutation_not_allowed')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        if not isinstance(raw, str):
            raise ValueError('guarded_wordpress_payload_required')
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid_guarded_wordpress_payload') from exc
        if not isinstance(payload, dict) or payload.get('protocol') != 1:
            raise ValueError('invalid_guarded_wordpress_payload')
        post_id = payload.get('post_id')
        expected = payload.get('expected')
        updates = payload.get('updates')
        if type(post_id) is not int or post_id not in allowed_ids:
            raise ValueError('unexpected_wordpress_update_target')
        required_expected = {
            'post_status', 'post_title', 'post_name', 'post_excerpt', 'content_sha256',
        }
        expected_status = 'publish' if action in _PUBLIC_EDIT_ACTIONS else 'draft'
        if (not isinstance(expected, dict) or set(expected) != required_expected
                or expected.get('post_status') != expected_status
                or not re.fullmatch(r'[0-9a-f]{64}', expected.get('content_sha256', ''))
                or any(not isinstance(value, str) or '\x00' in value for value in expected.values())):
            raise ValueError('invalid_guarded_wordpress_expectation')
        if not isinstance(updates, dict) or any(
                not isinstance(value, str) or '\x00' in value for value in updates.values()):
            raise ValueError('invalid_guarded_wordpress_update')
        if action == 'draft-fast':
            allowed_field_sets = {frozenset({'post_content', 'post_excerpt'})}
        elif action == 'draft-standard':
            allowed_field_sets = {frozenset({'post_content', 'post_excerpt'})}
            if allow_title_change:
                allowed_field_sets.add(frozenset({'post_content', 'post_excerpt', 'post_title'}))
        elif action == 'public-fast':
            allowed_field_sets = {
                frozenset({'post_content'}),
                frozenset({'post_content', 'post_excerpt'}),
            }
        else:
            allowed_field_sets = {
                frozenset({'post_content'}),
                frozenset({'post_content', 'post_excerpt'}),
            }
            if allow_title_change:
                allowed_field_sets.update({
                    frozenset({'post_content', 'post_title'}),
                    frozenset({'post_content', 'post_excerpt', 'post_title'}),
                })
        if frozenset(updates) not in allowed_field_sets:
            raise ValueError('unexpected_wordpress_update_flags')
        return payload

    def validate_section_snapshot_payload(raw):
        if action != 'import-section-image':
            raise ValueError('section_snapshot_not_allowed')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        if not isinstance(raw, str):
            raise ValueError('section_snapshot_payload_required')
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid_section_snapshot_payload') from exc
        if not isinstance(payload, dict) or set(payload) != {'protocol', 'post_id', 'attachment_id'}:
            raise ValueError('invalid_section_snapshot_payload')
        if payload.get('protocol') != 1:
            raise ValueError('invalid_section_snapshot_payload')
        post_id = payload.get('post_id')
        attachment_id = payload.get('attachment_id')
        if type(post_id) is not int or post_id not in allowed_ids:
            raise ValueError('unexpected_wordpress_get_target')
        if attachment_id is not None and (
                type(attachment_id) is not int or attachment_id not in readable_ids):
            raise ValueError('unexpected_wordpress_get_target')
        return payload

    def validate_wp(wp):
        if wp == _LIST_ARGS or wp == _LIGHT_INVENTORY_ARGS:
            return
        if any(not isinstance(item, str) or '\x00' in item for item in wp):
            raise ValueError('unsafe_wordpress_argument')
        if action in _CREATE_ACTIONS and wp[:2] == ['post', 'create']:
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
            if post_id not in readable_ids:
                raise ValueError('unexpected_wordpress_get_target')
            tail = wp[3:]
            if tail not in (["--format=json", "--allow-root"],
                            ['--fields=post_status,post_content', '--format=json', '--allow-root'],
                            ['--fields=post_status,post_title,post_name,post_content,post_excerpt',
                             '--format=json', '--allow-root'],
                            ['--fields=ID,guid,post_title,post_mime_type', '--format=json', '--allow-root']):
                raise ValueError('unexpected_wordpress_get_flags')
            return
        if (action == 'repair-draft-category'
                and len(wp) == 8
                and wp[:3] == ['post', 'term', 'list']
                and wp[3].isdigit() and int(wp[3]) in allowed_ids
                and wp[4:] == ['category', '--fields=term_id,name,slug', '--format=json', '--allow-root']):
            return
        if wp == ['eval', GUARDED_POST_MUTATION_SCRIPT, '--allow-root']:
            return 'guarded_mutation'
        if (action == 'import-section-image'
                and wp == ['eval', SECTION_IMAGE_SNAPSHOT_SCRIPT, '--allow-root']):
            return 'section_snapshot'
        if parse_update(wp) is not None:
            return
        if (action in _PERMALINK_ACTIONS and len(wp) == 3 and wp[0] == 'eval'
                and re.fullmatch(r'echo get_permalink\(([1-9][0-9]*)\);', wp[1])
                and int(re.fullmatch(r'echo get_permalink\(([1-9][0-9]*)\);', wp[1]).group(1)) in allowed_ids
                and wp[2] == '--allow-root'):
            return
        if (action in _CREATE_ACTIONS and len(wp) == 7 and wp[:3] == ['post', 'meta', 'set']
                and wp[3].isdigit() and int(wp[3]) in allowed_ids
                and wp[6] == '--allow-root'):
            if wp[4] in {'rank_math_focus_keyword', 'rank_math_title', 'rank_math_description'}:
                return
            if wp[4] == '_bloguito_permalink_scheme' and wp[5] == 'post-id-v1':
                return
        if (action in _CREATE_ACTIONS and len(wp) == 6 and wp[:2] == ['media', 'import']
                and _REMOTE_IMAGE.fullmatch(wp[2])
                and wp[3].startswith('--post_id=') and wp[3].split('=', 1)[1].isdigit()
                and int(wp[3].split('=', 1)[1]) in allowed_ids
                and int(_REMOTE_IMAGE.fullmatch(wp[2]).group(1)) == int(wp[3].split('=', 1)[1])
                and wp[4:] == ['--featured_image', '--allow-root']):
            return
        if (allow_image and action == 'draft-standard' and len(wp) == 7 and wp[:2] == ['media', 'import']
                and _REMOTE_IMAGE.fullmatch(wp[2])
                and wp[3].startswith('--post_id=') and wp[3].split('=', 1)[1].isdigit()
                and int(wp[3].split('=', 1)[1]) in allowed_ids
                and int(_REMOTE_IMAGE.fullmatch(wp[2]).group(1)) == int(wp[3].split('=', 1)[1])
                and wp[4:] == ['--featured_image', '--porcelain', '--allow-root']):
            return 'media_import'
        if (image_mutation_allowed and action in _IMAGE_EDIT_ACTIONS
                and len(wp) == 9 and wp[:2] == ['media', 'import']
                and _REMOTE_IMAGE.fullmatch(wp[2])
                and wp[3].startswith('--post_id=') and wp[3].split('=', 1)[1].isdigit()
                and int(wp[3].split('=', 1)[1]) in allowed_ids
                and int(_REMOTE_IMAGE.fullmatch(wp[2]).group(1)) == int(wp[3].split('=', 1)[1])
                and wp[4] == '--featured_image'
                and wp[5].startswith('--title=') and '\x00' not in wp[5]
                and wp[6].startswith('--alt=') and '\x00' not in wp[6]
                and wp[7:] == ['--porcelain', '--allow-root']):
            return 'media_import'
        if (action == 'import-section-image' and len(wp) == 8 and wp[:2] == ['media', 'import']
                and _REMOTE_SECTION_IMAGE.fullmatch(wp[2])
                and wp[3].startswith('--post_id=') and wp[3].split('=', 1)[1].isdigit()
                and int(wp[3].split('=', 1)[1]) in allowed_ids
                and int(_REMOTE_SECTION_IMAGE.fullmatch(wp[2]).group(1)) == int(wp[3].split('=', 1)[1])
                and wp[4].startswith('--title=') and '\x00' not in wp[4]
                and wp[5].startswith('--alt=') and '\x00' not in wp[5]
                and wp[6:] == ['--porcelain', '--allow-root']):
            return 'media_import'
        if (allow_image and action == 'draft-standard' and len(wp) == 6 and wp[:3] == ['post', 'meta', 'get']
                and wp[3].isdigit() and int(wp[3]) in allowed_ids
                and wp[4:] == ['_thumbnail_id', '--allow-root']):
            return
        if (image_mutation_allowed and action in {*_IMAGE_EDIT_ACTIONS, 'import-section-image'}
                and len(wp) == 6 and wp[:3] == ['post', 'meta', 'get']
                and wp[3].isdigit() and int(wp[3]) in readable_ids
                and wp[4] in {'_thumbnail_id', '_wp_attachment_image_alt',
                              'rank_math_focus_keyword', 'rank_math_title', 'rank_math_description'}
                and wp[5] == '--allow-root'):
            return
        if (action in {'public-standard', 'draft-standard'}
                and expected_rank_math_meta is not None
                and len(wp) == 6 and wp[:3] == ['post', 'meta', 'get']
                and wp[3].isdigit() and int(wp[3]) in allowed_ids
                and wp[4] in expected_rank_math_meta and wp[5] == '--allow-root'):
            return
        if (action in {'public-standard', 'draft-standard'}
                and expected_rank_math_meta is not None
                and len(wp) == 7 and wp[:3] == ['post', 'meta', 'set']
                and wp[3].isdigit() and int(wp[3]) in allowed_ids
                and wp[4] in expected_rank_math_meta
                and wp[5] == expected_rank_math_meta[wp[4]] and wp[6] == '--allow-root'):
            return
        raise ValueError('unexpected_wordpress_command_during_editorial_ssh')

    def run(command, *args, **kwargs):
        if args or not isinstance(command, (list, tuple)):
            raise ValueError('unexpected_subprocess_call_during_editorial_ssh')
        command = list(command)
        if command[:5] == _WP_PREFIX:
            wp = command[5:]
            kind = validate_wp(wp)
            if kind == 'guarded_mutation':
                payload = validate_guarded_payload(kwargs.get('input'))
                remote = ('sudo docker exec -i wordpress_app wp eval '
                          + shlex.quote(GUARDED_POST_MUTATION_SCRIPT) + ' --allow-root')
                options = dict(kwargs)
                raw = options.get('input')
                if options.get('text') or options.get('universal_newlines'):
                    options['input'] = raw if isinstance(raw, str) else raw.decode('utf-8')
                else:
                    options['input'] = raw.encode('utf-8') if isinstance(raw, str) else raw
                # The server-side CAS makes one replay safe. If the first write
                # committed but SSH lost its response, the replay sees the exact
                # desired state and the local guarded helper reconciles it.
                return remote_run(remote, retry_255=True, **options)
            if kind == 'section_snapshot':
                raw_payload = kwargs.get('input')
                validate_section_snapshot_payload(raw_payload)
                remote = ('sudo docker exec -i wordpress_app wp eval '
                          + shlex.quote(SECTION_IMAGE_SNAPSHOT_SCRIPT) + ' --allow-root')
                options = dict(kwargs)
                raw = options.get('input')
                if options.get('text') or options.get('universal_newlines'):
                    options['input'] = raw if isinstance(raw, str) else raw.decode('utf-8')
                else:
                    options['input'] = raw.encode('utf-8') if isinstance(raw, str) else raw
                return remote_run(remote, retry_255=True, **options)
            remote = 'sudo docker exec wordpress_app wp ' + ' '.join(shlex.quote(item) for item in wp)
            read_only = (wp == _LIST_ARGS or wp == _LIGHT_INVENTORY_ARGS
                         or wp[:2] == ['post', 'get'] or (wp and wp[0] == 'eval'))
            result = remote_run(
                remote,
                retry_255=read_only,
                **kwargs,
            )
            if wp == _LIGHT_INVENTORY_ARGS and getattr(result, 'returncode', 0) == 0:
                raw = result.stdout.decode() if isinstance(result.stdout, bytes) else str(result.stdout or '')
                rows = json.loads(raw)
                if not isinstance(rows, list):
                    raise ValueError('invalid_lightweight_inventory_response')
                for row in rows:
                    if isinstance(row, dict) and type(row.get('ID')) is int and row['ID'] > 0:
                        readable_ids.add(row['ID'])
            if kind == 'create' and getattr(result, 'returncode', 0) == 0:
                raw = result.stdout.decode() if isinstance(result.stdout, bytes) else str(result.stdout or '')
                created = raw.lstrip('\ufeff').strip()
                if not created.isdigit() or int(created) <= 0:
                    raise ValueError('invalid_created_wordpress_post_id')
                allowed_ids.add(int(created))
                readable_ids.add(int(created))
            if kind == 'media_import' and getattr(result, 'returncode', 0) == 0:
                raw = result.stdout.decode() if isinstance(result.stdout, bytes) else str(result.stdout or '')
                attachment_id = raw.lstrip('\ufeff').strip()
                if not attachment_id.isdigit() or int(attachment_id) <= 0:
                    raise ValueError('invalid_imported_media_id')
                readable_ids.add(int(attachment_id))
            return result

        if image_mutation_allowed and command[:3] == ['sudo', 'docker', 'cp'] and len(command) == 5:
            source = Path(command[3])
            target = command[4]
            prefix = 'wordpress_app:'
            if not source.is_file() or not target.startswith(prefix):
                raise ValueError('unexpected_docker_copy_during_draft_publish')
            remote_path = target[len(prefix):]
            html_copy = (action in _CREATE_ACTIONS and source.suffix.lower() == '.html'
                         and _REMOTE_HTML.fullmatch(remote_path))
            image_match = _REMOTE_IMAGE.fullmatch(remote_path)
            section_image_match = _REMOTE_SECTION_IMAGE.fullmatch(remote_path)
            image_copy = (
                source.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}
                and ((image_match is not None and int(image_match.group(1)) in allowed_ids)
                     or (section_image_match is not None
                         and int(section_image_match.group(1)) in allowed_ids))
            )
            if not (html_copy or image_copy):
                raise ValueError('unexpected_docker_copy_during_draft_publish')
            payload = source.read_bytes()
            remote = 'sudo docker exec -i wordpress_app sh -c ' + shlex.quote('cat > ' + remote_path)
            options = dict(kwargs)
            options.pop('text', None)
            options.pop('universal_newlines', None)
            options['input'] = payload
            return remote_run(remote, **options)

        if (image_mutation_allowed and command[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'rm']
                and len(command) == 7 and command[5] == '-f'):
            remote_path = command[6]
            image_match = _REMOTE_IMAGE.fullmatch(remote_path)
            section_image_match = _REMOTE_SECTION_IMAGE.fullmatch(remote_path)
            allowed_cleanup = (
                _REMOTE_HTML.fullmatch(remote_path)
                or (image_match and int(image_match.group(1)) in allowed_ids)
                or (section_image_match and int(section_image_match.group(1)) in allowed_ids)
            )
            if allowed_cleanup:
                return remote_run('sudo docker exec wordpress_app rm -f ' + shlex.quote(remote_path), **kwargs)

        raise ValueError('unexpected_subprocess_command_during_editorial_ssh')

    return run


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh-mode', choices=['direct', 'wsl', 'tailscale'])
    parser.add_argument('--ssh-host')
    parser.add_argument('--ssh-user')
    parser.add_argument('--wsl-distro')
    parser.add_argument('cli_args', nargs=argparse.REMAINDER,
                        help='Pass -- followed by editorial_cli.py arguments')
    args = parser.parse_args()
    cli_args = list(args.cli_args)
    if cli_args and cli_args[0] == '--':
        cli_args.pop(0)
    if not cli_args or cli_args[0] not in _CLI_ACTIONS:
        parser.error('use -- followed by a supported editorial_cli action')
    request = _parse_cli_request(cli_args)
    action = request.action
    targets = set(request.target_ids)
    image_path = request.image_path
    if action not in _CREATE_ACTIONS and not targets:
        parser.error('a concrete target post ID is required for this action')
    config = resolve_transport(
        ssh_mode=args.ssh_mode,
        ssh_host=args.ssh_host,
        ssh_user=args.ssh_user,
        wsl_distro=args.wsl_distro,
    )
    transport_action = action
    expected_rank_math_meta = None
    if action == 'edit-post':
        if request.bundle_path is None and not request.image_path_supplied:
            parser.error('edit-post requires a bundle file or --image-path')
        bundle_path = request.bundle_path
        bundle = None
        if bundle_path is not None:
            if not bundle_path.is_file():
                parser.error(f'{action} bundle file not found')
            bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
        post_ids = sorted(targets)
        if len(post_ids) != 1:
            parser.error(f'{action} requires exactly one --post-id')
        if request.image_path_supplied and image_path is None:
            parser.error('--image-path requires a value')
        if bundle is None:
            from agents.edit_post import reviewed_target_kind
            from agents.validation_router import build_validation_plan
            target_status = reviewed_target_kind(post_ids[0])
            transport_action = 'replace-featured-image'
            decision = {
                'route': 'image-only',
                'reasons': [],
                'validation_plan': build_validation_plan(
                    None, None, image_changed=True, target_status=target_status,
                    resume=request.resume, route='image-only', post_id=post_ids[0],
                    expected_content_sha256=request.expected_content_sha256),
            }
        else:
            from agents.edit_post import classify_reviewed_post_route
            decision = classify_reviewed_post_route(
                post_ids[0], bundle,
                expected_content_sha256=request.expected_content_sha256,
                confirm_title_change=request.confirm_title_change,
                image_path=image_path,
                resume=request.resume)
            if decision['target_status'] == 'draft':
                transport_action = 'draft-fast' if decision['route'] == 'fast' else 'draft-standard'
            else:
                transport_action = 'public-fast' if decision['route'] == 'fast' else 'public-standard'
                if transport_action == 'public-standard':
                    expected_rank_math_meta = rank_math_meta_from_brief(bundle.get('brief', {}))
        if transport_action == 'draft-standard' and bundle is not None:
            expected_rank_math_meta = rank_math_meta_from_brief(bundle.get('brief', {}))
        print(f"[Edit Route] {decision['route']}" +
              (f" ({', '.join(decision['reasons'])})" if decision['reasons'] else ''))
        plan = decision['validation_plan']
        if plan.get('full_regression_required'):
            # Repository/shared-code profiles still fail before mutation.
            from agents.validation_runner import require_validation_success
            with timed('validation'):
                validation = require_validation_success(plan, verbosity=0)
        else:
            validation = {
                'profile': plan.get('profile') or decision.get('route') or 'content',
                'tests_run': 0,
                'selected_files': [], 'duration_ms': 0.0, 'status': 'passed',
            }
        print(
            f"[Validation] {validation['profile']}: "
            f"{validation['tests_run']} tests PASS "
            f"({len(validation['selected_files'])} files, {validation['duration_ms']} ms)"
        )

    if _CLI_ACTION_METADATA[action].requires_image_path:
        if not request.image_path_supplied:
            parser.error(f'{action} requires --image-path')
        if image_path is None:
            parser.error('--image-path requires a value')

    transport = make_transport(
        transport_action, targets, config.host, ssh_user=config.user,
        wsl_distro=config.wsl_distro if config.mode in {'wsl', 'tailscale'} else None,
        allow_title_change=(transport_action in {'draft-standard', 'public-standard'}
                            and request.confirm_title_change),
        use_tailscale=config.mode == 'tailscale',
        expected_rank_math_meta=expected_rank_math_meta,
        allow_image=image_path is not None)
    decision_context = (
        editorial_cli.prepared_edit_decision(decision)
        if action == 'edit-post' else nullcontext()
    )
    with timed('remote_editorial_cli'):
        with decision_context, patch('subprocess.run', side_effect=transport), \
                patch.object(sys, 'argv', ['editorial_cli.py', *request.cli_args]):
            editorial_cli.main()

    # prepare-draft is the user-facing one-shot path. Keep the catalog follow-up
    # outside the patched WordPress transport so it uses the normal Direct SSH
    # sync script. A catalog failure must not make callers retry the already
    # successful post create and accidentally produce a duplicate draft.
    if action == 'prepare-draft':
        sync_cmd = [sys.executable, str(ROOT / 'scripts' / 'sync_post_catalog.py')]
        last = None
        attempts = 0
        synced = False
        with timed('catalog_sync'):
            for attempt in range(2):
                attempts = attempt + 1
                last = _RUN(sync_cmd, cwd=str(ROOT), capture_output=True, text=True,
                            encoding='utf-8', errors='strict', check=False)
                if last.returncode == 0:
                    if last.stdout:
                        print(last.stdout.rstrip())
                    print('[Catalog Sync] POST_CATALOG.md updated.')
                    _mark_catalog_sync(request, 'passed', attempts)
                    synced = True
                    break
        if not synced:
            _mark_catalog_sync(request, 'failed', attempts)
            detail = (last.stderr or last.stdout or '').strip() if last is not None else 'unknown error'
            print('[Catalog Sync] WARNING: draft is already saved, but catalog sync failed. '
                  'Run `python scripts/sync_post_catalog.py` only; do not rerun prepare-draft.',
                  file=sys.stderr)
            if detail:
                print(detail, file=sys.stderr)


def _metrics_action(argv) -> str:
    values = list(argv or [])
    if '--' in values:
        index = values.index('--') + 1
        if index < len(values):
            return 'ssh-' + values[index]
    for value in values:
        if value in _CLI_ACTIONS:
            return 'ssh-' + value
    return 'ssh-unknown'


def main():
    with workflow_run(_metrics_action(sys.argv[1:])):
        return _main()


if __name__ == '__main__':
    main()
