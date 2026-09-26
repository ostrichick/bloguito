import unittest

from agents.summary_label import normalize_summary_labels


class SummaryLabelTests(unittest.TestCase):
    def test_only_heading_changes_preserving_prose_and_markup(self):
        page = '<div class="bloguito-summary"><div>  핵심 답변 </div><p>핵심 답변은 본문에서도 쓰입니다.</p></div><h2>핵심 답변</h2>'
        saved, report = normalize_summary_labels(page)
        self.assertEqual(page.replace('>  핵심 답변 </div>', '>  한눈에 보기 </div>'), saved)
        self.assertEqual(1, len(report['edits']))
        self.assertFalse(normalize_summary_labels(saved)[1]['edits'])

    def test_legacy_badge_removed_and_byte_offsets_include_korean(self):
        page = '한글 앞부분<div class="bloguito-summary"><div><span style="color:white">3초 요약</span><strong>핵심요약</strong></div><p>내용</p></div>'
        saved, report = normalize_summary_labels(page)
        raw = page.encode('utf-8')
        for edit in reversed(report['edits']):
            self.assertEqual(edit['old'].encode(), raw[edit['start']:edit['end']])
            raw = raw[:edit['start']] + edit['new'].encode() + raw[edit['end']:]
        self.assertEqual(saved.encode(), raw)
        self.assertNotIn('3초 요약', saved)
        self.assertIn('<strong>한눈에 보기</strong>', saved)

    def test_unrelated_green_notice_is_untouched(self):
        page = '<div style="background:#edf7f4;border-left:5px solid green"><strong>마감일만 기억하면 놓칠 수 있습니다</strong><p>내용</p></div>'
        saved, report = normalize_summary_labels(page)
        self.assertEqual(page, saved)
        self.assertEqual(0, report['boxes'])

    def test_known_legacy_green_summary(self):
        page = '<div style="background: #eaf7f2; border-left:4px solid #11775a"><strong>먼저 답부터</strong><p>내용</p></div>'
        saved, report = normalize_summary_labels(page)
        self.assertIn('<strong>한눈에 보기</strong>', saved)
        self.assertEqual(1, report['boxes'])

    def test_ambiguous_or_unknown_explicit_summary_fails_closed(self):
        for page in ['<div class="bloguito-summary"><strong>낯선 제목</strong></div>',
                     '<div class="bloguito-summary"><strong>핵심요약</strong><strong>핵심 답변</strong></div>']:
            with self.assertRaises(ValueError):
                normalize_summary_labels(page)


if __name__ == '__main__':
    unittest.main()
