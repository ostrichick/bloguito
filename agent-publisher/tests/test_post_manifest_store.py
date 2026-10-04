import json
import tempfile
import unittest
from pathlib import Path

from agents.post_manifest_store import (
    activate_storage,
    assert_unchanged,
    load_record,
    load_records,
    migrate_index,
    move_record,
    remove_record,
    replace_record,
    upsert_record,
)


class PostManifestStoreTests(unittest.TestCase):
    def record(self, post_id=641, text='body'):
        return {
            'id': post_id,
            'title': f'post {post_id}',
            'status': 'draft',
            'fact_manifest': {'editorial_bundle': {'plan': {'lead': {'text': text}}}},
        }

    def test_legacy_mode_preserves_inline_shape(self):
        with tempfile.TemporaryDirectory() as folder:
            index = Path(folder) / 'draft_posts.json'
            first = self.record()
            index.write_text(json.dumps([first], ensure_ascii=False), encoding='utf-8')
            snap = load_record(index, 641)
            changed = self.record(text='changed')
            replace_record(snap, changed)
            stored = json.loads(index.read_text(encoding='utf-8'))
            self.assertIn('fact_manifest', stored[0])
            self.assertEqual(changed, load_record(index, 641).record)

    def test_activation_migrates_to_lightweight_index_and_per_post_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            index = data / 'draft_posts.json'
            index.write_text(json.dumps([self.record()], ensure_ascii=False), encoding='utf-8')
            activate_storage(data)
            self.assertEqual(1, migrate_index(index))
            compact = json.loads(index.read_text(encoding='utf-8'))[0]
            self.assertNotIn('fact_manifest', compact)
            self.assertRegex(compact['manifest_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(self.record(), load_record(index, 641).record)

    def test_target_cas_ignores_unrelated_index_row_change_in_per_post_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            index = data / 'draft_posts.json'
            index.write_text(json.dumps([self.record(641), self.record(657)], ensure_ascii=False), encoding='utf-8')
            activate_storage(data)
            migrate_index(index)
            snap = load_record(index, 641)
            rows = json.loads(index.read_text(encoding='utf-8'))
            rows[1]['title'] = 'unrelated changed'
            index.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
            assert_unchanged(snap)

    def test_target_cas_rejects_target_row_change(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            index = data / 'draft_posts.json'
            index.write_text(json.dumps([self.record()], ensure_ascii=False), encoding='utf-8')
            activate_storage(data)
            migrate_index(index)
            snap = load_record(index, 641)
            rows = json.loads(index.read_text(encoding='utf-8'))
            rows[0]['title'] = 'conflict'
            index.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'index_mismatch|manifest_changed'):
                assert_unchanged(snap)

    def test_digest_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            index = data / 'draft_posts.json'
            index.write_text(json.dumps([self.record()], ensure_ascii=False), encoding='utf-8')
            activate_storage(data)
            migrate_index(index)
            manifest = next((data / 'post_manifests').glob('post-641-*.json'))
            manifest.write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'digest_mismatch'):
                load_record(index, 641)

    def test_upsert_and_remove_work_in_per_post_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            index = data / 'draft_posts.json'
            index.write_text('[]', encoding='utf-8')
            activate_storage(data)
            upsert_record(index, self.record())
            self.assertEqual([641], [row['id'] for row in load_records(index)])
            self.assertTrue(remove_record(index, 641))
            self.assertEqual([], load_records(index))

    def test_move_record_uses_source_snapshot_and_moves_to_target_index(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            source = data / 'draft_posts.json'
            target = data / 'published_posts.json'
            source.write_text(json.dumps([self.record()], ensure_ascii=False), encoding='utf-8')
            target.write_text('[]', encoding='utf-8')
            activate_storage(data)
            migrate_index(source)
            snapshot = load_record(source, 641)
            public = {**snapshot.record, 'status': 'publish'}
            move_record(snapshot, target, public)
            self.assertEqual([], load_records(source))
            self.assertEqual('publish', load_record(target, 641).record['status'])

    def test_move_record_restores_both_indexes_when_source_changed(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            source = data / 'draft_posts.json'
            target = data / 'published_posts.json'
            source.write_text(json.dumps([self.record()], ensure_ascii=False), encoding='utf-8')
            target.write_text(json.dumps([self.record(657)], ensure_ascii=False), encoding='utf-8')
            activate_storage(data)
            migrate_index(source)
            migrate_index(target)
            snapshot = load_record(source, 641)
            source_before = source.read_bytes()
            target_before = target.read_bytes()
            rows = json.loads(source.read_text(encoding='utf-8'))
            rows[0]['title'] = 'conflict'
            source.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'index_mismatch|manifest_changed'):
                move_record(snapshot, target, {**snapshot.record, 'status': 'publish'})
            self.assertNotEqual(source_before, source.read_bytes())
            self.assertEqual(target_before, target.read_bytes())


if __name__ == '__main__':
    unittest.main()
