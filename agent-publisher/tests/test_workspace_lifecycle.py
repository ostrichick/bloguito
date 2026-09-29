import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.workspace_lifecycle import (
    ensure_task_workspace,
    load_workspace_manifest,
    mark_task_workspace,
    temporary_browser_profile,
    workspace_expired,
)


class WorkspaceLifecycleTests(unittest.TestCase):
    def test_managed_workspace_reuses_stable_path_and_keeps_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = ensure_task_workspace(root, "post-641")
            artifact = first / "candidate.json"
            artifact.write_text("{}", encoding="utf-8")
            mark_task_workspace(first, "completed")

            second = ensure_task_workspace(root, "post-641")
            self.assertEqual(first, second)
            self.assertTrue(artifact.exists())
            self.assertEqual("active", load_workspace_manifest(second)["status"])

    def test_nonempty_unmanaged_workspace_is_never_adopted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            unmanaged = root / "scratch" / "tasks" / "legacy"
            unmanaged.mkdir(parents=True)
            (unmanaged / "user-output.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unmanaged_nonempty"):
                ensure_task_workspace(root, "legacy")

    def test_expiry_is_status_and_ttl_aware(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
        payload = {"status": "completed", "finished_at": old}
        self.assertTrue(workspace_expired(payload, completed_ttl_hours=72))
        payload["status"] = "failed"
        self.assertFalse(workspace_expired(payload, failed_ttl_hours=168))
        payload["status"] = "preserved"
        self.assertFalse(workspace_expired(payload))
        payload["status"] = "active"
        self.assertFalse(workspace_expired(payload))

    def test_invalid_task_name_cannot_escape_task_root(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("../escape", "nested/task", "", " name"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    ensure_task_workspace(Path(folder), name)

    def test_temporary_browser_profile_is_os_temp_scoped_and_removed_on_error(self):
        with tempfile.TemporaryDirectory() as folder:
            temp_root = Path(folder)
            profile = None
            with self.assertRaisesRegex(RuntimeError, "qa failed"):
                with temporary_browser_profile(temp_root=temp_root) as current:
                    profile = current
                    self.assertTrue(current.is_dir())
                    self.assertEqual("browser-profiles", current.parent.name)
                    (current / "Local State").write_text("state", encoding="utf-8")
                    raise RuntimeError("qa failed")
            self.assertIsNotNone(profile)
            self.assertFalse(profile.exists())
            self.assertFalse((temp_root / "bloguito" / "browser-profiles").exists())


if __name__ == "__main__":
    unittest.main()
