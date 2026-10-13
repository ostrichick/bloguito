"""R2 staged MU bytes and rollback rehearsal without WordPress or host writes."""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/ops/mu_rollout_disposable_drill.py"
spec = importlib.util.spec_from_file_location("mu_disposable_drill", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MuRolloutDisposableDrillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root / "read-only-original.bin"
        self.staged = self.root / "reviewed-staged.php"
        self.original.write_bytes(b"<?php // old MU policy\n")
        self.staged.write_bytes(b"<?php // reviewed MU policy\n")
        self.current_sha = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.release_sha = hashlib.sha256(self.staged.read_bytes()).hexdigest()

    def run_drill(self, **kwargs):
        return module.run_drill(
            self.original, self.staged,
            current_sha=self.current_sha, release_sha=self.release_sha, **kwargs)

    def test_read_only_inputs_and_exact_swap_backup_rollback(self):
        before = (self.original.read_bytes(), self.staged.read_bytes())
        receipt = self.run_drill()
        self.assertTrue(receipt["backup_verified"])
        self.assertTrue(receipt["staged_verified"])
        self.assertTrue(receipt["swap_verified"])
        self.assertTrue(receipt["rollback_verified"])
        self.assertFalse(receipt["production_modified"])
        self.assertEqual(before, (self.original.read_bytes(), self.staged.read_bytes()))

    def test_failure_immediately_after_swap_still_restores_original(self):
        before = (self.original.read_bytes(), self.staged.read_bytes())
        receipt = self.run_drill(inject_failure=True)
        self.assertTrue(receipt["failure_injected"])
        self.assertTrue(receipt["rollback_verified"])
        self.assertFalse(receipt["swap_verified"])
        self.assertEqual(before, (self.original.read_bytes(), self.staged.read_bytes()))

    def test_rejects_stale_backup_or_modified_stage_before_rehearsal(self):
        with self.assertRaisesRegex(ValueError, "current_backup_sha_mismatch"):
            module.run_drill(self.original, self.staged, current_sha="0"*64,
                             release_sha=self.release_sha)
        self.staged.write_bytes(b"unreviewed modified staged bytes")
        with self.assertRaisesRegex(ValueError, "staged_release_sha_mismatch"):
            self.run_drill()

    def test_rejects_unbounded_or_nonsensical_inputs(self):
        with self.assertRaisesRegex(ValueError, "valid_independent_shas_required"):
            module.run_drill(self.original, self.staged, current_sha="garbled",
                             release_sha=self.release_sha)
        with self.assertRaisesRegex(ValueError, "distinct_existing_input_files_required"):
            module.run_drill(self.original, self.original,
                             current_sha=self.current_sha, release_sha=self.release_sha)
        self.staged.write_bytes(self.original.read_bytes())
        with self.assertRaisesRegex(ValueError, "no_plugin_change"):
            module.run_drill(self.original, self.staged,
                             current_sha=self.current_sha, release_sha=self.current_sha)


if __name__ == "__main__":
    unittest.main()
