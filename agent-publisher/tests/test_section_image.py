import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from agents.section_image import (
    SECTION_IMAGE_SNAPSHOT_SCRIPT,
    import_section_image,
    validate_section_image_file,
)


class SectionImageImportTests(unittest.TestCase):
    def _image(self, folder, size=(1200, 675)):
        path = Path(folder) / 'event.webp'
        Image.new('RGB', size, color=(230, 240, 235)).save(path, 'WEBP')
        return path

    def test_validation_requires_large_16_by_9_image(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(1200, validate_section_image_file(self._image(folder))['width'])
            with self.assertRaisesRegex(ValueError, 'section_image_too_small'):
                validate_section_image_file(self._image(folder, (800, 450)))

    def test_import_preserves_post_featured_image_and_seo(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = self._image(folder)
            live = {
                'post_status': 'draft', 'post_title': '부산 행사', 'post_name': 'busan',
                'post_content': '<p>본문</p>', 'post_excerpt': '요약',
            }
            sha = hashlib.sha256(live['post_content'].encode()).hexdigest()
            rank = {k: v for k, v in zip(
                ('rank_math_focus_keyword', 'rank_math_title', 'rank_math_description'),
                ('키워드', '제목', '설명'))}
            wp_calls = []

            def run(args, **kwargs):
                wp = args[5:] if args[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'wp'] else None
                if wp:
                    wp_calls.append(wp)
                if wp == ['eval', SECTION_IMAGE_SNAPSHOT_SCRIPT, '--allow-root']:
                    payload = json.loads(kwargs['input'])
                    attachment = None
                    if payload['attachment_id'] == 777:
                        attachment = {
                            'ID': 777, 'guid': 'https://lifeinfo24.org/uploads/event.webp',
                            'post_title': '행사 이미지', 'post_mime_type': 'image/webp',
                            'alt': '행사 장면',
                        }
                    return Mock(stdout=json.dumps({
                        'protocol': 1, 'post': live, 'thumbnail_id': '650',
                        'rank_math_meta': rank, 'attachment': attachment,
                    }), returncode=0)
                if wp and wp[:2] == ['media', 'import']:
                    self.assertNotIn('--featured_image', wp)
                    return Mock(stdout='777\n', stderr='', returncode=0)
                if args[:3] == ['sudo', 'docker', 'cp']:
                    return Mock(stdout=b'', stderr=b'', returncode=0)
                if args[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'rm']:
                    return Mock(stdout=b'', stderr=b'', returncode=0)
                raise AssertionError(args)

            with patch('agents.section_image.ROOT', root), \
                 patch('agents.section_image.subprocess.run', side_effect=run):
                result = import_section_image(
                    648, image, sha, media_title='행사 이미지', alt_text='행사 장면', confirmed=True)
            self.assertEqual(777, result['attachment_id'])
            self.assertEqual(sha, result['content_sha256'])
            self.assertEqual(3, len(wp_calls))
            self.assertEqual('eval', wp_calls[0][0])
            self.assertEqual(['media', 'import'], wp_calls[1][:2])
            self.assertEqual('eval', wp_calls[2][0])
            self.assertFalse(any(wp[:3] == ['post', 'meta', 'get'] for wp in wp_calls))


if __name__ == '__main__':
    unittest.main()
