import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sync_wordpress_inventory as inventory_sync


class InventoryCacheLifecycleTests(unittest.TestCase):
    def test_invalidate_removes_cached_full_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            inventory = Path(folder) / 'wordpress_inventory.json'
            inventory.write_text(json.dumps({
                'checked_on': '2026-09-26',
                'posts': [{'ID': 1, 'post_status': 'publish'}],
            }), encoding='utf-8')
            with patch.object(inventory_sync, 'INVENTORY', inventory):
                inventory_sync.invalidate_inventory()
            self.assertFalse(inventory.exists())

    def test_invalidate_is_idempotent_when_cache_is_already_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            inventory = Path(folder) / 'wordpress_inventory.json'
            with patch.object(inventory_sync, 'INVENTORY', inventory):
                inventory_sync.invalidate_inventory()
                inventory_sync.invalidate_inventory()
            self.assertFalse(inventory.exists())

    def test_ensure_reuses_fresh_snapshot_without_network_sync(self):
        with tempfile.TemporaryDirectory() as folder:
            inventory = Path(folder) / 'wordpress_inventory.json'
            inventory.write_text(json.dumps({
                'checked_on': inventory_sync.datetime.now(inventory_sync.KST).date().isoformat(),
                'posts': [],
            }), encoding='utf-8')
            with patch.object(inventory_sync, 'INVENTORY', inventory), \
                    patch.object(inventory_sync, 'sync_inventory') as sync:
                cached = inventory_sync.ensure_inventory()
            sync.assert_not_called()
            self.assertEqual([], cached['posts'])

    def test_ensure_refreshes_after_invalidation(self):
        with tempfile.TemporaryDirectory() as folder:
            inventory = Path(folder) / 'wordpress_inventory.json'

            def sync():
                inventory.write_text(json.dumps({
                    'checked_on': inventory_sync.datetime.now(inventory_sync.KST).date().isoformat(),
                    'posts': [{'ID': 7}],
                }), encoding='utf-8')

            with patch.object(inventory_sync, 'INVENTORY', inventory), \
                    patch.object(inventory_sync, 'sync_inventory', side_effect=sync) as refresh:
                cached = inventory_sync.ensure_inventory()
            refresh.assert_called_once_with()
            self.assertEqual([{'ID': 7}], cached['posts'])


if __name__ == '__main__':
    unittest.main()
