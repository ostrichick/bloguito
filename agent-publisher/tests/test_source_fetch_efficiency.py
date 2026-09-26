import copy
import unittest
from unittest.mock import patch

from agents import editorial_writer


class SourceFetchEfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.brief = {
            'entity': '테스트',
            'official_urls': ['https://example.org/a', 'https://example.org/b'],
            'reference_urls': ['https://example.org/c'],
        }

    @staticmethod
    def fake_fetch(brief, source_type, url):
        return {
            'id': 'temporary',
            'url': url,
            'title': url.rsplit('/', 1)[-1],
            'text': 'x' * 100,
            'source_type': source_type,
            'fetched_at': '2026-09-26T19:00:00+09:00',
            'sha256': url,
        }

    def test_parallel_fetch_preserves_declared_order_and_ids(self):
        with patch.object(editorial_writer, '_fetch_single_source', side_effect=self.fake_fetch):
            rows = editorial_writer.fetch_sources(self.brief)
        self.assertEqual(['s0', 's1', 's2'], [row['id'] for row in rows])
        self.assertEqual(
            ['https://example.org/a', 'https://example.org/b', 'https://example.org/c'],
            [row['url'] for row in rows],
        )

    def test_subset_fetch_preserves_manual_metadata(self):
        existing = [
            {
                **self.fake_fetch(self.brief, 'official', 'https://example.org/a'),
                'id': 's0',
                'actions': [{'kind': 'lookup', 'label': '조회하기', 'url': 'https://example.org/a'}],
            },
            {**self.fake_fetch(self.brief, 'official', 'https://example.org/b'), 'id': 's1'},
            {**self.fake_fetch(self.brief, 'reference', 'https://example.org/c'), 'id': 's2'},
        ]
        refreshed = copy.deepcopy(existing[0])
        refreshed['text'] = 'y' * 100
        refreshed['sha256'] = 'newhash'
        refreshed.pop('actions', None)
        with patch.object(editorial_writer, '_fetch_single_source', return_value=refreshed):
            rows = editorial_writer.fetch_sources_subset(self.brief, existing, ['s0'])
        self.assertEqual('s0', rows[0]['id'])
        self.assertEqual('newhash', rows[0]['sha256'])
        self.assertEqual(existing[0]['actions'], rows[0]['actions'])

    def test_subset_rejects_unknown_source_id(self):
        with self.assertRaisesRegex(ValueError, 'unknown_or_duplicate_source_id'):
            editorial_writer.fetch_sources_subset(self.brief, [], ['s9'])


if __name__ == '__main__':
    unittest.main()
