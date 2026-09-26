import unittest
from unittest.mock import MagicMock, patch

from agents.editorial_writer import fetch_sources


class SourceLimitTests(unittest.TestCase):
    @patch('agents.editorial_writer._official_get')
    def test_seven_official_sources_are_supported(self, get):
        body = '<html><head><title>자료</title></head><body>' + ('근거 문장 ' * 30) + '</body></html>'
        get.return_value = MagicMock(status_code=200, content=body.encode('utf-8'))
        brief = {'official_urls': [f'https://official.example.com/{i}' for i in range(7)],
                 'entity': '전국투어'}
        self.assertEqual(7, len(fetch_sources(brief)))

    def test_eight_official_sources_are_rejected(self):
        brief = {'official_urls': [f'https://official.example.com/{i}' for i in range(8)],
                 'entity': '전국투어'}
        with self.assertRaisesRegex(ValueError, 'too_many_editorial_sources'):
            fetch_sources(brief)


if __name__ == '__main__':
    unittest.main()
