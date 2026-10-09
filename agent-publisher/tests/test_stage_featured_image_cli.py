import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from agents.featured_image import verify_manual_image_upload_lineage
import editorial_cli


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "stage_featured_image.py"
SPEC = importlib.util.spec_from_file_location("stage_featured_image_cli", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class StageFeaturedImageCliTests(unittest.TestCase):
    def test_all_manual_cli_actions_refuse_unsealed_local_cover(self):
        with tempfile.TemporaryDirectory() as folder:
            local_cover = Path(folder) / "locally-drawn.webp"
            Image.new("RGB", (1200, 675), "white").save(local_cover, "WEBP")
            for action in ("replace-featured-image", "edit-post", "prepare-draft"):
                with self.subTest(action=action):
                    with patch("sys.argv", [
                        "editorial_cli.py", action, "--post-id", "123",
                        "--image-path", str(local_cover),
                    ]):
                        with self.assertRaisesRegex(
                            ValueError,
                            "manual_cover_requires_candidate_manifest_selection_and_mode",
                        ):
                            editorial_cli._main()

    def test_complete_selected_candidate_lineage_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "candidate-1.png"
            staged = root / "candidate-1-upload.webp"
            manifest = root / "candidate-manifest.json"
            Image.new("RGB", (1600, 900), "white").save(source, "PNG")
            from importlib.util import module_from_spec, spec_from_file_location
            seal_path = SCRIPT.parent / "seal_featured_image_candidates.py"
            seal_spec = spec_from_file_location("sealer_for_test", seal_path)
            sealer = module_from_spec(seal_spec)
            seal_spec.loader.exec_module(sealer)
            sealer.seal_candidates([source], manifest)
            with patch("sys.argv", [
                "stage_featured_image.py", str(source), str(staged),
                "--candidate-manifest", str(manifest),
                "--selected-candidate", "1",
                "--selection-mode", "agent-delegated",
            ]):
                MODULE.main()
            result = verify_manual_image_upload_lineage(
                staged, manifest, 1, "agent-delegated")
            self.assertEqual(1, result["candidate_number"])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             result["source_sha256"])
            with self.assertRaisesRegex(ValueError, "selected_candidate_not_sealed"):
                verify_manual_image_upload_lineage(staged, manifest, 2, "agent-delegated")
            with self.assertRaisesRegex(ValueError, "manual_cover_lineage_receipt_mismatch"):
                verify_manual_image_upload_lineage(staged, manifest, 1, "user")
            Image.new("RGB", (1600, 900), "black").save(source, "PNG")
            with self.assertRaisesRegex(ValueError, "candidate_sha_conflict"):
                verify_manual_image_upload_lineage(staged, manifest, 1, "agent-delegated")

    def test_local_unsealed_image_cannot_be_uploaded(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / "locally-painted.webp"
            Image.new("RGB", (1200, 675), "white").save(original, "WEBP")
            with self.assertRaisesRegex(
                ValueError, "manual_cover_requires_candidate_manifest_selection_and_mode"
            ):
                verify_manual_image_upload_lineage(original, None, None, None)

    def test_cli_requires_candidate_manifest_even_if_source_exists(self):
        with self.assertRaisesRegex(ValueError, "candidate_manifest_required_before_staging"):
            MODULE.require_sealed_candidate(None)

    def test_manifest_binding_accepts_exact_sealed_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidates = []
            for number, color in enumerate(("red", "blue", "white"), start=1):
                candidate = root / f"candidate-{number}.png"
                Image.new("RGB", (1672, 941), color).save(candidate, "PNG")
                candidates.append(candidate)
            source = candidates[2]
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = root / "candidate-manifest.json"
            from importlib.util import module_from_spec, spec_from_file_location
            spec = spec_from_file_location("sealer_candidate_three", SCRIPT.parent / "seal_featured_image_candidates.py")
            sealer = module_from_spec(spec)
            spec.loader.exec_module(sealer)
            sealer.seal_candidates(candidates, manifest)
            bound = MODULE.verify_candidate_manifest(
                source, manifest, selected_candidate=3, selection_mode="agent-delegated")
            self.assertEqual(3, bound["candidate_number"])
            self.assertEqual(sha, bound["sealed_source_sha256"])
            self.assertEqual("agent-delegated", bound["selection_mode"])
            with self.assertRaisesRegex(ValueError, "candidate_not_sealed"):
                MODULE.verify_candidate_manifest(
                    source, manifest, selected_candidate=2, selection_mode="user")

    def test_manifest_rejects_forged_format_even_when_sha_matches(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate-1.png"
            Image.new("RGB", (1672, 941), "white").save(source, "PNG")
            from importlib.util import module_from_spec, spec_from_file_location
            spec = spec_from_file_location("sealer_format_check", SCRIPT.parent / "seal_featured_image_candidates.py")
            sealer = module_from_spec(spec)
            spec.loader.exec_module(sealer)
            manifest = Path(folder) / "candidate-manifest.json"
            receipt = sealer.seal_candidates([source], manifest)
            receipt["candidates"][0]["format"] = "WEBP"
            manifest.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "candidate_format_or_size_conflict"):
                MODULE.verify_candidate_manifest(
                    source, manifest, selected_candidate=1, selection_mode="user")

    def test_manifest_binding_rejects_modified_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate-1.png"
            Image.new("RGB", (1672, 941), "white").save(source, "PNG")
            manifest = Path(folder) / "candidate-manifest.json"
            manifest.write_text(json.dumps({
                "version": 2,
                "origin_claim": {"generator_tool": "image_gen.text2im", "save_tool": "cos_core.save_image"},
                "candidates": [{
                    "candidate_number": 1, "path": str(source.resolve()), "sha256": "0" * 64,
                }],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "candidate_sha_conflict"):
                MODULE.verify_candidate_manifest(
                    source, manifest, selected_candidate=1, selection_mode="user")

    def test_cli_sha_mismatch_stops_without_staging_and_writes_failure_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate-1.png"
            Image.new("RGB", (1672, 941), "white").save(source, "PNG")
            manifest = Path(folder) / "candidate-manifest.json"
            manifest.write_text(json.dumps({
                "version": 2,
                "origin_claim": {"generator_tool": "image_gen.text2im", "save_tool": "cos_core.save_image"},
                "candidates": [{
                    "candidate_number": 1, "path": str(source.resolve()),
                    "sha256": "0" * 64,
                }],
            }), encoding="utf-8")
            staged = Path(folder) / "candidate-1-upload.webp"
            argv = ["stage_featured_image.py", str(source), str(staged),
                    "--candidate-manifest", str(manifest),
                    "--selected-candidate", "1", "--selection-mode", "user"]
            with patch("sys.argv", argv):
                with self.assertRaises(SystemExit) as error:
                    MODULE.main()
            self.assertEqual(2, error.exception.code)
            self.assertFalse(staged.exists())
            failure = json.loads(
                staged.with_suffix(staged.suffix + ".failed.json").read_text(encoding="utf-8"))
            self.assertEqual("local_webp_staging", failure["stage"])
            self.assertFalse(failure["import_attempted"])


if __name__ == "__main__":
    unittest.main()
