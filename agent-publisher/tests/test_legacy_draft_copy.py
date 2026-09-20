"""Legacy draft HTML copy checks; these files are not reviewed editorial bundles."""
import hashlib
import json
import unittest
from pathlib import Path

from agents.editorial import validate_bundle
from test_editorial_system import NOW, sample


ROOT = Path(__file__).resolve().parents[2]
REVISIONS = ROOT / 'content' / 'draft-revisions-2026-09-20'


class LegacyDraftCopyTests(unittest.TestCase):
    def test_editorial_validator_rejects_process_notes_not_source_dates(self):
        bundle = sample()
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        self.assertNotIn('internal_editorial_note_in_prose',
                         validate_bundle(bundle, inventory, NOW, require_review=False)['reasons'])
        for editorial_note in ('이 초안은 공개를 보류합니다.',
                               '자료 검토: 2026년 9월 20일.',
                               '독립적인 검색 질문이 확인되지 않으면 통합합니다.'):
            with self.subTest(note=editorial_note):
                bundle['plan']['sections'][0]['heading'] = editorial_note
                reasons = validate_bundle(bundle, inventory, NOW, require_review=False)['reasons']
                self.assertIn('internal_editorial_note_in_prose', reasons)

    def test_all_revision_copies_match_manifest_and_remain_unapproved(self):
        manifest = json.loads((REVISIONS / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest), 11)
        self.assertEqual(len({entry['wp_id'] for entry in manifest}), 11)
        for entry in manifest:
            with self.subTest(post=entry['wp_id']):
                content = (REVISIONS / entry['revision_path']).read_text(encoding='utf-8')
                checksum = hashlib.sha256(content.replace('\r\n', '\n').rstrip('\n').encode()).hexdigest()
                self.assertEqual(entry['sha256_normalized'], checksum)
                self.assertEqual(entry['publication_status'], 'draft')
                self.assertEqual(entry['review_status'], 'human_final_review_required')
                self.assertIn('<h2>공식 출처</h2><ul>', content)
                self.assertIn('https://', content)
                self.assertEqual(content.count('<article'), 1)
                self.assertEqual(content.count('</article>'), 1)
                for internal in ('공식 출처 및 검토 기록', '자료 검토:',
                                 '링크된 자료의 적용 시점과 실제 안내 화면을 확인해 사용하세요',
                                 '이 초안', '이 원고에서는', '근거가 없어 삭제했습니다'):
                    self.assertNotIn(internal, content)


if __name__ == '__main__':
    unittest.main()
