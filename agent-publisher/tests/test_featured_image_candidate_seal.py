import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seal_featured_image_candidates.py"
SPEC = importlib.util.spec_from_file_location("seal_featured_image_candidates", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FeaturedImageCandidateSealTests(unittest.TestCase):
    def test_seals_candidate_numbers_paths_and_sha(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            one = root / "candidate-1.png"
            two = root / "candidate-2.webp"
            Image.new("RGB", (1672, 941), "white").save(one, "PNG")
            Image.new("RGB", (1672, 941), "black").save(two, "WEBP")
            manifest = root / "candidate-manifest.json"

            receipt = MODULE.seal_candidates([one, two], manifest)

            self.assertEqual([1, 2], [row["candidate_number"] for row in receipt["candidates"]])
            self.assertEqual(2, len({row["sha256"] for row in receipt["candidates"]}))
            saved = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(receipt, saved)
            self.assertEqual("image_gen.text2im", saved["origin_claim"]["generator_tool"])
            self.assertEqual("cos_core.save_image", saved["origin_claim"]["save_tool"])

    def test_rejects_duplicate_candidate_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            one = root / "candidate-1.png"
            two = root / "candidate-2.png"
            Image.new("RGB", (1672, 941), "white").save(one, "PNG")
            two.write_bytes(one.read_bytes())
            with self.assertRaisesRegex(ValueError, "duplicate_candidate_content"):
                MODULE.seal_candidates([one, two], root / "manifest.json")

    def test_rejects_corrupt_candidate_before_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate-1.jpg"
            source.write_bytes(b"broken")
            with self.assertRaisesRegex(ValueError, "candidate_decode_failed:1"):
                MODULE.seal_candidates([source], Path(folder) / "manifest.json")

    def test_seal_is_immutable_even_when_image_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate-1.png"
            manifest = Path(folder) / "candidate-manifest.json"
            Image.new("RGB", (1600, 900), "white").save(source, "PNG")
            initial = MODULE.seal_candidates([source], manifest)
            with self.assertRaises(FileExistsError):
                MODULE.seal_candidates([source], manifest)
            Image.new("RGB", (1600, 900), "black").save(source, "PNG")
            with self.assertRaises(FileExistsError):
                MODULE.seal_candidates([source], manifest)
            self.assertEqual(initial, json.loads(manifest.read_text(encoding="utf-8")))

    def test_mismatched_file_extension_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate-1.webp"
            Image.new("RGB", (1600, 900), "white").save(source, "PNG")
            with self.assertRaisesRegex(ValueError, "candidate_extension_format_mismatch"):
                MODULE.seal_candidates([source], Path(folder) / "manifest.json")


if __name__ == "__main__":
    unittest.main()
