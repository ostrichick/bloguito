import unittest
from unittest.mock import MagicMock, patch

from agents.editorial import topic_reasons
from agents.editorial_writer import fetch_sources


class ReferenceSourceTests(unittest.TestCase):
    def test_fetch_sources_labels_declared_reference_urls(self):
        body = ('<html><head><title>자료</title></head><body>'
                + ('가격 참고 문장입니다. ' * 12) + '</body></html>')
        response = MagicMock(status_code=200, content=body.encode('utf-8'))
        brief = {
            'official_urls': ['https://www.mohw.go.kr/policy'],
            'reference_urls': ['https://news.example.com/price'],
            'entity': '안전상비의약품',
        }
        with patch('agents.editorial_writer.requests.get', return_value=response):
            sources = fetch_sources(brief)
        self.assertEqual([s['source_type'] for s in sources], ['official', 'reference'])
        self.assertEqual([s['id'] for s in sources], ['s0', 's1'])

    def test_topic_reasons_rejects_reference_url_duplicated_as_official(self):
        brief = {
            'approved': True,
            'reviewed_at': '2026-09-01',
            'review_until': '2026-10-01',
            'content_type': 'evergreen',
            'useful_until': None,
            'evergreen_reason': '반복 생활 정보',
            'entity': '안전상비의약품',
            'primary_keyword': '안전상비의약품 가격',
            'question': '가격은 얼마인가요?',
            'angle': '가격 참고',
            'required_title_terms': ['안전상비의약품'],
            'reader_questions': [{'id': 'q1', 'question': '가격은 얼마인가요?'}],
            'official_urls': ['https://www.mohw.go.kr/policy'],
            'reference_urls': ['https://www.mohw.go.kr/policy'],
        }
        self.assertIn('invalid_reference_urls', topic_reasons(brief))

    def test_fetch_sources_allows_eight_and_rejects_nine_total(self):
        response = MagicMock(
            status_code=200,
            content=('<html><body>' + ('공식 확인 문장입니다. ' * 12) + '</body></html>').encode('utf-8'),
        )
        brief = {
            'official_urls': [f'https://official.example.com/{i}' for i in range(4)],
            'reference_urls': [f'https://reference.example.com/{i}' for i in range(4)],
            'entity': '테스트',
        }
        with patch('agents.editorial_writer.requests.get', return_value=response):
            self.assertEqual(8, len(fetch_sources(brief)))
            brief['reference_urls'].append('https://reference.example.com/4')
            with self.assertRaisesRegex(ValueError, 'too_many_editorial_sources'):
                fetch_sources(brief)


if __name__ == '__main__':
    unittest.main()
