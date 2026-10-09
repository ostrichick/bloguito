import tempfile
import hashlib
import unittest
from pathlib import Path

from PIL import Image

from agents.featured_image import stage_featured_image


class FeaturedImageStageTests(unittest.TestCase):
    def test_binding_rejects_changed_candidate_before_writing_staged_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate.png"
            output = Path(folder) / "selected-upload.webp"
            Image.new("RGB", (1672, 941), "white").save(source, "PNG")
            sealed_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            Image.new("RGB", (1672, 941), "black").save(source, "PNG")
            with self.assertRaisesRegex(ValueError, "candidate_sha_conflict"):
                stage_featured_image(
                    source, output, expected_source_sha256=sealed_sha)
            self.assertFalse(output.exists())

    def test_stages_cos_native_near_16_9_png_to_exact_canvas(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate.png"
            output = Path(folder) / "selected-upload.png"
            Image.new("RGB", (1672, 941), "white").save(source, "PNG")

            receipt = stage_featured_image(source, output)

            self.assertEqual((1672, 941), (receipt["source_width"], receipt["source_height"]))
            self.assertEqual((1200, 675), (receipt["output_width"], receipt["output_height"]))
            self.assertEqual("PNG", receipt["output_format"])
            self.assertEqual(64, len(receipt["source_sha256"]))
            self.assertEqual(64, len(receipt["output_sha256"]))
            with Image.open(output) as staged:
                self.assertEqual((1200, 675), staged.size)

    def test_rejects_corrupt_file_even_if_extension_looks_like_image(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate.jpg"
            output = Path(folder) / "selected-upload.png"
            source.write_bytes(b"not-a-jpeg")

            with self.assertRaisesRegex(ValueError, "featured_image_stage_decode_failed"):
                stage_featured_image(source, output)

    def test_preserves_full_portrait_frame_with_fixed_output_canvas(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate.png"
            output = Path(folder) / "selected-upload.webp"
            Image.new("RGB", (900, 1200), "white").save(source, "PNG")

            receipt = stage_featured_image(source, output)

            self.assertEqual((1200, 675), (receipt["output_width"], receipt["output_height"]))
            self.assertEqual("WEBP", receipt["output_format"])


if __name__ == "__main__":
    unittest.main()
