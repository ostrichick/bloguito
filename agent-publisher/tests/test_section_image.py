import hashlib
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from agents.section_image import (
    cache_section_image_review,
    create_section_image_review,
    decide_section_image_candidate,
    find_cached_section_image_review,
    import_section_image,
    import_section_images,
    validate_section_image_file,
)
from editorial_cli import _main


class SectionImageImportTests(unittest.TestCase):
    def _image(self, folder, size=(1200, 675)):
        path = Path(folder) / 'event.webp'
        Image.new('RGB', size, color=(230, 240, 235)).save(path, 'WEBP')
        return path

    def test_validation_keeps_minimum_size_but_allows_original_aspect_ratio(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(1200, validate_section_image_file(self._image(folder))['width'])
            square = validate_section_image_file(self._image(folder, (1200, 1200)))
            self.assertEqual((1200, 1200), (square['width'], square['height']))
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

            def run(args, **kwargs):
                wp = args[5:] if args[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'wp'] else None
                if wp and wp[0] == 'eval':
                    payload = json.loads(kwargs['input'])
                    if 'keys' in payload:
                        values = {}
                        for key in payload['keys']:
                            if payload['post_id'] == 777 and key == '_wp_attachment_image_alt':
                                values[key] = '행사 장면'
                            elif key == '_thumbnail_id':
                                values[key] = '650'
                            else:
                                values[key] = rank[key]
                        return Mock(stdout=json.dumps({'status': 'ok', 'meta': values}), returncode=0)
                if wp and wp[:2] == ['post', 'get']:
                    if wp[2] == '777':
                        return Mock(stdout=json.dumps({
                            'ID': 777, 'guid': 'https://lifeinfo24.org/uploads/event.webp',
                            'post_title': '행사 이미지', 'post_mime_type': 'image/webp'}), returncode=0)
                    return Mock(stdout=json.dumps(live), returncode=0)
                if wp and wp[:3] == ['post', 'meta', 'get']:
                    if wp[3] == '777' and wp[4] == '_wp_attachment_image_alt':
                        return Mock(stdout='행사 장면\n', stderr='', returncode=0)
                    if wp[4] == '_thumbnail_id':
                        return Mock(stdout='650\n', stderr='', returncode=0)
                    return Mock(stdout=rank[wp[4]] + '\n', stderr='', returncode=0)
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
            self.assertEqual('650', '650')
            self.assertEqual(sha, result['content_sha256'])

    def test_batch_import_reads_target_baseline_and_readback_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = self._image(folder, (1200, 800))
            second = root / 'second.jpg'
            Image.new('RGB', (1400, 900), color=(220, 230, 240)).save(second, 'JPEG')
            live = {
                'post_status': 'draft', 'post_title': '대구 행사', 'post_name': 'daegu',
                'post_content': '<p>본문</p>', 'post_excerpt': '요약',
            }
            sha = hashlib.sha256(live['post_content'].encode()).hexdigest()
            rank = {k: v for k, v in zip(
                ('rank_math_focus_keyword', 'rank_math_title', 'rank_math_description'),
                ('키워드', '제목', '설명'))}
            attachment_data = {
                '777': ('첫 이미지', '첫 장면', 'https://lifeinfo24.org/uploads/first.webp', 'image/webp'),
                '778': ('둘째 이미지', '둘째 장면', 'https://lifeinfo24.org/uploads/second.jpg', 'image/jpeg'),
            }
            target_reads = 0
            media_imports = 0

            def run(args, **kwargs):
                nonlocal target_reads, media_imports
                wp = args[5:] if args[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'wp'] else None
                if wp and wp[0] == 'eval':
                    payload = json.loads(kwargs['input'])
                    if 'keys' in payload:
                        values = {}
                        for key in payload['keys']:
                            attachment_row = attachment_data.get(str(payload['post_id']))
                            if attachment_row and key == '_wp_attachment_image_alt':
                                values[key] = attachment_row[1]
                            elif key == '_thumbnail_id':
                                values[key] = '650'
                            else:
                                values[key] = rank[key]
                        return Mock(stdout=json.dumps({'status': 'ok', 'meta': values}), returncode=0)
                if wp and wp[:2] == ['post', 'get']:
                    if wp[2] in attachment_data:
                        title, _, guid, mime = attachment_data[wp[2]]
                        return Mock(stdout=json.dumps({
                            'ID': int(wp[2]), 'guid': guid, 'post_title': title,
                            'post_mime_type': mime}), returncode=0)
                    target_reads += 1
                    return Mock(stdout=json.dumps(live), returncode=0)
                if wp and wp[:3] == ['post', 'meta', 'get']:
                    if wp[3] in attachment_data and wp[4] == '_wp_attachment_image_alt':
                        return Mock(stdout=attachment_data[wp[3]][1] + '\n', stderr='', returncode=0)
                    if wp[4] == '_thumbnail_id':
                        return Mock(stdout='650\n', stderr='', returncode=0)
                    return Mock(stdout=rank[wp[4]] + '\n', stderr='', returncode=0)
                if wp and wp[:2] == ['media', 'import']:
                    media_imports += 1
                    return Mock(stdout=f'{776 + media_imports}\n', stderr='', returncode=0)
                if args[:3] == ['sudo', 'docker', 'cp']:
                    return Mock(stdout=b'', stderr=b'', returncode=0)
                if args[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'rm']:
                    return Mock(stdout=b'', stderr=b'', returncode=0)
                raise AssertionError(args)

            with patch('agents.section_image.ROOT', root), \
                 patch('agents.section_image.subprocess.run', side_effect=run):
                result = import_section_images(648, [
                    {'image_path': first, 'media_title': '첫 이미지', 'alt_text': '첫 장면'},
                    {'image_path': second, 'media_title': '둘째 이미지', 'alt_text': '둘째 장면'},
                ], sha, confirmed=True)

            self.assertEqual(2, target_reads)
            self.assertEqual(2, media_imports)
            self.assertEqual([777, 778], [item['attachment_id'] for item in result['attachments']])
            self.assertEqual(2, result['imported_count'])
            self.assertEqual(0, result['reused_count'])
            self.assertEqual(sha, result['content_sha256'])

    def test_review_cache_reuses_only_same_source_and_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = self._image(folder, (1400, 900))
            cache = root / 'section-image-reviews.json'
            review = create_section_image_review(
                image,
                source_url='https://example.org/events/photo.jpg',
                media_title='행사 활동사진',
                alt_text='무대에서 공연 중인 출연진',
                rights_basis='공공누리 제1유형',
                rights_reference='https://www.kogl.or.kr/info/license.do',
            )

            cache_section_image_review(review, cache_path=cache)
            cache_section_image_review(review, cache_path=cache)
            manifest = json.loads(cache.read_text(encoding='utf-8'))
            self.assertEqual(1, len(manifest['entries']))

            reused = find_cached_section_image_review(
                review['source_url'], review['content_sha256'], cache_path=cache)
            self.assertEqual(review, reused)
            self.assertIsNone(find_cached_section_image_review(
                'https://example.org/events/other.jpg', review['content_sha256'], cache_path=cache))
            self.assertIsNone(find_cached_section_image_review(
                review['source_url'], 'b' * 64, cache_path=cache))

    def test_candidate_decision_stops_at_first_commercially_safe_candidate(self):
        unsafe = {
            'source_url': 'https://example.org/noncommercial.jpg',
            'rights': {
                'commercial_reuse_allowed': False,
                'basis': '공공누리 제4유형',
                'reference': 'https://www.kogl.or.kr/info/license.do',
            },
        }
        safe = {
            'source_url': 'https://example.org/safe.jpg',
            'rights': {
                'commercial_reuse_allowed': True,
                'basis': '공공누리 제1유형',
                'reference': 'https://www.kogl.or.kr/info/license.do',
            },
        }
        later = {
            'source_url': 'https://example.org/later.jpg',
            'rights': {
                'commercial_reuse_allowed': True,
                'basis': 'CC BY 4.0',
                'reference': 'https://creativecommons.org/licenses/by/4.0/',
            },
        }

        decision = decide_section_image_candidate([unsafe, safe, later])
        self.assertEqual('adopt', decision['decision'])
        self.assertTrue(decision['stop_search'])
        self.assertIs(safe, decision['candidate'])
        self.assertEqual(
            {'decision': 'no_image', 'stop_search': True, 'candidate': None},
            decide_section_image_candidate([safe], image_required=False),
        )

    def test_batch_reuses_explicit_reviewed_attachment_without_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = self._image(folder, (1400, 900))
            live = {
                'post_status': 'draft', 'post_title': '대구 행사', 'post_name': 'daegu',
                'post_content': '<p>본문</p>', 'post_excerpt': '요약',
            }
            sha = hashlib.sha256(live['post_content'].encode()).hexdigest()
            rank = {k: v for k, v in zip(
                ('rank_math_focus_keyword', 'rank_math_title', 'rank_math_description'),
                ('키워드', '제목', '설명'))}
            attachment_url = 'https://lifeinfo24.org/uploads/reused.webp'
            attachment = {
                'reviewed': True,
                'attachment_id': 777,
                'attachment_url': attachment_url,
            }
            review = create_section_image_review(
                image,
                source_url='https://example.org/events/reused.webp',
                media_title='검증된 행사 이미지',
                alt_text='행사장 활동 장면',
                rights_basis='공공누리 제1유형',
                rights_reference='https://www.kogl.or.kr/info/license.do',
                attachment=attachment,
            )
            target_reads = 0
            media_imports = 0

            def run(args, **kwargs):
                nonlocal target_reads, media_imports
                wp = args[5:] if args[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'wp'] else None
                if wp and wp[0] == 'eval':
                    payload = json.loads(kwargs['input'])
                    if 'keys' in payload:
                        values = {}
                        for key in payload['keys']:
                            if payload['post_id'] == 777 and key == '_wp_attachment_image_alt':
                                values[key] = '행사장 활동 장면'
                            elif key == '_thumbnail_id':
                                values[key] = '650'
                            else:
                                values[key] = rank[key]
                        return Mock(stdout=json.dumps({'status': 'ok', 'meta': values}), returncode=0)
                if wp and wp[:2] == ['post', 'get']:
                    if wp[2] == '777':
                        return Mock(stdout=json.dumps({
                            'ID': 777, 'guid': attachment_url,
                            'post_title': '검증된 행사 이미지', 'post_mime_type': 'image/webp',
                        }), returncode=0)
                    target_reads += 1
                    return Mock(stdout=json.dumps(live), returncode=0)
                if wp and wp[:3] == ['post', 'meta', 'get']:
                    if wp[3] == '777' and wp[4] == '_wp_attachment_image_alt':
                        return Mock(stdout='행사장 활동 장면\n', stderr='', returncode=0)
                    if wp[4] == '_thumbnail_id':
                        return Mock(stdout='650\n', stderr='', returncode=0)
                    return Mock(stdout=rank[wp[4]] + '\n', stderr='', returncode=0)
                if wp and wp[:2] == ['media', 'import']:
                    media_imports += 1
                    raise AssertionError('existing reviewed attachment must skip media import')
                if args[:3] == ['sudo', 'docker', 'cp']:
                    raise AssertionError('existing reviewed attachment must skip docker copy')
                if args[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'rm']:
                    raise AssertionError('existing reviewed attachment must skip temp cleanup')
                raise AssertionError(args)

            with patch('agents.section_image.ROOT', root), \
                 patch('agents.section_image.subprocess.run', side_effect=run):
                result = import_section_images(648, [{
                    'media_title': '검증된 행사 이미지',
                    'alt_text': '행사장 활동 장면',
                    'review': review,
                }], sha, confirmed=True)

            self.assertEqual(2, target_reads)
            self.assertEqual(0, media_imports)
            self.assertEqual(0, result['imported_count'])
            self.assertEqual(1, result['reused_count'])
            self.assertTrue(result['attachments'][0]['reused_existing'])
            self.assertEqual(777, result['attachments'][0]['attachment_id'])

    def test_cli_batch_manifest_resolves_relative_image_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_dir = root / 'images'
            image_dir.mkdir()
            image = self._image(image_dir)
            manifest = root / 'section-images.json'
            manifest.write_text(json.dumps({'images': [{
                'image_path': 'images/event.webp',
                'media_title': '행사 이미지',
                'alt_text': '행사 장면',
            }]}), encoding='utf-8')
            sha = 'a' * 64
            result = {'post_id': 648, 'attachments': [], 'content_sha256': sha}
            argv = [
                'editorial_cli.py', 'import-section-images', str(manifest),
                '--post-id', '648', '--expected-content-sha256', sha, '--confirm-update',
            ]
            with patch.object(sys, 'argv', argv), \
                 patch('agents.section_image.import_section_images', return_value=result) as batch_import, \
                 patch('builtins.print'):
                _main()

            args, kwargs = batch_import.call_args
            self.assertEqual(648, args[0])
            self.assertEqual(image.resolve(), Path(args[1][0]['image_path']).resolve())
            self.assertEqual('행사 이미지', args[1][0]['media_title'])
            self.assertEqual(sha, args[2])
            self.assertTrue(kwargs['confirmed'])

    def test_cli_batch_manifest_preserves_reviewed_attachment_without_image_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = root / 'section-images.json'
            review = {
                'schema': 'section-image-review/v1',
                'source_url': 'https://example.org/reused.webp',
                'content_sha256': 'b' * 64,
                'media_title': '검증된 행사 이미지',
                'alt_text': '행사 장면',
                'rights': {
                    'commercial_reuse_allowed': True,
                    'basis': '공공누리 제1유형',
                    'reference': 'https://www.kogl.or.kr/info/license.do',
                },
                'image': {'width': 1400, 'height': 900, 'format': 'WEBP'},
                'attachment': {
                    'reviewed': True, 'attachment_id': 777,
                    'attachment_url': 'https://lifeinfo24.org/uploads/reused.webp',
                },
            }
            manifest.write_text(json.dumps({'images': [{
                'media_title': '검증된 행사 이미지', 'alt_text': '행사 장면', 'review': review,
            }]}), encoding='utf-8')
            sha = 'a' * 64
            argv = [
                'editorial_cli.py', 'import-section-images', str(manifest),
                '--post-id', '648', '--expected-content-sha256', sha, '--confirm-update',
            ]
            with patch.object(sys, 'argv', argv), \
                 patch('agents.section_image.import_section_images', return_value={
                     'post_id': 648, 'attachments': [], 'content_sha256': sha,
                 }) as batch_import, patch('builtins.print'):
                _main()
            item = batch_import.call_args.args[1][0]
            self.assertNotIn('image_path', item)
            self.assertEqual(777, item['review']['attachment']['attachment_id'])


if __name__ == '__main__':
    unittest.main()
