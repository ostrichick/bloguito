"""Safety checks for the local-only, per-post modernization approval index."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'build_legacy_full_approval_index.py'
SPEC = importlib.util.spec_from_file_location('bloguito_full_approval_index', SCRIPT)
INDEX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INDEX)


class ApprovalIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.patches = [patch.object(INDEX, 'ROOT', root),
                        patch.object(INDEX, 'TMP', root / 'tmp' / 'legacy_audit_20260922')]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        INDEX.TMP.mkdir(parents=True)

    def write_status(self, status, post_id=145, group='full-seasonal', manifest=None):
        folder = INDEX.TMP / group / f'post-{post_id}'
        folder.mkdir(parents=True)
        approval = folder / 'approval'
        approval.mkdir()
        status = {'post_id': post_id, 'approval_dir': approval.relative_to(INDEX.ROOT).as_posix(), **status}
        (folder / 'status.json').write_text(json.dumps(status), encoding='utf-8')
        if manifest:
            (approval / 'approval-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return folder, approval

    def test_all_25_plus_103_pending_without_worker_artifacts(self):
        records = INDEX.build()
        self.assertEqual(len(records), 26)
        self.assertEqual(len({r['post_id'] for r in records}), 26)
        self.assertTrue(all(r['stage'] == 'pending' for r in records))
        self.assertNotIn('PRIVATE', INDEX.render(records))

    def test_ready_claim_without_actual_preflight_is_downgraded(self):
        self.write_status({'stage': 'ready', 'review_passed': True, 'preflight_status': 'ready'})
        self.assertEqual(INDEX.load_status('full-seasonal', 145)['stage'], 'blocked')

    def test_ready_requires_matching_real_manifest_and_source_hash(self):
        folder, approval = self.write_status({'stage': 'ready', 'review_passed': True,
                                              'preflight_status': 'ready'},
                                             manifest={'post_id': 145, 'preflight_status': 'ready',
                                                       'source_hashes_match_live': True})
        (approval / 'compare-preview.html').write_text('<h1>reviewable</h1>', encoding='utf-8')
        (approval / 'post-original.PRIVATE.json').write_text('secret', encoding='utf-8')
        result = INDEX.load_status('full-seasonal', 145)
        self.assertEqual(result['stage'], 'ready')
        markup = INDEX.render([result])
        self.assertIn('compare-preview.html', markup)
        self.assertNotIn('PRIVATE', markup)
        self.assertNotIn('secret', markup)

    def test_mismatched_post_id_rejected(self):
        self.write_status({'stage': 'ready', 'review_passed': True,
                           'preflight_status': 'ready'},
                          manifest={'post_id': 144, 'preflight_status': 'ready',
                                    'source_hashes_match_live': True})
        with self.assertRaisesRegex(ValueError, 'approval_id_mismatch'):
            INDEX.load_status('full-seasonal', 145)

    def test_approval_path_outside_workspace_rejected(self):
        folder = INDEX.TMP / 'full-seasonal' / 'post-145'
        folder.mkdir(parents=True)
        (folder / 'status.json').write_text(json.dumps({
            'post_id': 145, 'stage': 'draft', 'approval_dir': '../outside',
        }), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'approval_dir_outside_workspace'):
            INDEX.load_status('full-seasonal', 145)

    def test_link_to_private_original_is_denied(self):
        path = INDEX.TMP / 'original.PRIVATE.json'
        path.write_text('private', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'private_or_machine_data'):
            INDEX.safe_file(path.relative_to(INDEX.ROOT).as_posix())


if __name__ == '__main__':
    unittest.main()
