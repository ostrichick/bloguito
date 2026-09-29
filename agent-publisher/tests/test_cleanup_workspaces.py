import os
import tempfile
import time
import unittest
from pathlib import Path

from scripts import cleanup_workspaces


class CleanupWorkspacesTests(unittest.TestCase):
    def _old(self, path: Path):
        timestamp = time.time() - 48 * 3600
        for current, dirs, files in os.walk(path):
            for name in files:
                os.utime(Path(current) / name, (timestamp, timestamp))
            for name in dirs:
                os.utime(Path(current) / name, (timestamp, timestamp))
        os.utime(path, (timestamp, timestamp))

    def test_dry_run_only_selects_old_browser_profiles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old_profile = root / "tmp" / "task" / "edge-profile"
            (old_profile / "Default").mkdir(parents=True)
            (old_profile / "Local State").write_text("state", encoding="utf-8")
            (old_profile / "Default" / "cache.bin").write_bytes(b"x" * 32)
            self._old(old_profile)

            evidence = root / "tmp" / "task" / "edge-profile-not-browser"
            evidence.mkdir(parents=True)
            (evidence / "report.json").write_text("{}", encoding="utf-8")

            recent = root / "tmp" / "recent-qa-profile"
            (recent / "Default").mkdir(parents=True)
            (recent / "Local State").write_text("state", encoding="utf-8")

            generic_name = root / "tmp" / "edge-header-qa"
            (generic_name / "Default").mkdir(parents=True)
            (generic_name / "Local State").write_text("state", encoding="utf-8")
            self._old(generic_name)

            result = cleanup_workspaces.cleanup(root, min_age_hours=24)
            self.assertEqual(2, result["candidate_count"])
            selected = {item["path"] for item in result["candidates"]}
            self.assertEqual({old_profile.resolve(), generic_name.resolve()}, selected)
            self.assertTrue(old_profile.exists())
            self.assertTrue(evidence.exists())
            self.assertTrue(recent.exists())

    def test_apply_removes_profile_but_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile = root / "tmp" / "task" / "qa-profile"
            (profile / "Default").mkdir(parents=True)
            (profile / "Local State").write_text("state", encoding="utf-8")
            self._old(profile)
            evidence = root / "tmp" / "task" / "approval-manifest.json"
            evidence.write_text("{}", encoding="utf-8")

            result = cleanup_workspaces.cleanup(root, apply=True, min_age_hours=24)
            self.assertEqual(1, result["removed_count"])
            self.assertFalse(profile.exists())
            self.assertTrue(evidence.exists())


if __name__ == "__main__":
    unittest.main()
