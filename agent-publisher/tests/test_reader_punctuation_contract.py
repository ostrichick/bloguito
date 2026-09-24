"""Reader-facing punctuation contract for shared Bloguito UI."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ReaderPunctuationContractTests(unittest.TestCase):
    def test_social_share_source_has_no_middle_dot(self):
        source = (ROOT / "wordpress" / "mu-plugins" / "bloguito-social-share.php").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("\u00b7", source)
        self.assertIn("카톡, 공유", source)
        self.assertIn("가족, 지인분들과", source)
        self.assertIn("카카오톡, 메신저", source)


if __name__ == "__main__":
    unittest.main()
