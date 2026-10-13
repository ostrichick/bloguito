"""Pure command-argument parser for the restricted editorial SSH adapter.

The entrypoint still owns action metadata, the request value object, and the
transport command allowlist. This module cannot run SSH, WordPress or filesystem
mutations, preserving the public CLI and existing adapter contract.
"""
from __future__ import annotations

from pathlib import Path


def parse_cli_request(cli_args, *, actions: dict, request_type, value_flags: set):
    if not cli_args or cli_args[0] not in actions:
        raise ValueError('unsupported_editorial_ssh_action')
    action = cli_args[0]
    meta = actions[action]
    positional = cli_args[1] if len(cli_args) > 1 and not cli_args[1].startswith('--') else None
    ids = set()
    values = {}
    confirm_title_change = False
    resume = False
    promotion_ids_seen = False
    index = 1
    while index < len(cli_args):
        value = cli_args[index]
        if value in value_flags:
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
    return request_type(
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
