import unittest

from agents.editorial_writer import _normalize_post239_chuseok_sources


class Post239SourceNormalizationTest(unittest.TestCase):
    def test_koreakr_rotating_news_is_removed_only_for_exact_release(self):
        url = 'https://www.korea.kr/briefing/pressReleaseView.do?newsId=156782379'
        text = '공식 본문\n9월 24일(목)부터 27일(일)까지\n실시간 인기뉴스\n09.24. 20:22 기준\n회전 기사'
        self.assertEqual(
            _normalize_post239_chuseok_sources(text, url),
            '공식 본문\n9월 24일(목)부터 27일(일)까지',
        )
        other = url.replace('156782379', '156700000')
        self.assertEqual(_normalize_post239_chuseok_sources(text, other), text)

    def test_royal_notice_view_counter_is_removed_but_date_is_kept(self):
        url = ('https://royal.khs.go.kr/ROYAL/contents/R403000000.do?'
               'id=20260921134912308090&schBcid=notice01&schM=view')
        first = '제목\n창덕궁\n873\n2026-09-21\n후원 특별관람 제외'
        second = first.replace('\n873\n', '\n999\n')
        self.assertEqual(
            _normalize_post239_chuseok_sources(first, url),
            _normalize_post239_chuseok_sources(second, url),
        )
        self.assertIn('2026-09-21', _normalize_post239_chuseok_sources(first, url))

    def test_mmca_view_counter_is_removed_but_content_is_kept(self):
        url = 'https://m.mmca.go.kr/pr/newsDetail.do?bdCId=202609080010583'
        first = '안내\n조회수\n7349\nSNS 공유\n9.25.(금) 추석 당일 휴관'
        second = first.replace('\n7349\n', '\n7353\n')
        self.assertEqual(
            _normalize_post239_chuseok_sources(first, url),
            _normalize_post239_chuseok_sources(second, url),
        )
        self.assertIn('9.25.(금)', _normalize_post239_chuseok_sources(first, url))


if __name__ == '__main__':
    unittest.main()
