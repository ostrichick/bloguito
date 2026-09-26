import unittest
from unittest.mock import MagicMock, patch

from agents.editorial_writer import fetch_sources


URL = 'https://blog.naver.com/PostView.naver?blogId=coocoo625&logNo=223501023245'


class Post233PriceReferenceTests(unittest.TestCase):
    def test_naver_reference_keeps_article_and_drops_chrome(self):
        body = ('<html><head><title>가격 비교</title></head><body>'
                '<div class="volatile">좋아요 99 추천 88</div>'
                '<div class="se-main-container">'
                + ('편의점 가격 비교 본문 타이레놀정 500mg 3600원 ' * 20)
                + '</div></body></html>')
        response = MagicMock(status_code=200, content=body.encode('utf-8'))
        brief = {'official_urls': [], 'reference_urls': [URL], 'entity': '안전상비의약품'}
        with patch('agents.editorial_writer.requests.get', return_value=response):
            source = fetch_sources(brief)[0]
        self.assertEqual(source['source_type'], 'reference')
        self.assertIn('타이레놀정 500mg 3600원', source['text'])
        self.assertNotIn('좋아요 99', source['text'])


if __name__ == '__main__':
    unittest.main()
