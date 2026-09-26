import unittest
from unittest.mock import MagicMock, patch

from agents.editorial_writer import fetch_sources


URL = 'https://www.yna.co.kr/view/AKR20260619134300017'


class Post233YonhapReferenceTests(unittest.TestCase):
    def test_exact_article_uses_stable_story_body_only(self):
        article = (
            '현재 편의점 판매가 허용된 의약품은 모두 13종이다. '
            + ('안전상비의약품 기사 본문 문장입니다. ' * 80)
            + '실제로 구입할 수 있는 의약품은 11종이다.'
        )
        body = (
            '<html><head><title>상비약 기사</title></head><body>'
            '<div class="live-ranking">실시간 인기기사 999</div>'
            f'<div class="story-news article"><p>{article}</p></div>'
            '<div class="recommend">추천기사 123</div>'
            '</body></html>'
        )
        response = MagicMock(status_code=200, content=body.encode('utf-8'))
        brief = {'official_urls': [], 'reference_urls': [URL], 'entity': '안전상비의약품'}
        with patch('agents.editorial_writer.requests.get', return_value=response):
            source = fetch_sources(brief)[0]
        self.assertEqual(source['source_type'], 'reference')
        self.assertIn('실제로 구입할 수 있는 의약품은 11종이다.', source['text'])
        self.assertNotIn('실시간 인기기사 999', source['text'])
        self.assertNotIn('추천기사 123', source['text'])


if __name__ == '__main__':
    unittest.main()
