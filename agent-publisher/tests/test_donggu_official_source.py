import unittest

from agents.editorial_writer import _official_request_headers


class DongguOfficialSourceTests(unittest.TestCase):
    def test_public_event_detail_uses_browser_headers(self):
        url = ('https://www.donggu.go.kr/yeyak/www/viewTnExprnU.do?'
               'exprnKey=6027&guid=64e29739-d4ea-4b73-8761-0e3aae86abe1&key=218')
        headers = _official_request_headers(url)
        self.assertIn('Mozilla/5.0', headers.get('User-Agent', ''))
        self.assertIn('ko-KR', headers.get('Accept-Language', ''))

    def test_public_event_list_uses_browser_headers(self):
        headers = _official_request_headers(
            'https://www.donggu.go.kr/yeyak/www/selectTnExprnListU.do?key=243&sc9=EVENT')
        self.assertIn('Mozilla/5.0', headers.get('User-Agent', ''))

    def test_unrelated_donggu_page_does_not_inherit_browser_headers(self):
        self.assertEqual({}, _official_request_headers(
            'https://www.donggu.go.kr/dg/kor/article/newsNotice/143089'))


if __name__ == '__main__':
    unittest.main()
