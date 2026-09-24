"""Incheon Airport public pages remain strict evidence despite their Python-UA gate."""
import unittest
from unittest.mock import patch

from agents.editorial_writer import fetch_sources


URL = 'https://www.airport.kr/ap_ko/6651/subview.do'
BODY = '''<html><head><title>Incheon Airport</title></head><body>
<main>
<h1>실시간 대기시간</h1>
<p>보안검색 및 출국심사 소요시간에 따라 대기시간은 변경될 수 있습니다.</p>
<p>제1 여객터미널 출국장별 실시간 대기시간을 분 단위로 확인하고 필요하면 새로고침할 수 있습니다.</p>
</main></body></html>'''.encode('utf-8')


class Response:
    status_code = 200
    content = BODY


class AirportOfficialSourceTests(unittest.TestCase):
    def test_airport_public_subview_uses_browser_headers_without_following_redirects(self):
        with patch('agents.editorial_writer.requests.get', return_value=Response()) as get:
            source = fetch_sources({'official_urls': [URL], 'entity': '인천국제공항'})[0]
        headers = get.call_args.kwargs['headers']
        self.assertIn('Mozilla/5.0', headers['User-Agent'])
        self.assertEqual('ko-KR,ko;q=0.9,en;q=0.8', headers['Accept-Language'])
        self.assertFalse(get.call_args.kwargs['allow_redirects'])
        self.assertIn('실시간 대기시간', source['text'])

    def test_unrelated_airport_path_keeps_default_header_policy(self):
        url = 'https://www.airport.kr/other'
        with patch('agents.editorial_writer.requests.get', return_value=Response()) as get:
            fetch_sources({'official_urls': [url], 'entity': '인천국제공항'})
        self.assertEqual({}, get.call_args.kwargs['headers'])


if __name__ == '__main__':
    unittest.main()
