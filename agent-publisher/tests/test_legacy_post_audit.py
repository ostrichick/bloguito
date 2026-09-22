"""Focused guards for completeness and conservative read-only audit labels."""

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'audit_legacy_posts.py'
spec = importlib.util.spec_from_file_location('bloguito_legacy_audit', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def post(post_id, markup, title='예시'):
    return {'id': post_id, 'date': '2026-09-22T09:00:00',
            'modified': '2026-09-22T10:00:00', 'status': 'publish',
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
        responses = iter([response([post(1, '<p>첫 글</p>')], 2, 2),
                          response([post(2, '<p>둘째 글</p>')], 2, 2)])
        self.assertEqual([1, 2], [p['id'] for p in audit.fetch_public_posts(
            'https://lifeinfo24.org', opener=lambda *a, **k: next(responses))])

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


if __name__ == '__main__':
    unittest.main()
