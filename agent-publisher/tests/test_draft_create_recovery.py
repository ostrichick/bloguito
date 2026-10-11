"""Fail-closed draft creation under lost replies and metadata failures."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.draft_create_journal import DraftCreateBlocked, DraftCreateJournal
from agents.editorial_writer import article_from_bundle
from agents.publisher import PublisherAgent
from test_editorial_system import sample


READY = {"status": "ready", "reasons": []}


class JournalTests(unittest.TestCase):
    def test_overlapping_begin_cannot_both_authorize_post_create(self):
        """An interleaving before the first atomic receipt must not allow 2 writers."""
        with tempfile.TemporaryDirectory() as folder:
            first = DraftCreateJournal("c" * 64, directory=Path(folder))
            second = DraftCreateJournal("c" * 64, directory=Path(folder))
            entered, release = threading.Event(), threading.Event()
            errors = []
            original_write = first._write

            def paused_write(payload):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("test_write_not_released")
                return original_write(payload)

            def launch():
                try:
                    first.begin()
                except BaseException as exc:
                    errors.append(exc)

            with patch.object(first, "_write", side_effect=paused_write):
                worker = threading.Thread(target=launch, name="draft-first-begin")
                worker.start()
                try:
                    self.assertTrue(entered.wait(2), "first journal reached write boundary")
                    with self.assertRaisesRegex(DraftCreateBlocked, "draft_create_journal_busy"):
                        second.begin()
                finally:
                    release.set()
                    worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual([], errors)
            self.assertEqual("creating", first.read()["state"])

    def test_parallel_created_cannot_replace_first_durable_post_id(self):
        """Both writers observed `creating`: only one may commit an owner ID."""
        with tempfile.TemporaryDirectory() as folder:
            first = DraftCreateJournal("d" * 64, directory=Path(folder))
            second = DraftCreateJournal("d" * 64, directory=Path(folder))
            first.begin()
            entered, release = threading.Event(), threading.Event()
            errors = []
            original_write = first._write

            def paused_write(payload):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("test_write_not_released")
                return original_write(payload)

            def launch():
                try:
                    first.created(501)
                except BaseException as exc:
                    errors.append(exc)

            with patch.object(first, "_write", side_effect=paused_write):
                worker = threading.Thread(target=launch, name="draft-first-created")
                worker.start()
                try:
                    self.assertTrue(entered.wait(2), "first journal reached ID write boundary")
                    with self.assertRaisesRegex(DraftCreateBlocked, "draft_create_journal_busy"):
                        second.created(502)
                finally:
                    release.set()
                    worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual([], errors)
            self.assertEqual({"state": "created", "post_id": 501},
                             {k: first.read()[k] for k in ("state", "post_id")})

    def test_outstanding_lock_blocks_separate_python_process(self):
        """Filesystem exclusivity, not a thread-local mutex, protects WordPress create."""
        with tempfile.TemporaryDirectory() as folder:
            journal = DraftCreateJournal("e" * 64, directory=Path(folder))
            snippet = (
                "from pathlib import Path; "
                "from agents.draft_create_journal import DraftCreateJournal, DraftCreateBlocked; "
                f"j=DraftCreateJournal({'e' * 64!r},directory=Path({folder!r})); "
                "\ntry: j.begin()\n"
                "except DraftCreateBlocked as exc: "
                "\n assert str(exc)=='draft_create_journal_busy_or_stale_lock'; print('BLOCKED')\n"
                "else: raise AssertionError('parallel post create permitted')\n"
            )
            with journal._exclusive_transition():
                result = subprocess.run(
                    [sys.executable, "-c", snippet], capture_output=True,
                    text=True, timeout=5,
                    env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])})
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("BLOCKED", result.stdout.strip())
                self.assertIsNone(journal.read())
            self.assertFalse(journal.lock_path.exists())

    def test_stale_transition_lock_blocks_all_writes_without_recovery_guess(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = DraftCreateJournal("f" * 64, directory=Path(folder))
            journal.directory.mkdir(exist_ok=True)
            journal.lock_path.write_text("interrupted before any durable ID receipt")
            with self.assertRaisesRegex(DraftCreateBlocked, "draft_create_journal_busy_or_stale_lock"):
                journal.begin()
            self.assertIsNone(journal.read())
            self.assertTrue(journal.lock_path.exists())  # No automatic stale-lock theft.
            journal.lock_path.unlink()  # Test-only teardown, not a recovery instruction.
            journal.begin()
            journal.created(501)
            with patch.object(journal, "_write", side_effect=OSError("simulated interrupted write")):
                with self.assertRaisesRegex(OSError, "simulated interrupted write"):
                    journal.complete(501)
            self.assertEqual("created", journal.read()["state"])
            self.assertFalse(journal.lock_path.exists())  # Caught fault releases owned lock.
            journal.complete(501)
            self.assertEqual("complete", journal.read()["state"])

    def test_journal_persists_atomic_attempt_and_id(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = DraftCreateJournal("a" * 64, directory=Path(folder))
            self.assertIsNone(journal.read())
            journal.begin()
            self.assertEqual("creating", journal.read()["state"])
            with self.assertRaises(DraftCreateBlocked):
                journal.begin()
            journal.created(509)
            self.assertEqual(509, DraftCreateJournal(
                "a" * 64, directory=Path(folder)).read()["post_id"])
            journal.complete(509)
            self.assertEqual("complete", journal.read()["state"])

    def test_unknown_or_corrupt_journal_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = DraftCreateJournal("a" * 64, directory=Path(folder))
            journal.directory.mkdir(parents=True, exist_ok=True)
            journal.path.write_text('{"state":"complete","post_id":1}', encoding="utf-8")
            with self.assertRaisesRegex(DraftCreateBlocked, "draft_create_journal_invalid"):
                journal.read()

    def test_durable_created_post_id_cannot_be_rebound_or_completed_with_a_new_id(self):
        """A known ID receipt is immutable across interrupted resume attempts."""
        with tempfile.TemporaryDirectory() as folder:
            journal = DraftCreateJournal("b" * 64, directory=Path(folder))
            journal.begin()
            with self.assertRaisesRegex(DraftCreateBlocked, "draft_create_id_receipt_required"):
                journal.complete(777)
            journal.created(777)
            with self.assertRaisesRegex(DraftCreateBlocked, "draft_create_id_receipt_conflict"):
                journal.created(778)
            with self.assertRaisesRegex(DraftCreateBlocked, "draft_create_id_receipt_conflict"):
                journal.complete(778)
            self.assertEqual(777, journal.read()["post_id"])
            journal.complete(777)
            with self.assertRaisesRegex(DraftCreateBlocked, "draft_create_id_receipt_conflict"):
                journal.created(778)
            self.assertEqual(777, journal.read()["post_id"])


class PublisherRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.data_patch = patch("agents.draft_create_journal.DATA_DIR", Path(self.folder.name))
        self.data_patch.start()
        self.addCleanup(self.data_patch.stop)
        self.bundle = sample()
        self.article = article_from_bundle(self.bundle)
        from agents.editorial import excerpt_from_lead
        self.saved = {
            "post_status": "draft",
            "post_title": self.article["title"],
            "post_name": "",
            "post_content": self.article["content"],
            "post_excerpt": excerpt_from_lead(self.bundle["plan"]["lead"]),
        }
        self.calls = []
        self.create_count = 0
        self.fail_create = False
        self.fail_permalink_once = False
        self.change_saved = False
        self.inventory = {"posts": [{"ID": 999}, {"ID": 888}]}

    def remote(self, cmd, **kwargs):
        self.calls.append(cmd)
        if "eval" in cmd and "post-id-v1" in " ".join(cmd):
            if self.fail_permalink_once:
                self.fail_permalink_once = False
                return Mock(stdout=json.dumps({"status": "update_failed"}), returncode=0)
            return Mock(stdout=json.dumps({
                "status": "ok", "saved_meta": json.loads(kwargs["input"])["meta"],
            }), returncode=0)
        if "create" in cmd:
            self.create_count += 1
            if self.fail_create:
                raise subprocess.CalledProcessError(255, cmd)
            return Mock(stdout="999", returncode=0)
        if "--fields=post_status,post_title,post_name,post_content,post_excerpt" in cmd:
            saved = dict(self.saved)
            if self.change_saved:
                saved["post_content"] = "<p>changed externally</p>"
            return Mock(stdout=json.dumps(saved), returncode=0)
        if (len(cmd) > 8 and cmd[5:8] == ["post", "meta", "set"]
                and "_bloguito_permalink_scheme" in cmd):
            if self.fail_permalink_once:
                self.fail_permalink_once = False
                raise RuntimeError("permalink metadata failed")
        return Mock(stdout="", returncode=0)

    def invoke(self):
        with patch("sync_wordpress_inventory.sync_inventory"), \
                patch("sync_wordpress_inventory.invalidate_inventory"), \
                patch("agents.editorial_writer.load_inventory", return_value=self.inventory), \
                patch("agents.editorial.validate_bundle", return_value=READY) as validated, \
                patch("agents.source_validation_cache.verify_explicit_live_sources"), \
                patch("agents.publisher.run_wordpress", side_effect=self.remote), \
                patch("agents.wordpress_mutation.run_wordpress", side_effect=self.remote), \
                patch.object(PublisherAgent, "_record_post"):
            result = PublisherAgent().publish(self.article)
            return result, validated.call_args.args[1]

    def test_metadata_failure_recovers_same_post_without_second_create(self):
        self.fail_permalink_once = True
        with self.assertRaisesRegex(ValueError, "wordpress_draft_meta_update_failed"):
            self.invoke()
        self.assertEqual(1, self.create_count)
        journal_paths = list(Path(self.folder.name).rglob("*.json"))
        self.assertEqual(1, len(journal_paths))
        self.assertEqual("created", json.loads(journal_paths[0].read_text())["state"])

        post_id, checked_inventory = self.invoke()
        self.assertEqual(999, post_id)
        self.assertEqual(1, self.create_count)
        self.assertEqual(["888"], [str(p["ID"]) for p in checked_inventory["posts"]])
        self.assertEqual("complete", json.loads(journal_paths[0].read_text())["state"])

    def test_lost_create_reply_is_blocked_without_retry(self):
        self.fail_create = True
        with self.assertRaisesRegex(DraftCreateBlocked, "draft_create_outcome_ambiguous"):
            self.invoke()
        self.fail_create = False
        with self.assertRaisesRegex(
                DraftCreateBlocked, "draft_create_outcome_ambiguous"):
            self.invoke()
        self.assertEqual(1, self.create_count)

    def test_known_post_changed_externally_is_blocked(self):
        self.fail_permalink_once = True
        with self.assertRaisesRegex(ValueError, "wordpress_draft_meta_update_failed"):
            self.invoke()
        self.change_saved = True
        with self.assertRaisesRegex(DraftCreateBlocked, "draft_create_saved_post_changed"):
            self.invoke()
        self.assertEqual(1, self.create_count)

    def test_completed_receipt_reuses_exact_post_id_and_never_creates_again(self):
        first, _ = self.invoke()
        self.assertEqual(first, 999)
        second, inspected_inventory = self.invoke()
        self.assertEqual(second, first)
        self.assertEqual(1, self.create_count)
        self.assertEqual([888], [post["ID"] for post in inspected_inventory["posts"]])
        journal_file, = Path(self.folder.name).rglob("*.json")
        journal = json.loads(journal_file.read_text(encoding="utf-8"))
        self.assertEqual({"state": "complete", "post_id": 999},
                         {key: journal[key] for key in ("state", "post_id")})


if __name__ == "__main__":
    unittest.main()
