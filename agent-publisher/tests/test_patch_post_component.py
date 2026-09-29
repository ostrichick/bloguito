import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.patch_post_component import apply_component_patch, atomic_write_text, verify_and_patch


class PatchPostComponentTests(unittest.TestCase):
    def setUp(self):
        self.html = (
            '<article><div class="summary">summary</div>'
            '<div class="cta">apply</div><div class="legacy">old</div></article>'
        )

    def test_inject_replace_remove(self):
        injected = apply_component_patch(
            self.html, "inject-after", r'<div class="summary">.*?</div>', '<div class="map">map</div>')
        self.assertIn('</div><div class="map">map</div><div class="cta">', injected)

        replaced = apply_component_patch(
            self.html, "replace", r'<div class="legacy">old</div>', '<div class="modern">new</div>')
        self.assertNotIn('class="legacy"', replaced)
        self.assertIn('class="modern"', replaced)

        removed = apply_component_patch(
            self.html, "remove", r'<div class="legacy">old</div>')
        self.assertNotIn('class="legacy"', removed)

    def test_ambiguous_target_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "target_pattern_ambiguous:2"):
            apply_component_patch(
                '<p class="x">a</p><p class="x">b</p>',
                "replace", r'<p class="x">.*?</p>', '<p>new</p>')

    def test_cas_mismatch_blocks_patch(self):
        with self.assertRaisesRegex(ValueError, "cas_mismatch"):
            verify_and_patch(
                self.html, "remove", r'<div class="legacy">old</div>',
                expected_sha256="0" * 64)

    def test_cas_success_returns_new_digest(self):
        expected = hashlib.sha256(self.html.encode("utf-8")).hexdigest()
        patched, digest = verify_and_patch(
            self.html, "remove", r'<div class="legacy">old</div>', expected_sha256=expected)
        self.assertEqual(hashlib.sha256(patched.encode("utf-8")).hexdigest(), digest)

    def test_atomic_write_replaces_target(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "article.html"
            target.write_text("old", encoding="utf-8")
            atomic_write_text(target, "new")
            self.assertEqual("new", target.read_text(encoding="utf-8"))
            self.assertFalse(list(Path(folder).glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
