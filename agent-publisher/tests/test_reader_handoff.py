"""A fact already published in a source must be delivered in the article."""
import unittest

from agents.editorial import validate_bundle
from test_editorial_system import NOW, sample


class ReaderHandoffTests(unittest.TestCase):
    def setUp(self):
        self.bundle = sample()
        self.inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}

    def reasons(self, prose):
        self.bundle['plan']['sections'][0]['paragraphs'][0]['text'] = prose
        return validate_bundle(self.bundle, self.inventory, NOW, require_review=False)['reasons']

    def test_attachment_lookup_is_rejected(self):
        for sentence in (
            '첨부자료 「참고2」에서 은행별 날짜와 장소를 찾고, 은행에 문의하세요.',
            '발표의 「참고2」에 연결된 은행별 점포 공지를 대조한 뒤 결정하세요.',
            '공식 홈페이지에서 상세 내용을 직접 찾아보세요.',
        ):
            with self.subTest(sentence=sentence):
                self.assertIn('reader_deflection_or_disclaimer', self.reasons(sentence))

    def test_direct_facts_with_legitimate_stock_caveat_are_allowed(self):
        text = ('하남드림휴게소에서는 9월 23일에 신권교환을 진행합니다. '
                '실시간 신권 재고는 해당 은행에 문의하세요.')
        self.assertNotIn('reader_deflection_or_disclaimer', self.reasons(text))


if __name__ == '__main__':
    unittest.main()
