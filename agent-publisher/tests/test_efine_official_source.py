"""Police eFine's same-URL cookie challenge must not weaken redirect checks."""
import unittest
from unittest.mock import Mock, patch

from agents.editorial_writer import _normalize_efine_text, fetch_sources


URL = 'https://www.efine.go.kr/main/main.do'
BODY = '''<html><head><title>경찰청교통민원24(이파인)</title></head><body>
<main><h1>교통민원24</h1><p>최근단속내역 미납과태료 기납과태료 미납범칙금 기납범칙금 운전면허 벌점 조회를 제공합니다.</p>
<p>간편인증 금융인증서 공동인증서 모바일신분증으로 로그인할 수 있습니다.</p></main>
</body></html>'''.encode('utf-8')


class EfineOfficialSourceTests(unittest.TestCase):
    def test_same_url_cookie_challenge_is_retried_once_in_same_session(self):
        first = Mock(status_code=307, headers={'Location': URL}, content=b'')
        second = Mock(status_code=200, headers={}, content=BODY)
        session = Mock()
        session.get.side_effect = [first, second]
        session.cookies.get.return_value = 'challenge-cookie'
        with patch('agents.editorial_writer.requests.Session', return_value=session):
            source = fetch_sources({'official_urls': [URL], 'entity': '교통민원24 이파인'})[0]
        self.assertEqual(2, session.get.call_count)
        self.assertTrue(all(call.kwargs['allow_redirects'] is False for call in session.get.call_args_list))
        self.assertIn('최근단속내역', source['text'])

    def test_different_redirect_target_is_not_followed(self):
        response = Mock(
            status_code=307,
            headers={'Location': 'https://example.com/elsewhere'},
            content=b'',
        )
        session = Mock()
        session.get.return_value = response
        session.cookies.get.return_value = 'challenge-cookie'
        with patch('agents.editorial_writer.requests.Session', return_value=session):
            with self.assertRaisesRegex(ValueError, 'official_source_http_307'):
                fetch_sources({'official_urls': [URL], 'entity': '교통민원24 이파인'})
        self.assertEqual(1, session.get.call_count)

    def test_only_exact_skip_link_line_is_removed(self):
        text = '경찰청교통민원24(이파인)\n본문 바로가기\n본문 바로가기 안내 문장\n최근단속내역'
        self.assertEqual(
            '경찰청교통민원24(이파인)\n본문 바로가기 안내 문장\n최근단속내역',
            _normalize_efine_text(text, URL),
        )
        self.assertEqual(
            text,
            _normalize_efine_text(text, 'https://example.org/main.do'),
        )


if __name__ == '__main__':
    unittest.main()
