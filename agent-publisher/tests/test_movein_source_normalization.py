import unittest

from agents.editorial_writer import _normalize_movein_service_text


class MoveinSourceNormalizationTests(unittest.TestCase):
    def test_government24_household_faq_drops_only_counter(self):
        text = '전입신고\n794,646\n① 온라인 전입신고 시 [세대주확인]이 필요한 경우 안내'
        self.assertEqual(
            '전입신고\n① 온라인 전입신고 시 [세대주확인]이 필요한 경우 안내',
            _normalize_movein_service_text(
                text, 'https://www.gov.kr/portal/faq/869?backBtnYn=N'))

    def test_government24_result_faq_drops_only_counter(self):
        text = '처리결과\n264,968\n전입신고 담당자가 전입처리를 완료한 후 안내'
        self.assertEqual(
            '처리결과\n전입신고 담당자가 전입처리를 완료한 후 안내',
            _normalize_movein_service_text(
                text, 'https://www.gov.kr/portal/faq/867?backBtnYn=N'))

    def test_110_faq_drops_only_counter(self):
        text = '조회수 :\n60995\n질문내용\n본문'
        self.assertEqual(
            '조회수 :\n질문내용\n본문',
            _normalize_movein_service_text(
                text,
                'https://www.110.go.kr/data/counselView.do?curPage=10&num=A01_660027&scCate1=&scCate2=&scIntt=&scText=&scType='))

    def test_exact_source_fails_closed_if_counter_structure_changes(self):
        with self.assertRaisesRegex(
                ValueError, 'movein_household_faq_view_counter_structure_changed'):
            _normalize_movein_service_text(
                '전입신고\n조회수 비공개\n① 온라인 전입신고 시 [세대주확인]이 필요한 경우 안내',
                'https://www.gov.kr/portal/faq/869?backBtnYn=N')


if __name__ == '__main__':
    unittest.main()
