import hashlib
import tempfile
import unittest
from pathlib import Path

from agents.edit_orchestration import run_combined_image_phase
from agents.task_state import (
    load_after_image_checkpoint,
    update_after_image_checkpoint,
    write_after_image_checkpoint,
)


class CombinedImagePhaseTests(unittest.TestCase):
    def test_approved_combined_image_passes_exact_evidence_to_wordpress_mutator(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "selected.webp"
            image_path.write_bytes(b"verified-candidate")
            sent = []

            def replace(post_id, path, sha, **kwargs):
                sent.append((post_id, path, sha, kwargs))
                return {"attachment_id": 906, "publish_attestation": {"version": 1}}

            result = run_combined_image_phase(
                887, image_path=image_path, desired_content_sha256="a" * 64,
                expected_thumbnail_id=888, alt_text="Approved image", resume=False,
                state=None, update_state=lambda *args, **kwargs: None,
                reconcile_image=lambda *args, **kwargs: self.fail("unexpected reconcile"),
                recover_imported_image=lambda *args, **kwargs: self.fail("unexpected recovery"),
                replace_image=replace, approval_kind="manual_user_selected",
                approval_evidence_sha256="b" * 64)
            self.assertEqual(906, result["attachment_id"])
            self.assertEqual(1, len(sent))
            self.assertEqual("manual_user_selected", sent[0][3]["approval_kind"])
            self.assertEqual("b" * 64, sent[0][3]["approval_evidence_sha256"])

    def test_approved_import_recovery_never_claims_attestation_without_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "selected.webp"
            path.write_bytes(b"verified-candidate")
            image_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "recovered_image_requires_separate_publish_attestation"):
                run_combined_image_phase(
                    887, image_path=path, desired_content_sha256="a" * 64,
                    expected_thumbnail_id=888, alt_text="Approved image", resume=True,
                    state={"checkpoints": {"image_import_attempt": {
                        "started": True, "image_sha256": image_sha,
                        "expected_thumbnail_id": 888,
                    }}},
                    update_state=lambda *args, **kwargs: None,
                    reconcile_image=lambda *args, **kwargs: None,
                    recover_imported_image=lambda *args, **kwargs: {"attachment_id": 906},
                    replace_image=lambda *args, **kwargs: self.fail("do not duplicate import"),
                    approval_kind="manual_user_selected",
                    approval_evidence_sha256="b" * 64,
                )

    def test_after_image_allows_absent_baseline_thumbnail_and_seals_saved_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = root / "cover.jpg"
            checkpoint = write_after_image_checkpoint(
                393,
                remaining_steps=["generate", "save", "upload"],
                expected_content_sha256="a" * 64,
                expected_thumbnail_id=None,
                target_image_handle="chatgpt-native:pending",
                completion_requirements=["image_saved_or_handed_off", "uploaded"],
                root=root,
            )
            self.assertIsNone(checkpoint["expected_thumbnail_id"])
            self.assertIsNone(checkpoint["target_image_sha256"])
            image_path.write_bytes(b"selected-image")
            updated = update_after_image_checkpoint(
                393, target_image_handle=str(image_path),
                completed_steps=["image_saved_or_handed_off"], root=root,
            )
            self.assertEqual(
                hashlib.sha256(b"selected-image").hexdigest(),
                updated["target_image_sha256"],
            )
            self.assertEqual(updated, load_after_image_checkpoint(393, root))

    def test_after_image_rejects_invalid_nonempty_baseline_thumbnail(self):
        for invalid_thumbnail in (0, -1, "70", True):
            with self.subTest(invalid_thumbnail=invalid_thumbnail):
                with tempfile.TemporaryDirectory() as folder:
                    with self.assertRaisesRegex(ValueError, "expected_thumbnail_id_required"):
                        write_after_image_checkpoint(
                            393,
                            remaining_steps=["upload"],
                            expected_content_sha256="a" * 64,
                            expected_thumbnail_id=invalid_thumbnail,
                            target_image_handle="chatgpt-native:pending",
                            completion_requirements=["uploaded"],
                            root=Path(folder),
                        )

    def test_resume_after_import_attempt_recovers_without_second_import(self):
        updates = []
        media_imports = 0
        image_sha = hashlib.sha256(b"image-bytes").hexdigest()

        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "cover.jpg"
            image_path.write_bytes(b"image-bytes")

            def update_state(post_id, **kwargs):
                updates.append((post_id, kwargs))

            def first_replace(post_id, image, desired_sha, **kwargs):
                nonlocal media_imports
                attempt = {
                    "image_sha256": image_sha,
                    "expected_thumbnail_id": 70,
                    "started": True,
                }
                kwargs["import_attempt_callback"](attempt)
                media_imports += 1
                raise RuntimeError("process interrupted after media import commit")

            with self.assertRaisesRegex(RuntimeError, "process interrupted"):
                run_combined_image_phase(
                    393,
                    image_path=image_path,
                    desired_content_sha256="a" * 64,
                    expected_thumbnail_id=70,
                    alt_text="검토된 이미지",
                    resume=False,
                    state=None,
                    update_state=update_state,
                    reconcile_image=lambda *args, **kwargs: None,
                    recover_imported_image=lambda *args, **kwargs: None,
                    replace_image=first_replace,
                )

            attempt_payload = next(
                kwargs["checkpoints"]["image_import_attempt"]
                for _, kwargs in updates
                if "image_import_attempt" in kwargs.get("checkpoints", {})
            )
            self.assertEqual(image_sha, attempt_payload["image_sha256"])

            recovered = {
                "attachment_id": 777,
                "attachment_url": "https://lifeinfo24.org/uploads/cover.jpg",
                "reconciled": True,
            }
            state = {
                "checkpoints": {"image_import_attempt": attempt_payload},
            }
            result = run_combined_image_phase(
                393,
                image_path=image_path,
                desired_content_sha256="a" * 64,
                expected_thumbnail_id=70,
                alt_text="검토된 이미지",
                resume=True,
                state=state,
                update_state=update_state,
                reconcile_image=lambda *args, **kwargs: None,
                recover_imported_image=lambda *args, **kwargs: recovered,
                replace_image=lambda *args, **kwargs: self.fail("must not import again"),
            )

        self.assertEqual(1, media_imports)
        self.assertEqual(777, result["attachment_id"])

    def test_resume_after_import_attempt_blocks_when_sha_recovery_is_empty(self):
        image_sha = hashlib.sha256(b"image").hexdigest()
        state = {
            "checkpoints": {"image_import_attempt": {
                "image_sha256": image_sha,
                "expected_thumbnail_id": 70,
                "started": True,
            }},
        }
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "cover.jpg"
            image_path.write_bytes(b"image")
            with self.assertRaisesRegex(ValueError, "featured_image_import_outcome_ambiguous"):
                run_combined_image_phase(
                    393,
                    image_path=image_path,
                    desired_content_sha256="a" * 64,
                    expected_thumbnail_id=70,
                    alt_text="검토된 이미지",
                    resume=True,
                    state=state,
                    update_state=lambda *args, **kwargs: None,
                    reconcile_image=lambda *args, **kwargs: None,
                    recover_imported_image=lambda *args, **kwargs: None,
                    replace_image=lambda *args, **kwargs: self.fail("must not import again"),
                )

    def test_resume_rejects_a_different_image_before_remote_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "cover.jpg"
            image_path.write_bytes(b"selected-image")
            state = {"checkpoints": {"image_import_attempt": {
                "image_sha256": hashlib.sha256(b"other-image").hexdigest(),
                "expected_thumbnail_id": 70,
                "started": True,
            }}}
            with self.assertRaisesRegex(ValueError, "resume_image_import_artifact_conflict"):
                run_combined_image_phase(
                    393,
                    image_path=image_path,
                    desired_content_sha256="a" * 64,
                    expected_thumbnail_id=70,
                    alt_text="검토된 이미지",
                    resume=True,
                    state=state,
                    update_state=lambda *args, **kwargs: None,
                    reconcile_image=lambda *args, **kwargs: self.fail("must not reconcile"),
                    recover_imported_image=lambda *args, **kwargs: self.fail("must not recover"),
                    replace_image=lambda *args, **kwargs: self.fail("must not import again"),
                )

    def test_resume_rejects_a_different_thumbnail_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "cover.jpg"
            image_path.write_bytes(b"selected-image")
            state = {"checkpoints": {"image_import_attempt": {
                "image_sha256": hashlib.sha256(b"selected-image").hexdigest(),
                "expected_thumbnail_id": 71,
                "started": True,
            }}}
            with self.assertRaisesRegex(ValueError, "resume_image_import_artifact_conflict"):
                run_combined_image_phase(
                    393,
                    image_path=image_path,
                    desired_content_sha256="a" * 64,
                    expected_thumbnail_id=70,
                    alt_text="검토된 이미지",
                    resume=True,
                    state=state,
                    update_state=lambda *args, **kwargs: None,
                    reconcile_image=lambda *args, **kwargs: self.fail("must not reconcile"),
                    recover_imported_image=lambda *args, **kwargs: self.fail("must not recover"),
                    replace_image=lambda *args, **kwargs: self.fail("must not import again"),
                )


if __name__ == "__main__":
    unittest.main()
