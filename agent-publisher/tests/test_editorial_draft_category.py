import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents import editorial_draft_category as category_repair


class EditorialDraftCategoryTest(unittest.TestCase):
    def test_requires_specific_confirmation_and_sha(self):
        with self.assertRaisesRegex(ValueError, 'specific_draft_category_repair_confirmation_required'):
            category_repair.repair_reviewed_draft_category(239, None, confirmed=True)

    def test_rejects_changed_draft_before_wordpress_mutation(self):
        content = '<p>reviewed</p>'
        inventory = {
            'checked_on': '2026-09-24',
            'posts': [{
                'ID': 239,
                'post_status': 'draft',
                'post_title': 'title',
                'post_content': content,
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / 'drafts.json'
            index.write_text(json.dumps([{
                'id': 239,
                'fact_manifest': {'editorial_bundle': {
                    'brief': {'category_key': 'life-health'},
                    'plan': {'title': 'title'},
                    'sources': [],
                }},
            }]), encoding='utf-8')
            lock_root = Path(tmp) / 'data'
            lock_root.mkdir()
            fake_root = Path(tmp)
            with patch.object(category_repair, 'ROOT', fake_root), \
                    patch.object(category_repair, 'DRAFTS_INDEX_FILE', index), \
                    patch.object(category_repair, 'sync_inventory'), \
                    patch.object(category_repair, 'load_inventory', return_value=inventory), \
                    patch.object(category_repair, 'validate_bundle',
                                 return_value={'status': 'ready', 'reasons': []}), \
                    patch.object(category_repair, 'fetch_sources', return_value=[]), \
                    patch.object(category_repair.subprocess, 'run') as run:
                live = {
                    'post_status': 'draft',
                    'post_title': 'title',
                    'post_name': '',
                    'post_content': '<p>changed</p>',
                }
                run.return_value = MagicMock(stdout=json.dumps(live))
                expected = hashlib.sha256(content.encode()).hexdigest()
                with self.assertRaisesRegex(ValueError, 'draft_changed_during_category_repair'):
                    category_repair.repair_reviewed_draft_category(
                        239, expected, confirmed=True)
                self.assertEqual(run.call_count, 2)


if __name__ == '__main__':
    unittest.main()
