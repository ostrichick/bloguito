import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import cleanup_workspaces
from agents.workspace_lifecycle import ensure_task_workspace, mark_task_workspace


class CleanupWorkspacesTests(unittest.TestCase):
    def _old(self, path: Path):
        timestamp = time.time() - 48 * 3600
        for current, dirs, files in os.walk(path):
            for name in files:
                os.utime(Path(current) / name, (timestamp, timestamp))
            for name in dirs:
                os.utime(Path(current) / name, (timestamp, timestamp))
        os.utime(path, (timestamp, timestamp))

    def test_browser_user_data_dir_parser_keeps_paths_with_spaces(self):
        quoted = cleanup_workspaces.browser_profile_path_from_command_line(
            'msedge.exe --user-data-dir="C:\\Temp\\Edge QA Profile" --remote-debugging-port=9222'
        )
        whole_arg_quoted = cleanup_workspaces.browser_profile_path_from_command_line(
            'msedge.exe "--user-data-dir=C:\\Temp\\Edge User Data" /prefetch:4 --type=crashpad-handler'
        )
        unquoted = cleanup_workspaces.browser_profile_path_from_command_line(
            'chrome.exe --user-data-dir=C:\\Temp\\Chrome QA Profile --remote-debugging-port=9223'
        )
        self.assertEqual(Path(r"C:\Temp\Edge QA Profile").resolve(strict=False), quoted)
        self.assertEqual(Path(r"C:\Temp\Edge User Data").resolve(strict=False), whole_arg_quoted)
        self.assertEqual(Path(r"C:\Temp\Chrome QA Profile").resolve(strict=False), unquoted)

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

            with patch("scripts.cleanup_workspaces.active_browser_profile_paths", return_value=set()):
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

            with patch("scripts.cleanup_workspaces.active_browser_profile_paths", return_value=set()):
                result = cleanup_workspaces.cleanup(root, apply=True, min_age_hours=24)
            self.assertEqual(1, result["removed_count"])
            self.assertFalse(profile.exists())
            self.assertTrue(evidence.exists())

    def test_active_or_pinned_browser_profile_is_not_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            active = root / "tmp" / "active-profile"
            (active / "Default").mkdir(parents=True)
            (active / "Local State").write_text("state", encoding="utf-8")
            self._old(active)

            pinned = root / "tmp" / "pinned-profile"
            (pinned / "Default").mkdir(parents=True)
            (pinned / "Local State").write_text("state", encoding="utf-8")
            (pinned / ".keep").write_text("preserve", encoding="utf-8")
            self._old(pinned)

            selected = cleanup_workspaces.find_browser_profiles(
                root,
                min_age_hours=24,
                active_profiles={active},
            )
            self.assertEqual([], selected)

    def test_apply_fails_closed_when_browser_process_check_is_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile = root / "tmp" / "old-profile"
            (profile / "Default").mkdir(parents=True)
            (profile / "Local State").write_text("state", encoding="utf-8")
            self._old(profile)
            with patch(
                "scripts.cleanup_workspaces.active_browser_profile_paths",
                side_effect=RuntimeError("browser_process_check_failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "browser_process_check_failed"):
                    cleanup_workspaces.cleanup(root, apply=True, min_age_hours=24)
            self.assertTrue(profile.exists())

    def test_generated_cover_cleanup_only_targets_old_owned_cover_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            (root / "tmp").mkdir(parents=True)
            cover_root = Path(folder) / "os-temp" / "bloguito" / "covers"
            cover_root.mkdir(parents=True)
            old_cover = cover_root / "thumb_deadbeef_old.jpg"
            old_cover.write_bytes(b"old")
            self._old(cover_root)

            recent_cover = cover_root / "thumb_deadbeef_recent.jpg"
            recent_cover.write_bytes(b"recent")
            unrelated = cover_root / "keep.jpg"
            unrelated.write_bytes(b"keep")

            result = cleanup_workspaces.cleanup(
                root,
                apply=True,
                min_age_hours=24,
                cover_root=cover_root,
            )
            self.assertEqual(1, result["cover_candidate_count"])
            self.assertEqual(1, result["cover_removed_count"])
            self.assertFalse(old_cover.exists())
            self.assertTrue(recent_cover.exists())
            self.assertTrue(unrelated.exists())

    @staticmethod
    def _age_managed_workspace(path: Path, *, hours: float):
        manifest_path = path / ".bloguito-workspace.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        old = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        payload["updated_at"] = old
        payload["finished_at"] = old
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_cleanup_removes_only_expired_managed_task_workspaces(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "tmp").mkdir()

            completed = ensure_task_workspace(root, "completed-task")
            (completed / "candidate.json").write_text("{}", encoding="utf-8")
            mark_task_workspace(completed, "completed")
            self._age_managed_workspace(completed, hours=96)

            failed = ensure_task_workspace(root, "failed-task")
            mark_task_workspace(failed, "failed")
            self._age_managed_workspace(failed, hours=96)

            active = ensure_task_workspace(root, "active-task")
            preserved = ensure_task_workspace(root, "preserved-task")
            mark_task_workspace(preserved, "preserved", preserve_reason="manual evidence")

            unmanaged = root / "scratch" / "tasks" / "legacy-unmanaged"
            unmanaged.mkdir(parents=True)
            (unmanaged / "keep.json").write_text("{}", encoding="utf-8")

            result = cleanup_workspaces.cleanup(
                root,
                apply=True,
                completed_ttl_hours=72,
                failed_ttl_hours=168,
            )
            self.assertEqual(1, result["workspace_candidate_count"])
            self.assertEqual(1, result["workspace_removed_count"])
            self.assertFalse(completed.exists())
            self.assertTrue(failed.exists())
            self.assertTrue(active.exists())
            self.assertTrue(preserved.exists())
            self.assertTrue(unmanaged.exists())

    def test_malformed_workspace_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "tmp").mkdir()
            broken = root / "scratch" / "tasks" / "broken"
            broken.mkdir(parents=True)
            (broken / ".bloguito-workspace.json").write_text("not-json", encoding="utf-8")
            result = cleanup_workspaces.cleanup(
                root,
                apply=True,
                completed_ttl_hours=0,
                failed_ttl_hours=0,
            )
            self.assertEqual(0, result["workspace_candidate_count"])
            self.assertTrue(broken.exists())


if __name__ == "__main__":
    unittest.main()
