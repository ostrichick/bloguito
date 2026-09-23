"""Focused guards for completeness and conservative read-only audit labels."""

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError
from uuid import UUID


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'audit_legacy_posts.py'
spec = importlib.util.spec_from_file_location('bloguito_legacy_audit', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def post(post_id, markup, title='예시'):
    return {'id': post_id, 'date': '2026-09-22T09:00:00',
            'modified': '2026-09-22T10:00:00', 'status': 'publish',
            'slug': f'post-{post_id}', 'categories': [], 'featured_media': 0,
            'link': f'https://lifeinfo24.org/?p={post_id}',
            'title': {'rendered': title}, 'content': {'rendered': markup},
            'excerpt': {'rendered': '짧은 답변'}}


def response(items, total, pages):
    handle = Mock()
    handle.read.return_value = json.dumps(items).encode('utf-8')
    handle.headers = {'X-WP-Total': str(total), 'X-WP-TotalPages': str(pages)}
    context = MagicMock()
    context.__enter__.return_value = handle
    return context


class LegacyAuditTests(unittest.TestCase):
    def test_complete_pagination(self):
        responses = iter([response([post(i, '<p>글</p>') for i in range(1, 101)], 101, 2),
                          response([post(101, '<p>마지막</p>')], 101, 2)])
        inventory = audit.fetch_public_posts('https://lifeinfo24.org',
                                             opener=lambda *a, **k: next(responses), with_metadata=True)
        self.assertEqual(list(range(1, 102)), [p['id'] for p in inventory['posts']])
        self.assertEqual((101, 2, True),
                         (inventory['expected_total'], inventory['total_pages'], inventory['complete']))

    def test_rejects_inconsistent_page_headers_and_short_middle_page(self):
        first = [post(i, 'body') for i in range(1, 101)]
        for second, expected, pages in [([post(101, 'body')], 102, 2),
                                         ([post(101, 'body')], 101, 3),
                                         ([], 101, 2)]:
            with self.subTest(expected=expected, pages=pages, count=len(second)):
                replies = iter([response(first, 101, 2), response(second, expected, pages)])
                with self.assertRaises(ValueError):
                    audit.fetch_public_posts('https://lifeinfo24.org',
                                             opener=lambda *a, **k: next(replies))
        with self.assertRaisesRegex(ValueError, 'page headers disagree'):
            audit.fetch_public_posts('https://lifeinfo24.org',
                opener=lambda *a, **k: response([post(1, 'a')], 1, 2))

    def test_rejects_missing_headers_http_error_and_non_list(self):
        missing = response([post(1, 'body')], 1, 1)
        missing.__enter__.return_value.headers.pop('X-WP-Total')
        with self.assertRaisesRegex(ValueError, 'Missing or invalid WordPress header'):
            audit.fetch_public_posts('https://lifeinfo24.org', opener=lambda *a, **k: missing)
        with self.assertRaises(HTTPError):
            audit.fetch_public_posts('https://lifeinfo24.org', opener=lambda *a, **k: (
                _ for _ in ()).throw(HTTPError('https://lifeinfo24.org', 503, 'offline', {}, None)))
        with self.assertRaises(ValueError):
            audit.fetch_public_posts('https://lifeinfo24.org',
                opener=lambda *a, **k: response({'error': 'bad'}, 1, 1))

    def test_rejects_incomplete_duplicate_and_nonpublic(self):
        examples = [([post(1, 'a')], 2),
                    ([post(1, 'a'), post(1, 'b')], 2),
                    ([dict(post(1, 'a'), status='draft')], 1)]
        for items, expected in examples:
            with self.subTest(items=items, expected=expected):
                with self.assertRaises(ValueError):
                    audit.fetch_public_posts('https://lifeinfo24.org',
                        opener=lambda *a, **k: response(items, expected, 1))

    def test_new_layout_has_no_false_legacy_flag_and_bad_anchor_is_detected(self):
        markup = ('<div class="bloguito-article"><nav class="bloguito-toc">'
                  '<a href="#absent">이동</a></nav><h2 id="valid">내용</h2></div>')
        row = audit.inspect_post(post(1, markup))
        self.assertNotIn('legacy_layout', row['flags'])
        self.assertIn('broken_toc_anchor', row['flags'])
        self.assertEqual(['#absent'], row['toc_broken_anchors'])
        self.assertNotIn('fact_verified', row['flags'])

    def test_source_link_candidates_do_not_claim_verified_status(self):
        markup = ('<div class="bloguito-article"><h2>절차</h2>'
                  '<a href="javascript:void(0)">실행</a><a href="http://example.org/source">출처</a>'
                  '</div>')
        row = audit.inspect_post(post(7, markup))
        self.assertIn('source_section_missing_candidate', row['flags'])
        self.assertIn('link_target_candidate', row['flags'])
        self.assertEqual('unverified', row['fact_review_status'])
        self.assertEqual('unverified', row['visual_review_status'])
        self.assertEqual('unverified', row['link_behavior_review_status'])

    def test_review_register_only_supplies_due_date_and_invalidates_changed_content(self):
        first = audit.inspect_post(post(7, '<p>첫 글</p>'))
        second = audit.inspect_post(post(8, '<p>다른 글</p>'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'verified.json'
            entry = {'id': 7, 'rendered_sha256': first['rendered_sha256'],
                     'verification_status': 'human_verified', 'verified_by': 'editor',
                     'verified_at': '2026-09-21T10:00:00+09:00',
                     'review_until': '2026-09-22', 'source_urls': ['https://www.nts.go.kr/']}
            path.write_text(json.dumps({'schema_version': 1, 'site': 'https://lifeinfo24.org',
                                        'entries': [entry]}), encoding='utf-8')
            records = audit.load_review_register(path, 'https://lifeinfo24.org',
                                                 '2026-09-22T12:00:00+09:00')
            audit.annotate_review([first, second], records, datetime(2026, 9, 22).date())
            self.assertEqual(('due', True, 'unverified'),
                             (first['review_register_status'], first['review_due'], first['fact_review_status']))
            self.assertEqual(('unregistered', None),
                             (second['review_register_status'], second['review_due']))
            changed = audit.inspect_post(post(7, '<p>수정된 글</p>'))
            audit.annotate_review([changed], records, datetime(2026, 9, 22).date())
            self.assertEqual(('content_changed', True),
                             (changed['review_register_status'], changed['review_due']))
            upcoming = audit.inspect_post(post(7, '<p>첫 글</p>'))
            audit.annotate_review([upcoming], records, datetime(2026, 9, 21).date())
            self.assertEqual(('scheduled', False),
                             (upcoming['review_register_status'], upcoming['review_due']))
            path.write_text(json.dumps({'schema_version': 1, 'site': 'https://lifeinfo24.org',
                                        'entries': [{**entry, 'verified_by': ''}]}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Invalid review provenance'):
                audit.load_review_register(path, 'https://lifeinfo24.org',
                                           '2026-09-22T12:00:00+09:00')

    def test_complete_previous_snapshot_change_detection(self):
        old = post(7, '<p>이전 글</p>')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'previous.json'
            path.write_text(json.dumps({'schema_version': 2, 'site': 'https://lifeinfo24.org',
                                        'complete': True, 'expected_total': 1, 'total_pages': 1,
                                        'posts': [old]}), encoding='utf-8')
            previous = audit.load_previous(path, 'https://lifeinfo24.org')
            current = audit.inspect_post(post(7, '<p>변경된 글</p>'))
            new = audit.inspect_post(post(8, '<p>새 글</p>'))
            audit.annotate_review([current, new], None, datetime(2026, 9, 22).date())
            changes = audit.compare_previous([current, new], previous)
            self.assertEqual([{'id': 7, 'fields': ['rendered_sha256']}], changes['changed_posts'])
            self.assertEqual([8], changes['new_post_ids'])
            self.assertEqual('changed', current['change_status'])
            self.assertEqual([7, 8], changes['review_unknown_ids'])
            only_new = audit.inspect_post(post(8, '<p>새 글</p>'))
            audit.annotate_review([only_new], None, datetime(2026, 9, 22).date())
            self.assertEqual([7], audit.compare_previous([only_new], previous)[
                'missing_from_public_snapshot_ids'])
            path.write_text(json.dumps({'audited_at': '2026-09-22', 'posts': [old]}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Previous snapshot is unverified'):
                audit.load_previous(path, 'https://lifeinfo24.org')

    def test_failed_collection_never_creates_a_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = ['audit_legacy_posts.py', '--snapshot-dir', str(root / 'run'),
                    '--report', str(root / 'report.md')]
            with patch('sys.argv', args), patch.object(audit, 'fetch_public_posts',
                                                      side_effect=ValueError('Incomplete WordPress inventory')):
                with self.assertRaisesRegex(ValueError, 'Incomplete WordPress inventory'):
                    audit.main()
            self.assertFalse((root / 'run').exists())
            self.assertFalse((root / 'report.md').exists())

    def test_recurring_dry_run_is_byte_free_and_flags_changed_content(self):
        clock = datetime(2026, 9, 22, 12, tzinfo=audit.KST)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'dedicated'
            initial = audit.recurring_audit(root, 'https://lifeinfo24.org',
                opener=lambda *a, **k: response([post(7, '<p>original</p>')], 1, 1),
                now=clock, dry_run=True)
            self.assertTrue(initial['dry_run'])
            self.assertEqual({}, initial['new_flags_by_post_id'])
            self.assertFalse(initial['attention_required'])
            self.assertFalse(root.exists())
            before = audit.recurring_audit(root, 'https://lifeinfo24.org',
                opener=lambda *a, **k: response([post(7, '<p>original</p>')], 1, 1),
                now=clock)
            snapshot = root / 'latest.json'
            old_bytes = snapshot.read_bytes()
            changed = audit.recurring_audit(root, 'https://lifeinfo24.org',
                opener=lambda *a, **k: response([post(7, '<p>changed</p>')], 1, 1),
                now=clock + timedelta(hours=25), dry_run=True)
            self.assertEqual([{'id': 7, 'fields': ['rendered_sha256']}], changed['changed_posts'])
            self.assertEqual(1, changed['missed_expected_runs'])
            self.assertIn('public_inventory_changed', changed['alert_codes'])
            self.assertIn('missed_expected_runs', changed['alert_codes'])
            self.assertEqual(old_bytes, snapshot.read_bytes())
            self.assertEqual(1, len(list((root / 'runs').iterdir())))

    def test_recurring_failure_preserves_baseline_and_recovers(self):
        clock = datetime(2026, 9, 22, 12, tzinfo=audit.KST)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'dedicated'
            audit.recurring_audit(root, 'https://lifeinfo24.org',
                opener=lambda *a, **k: response([post(7, 'original')], 1, 1), now=clock)
            last = (root / 'latest.json').read_bytes()
            with self.assertRaises(HTTPError):
                audit.recurring_audit(root, 'https://lifeinfo24.org',
                    opener=lambda *a, **k: (_ for _ in ()).throw(HTTPError(
                        'https://lifeinfo24.org/?password=secret', 503, 'down', {}, None)),
                    now=clock + timedelta(hours=24))
            self.assertEqual(last, (root / 'latest.json').read_bytes())
            self.assertEqual('failed', json.loads((root / 'last-attempt.json').read_text())['status'])
            self.assertNotIn('password', (root / 'last-attempt.json').read_text())
            self.assertEqual(1, len(list((root / 'runs').iterdir())))
            recovered = audit.recurring_audit(root, 'https://lifeinfo24.org',
                opener=lambda *a, **k: response([post(7, 'updated')], 1, 1),
                now=clock + timedelta(hours=50))
            self.assertTrue(recovered['recovered_prior_failure'])
            self.assertEqual(2, recovered['missed_expected_runs'])
            self.assertIn('recovered_prior_failure', recovered['alert_codes'])

    def test_partial_second_page_http_failure_does_not_advance_checkpoint(self):
        clock = datetime(2026, 9, 22, 12, tzinfo=audit.KST)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'dedicated'
            audit.recurring_audit(root, 'https://lifeinfo24.org',
                opener=lambda *a, **k: response([post(7, 'original')], 1, 1), now=clock)
            checkpoint = (root / 'latest.json').read_bytes()
            calls = iter([response([post(i, 'content') for i in range(1, 101)], 101, 2),
                HTTPError('https://lifeinfo24.org/wp-json/', 503, 'down', {}, None)])
            def partial(*args, **kwargs):
                item = next(calls)
                if isinstance(item, HTTPError):
                    raise item
                return item
            with self.assertRaises(HTTPError):
                audit.recurring_audit(root, 'https://lifeinfo24.org',
                                      opener=partial, now=clock + timedelta(hours=24))
            self.assertEqual(checkpoint, (root / 'latest.json').read_bytes())
            self.assertEqual(1, len(list((root / 'runs').iterdir())))
            self.assertFalse((root / '.audit.lock').exists())

    def test_recurring_lock_and_corrupt_checkpoint_fail_closed(self):
        clock = datetime(2026, 9, 22, 12, tzinfo=audit.KST)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'dedicated'
            audit.recurring_audit(root, 'https://lifeinfo24.org',
                opener=lambda *a, **k: response([post(7, 'body')], 1, 1), now=clock)
            (root / '.audit.lock').mkdir()
            with self.assertRaisesRegex(ValueError, 'already locked'):
                audit.recurring_audit(root, 'https://lifeinfo24.org',
                    opener=lambda *a, **k: response([post(7, 'body')], 1, 1), now=clock)
            self.assertTrue((root / '.audit.lock').exists())
            (root / '.audit.lock').rmdir()
            pointer = root / 'latest.json'
            data = json.loads(pointer.read_text())
            data['snapshot_sha256'] = '0' * 64
            pointer.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                audit.recurring_audit(root, 'https://lifeinfo24.org',
                    opener=lambda *a, **k: response([post(7, 'body')], 1, 1), now=clock)

    def test_recurring_due_dates_flags_retention_and_cli_no_leaks(self):
        clock = datetime(2026, 9, 22, 12, tzinfo=audit.KST)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'dedicated'
            original = post(7, '<p>original</p>')
            record = audit.inspect_post(original)
            register = Path(directory) / 'register.json'
            register.write_text(json.dumps({'schema_version': 1, 'site': 'https://lifeinfo24.org',
                'entries': [{'id': 7, 'rendered_sha256': record['rendered_sha256'],
                    'verification_status': 'human_verified', 'verified_by': 'human',
                    'verified_at': '2026-09-21T12:00:00+09:00', 'review_until': '2026-09-22',
                    'source_urls': ['https://www.nts.go.kr/']}]}), encoding='utf-8')
            result = audit.recurring_audit(root, 'https://lifeinfo24.org',
                opener=lambda *a, **k: response([original], 1, 1),
                review_register=register, now=clock, retain=2)
            self.assertEqual([7], result['review_due_ids'])
            self.assertIn('review_due', result['alert_codes'])
            for offset in (24, 48):
                audit.recurring_audit(root, 'https://lifeinfo24.org',
                    opener=lambda *a, **k: response([original], 1, 1),
                    now=clock + timedelta(hours=offset), retain=2)
            self.assertEqual(2, len(list((root / 'runs').iterdir())))
            self.assertIsNotNone(audit._read_checkpoint(root, 'https://lifeinfo24.org')[0])
            error_url = 'https://lifeinfo24.org/?password=do-not-print'
            args = ['audit_legacy_posts.py', '--url', error_url,
                    '--recurring-state-dir', str(root), '--dry-run']
            with patch('sys.argv', args), patch('builtins.print') as output:
                with self.assertRaises(SystemExit) as failure:
                    audit.main()
            self.assertEqual(3, failure.exception.code)
            self.assertNotIn('do-not-print', str(output.call_args_list))

    def test_retention_preserves_forged_run_and_unrelated_sentinel(self):
        clock = datetime(2026, 9, 23, 9, tzinfo=audit.KST)
        fetch = lambda *a, **k: response([post(7, '<p>original</p>')], 1, 1)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'dedicated'
            audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                                  now=clock, retain=2)
            forged = state / 'runs' / '20260901T000000Z-deadbeef'
            forged.mkdir()
            (forged / 'public-rest-snapshot.json').write_text('not valid JSON', encoding='utf-8')
            sentinel = forged / 'unrelated-sentinel.txt'
            sentinel.write_text('retain me', encoding='utf-8')
            result = audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                                           now=clock + timedelta(hours=1), retain=2)
            self.assertTrue(forged.is_dir())
            self.assertEqual('retain me', sentinel.read_text(encoding='utf-8'))
            self.assertIsNone(result.get('pruned_runs'))
            self.assertEqual('ValueError', result['retention_warning'])
            self.assertIn('retention_requires_attention', result['alert_codes'])
            self.assertEqual(3, len(list((state / 'runs').iterdir())))
            self.assertIsNotNone(audit._read_checkpoint(state, 'https://lifeinfo24.org')[0])

    def test_retention_prunes_only_integrity_verified_old_runs(self):
        clock = datetime(2026, 9, 23, 9, tzinfo=audit.KST)
        fetch = lambda *a, **k: response([post(7, '<p>original</p>')], 1, 1)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'dedicated'
            first = audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                                          now=clock, retain=2)
            first_run = next((state / 'runs').iterdir())
            manifest = json.loads((first_run / 'run-manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(first_run.name, manifest['run_id'])
            self.assertEqual('https://lifeinfo24.org', manifest['site'])
            self.assertIsNone(first.get('retention_warning'))
            second = audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                                           now=clock + timedelta(hours=1), retain=2)
            self.assertEqual(0, second['pruned_runs'])
            third = audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                                          now=clock + timedelta(hours=2), retain=2)
            self.assertEqual(1, third['pruned_runs'])
            self.assertFalse(first_run.exists())
            self.assertEqual(2, len(list((state / 'runs').iterdir())))
            self.assertIsNone(third.get('retention_warning'))
            self.assertIsNotNone(audit._read_checkpoint(state, 'https://lifeinfo24.org')[0])

    def test_retention_orders_same_second_runs_by_precise_timestamp_not_random_suffix(self):
        clock = datetime(2026, 9, 23, 9, tzinfo=audit.KST)
        fetch = lambda *a, **k: response([post(7, '<p>original</p>')], 1, 1)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'dedicated'
            # Force run-name suffixes into reverse lexicographic order. A
            # name-based retention implementation deterministically keeps the
            # oldest run instead of the newer second run in this fixture.
            uuids = [UUID(f'{prefix}-0000-4000-8000-000000000001')
                     for prefix in ('f0000000', 'f1000000', '80000000',
                                    '81000000', '10000000', '11000000')]
            with patch.object(audit, 'uuid4', side_effect=uuids):
                audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                    now=clock.replace(microsecond=100000), retain=2)
                first = next((state / 'runs').iterdir())
                audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                    now=clock.replace(microsecond=200000), retain=2)
                third = audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                    now=clock.replace(microsecond=300000), retain=2)
            self.assertEqual(1, third['pruned_runs'])
            self.assertFalse(first.exists(), 'the oldest run must be pruned despite random names')
            self.assertEqual(2, len(list((state / 'runs').iterdir())))
            self.assertIsNotNone(audit._read_checkpoint(state, 'https://lifeinfo24.org')[0])

    def test_retention_ambiguous_equal_timestamps_preserves_all_runs(self):
        clock = datetime(2026, 9, 23, 9, tzinfo=audit.KST)
        fetch = lambda *a, **k: response([post(7, '<p>original</p>')], 1, 1)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'dedicated'
            audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                                  now=clock, retain=2)
            first = next((state / 'runs').iterdir())
            audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                                  now=clock, retain=2)
            third = audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                                          now=clock, retain=2)
            self.assertEqual('ValueError', third['retention_warning'])
            self.assertIn('retention_requires_attention', third['alert_codes'])
            self.assertTrue(first.exists())
            self.assertEqual(3, len(list((state / 'runs').iterdir())))

    def test_retention_never_partially_deletes_on_bad_manifest_hash_or_extra_file(self):
        clock = datetime(2026, 9, 23, 9, tzinfo=audit.KST)
        fetch = lambda *a, **k: response([post(7, '<p>original</p>')], 1, 1)
        for corruption in ('missing_manifest', 'invalid_hash', 'altered_report', 'extra_sentinel'):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as directory:
                state = Path(directory) / 'dedicated'
                audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                                      now=clock, retain=2)
                audit.recurring_audit(state, 'https://lifeinfo24.org', opener=fetch,
                                      now=clock + timedelta(hours=1), retain=2)
                first, second = sorted((state / 'runs').iterdir())
                if corruption == 'missing_manifest':
                    (first / 'run-manifest.json').unlink()
                elif corruption == 'invalid_hash':
                    manifest_path = first / 'run-manifest.json'
                    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                    manifest['sha256']['triage.json'] = '0' * 64
                    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
                elif corruption == 'altered_report':
                    (first / 'report.md').write_text('tampered', encoding='utf-8')
                else:
                    (first / 'unrelated-sentinel.txt').write_text('preserve', encoding='utf-8')
                result = audit.recurring_audit(state, 'https://lifeinfo24.org',
                    opener=fetch, now=clock + timedelta(hours=2), retain=2)
                self.assertEqual('ValueError', result['retention_warning'])
                self.assertIn('retention_requires_attention', result['alert_codes'])
                self.assertTrue(first.is_dir())
                self.assertTrue(second.is_dir())
                self.assertEqual(3, len(list((state / 'runs').iterdir())))
                self.assertIsNotNone(audit._read_checkpoint(state, 'https://lifeinfo24.org')[0])

    def test_linked_runs_directory_is_refused_before_collect_or_write(self):
        clock = datetime(2026, 9, 23, 9, tzinfo=audit.KST)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'dedicated'
            state.mkdir()
            external = Path(directory) / 'outside'
            external.mkdir()
            with patch.object(audit, '_linked_path', side_effect=lambda path: path.name == 'runs'):
                opener = Mock()
                with self.assertRaisesRegex(ValueError, 'runs directory is linked or unsafe'):
                    audit.recurring_audit(state, 'https://lifeinfo24.org', opener=opener,
                                          now=clock, retain=2)
                opener.assert_not_called()
            self.assertFalse((state / 'runs').exists())
            self.assertEqual([], list(external.iterdir()))
            try:
                (state / 'runs').symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError):
                pass  # Windows without symlink privilege: mock branch still tested.
            else:
                with self.assertRaisesRegex(ValueError, 'runs directory is linked or unsafe'):
                    audit.recurring_audit(state, 'https://lifeinfo24.org',
                        opener=Mock(), now=clock, retain=2)
                self.assertEqual([], list(external.iterdir()))


if __name__ == '__main__':
    unittest.main()
