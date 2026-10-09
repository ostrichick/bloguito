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
import hashlib
from contextlib import nullcontext
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent-publisher'))

import editorial_cli  # noqa: E402
from agents.editorial_updater import rank_math_meta_from_brief  # noqa: E402
from agents.publish_gate import (  # noqa: E402
    PUBLISH_GATE_RECORD_SCRIPT,
    PUBLISH_GATE_VALIDATE_SCRIPT,
)
from agents.wordpress_transport import wordpress_transport
from agents.remote_transport_config import resolve_transport  # noqa: E402
from agents.runtime_stdio import configure_utf8_stdio  # noqa: E402
from agents.section_image import SECTION_IMAGE_SNAPSHOT_SCRIPT  # noqa: E402
from agents.workflow_metrics import annotate, increment, timed, workflow_run  # noqa: E402
from agents.wordpress_mutation import (  # noqa: E402
    ATTACHMENT_SHA_LOOKUP_SCRIPT,
    FEATURED_IMAGE_LOCK_SCRIPT,
    GUARDED_ATTACHMENT_ALT_MUTATION_SCRIPT,
    GUARDED_CATEGORY_MUTATION_SCRIPT,
    GUARDED_POST_MUTATION_SCRIPT,
    GUARDED_THUMBNAIL_MUTATION_SCRIPT,
    POST_THUMBNAIL_SNAPSHOT_SCRIPT,
)
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
_REMOTE_IMAGE = re.compile(r'/tmp/editorial_cover_([1-9][0-9]*)(?:_[0-9a-f]{32})?\.(?:jpg|jpeg|png|webp)', re.IGNORECASE)
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
    pending_thumbnail = None
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

    def remote_run(remote, *, retry_255=False, retry_timeout=False, **kwargs):
        increment('ssh_roundtrips')
        options = dict(kwargs)
        if options.get('text') or options.get('universal_newlines'):
            options.setdefault('encoding', 'utf-8')
        options.setdefault('timeout', 120)
        timeout_budget = options.get('timeout')
        started = time.monotonic()
        argv = ssh_argv(remote)

        def retry_once():
            retry_options = dict(options)
            if isinstance(timeout_budget, (int, float)):
                remaining = float(timeout_budget) - (time.monotonic() - started)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, timeout_budget)
                retry_options['timeout'] = remaining
            increment('ssh_roundtrips')
            return _RUN(argv, **retry_options)

        try:
            result = _RUN(argv, **options)
        except subprocess.CalledProcessError as exc:
            if exc.returncode != 255:
                raise
            diagnose_once()
            if retry_255:
                return retry_once()
            raise
        except subprocess.TimeoutExpired:
            if retry_timeout:
                return retry_once()
            raise
        except (OSError, subprocess.SubprocessError):
            raise
        if getattr(result, 'returncode', 0) == 255:
            diagnose_once()
            if retry_255:
                return retry_once()
        return result

    def validate_guarded_payload(raw):
        guarded_actions = {
            'draft-standard', 'draft-fast', 'public-fast', 'public-standard',
            'reformat', 'fix-excerpt', 'promote-draft',
        }
        if action not in guarded_actions:
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
        expected_meta = payload.get('expected_meta')
        updates_meta = payload.get('updates_meta')
        if type(post_id) is not int or post_id not in allowed_ids:
            raise ValueError('unexpected_wordpress_update_target')
        required_expected = {
            'post_status', 'post_title', 'post_name', 'post_excerpt', 'content_sha256',
        }
        allowed_expected_sets = {frozenset(required_expected)}
        if action in {'public-standard', 'draft-standard'}:
            allowed_expected_sets.add(frozenset(required_expected | {'category_ids'}))
        expected_status = 'publish' if action in {*_PUBLIC_EDIT_ACTIONS, 'fix-excerpt'} else 'draft'
        if (not isinstance(expected, dict) or frozenset(expected) not in allowed_expected_sets
                or expected.get('post_status') != expected_status
                or not re.fullmatch(r'[0-9a-f]{64}', expected.get('content_sha256', ''))
                or any(not isinstance(expected[key], str) or '\x00' in expected[key]
                       for key in required_expected)
                or ('category_ids' in expected and (
                    not isinstance(expected['category_ids'], list)
                    or any(type(value) is not int or value <= 0 for value in expected['category_ids'])
                    or len(expected['category_ids']) != len(set(expected['category_ids']))))):
            raise ValueError('invalid_guarded_wordpress_expectation')
        if not isinstance(updates, dict) or any(
                not isinstance(value, str) or '\x00' in value for value in updates.values()):
            raise ValueError('invalid_guarded_wordpress_update')
        if (expected_meta is None) != (updates_meta is None):
            raise ValueError('invalid_guarded_wordpress_meta_expectation')
        if expected_meta is not None:
            if (action not in {'public-standard', 'draft-standard'}
                    or expected_rank_math_meta is None
                    or not isinstance(expected_meta, dict) or not isinstance(updates_meta, dict)
                    or set(expected_meta) != set(expected_rank_math_meta)
                    or set(updates_meta) != set(expected_rank_math_meta)
                    or any(value is not None and (
                        not isinstance(value, str) or '\x00' in value)
                        for value in expected_meta.values())
                    or updates_meta != expected_rank_math_meta):
                raise ValueError('invalid_guarded_wordpress_meta_expectation')
        if action == 'promote-draft':
            allowed_field_sets = {frozenset({'post_status'})}
            if updates.get('post_status') != 'publish':
                raise ValueError('unexpected_wordpress_update_flags')
        elif action == 'reformat':
            allowed_field_sets = {frozenset({'post_content'})}
        elif action == 'fix-excerpt':
            allowed_field_sets = {frozenset({'post_excerpt'})}
        elif action == 'draft-fast':
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

    def validate_category_payload(raw):
        if action != 'repair-draft-category':
            raise ValueError('guarded_category_mutation_not_allowed')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        if not isinstance(raw, str):
            raise ValueError('guarded_category_payload_required')
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid_guarded_category_payload') from exc
        if (not isinstance(payload, dict)
                or set(payload) != {'protocol', 'post_id', 'expected', 'target_category_id'}
                or payload.get('protocol') != 1):
            raise ValueError('invalid_guarded_category_payload')
        post_id = payload.get('post_id')
        target = payload.get('target_category_id')
        expected = payload.get('expected')
        required_expected = {
            'post_status', 'post_title', 'post_name', 'post_excerpt',
            'content_sha256', 'category_ids',
        }
        if (type(post_id) is not int or post_id not in allowed_ids
                or type(target) is not int or target <= 0
                or not isinstance(expected, dict) or set(expected) != required_expected
                or expected.get('post_status') != 'draft'
                or not re.fullmatch(r'[0-9a-f]{64}', expected.get('content_sha256', ''))
                or any(not isinstance(expected.get(key), str) or '\x00' in expected[key]
                       for key in required_expected - {'category_ids'})
                or not isinstance(expected.get('category_ids'), list)
                or any(type(value) is not int or value <= 0 for value in expected['category_ids'])):
            raise ValueError('invalid_guarded_category_expectation')
        return payload

    def validate_thumbnail_payload(raw):
        if not image_mutation_allowed or action not in _FEATURED_IMAGE_ACTIONS:
            raise ValueError('guarded_thumbnail_mutation_not_allowed')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        if not isinstance(raw, str):
            raise ValueError('guarded_thumbnail_payload_required')
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid_guarded_thumbnail_payload') from exc
        if (not isinstance(payload, dict)
                or set(payload) != {
                    'protocol', 'post_id', 'expected',
                    'expected_thumbnail_id', 'attachment_id',
                }
                or payload.get('protocol') != 1):
            raise ValueError('invalid_guarded_thumbnail_payload')
        post_id = payload.get('post_id')
        attachment_id = payload.get('attachment_id')
        expected_thumb = payload.get('expected_thumbnail_id')
        expected = payload.get('expected')
        required_expected = {
            'post_status', 'post_title', 'post_name', 'post_excerpt', 'content_sha256',
        }
        if action == 'replace-featured-image':
            expected_statuses = {'publish', 'draft', 'pending', 'future', 'private'}
        else:
            expected_statuses = {'publish'} if action in _PUBLIC_EDIT_ACTIONS else {'draft'}
        if (type(post_id) is not int or post_id not in allowed_ids
                or type(attachment_id) is not int or attachment_id <= 0
                or (expected_thumb is not None and (type(expected_thumb) is not int or expected_thumb <= 0))
                or not isinstance(expected, dict) or set(expected) != required_expected
                or expected.get('post_status') not in expected_statuses
                or not re.fullmatch(r'[0-9a-f]{64}', expected.get('content_sha256', ''))
                or any(not isinstance(value, str) or '\x00' in value for value in expected.values())):
            raise ValueError('invalid_guarded_thumbnail_expectation')
        readable_ids.add(attachment_id)
        return payload

    def validate_attachment_alt_payload(raw):
        if action != 'replace-featured-image':
            raise ValueError('guarded_attachment_alt_mutation_not_allowed')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        if not isinstance(raw, str):
            raise ValueError('guarded_attachment_alt_payload_required')
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid_guarded_attachment_alt_payload') from exc
        if (not isinstance(payload, dict)
                or set(payload) != {
                    'protocol', 'post_id', 'expected', 'attachment_id', 'expected_alt', 'alt_text',
                }
                or payload.get('protocol') != 1):
            raise ValueError('invalid_guarded_attachment_alt_payload')
        post_id = payload.get('post_id')
        attachment_id = payload.get('attachment_id')
        expected = payload.get('expected')
        expected_alt = payload.get('expected_alt')
        alt_text = payload.get('alt_text')
        required_expected = {
            'post_status', 'post_title', 'post_name', 'post_excerpt', 'content_sha256',
        }
        if (type(post_id) is not int or post_id not in allowed_ids
                or type(attachment_id) is not int or attachment_id not in readable_ids
                or not isinstance(expected, dict) or set(expected) != required_expected
                or expected.get('post_status') not in {'publish', 'draft', 'pending', 'future', 'private'}
                or not re.fullmatch(r'[0-9a-f]{64}', expected.get('content_sha256', ''))
                or any(not isinstance(value, str) or '\x00' in value for value in expected.values())
                or (expected_alt is not None and (
                    not isinstance(expected_alt, str) or '\x00' in expected_alt))
                or not isinstance(alt_text, str) or not alt_text or len(alt_text) > 180
                or '\x00' in alt_text):
            raise ValueError('invalid_guarded_attachment_alt_expectation')
        return payload

    def validate_attachment_sha_lookup_payload(raw):
        if action not in _FEATURED_IMAGE_ACTIONS:
            raise ValueError('attachment_sha_lookup_not_allowed')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid_attachment_sha_lookup_payload') from exc
        if (not isinstance(payload, dict)
                or set(payload) != {'protocol', 'post_id', 'sha256'}
                or payload.get('protocol') != 1
                or type(payload.get('post_id')) is not int
                or payload['post_id'] not in allowed_ids
                or not re.fullmatch(r'[0-9a-f]{64}', payload.get('sha256', ''))):
            raise ValueError('invalid_attachment_sha_lookup_payload')
        return payload

    def validate_publish_gate_record_payload(raw):
        if action not in _FEATURED_IMAGE_ACTIONS:
            raise ValueError('publish_attestation_write_not_allowed')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            payload = json.loads(raw) if isinstance(raw, str) else None
        except ValueError as exc:
            raise ValueError('invalid_publish_attestation_payload') from exc
        required = {
            'protocol', 'post_id', 'content_sha256', 'review_digest', 'title_sha256',
            'thumbnail_id', 'image_sha256', 'alt_text_sha256', 'approval_kind',
            'approval_evidence_sha256', 'expires_at_gmt', 'requires_live_state',
        }
        sha_keys = {
            'content_sha256', 'review_digest', 'title_sha256', 'image_sha256',
            'alt_text_sha256', 'approval_evidence_sha256',
        }
        if (not isinstance(payload, dict) or set(payload) != required
                or payload.get('protocol') != 1
                or type(payload.get('post_id')) is not int or payload['post_id'] not in allowed_ids
                or type(payload.get('thumbnail_id')) is not int or payload['thumbnail_id'] <= 0
                or payload.get('approval_kind') not in {'manual_user_selected', 'automated_visual_review'}
                or type(payload.get('requires_live_state')) is not bool
                or any(not re.fullmatch(r'[0-9a-f]{64}', payload.get(key, '')) for key in sha_keys)
                or not isinstance(payload.get('expires_at_gmt'), str)
                or '\x00' in payload['expires_at_gmt']):
            raise ValueError('invalid_publish_attestation_payload')
        readable_ids.add(payload['thumbnail_id'])
        return payload

    def validate_publish_gate_validate_payload(raw):
        if action != 'promote-draft':
            raise ValueError('publish_attestation_validate_not_allowed')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            payload = json.loads(raw) if isinstance(raw, str) else None
        except ValueError as exc:
            raise ValueError('invalid_publish_attestation_validate_payload') from exc
        if (not isinstance(payload, dict)
                or set(payload) != {'protocol', 'post_id', 'expected_review_digest'}
                or payload.get('protocol') != 1
                or type(payload.get('post_id')) is not int or payload['post_id'] not in allowed_ids
                or not re.fullmatch(r'[0-9a-f]{64}', payload.get('expected_review_digest') or '')):
            raise ValueError('invalid_publish_attestation_validate_payload')
        return payload

    def validate_featured_image_lock_payload(raw):
        if action not in _FEATURED_IMAGE_ACTIONS:
            raise ValueError('featured_image_lock_not_allowed')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid_featured_image_lock_payload') from exc
        if (not isinstance(payload, dict)
                or set(payload) != {'protocol', 'post_id', 'action', 'token', 'ttl_seconds'}
                or payload.get('protocol') != 1
                or type(payload.get('post_id')) is not int
                or payload['post_id'] not in allowed_ids
                or payload.get('action') not in {'acquire', 'release', 'mark_import', 'complete_import'}
                or not isinstance(payload.get('token'), str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', payload['token'])
                or type(payload.get('ttl_seconds')) is not int
                or (payload['action'] == 'acquire' and not 30 <= payload['ttl_seconds'] <= 900)
                or (payload['action'] != 'acquire' and payload['ttl_seconds'] != 0)):
            raise ValueError('invalid_featured_image_lock_payload')
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
                            ['--fields=post_status,post_title,post_content', '--format=json', '--allow-root'],
                            ['--fields=post_status,post_title,post_name,post_content,post_excerpt',
                             '--format=json', '--allow-root'],
                            ['--fields=ID,guid,post_title,post_mime_type', '--format=json', '--allow-root']):
                raise ValueError('unexpected_wordpress_get_flags')
            return
        if (action in {'repair-draft-category', 'draft-standard'}
                and len(wp) == 8
                and wp[:3] == ['post', 'term', 'list']
                and wp[3].isdigit() and int(wp[3]) in allowed_ids
                and wp[4:] == ['category', '--fields=term_id,name,slug', '--format=json', '--allow-root']):
            return
        if wp == ['eval', GUARDED_POST_MUTATION_SCRIPT, '--allow-root']:
            return 'guarded_mutation'
        if (action == 'repair-draft-category'
                and wp == ['eval', GUARDED_CATEGORY_MUTATION_SCRIPT, '--allow-root']):
            return 'guarded_category_mutation'
        if (image_mutation_allowed and action in _FEATURED_IMAGE_ACTIONS
                and wp == ['eval', GUARDED_THUMBNAIL_MUTATION_SCRIPT, '--allow-root']):
            return 'guarded_thumbnail_mutation'
        if (action == 'replace-featured-image'
                and wp == ['eval', GUARDED_ATTACHMENT_ALT_MUTATION_SCRIPT, '--allow-root']):
            return 'guarded_attachment_alt_mutation'
        if (action in _FEATURED_IMAGE_ACTIONS
                and wp == ['eval', ATTACHMENT_SHA_LOOKUP_SCRIPT, '--allow-root']):
            return 'attachment_sha_lookup'
        if (action in _FEATURED_IMAGE_ACTIONS
                and wp == ['eval', FEATURED_IMAGE_LOCK_SCRIPT, '--allow-root']):
            return 'featured_image_lock'
        if (action in _FEATURED_IMAGE_ACTIONS
                and wp == ['eval', PUBLISH_GATE_RECORD_SCRIPT, '--allow-root']):
            return 'publish_attestation_write'
        if (action == 'promote-draft'
                and wp == ['eval', PUBLISH_GATE_VALIDATE_SCRIPT, '--allow-root']):
            return 'publish_attestation_validate'
        if (action == 'import-section-image'
                and wp == ['eval', SECTION_IMAGE_SNAPSHOT_SCRIPT, '--allow-root']):
            return 'section_snapshot'
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
        if (allow_image and action == 'draft-standard' and len(wp) == 6 and wp[:2] == ['media', 'import']
                and _REMOTE_IMAGE.fullmatch(wp[2])
                and wp[3].startswith('--post_id=') and wp[3].split('=', 1)[1].isdigit()
                and int(wp[3].split('=', 1)[1]) in allowed_ids
                and int(_REMOTE_IMAGE.fullmatch(wp[2]).group(1)) == int(wp[3].split('=', 1)[1])
                and wp[4:] == ['--porcelain', '--allow-root']):
            return 'media_import'
        if (image_mutation_allowed and action in _FEATURED_IMAGE_ACTIONS
                and len(wp) == 8 and wp[:2] == ['media', 'import']
                and _REMOTE_IMAGE.fullmatch(wp[2])
                and wp[3].startswith('--post_id=') and wp[3].split('=', 1)[1].isdigit()
                and int(wp[3].split('=', 1)[1]) in allowed_ids
                and int(_REMOTE_IMAGE.fullmatch(wp[2]).group(1)) == int(wp[3].split('=', 1)[1])
                and wp[4].startswith('--title=') and '\x00' not in wp[4]
                and wp[5].startswith('--alt=') and '\x00' not in wp[5]
                and wp[6:] == ['--porcelain', '--allow-root']):
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
        # The exact #848 full-reviewed legacy-draft onboarding must read the
        # preserved thumbnail baseline even though it performs NO image import.
        # Scope this extra read-only permission to that immutable post ID.
        if (action == 'draft-standard' and len(wp) == 6
                and wp[:3] == ['post', 'meta', 'get']
                and wp[3] == '848' and 848 in allowed_ids
                and wp[4:] == ['_thumbnail_id', '--allow-root']):
            return
        if (image_mutation_allowed and action in {*_FEATURED_IMAGE_ACTIONS, 'import-section-image'}
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
        raise ValueError('unexpected_wordpress_command_during_editorial_ssh')

    def run(command, *args, **kwargs):
        nonlocal pending_thumbnail
        previous_thumbnail = pending_thumbnail
        pending_thumbnail = None
        if args or not isinstance(command, (list, tuple)):
            raise ValueError('unexpected_subprocess_call_during_editorial_ssh')
        command = list(command)
        if command[:5] == _WP_PREFIX:
            wp = command[5:]
            kind = validate_wp(wp)
            if previous_thumbnail is not None and wp == previous_thumbnail[0]:
                increment('wp_snapshot_reuses')
                value = previous_thumbnail[1]
                result = subprocess.CompletedProcess(command, 0 if value is not None else 1,
                                                     stdout=(value or ''), stderr='')
                if kwargs.get('check') and result.returncode:
                    raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout)
                return result
            if (action == 'replace-featured-image' and wp[:2] == ['post', 'get']
                    and wp[3:] == ['--fields=post_status,post_title,post_name,post_content,post_excerpt',
                                  '--format=json', '--allow-root']
                    and kwargs.get('text')):
                remote = ('sudo docker exec -i wordpress_app wp eval '
                          + shlex.quote(POST_THUMBNAIL_SNAPSHOT_SCRIPT) + ' --allow-root')
                options = dict(kwargs)
                options['input'] = json.dumps({'post_id': int(wp[2])})
                result = remote_run(remote, retry_255=True, **options)
                if result.returncode == 0:
                    payload = json.loads(result.stdout)
                    if (not isinstance(payload.get('post'), dict)
                            or set(payload['post']) != {'post_status', 'post_title', 'post_name', 'post_content', 'post_excerpt'}
                            or payload.get('thumbnail_id') is not None and not isinstance(payload['thumbnail_id'], str)):
                        raise ValueError('invalid_image_baseline_snapshot')
                    pending_thumbnail = (['post', 'meta', 'get', wp[2], '_thumbnail_id', '--allow-root'], payload['thumbnail_id'])
                    if isinstance(payload.get('thumbnail_id'), str) and payload['thumbnail_id'].isdigit():
                        readable_ids.add(int(payload['thumbnail_id']))
                    result.stdout = json.dumps(payload['post'], ensure_ascii=False)
                return result
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
            if kind == 'guarded_category_mutation':
                validate_category_payload(kwargs.get('input'))
                remote = ('sudo docker exec -i wordpress_app wp eval '
                          + shlex.quote(GUARDED_CATEGORY_MUTATION_SCRIPT) + ' --allow-root')
                options = dict(kwargs)
                raw = options.get('input')
                if options.get('text') or options.get('universal_newlines'):
                    options['input'] = raw if isinstance(raw, str) else raw.decode('utf-8')
                else:
                    options['input'] = raw.encode('utf-8') if isinstance(raw, str) else raw
                return remote_run(remote, retry_255=True, **options)
            if kind == 'guarded_thumbnail_mutation':
                validate_thumbnail_payload(kwargs.get('input'))
                remote = ('sudo docker exec -i wordpress_app wp eval '
                          + shlex.quote(GUARDED_THUMBNAIL_MUTATION_SCRIPT) + ' --allow-root')
                options = dict(kwargs)
                raw = options.get('input')
                if options.get('text') or options.get('universal_newlines'):
                    options['input'] = raw if isinstance(raw, str) else raw.decode('utf-8')
                else:
                    options['input'] = raw.encode('utf-8') if isinstance(raw, str) else raw
                return remote_run(remote, retry_255=True, **options)
            if kind == 'guarded_attachment_alt_mutation':
                validate_attachment_alt_payload(kwargs.get('input'))
                remote = ('sudo docker exec -i wordpress_app wp eval '
                          + shlex.quote(GUARDED_ATTACHMENT_ALT_MUTATION_SCRIPT) + ' --allow-root')
                options = dict(kwargs)
                raw = options.get('input')
                if options.get('text') or options.get('universal_newlines'):
                    options['input'] = raw if isinstance(raw, str) else raw.decode('utf-8')
                else:
                    options['input'] = raw.encode('utf-8') if isinstance(raw, str) else raw
                return remote_run(remote, retry_255=True, **options)
            if kind == 'attachment_sha_lookup':
                validate_attachment_sha_lookup_payload(kwargs.get('input'))
                remote = ('sudo docker exec -i wordpress_app wp eval '
                          + shlex.quote(ATTACHMENT_SHA_LOOKUP_SCRIPT) + ' --allow-root')
                options = dict(kwargs)
                raw = options.get('input')
                if options.get('text') or options.get('universal_newlines'):
                    options['input'] = raw if isinstance(raw, str) else raw.decode('utf-8')
                else:
                    options['input'] = raw.encode('utf-8') if isinstance(raw, str) else raw
                result = remote_run(remote, retry_255=True, **options)
                if result.returncode == 0:
                    observed = json.loads(result.stdout or '{}')
                    ids = observed.get('attachment_ids') if isinstance(observed, dict) else None
                    if observed.get('status') != 'ok' or not isinstance(ids, list) or any(
                            type(value) is not int or value <= 0 for value in ids):
                        raise ValueError('invalid_attachment_sha_lookup_response')
                    readable_ids.update(ids)
                return result
            if kind == 'featured_image_lock':
                validate_featured_image_lock_payload(kwargs.get('input'))
                remote = ('sudo docker exec -i wordpress_app wp eval '
                          + shlex.quote(FEATURED_IMAGE_LOCK_SCRIPT) + ' --allow-root')
                options = dict(kwargs)
                raw = options.get('input')
                if options.get('text') or options.get('universal_newlines'):
                    options['input'] = raw if isinstance(raw, str) else raw.decode('utf-8')
                else:
                    options['input'] = raw.encode('utf-8') if isinstance(raw, str) else raw
                # The payload token makes acquire/release replay-safe: an acquire
                # with the same token is reentrant and release of a missing lock is
                # idempotent. One SSH-255 replay is therefore bounded and safe.
                return remote_run(remote, retry_255=True, retry_timeout=True, **options)
            if kind == 'publish_attestation_write':
                validate_publish_gate_record_payload(kwargs.get('input'))
                remote = ('sudo docker exec -i wordpress_app wp eval '
                          + shlex.quote(PUBLISH_GATE_RECORD_SCRIPT) + ' --allow-root')
                options = dict(kwargs)
                return remote_run(remote, retry_255=True, **options)
            if kind == 'publish_attestation_validate':
                validate_publish_gate_validate_payload(kwargs.get('input'))
                remote = ('sudo docker exec -i wordpress_app wp eval '
                          + shlex.quote(PUBLISH_GATE_VALIDATE_SCRIPT) + ' --allow-root')
                options = dict(kwargs)
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
                # The domain helper owns ambiguous import reconciliation.  The
                # transport only expands readable IDs when stdout is a valid ID;
                # empty/garbled success output must reach the helper so it can do
                # exactly one SHA reconcile instead of inviting a re-import.
                if attachment_id.isdigit() and int(attachment_id) > 0:
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
            return remote_run(remote, retry_255=True, retry_timeout=True, **options)

        if (image_mutation_allowed
                and command[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'sha256sum']
                and len(command) == 6):
            remote_path = command[5]
            image_match = _REMOTE_IMAGE.fullmatch(remote_path)
            section_image_match = _REMOTE_SECTION_IMAGE.fullmatch(remote_path)
            allowed_hash = (
                (image_match and int(image_match.group(1)) in allowed_ids)
                or (section_image_match and int(section_image_match.group(1)) in allowed_ids)
            )
            if allowed_hash:
                remote = 'sudo docker exec wordpress_app sha256sum ' + shlex.quote(remote_path)
                return remote_run(remote, retry_255=True, **kwargs)

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
    annotate(transport=config.mode, transport_adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
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
            if '--onboard-legacy-draft' in request.cli_args:
                parser.error('legacy draft onboarding requires a fully reviewed bundle')
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
            if '--onboard-legacy-draft' in request.cli_args:
                from agents.legacy_draft_onboarding import classify_legacy_draft_848
                decision = classify_legacy_draft_848(
                    post_ids[0], bundle, request.expected_content_sha256,
                    confirmed='--confirm-update' in request.cli_args,
                    edit_intent=request.cli_args[request.cli_args.index('--edit-intent') + 1]
                    if '--edit-intent' in request.cli_args and
                    request.cli_args.index('--edit-intent') + 1 < len(request.cli_args)
                    else '',
                    image_path=image_path, resume=request.resume,
                    confirm_title_change=request.confirm_title_change)
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
        annotate(route=decision['route'])
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
        with decision_context, wordpress_transport(transport), \
                patch.object(sys, 'argv', ['editorial_cli.py', *request.cli_args]):
            try:
                editorial_cli.main()
            except Exception as exc:
                receipt = getattr(exc, 'failure_receipt', None)
                stage = getattr(exc, 'failure_stage', None)
                if receipt:
                    failure = {
                        'status': 'blocked',
                        'failure_stage': stage,
                        'failure_receipt': receipt,
                        'automatic_retry': False,
                    }
                    if request.output_path is not None:
                        request.output_path.parent.mkdir(parents=True, exist_ok=True)
                        request.output_path.write_text(
                            json.dumps(failure, ensure_ascii=False, indent=2) + '\n',
                            encoding='utf-8')
                    print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
                raise

    # prepare-draft is the user-facing one-shot path. Keep the catalog follow-up
    # outside the WordPress transport context so it uses the normal Direct SSH
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
