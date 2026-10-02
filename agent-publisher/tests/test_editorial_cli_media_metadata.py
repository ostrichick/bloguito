import json
import tempfile
import unittest
from pathlib import Path

import editorial_cli


class EditorialCliMediaMetadataTests(unittest.TestCase):
    def test_loads_utf8_korean_media_metadata_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'media-metadata.json'
            path.write_text(json.dumps({
                'media_title': '2026 세종한글축제 공식 행사 이미지',
                'alt_text': '2026 세종한글축제 공식 행사 이미지',
            }, ensure_ascii=False), encoding='utf-8')
            title, alt = editorial_cli._load_media_metadata_file(path)
            self.assertEqual('2026 세종한글축제 공식 행사 이미지', title)
            self.assertEqual('2026 세종한글축제 공식 행사 이미지', alt)

    def test_rejects_wrong_metadata_shape(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'media-metadata.json'
            path.write_text('{"media_title":"제목"}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'invalid_media_metadata_file'):
                editorial_cli._load_media_metadata_file(path)


if __name__ == '__main__':
    unittest.main()
