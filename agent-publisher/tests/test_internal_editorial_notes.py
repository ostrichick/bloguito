"""Editor-only notices stay in audit records, not reader-facing articles."""
import importlib.util
import unittest
from pathlib import Path

from agents.editorial import validate_bundle
from test_editorial_system import NOW, sample


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'strip_internal_editorial_notes.py'
SPEC = importlib.util.spec_from_file_location('strip_internal_editorial_notes', SCRIPT)
NOTES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NOTES)


class InternalNotesTests(unittest.TestCase):
    def test_review_blocks_revision_notices_but_allows_actual_source_date(self):
        bundle = sample()
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        original_heading = bundle['plan']['sections'][0]['heading']
        self.assertEqual(validate_bundle(bundle, inventory, NOW, require_review=False)['status'], 'ready')
        for note in ('정정 안내 (2026년 9월 20일)',
                     '기존 글의 오류를 삭제했습니다.',
                     '내용 재검토: 2026년 9월 20일',
                     '기존 수치의 정정'):
            with self.subTest(note=note):
                bundle['plan']['sections'][0]['heading'] = note
                issues = validate_bundle(bundle, inventory, NOW, require_review=False)['reasons']
                self.assertIn('internal_editorial_note_in_prose', issues)
        bundle['plan']['sections'][0]['heading'] = '서초구 2026년 9월 14일 공식 공고'
        self.assertNotIn('internal_editorial_note_in_prose',
                         validate_bundle(bundle, inventory, NOW, require_review=False)['reasons'])
        bundle['plan']['sections'][0]['heading'] = original_heading

    def test_correction_box_is_removed_and_current_advice_kept(self):
        markup = ('<article><div><strong>정정 안내 (2026년 9월 20일)</strong>'
                  '<p>과거 오류 수정했습니다.</p></div><div><strong>핵심 요약</strong>'
                  '<p>충전소 상태를 먼저 확인하세요. 기존 글에 실린 ‘모든 열거 휴게소의 무료 충전’, '
                  '‘차량당 20kW 무료 제공’ 등은 2026년 공식 운영 근거를 확보하지 못해 삭제했습니다.'
                  '</p></div><p>공식 충전소 조회 링크</p>'
                  '<p>내용 재검토: 2026년 9월 20일. 원문 기준 확인합니다.</p></article>')
        post = {'ID': 219, 'post_status': 'publish', 'post_content': markup}
        updated, reasons = NOTES.transform(post)
        self.assertEqual(reasons, ['correction_banner', 'editorial_phrase', 'internal_review_footer'])
        self.assertIn('충전소 상태를 먼저 확인하세요.', updated)
        self.assertIn('공식 충전소 조회 링크', updated)
        self.assertNotIn('정정 안내', updated)
        self.assertNotIn('기존 글에 실린', updated)
        self.assertNotIn('내용 재검토', updated)


if __name__ == '__main__':
    unittest.main()
