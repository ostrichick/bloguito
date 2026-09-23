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

    def test_nts_bare_host_uses_same_view_counter_filter(self):
        class Response:
            status_code = 200

            def __init__(self, views):
                self.content = (
                    '<html><head><title>국세청 보도자료</title></head><body>'
                    '<div class="bbs_ViewA"><ul class="bbsV_data">'
                    '<li><strong>작성일자</strong>2026.09.17.</li>'
                    f'<li><strong>조회수</strong>{views}</li></ul>'
                    '<div class="bbsV_cont"><p>개인납세자는 ’25년에 부여하는 포인트부터 '
                    '5년 소멸기한이 적용되고 연간 1,000포인트 한도입니다.</p></div></div>'
                    '</body></html>').encode('utf-8')

        url = 'https://nts.go.kr/nts/na/ntt/selectNttInfo.do?bbsId=1028&mi=2201&nttSn=1355091'
        with patch('agents.editorial_writer.requests.get',
                   side_effect=[Response(6709), Response(6710)]):
            first = fetch_sources({'official_urls': [url], 'entity': '세금포인트'})[0]
            second = fetch_sources({'official_urls': [url], 'entity': '세금포인트'})[0]
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertNotIn('6709', first['text'])
        self.assertIn('’25년에 부여', first['text'])

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

    def test_mohw_board_metadata_counter_is_stable_but_article_facts_are_not(self):
        class Response:
            status_code = 200

            def __init__(self, views, claim):
                self.content = (
                    '<html><head><title>보건복지부 공식 보도자료</title></head><body>'
                    '<ul class="meta">'
                    f'<li class="hit"><strong>조회수</strong><span style="display:none">: </span><span>{views}</span></li>'
                    '</ul><article>'
                    f'<p>{claim}</p>'
                    '<p>기사 본문의 조회수 : 500은 조사 보고에 포함된 실제 수치입니다.</p>'
                    '<p>지급일과 선정 기준을 공식 발표에 근거해 설명합니다.</p>'
                    '</article></body></html>'
                ).encode('utf-8')

        url = 'https://www.mohw.go.kr/board.es?act=view&bid=0027&list_no=1488478&mid=a10503010100'
        brief = {'official_urls': [url], 'entity': '기초연금'}
        with patch('agents.editorial_writer.requests.get', side_effect=[
            Response('163,944', '기초연금 단독가구 기준은 월 247만 원입니다.'),
            Response('163,951', '기초연금 단독가구 기준은 월 247만 원입니다.'),
            Response('163,953', '기초연금 단독가구 기준은 월 248만 원입니다.'),
        ]):
            first, same, changed = (fetch_sources(brief)[0] for _ in range(3))
        self.assertEqual(first['sha256'], same['sha256'])
        self.assertNotEqual(first['sha256'], changed['sha256'])
        self.assertNotIn('163,944', first['text'])
        self.assertIn('조회수 : 500은 조사 보고', first['text'])
        self.assertIn('247만 원', first['text'])

    def test_mohw_other_article_metadata_is_not_removed(self):
        class Response:
            status_code = 200
            content = (
                '<html><body><li class="hit"><strong>총 지급인원</strong><span>12,345명</span></li>'
                '<article><p>해당 내용은 공식 보도자료의 실제 중요한 수치입니다. ' * 5
                + '</p></article></body></html>'
            ).encode('utf-8')

        url = 'https://www.mohw.go.kr/board.es?act=view&bid=0027&list_no=1488478'
        with patch('agents.editorial_writer.requests.get', return_value=Response()):
            result = fetch_sources({'official_urls': [url], 'entity': '기초연금'})[0]
        self.assertIn('총 지급인원', result['text'])
        self.assertIn('12,345명', result['text'])

    def test_mokpo_bulletin_read_counts_do_not_change_official_body_hash(self):
        class Response:
            status_code = 200

            def __init__(self, views, downloads, size, claim):
                self.content = (
                    '<html><head><title>목포시 예방접종 안내</title></head><body>'
                    '<div class="module_view_box"><div class="view_titlebox"><dl>'
                    '<dt>날짜</dt><dd>2026.09.16</dd>'
                    f'<dt>조회수</dt><dd>{views}</dd>'
                    '<dt>등록부서</dt><dd>예방접종팀</dd>'
                    '</dl></div></div><article>'
                    f'<p>{claim}</p>'
                    '<p>이 안내문 본문의 조회수 30은 해당 통계의 실제 값입니다.</p>'
                    '</article><a href="/www/site/common/file_download/548678/621659/file.hwp">'
                    '<strong>접종기관 명단.hwp</strong>'
                    f'<span class="file_info">({downloads} hit/ {size})</span></a>'
                    '</body></html>'
                ).encode('utf-8')

        url = 'https://www.mokpo.go.kr/health/citizen_participation/notice?idx=548678&mode=view'
        brief = {'official_urls': [url], 'entity': '목포 독감'}
        claim = '2026년 9월 21일부터 어린이 접종을 실시하고 2027년 4월 30일까지 운영합니다.'
        with patch('agents.editorial_writer.requests.get', side_effect=[
            Response('336', '270', '221.5 KB', claim),
            Response('338', '276', '221.5 KB', claim),
            Response('339', '279', '223.0 KB', claim),
            Response('340', '280', '221.5 KB', claim.replace('9월 21일', '9월 22일')),
        ]):
            first, same, attachment_changed, body_changed = (
                fetch_sources(brief)[0] for _ in range(4))
        self.assertEqual(first['sha256'], same['sha256'])
        self.assertNotEqual(first['sha256'], attachment_changed['sha256'])
        self.assertNotEqual(first['sha256'], body_changed['sha256'])
        self.assertIn('221.5 KB', first['text'])
        self.assertNotIn('270 hit', first['text'])
        self.assertIn('2026.09.16', first['text'])
        self.assertIn('조회수 30은 해당 통계', first['text'])

    def test_mokpo_view_counter_filter_is_not_global(self):
        class Response:
            status_code = 200
            content = ('<html><body><div class="view_titlebox"><dl>'
                       '<dt>조회수</dt><dd>921</dd></dl></div>'
                       '<p>정책에 관한 원문은 여기에서 그대로 제공됩니다. ' * 5
                       + '</p></body></html>').encode('utf-8')

        with patch('agents.editorial_writer.requests.get', return_value=Response()):
            result = fetch_sources({'official_urls': [
                'https://example.org/health/citizen_participation/notice'],
                'entity': '다른 사이트'})[0]
        self.assertIn('921', result['text'])

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
