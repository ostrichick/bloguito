"""Focused guards for completeness and conservative read-only audit labels."""

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError


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


if __name__ == '__main__':
    unittest.main()
