"""Volatile webpage chrome must not defeat an otherwise strict source recheck."""
import hashlib
import unittest
from unittest.mock import patch

from agents.editorial_writer import fetch_sources


class EditorialSourceProvenanceTests(unittest.TestCase):
    def test_nts_metadata_view_count_is_stable_and_article_facts_are_preserved(self):
        class Response:
            status_code = 200

            def __init__(self, views, fact):
                self.content = (f'<html><head><title>국세청</title></head><body>'
                                '<div class="bbs_ViewA"><ul class="bbsV_data">'
                                '<li><strong>작성일자</strong>2026.09.01.</li>'
                                f'<li><strong>조회수</strong>{views}</li></ul>'
                                f'<div class="bbsV_cont">{fact}</div></div>'
                                '</body></html>').encode('utf-8')

        url = 'https://kids.nts.go.kr/nts/na/ntt/selectNttInfo.do?mi=2201&nttSn=1354576'
        brief = {'official_urls': [url], 'entity': '근로장려금'}
        same_fact = ('<p>2027년 3월 1일부터 15일까지 신청할 수 있습니다. '
                     '신청 가능 가구는 소득 종류와 가구별 요건을 확인합니다.</p>' * 2)
        changed_fact = same_fact.replace('3월 1일부터', '3월 2일부터')
        with patch('agents.editorial_writer.requests.get', side_effect=[
            Response(65288, same_fact),
            Response(65289, same_fact),
            Response(65290, changed_fact),
        ]):
            first, second, changed = (fetch_sources(brief)[0] for _ in range(3))
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertNotEqual(first['sha256'], changed['sha256'])
        self.assertNotIn('65288', first['text'])
        self.assertIn('2027년 3월 1일부터', first['text'])

    def test_page_views_are_excluded_but_actual_content_is_hashed(self):
        class Response:
            status_code = 200

            def __init__(self, views, body):
                self.content = (
                    f'<html><head><title>Government</title></head><body>'
                    f'<p>조회수 : {views}</p><p>{body}</p></body></html>'
                ).encode('utf-8')

        url = 'https://www.fsc.go.kr/po010103/example'
        brief = {'official_urls': [url], 'entity': 'test'}
        with patch('agents.editorial_writer.requests.get', side_effect=[
            Response(100, '확인된 조건과 지급 절차 안내입니다. ' * 5),
            Response(101, '확인된 조건과 지급 절차 안내입니다. ' * 5),
            Response(102, '변경된 조건과 지급 절차 안내입니다. ' * 5),
        ]):
            first, second, changed = (fetch_sources(brief)[0] for _ in range(3))
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertNotEqual(first['sha256'], changed['sha256'])
        self.assertEqual(first['sha256'], hashlib.sha256(first['text'].encode()).hexdigest())
        self.assertNotIn('조회수', first['text'])
        self.assertIn('확인된 조건', first['text'])

    def test_view_count_in_article_sentence_is_preserved(self):
        class Response:
            status_code = 200
            content = ('<html><body><p>조회수 : 120은 이번 공고의 조건입니다.</p>'
                       '<p>다른 관련 안내와 조회 조건을 보존합니다. ' * 5 + '</p></body></html>').encode('utf-8')

        with patch('agents.editorial_writer.requests.get', return_value=Response()):
            result = fetch_sources({'official_urls': ['https://example.org/notice'], 'entity': 'test'})[0]
        self.assertIn('조회수 : 120은 이번 공고의 조건입니다.', result['text'])


if __name__ == '__main__':
    unittest.main()
