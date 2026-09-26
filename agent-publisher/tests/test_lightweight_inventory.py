import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import sync_wordpress_inventory as inventory_sync
from agents.search_intent import duplicate_posts


class LightweightInventoryTests(unittest.TestCase):
    def test_sync_writes_schema_v2_without_post_content(self):
        body = '<p>hello https://example.org/official</p>'
        rows = [{
            'ID': 7,
            'post_title': 'Title',
            'post_status': 'publish',
            'content_sha256': hashlib.sha256(body.encode()).hexdigest(),
            'content_urls': ['https://example.org/official'],
        }]
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'inventory.json'
            with patch.object(inventory_sync, 'INVENTORY', target), \
                 patch.object(inventory_sync.subprocess, 'run', return_value=Mock(stdout=json.dumps(rows))) as run:
                inventory_sync.sync_inventory()
            saved = json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual(2, saved['schema_version'])
        self.assertNotIn('post_content', saved['posts'][0])
        self.assertEqual('eval', run.call_args.args[0][5])

    def test_new_post_duplicate_uses_url_signature_without_body(self):
        brief = {'required_title_terms': [], 'official_urls': ['https://example.org/a']}
        posts = [{
            'ID': 1, 'post_title': 'other', 'post_status': 'publish',
            'content_sha256': '0' * 64, 'content_urls': ['https://example.org/a'],
        }]
        self.assertEqual([posts[0]], duplicate_posts(brief, posts))

    def test_existing_post_candidate_is_hydrated_only_for_url_overlap(self):
        body = '<p>body https://example.org/a</p>'
        digest = hashlib.sha256(body.encode()).hexdigest()
        inventory = {
            'schema_version': 2,
            'checked_on': '2026-09-26',
            'posts': [
                {'ID': 1, 'post_title': 'candidate', 'post_status': 'publish',
                 'content_sha256': digest, 'content_urls': ['https://example.org/a']},
                {'ID': 2, 'post_title': 'unrelated', 'post_status': 'publish',
                 'content_sha256': 'f' * 64, 'content_urls': []},
            ],
        }
        brief = {'existing_post_id': 9, 'official_urls': ['https://example.org/a']}
        detail = {'ID': 1, 'post_title': 'candidate', 'post_status': 'publish', 'post_content': body}
        with patch.object(inventory_sync, 'fetch_post_detail', return_value=detail) as fetch:
            hydrated = inventory_sync.hydrate_duplicate_candidates(brief, inventory)
        fetch.assert_called_once_with(1)
        self.assertEqual(body, hydrated['posts'][0]['post_content'])
        self.assertNotIn('post_content', hydrated['posts'][1])


if __name__ == '__main__':
    unittest.main()
