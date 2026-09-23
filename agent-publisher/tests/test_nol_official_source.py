"""NOL ticket product pages remain strict evidence despite their UA gate."""
import hashlib
import unittest
from unittest.mock import patch

from agents.editorial_writer import fetch_sources


URL = 'https://nol.yanolja.com/ticket/products/26013136'
BODY = '''<html><head><title>2026 무명전설 수원앵콜 | NOL</title></head><body>
<main>
<h1>2026 무명전설 크리스마스 콘서트 - 수원앵콜</h1>
<p>장소 수원컨벤션센터</p><p>기간 2026.12.25</p>
<p>콘서트 주간 {rank}위</p><p>찜 {likes}명</p>
<div>리뷰
{reviews}
개</div>
<h2>가격</h2><p>R석 154,000원</p><p>S석 143,000원</p>
<h2>이용안내</h2><p>예매 가능 시간 월~토요일 관람시: 전일 17시까지</p>
<p>운영 시간 2026년 12월 25일(금) 오후 1시, 오후 6시</p>
<p>{claim}</p>
</main></body></html>'''


class Response:
    status_code = 200

    def __init__(self, *, rank=16, likes='400', reviews=15,
                 claim='공식 상품의 공연일과 가격 안내입니다.'):
        self.content = BODY.format(rank=rank, likes=likes, reviews=reviews,
                                   claim=claim).encode('utf-8')


class NolOfficialSourceTests(unittest.TestCase):
    def test_product_route_uses_browser_headers_and_volatile_counts_do_not_change_hash(self):
        with patch('agents.editorial_writer.requests.get', side_effect=[
                Response(rank=16, likes='400', reviews=15),
                Response(rank=3, likes='4,999', reviews=44),
        ]) as get:
            first = fetch_sources({'official_urls': [URL], 'entity': '무명전설'})[0]
            same = fetch_sources({'official_urls': [URL], 'entity': '무명전설'})[0]
        self.assertEqual(first['sha256'], same['sha256'])
        self.assertEqual(first['sha256'], hashlib.sha256(first['text'].encode()).hexdigest())
        self.assertIn('2026.12.25', first['text'])
        self.assertIn('154,000원', first['text'])
        self.assertNotIn('콘서트 주간', first['text'])
        self.assertNotIn('찜 400명', first['text'])
        self.assertNotIn('\n15\n개', first['text'])
        for call in get.call_args_list:
            headers = call.kwargs['headers']
            self.assertIn('Mozilla/5.0', headers['User-Agent'])
            self.assertEqual('ko-KR,ko;q=0.9,en;q=0.8', headers['Accept-Language'])
            self.assertFalse(call.kwargs['allow_redirects'])

    def test_product_fact_change_changes_hash(self):
        with patch('agents.editorial_writer.requests.get', side_effect=[
                Response(), Response(claim='공식 상품의 공연일이 변경되었습니다.'),
        ]):
            first = fetch_sources({'official_urls': [URL], 'entity': '무명전설'})[0]
            changed = fetch_sources({'official_urls': [URL], 'entity': '무명전설'})[0]
        self.assertNotEqual(first['sha256'], changed['sha256'])

    def test_other_hosts_keep_default_header_policy(self):
        url = 'https://example.org/official'
        with patch('agents.editorial_writer.requests.get', return_value=Response()) as get:
            fetch_sources({'official_urls': [url], 'entity': '다른 공식 페이지'})
        self.assertEqual({}, get.call_args.kwargs['headers'])


if __name__ == '__main__':
    unittest.main()
