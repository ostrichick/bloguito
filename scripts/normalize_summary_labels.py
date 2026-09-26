"""Audit/apply the fixed label-only WordPress migration with CAS and backups.

This scoped updater intentionally does not regenerate articles or change claims.
The permanent WP backend locks each row, checks CAS, backs up, applies only
allowlisted label spans and verifies preserved fields before committing.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent-publisher'))
from agents.summary_label import normalize_summary_labels

FIELDS = ['post_title', 'post_status', 'post_excerpt', 'post_name', 'post_date', 'post_date_gmt', 'post_author']


class LocalWordPress:
    """The same fixed migration checks, executed on the WordPress host."""
    prefix = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']

    def inventory(self):
        result = subprocess.run(self.prefix + ['post', 'list', '--post_type=post',
            '--post_status=any,trash', '--posts_per_page=-1',
            '--fields=ID,' + ','.join(FIELDS) + ',post_content', '--format=json', '--allow-root'],
            capture_output=True, encoding='utf-8', timeout=60, check=True)
        return json.loads(result.stdout)

    def apply(self, payload):
        result = subprocess.run(['sudo', 'docker', 'exec', '-i', 'wordpress_app', 'wp',
            'eval-file', '/tmp/bloguito-summary-label-wp.php', '--allow-root'],
            input=json.dumps(payload, ensure_ascii=False), capture_output=True,
            encoding='utf-8', timeout=60)
        if result.returncode:
            raise RuntimeError('local_wp_operation_failed: ' + result.stderr[:500])
        return json.loads(result.stdout)


class Transport:
    def __init__(self, host, distro):
        if not re.fullmatch(r'[A-Za-z0-9_.@-]+', host) or not re.fullmatch(r'[A-Za-z0-9_.-]+', distro):
            raise ValueError('invalid_transport')
        self.prefix = ['wsl.exe', '-d', distro, '--', 'tailscale', 'ssh', host]

    def run(self, remote, data=None):
        result = subprocess.run(self.prefix + [remote], input=data, capture_output=True,
                                encoding='utf-8', timeout=120)
        if result.returncode:
            raise RuntimeError('remote_operation_failed: ' + result.stderr[:500])
        return result.stdout

    def inventory(self):
        return json.loads(self.run('sudo docker exec wordpress_app wp post list --post_type=post '
            '--post_status=any,trash --posts_per_page=-1 --fields=ID,' + ','.join(FIELDS) +
            ',post_content --format=json --allow-root'))

    def apply(self, payload):
        return json.loads(self.run('sudo docker exec -i wordpress_app wp eval-file '
            '/tmp/bloguito-summary-label-wp.php --allow-root', json.dumps(payload, ensure_ascii=False)))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--host')
    mode.add_argument('--local-wordpress', action='store_true')
    parser.add_argument('--wsl-distro', default='Ubuntu-24.04')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--confirm-update', action='store_true')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    transport = LocalWordPress() if args.local_wordpress else Transport(args.host, args.wsl_distro)
    before = transport.inventory()
    save(args.output_dir / 'before.json', before)
    targets, report_rows = [], []
    for row in before:
        updated, report = normalize_summary_labels(row['post_content'])
        report_rows.append({'id': row['ID'], 'status': row['post_status'], **report})
        if report['edits']:
            targets.append({'id': int(row['ID']), **report,
                            'preserved': {key: row[key] for key in FIELDS}})
    save(args.output_dir / 'plan.json', targets)
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'inventory_count': len(before),
              'inventory_statuses': dict(Counter(row['post_status'] for row in before)),
              'target_count': len(targets), 'targets_by_status': dict(Counter(p['preserved']['post_status'] for p in targets)),
              'rows': report_rows, 'applied': [], 'errors': [], 'apply_requested': args.confirm_update}
    save(args.output_dir / 'report.json', report)
    print(json.dumps({k: report[k] for k in ['inventory_count', 'target_count', 'targets_by_status']}, ensure_ascii=False), flush=True)
    if not args.confirm_update:
        return
    for target in targets:
        try:
            result = transport.apply(target)
            if result.get('id') != target['id'] or result.get('after_sha256') != target['after_sha256'] or result.get('verified') is not True:
                raise ValueError('invalid_saved_verification')
            report['applied'].append(result)
            print('Verified post ' + str(target['id']), flush=True)
        except Exception as exc:
            report['errors'].append({'id': target['id'], 'error': str(exc)})
            save(args.output_dir / 'report.json', report)
            raise
        save(args.output_dir / 'report.json', report)
    after = transport.inventory()
    save(args.output_dir / 'after.json', after)
    by_id = {int(row['ID']): row for row in after}
    if set(by_id) != {int(row['ID']) for row in before}:
        raise ValueError('inventory_changed_during_migration')
    for original in before:
        post_id = int(original['ID'])
        saved = by_id[post_id]
        content, _ = normalize_summary_labels(original['post_content'])
        if saved['post_content'] != content or any(saved[key] != original[key] for key in FIELDS):
            raise ValueError('full_inventory_verification_failed:' + str(post_id))
        _, check = normalize_summary_labels(saved['post_content'])
        if check['edits']:
            raise ValueError('remaining_legacy_heading:' + str(post_id))
    report['all_posts_verified'] = len(after)
    report['remaining_legacy_headings'] = 0
    report['completed_at'] = datetime.now(timezone.utc).isoformat()
    save(args.output_dir / 'report.json', report)
    print('All ' + str(len(after)) + ' posts verified; remaining legacy headings: 0', flush=True)


if __name__ == '__main__':
    main()
