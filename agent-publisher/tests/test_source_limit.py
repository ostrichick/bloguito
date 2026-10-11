import hashlib
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agents.editorial_writer import fetch_sources
from agents.source_collector import fetch_sources_subset
from agents.source_extractors import scoped_source_provenance_valid
from agents.editorial import validate_bundle
from test_editorial_system import sample, NOW


class SourceLimitTests(unittest.TestCase):
    LAW = 'https://www.law.go.kr/법령/테스트법'
    PDF = 'https://www.moleg.go.kr/files/test.pdf'

    @staticmethod
    def law_html(*, extra='원문 뒤 문구', duplicate=False, absent=False):
        target = ('제2조(정의)\n' + ('주민이 이용할 수 있는 서비스의 법적 요건과 적용 대상입니다.\n' * 4)
                  + '제3조(적용범위)')
        if duplicate:
            target += '\n제2조(정의)'
        if absent:
            target = target.replace('제3조(적용범위)', '제4조(다른 조문)')
        # The whole rendered document exceeds the old 60k limit.
        text = '2026.10.01\n' + '법령 머리말과 다른 조항입니다.\n' * 3500 + target + '\n' + extra
        return ('<html><head><title>공식 법령</title></head><body><main>'
                + text.replace('\n', '<br/>') + '</main></body></html>').encode('utf-8')

    @staticmethod
    def law_brief():
        return {
            'official_urls': [SourceLimitTests.LAW], 'entity': '공식 법령',
            'official_source_scopes': {SourceLimitTests.LAW: {
                'kind': 'law-section', 'start_marker': '제2조(정의)',
                'end_marker': '제3조(적용범위)', 'version_marker': '2026.10.01',
            }},
        }

    @patch('agents.source_collector._official_get')
    def test_over_60k_law_extracts_only_unique_official_article_and_retains_raw_hash(self, get):
        raw = self.law_html()
        get.return_value = SimpleNamespace(status_code=200, content=raw)
        brief = self.law_brief()
        source = fetch_sources(brief)[0]
        self.assertTrue(80 <= len(source['text']) < 60000)
        self.assertTrue(source['text'].startswith('제2조(정의)'))
        self.assertNotIn('제3조(적용범위)', source['text'])
        self.assertEqual(hashlib.sha256(source['text'].encode()).hexdigest(), source['sha256'])
        self.assertRegex(source['raw_sha256'], '^[0-9a-f]{64}$')
        self.assertEqual(self.LAW, source['raw_url'])
        self.assertEqual('2026.10.01', source['raw_source_version'])
        self.assertTrue(scoped_source_provenance_valid(source, brief))
        self.assertFalse(scoped_source_provenance_valid(source, {'official_urls': [self.LAW]}))

    @patch('agents.source_collector._official_get')
    def test_over_60k_law_without_scope_remains_rejected(self, get):
        get.return_value = SimpleNamespace(status_code=200, content=self.law_html())
        with self.assertRaisesRegex(ValueError, 'official_source_text_missing_or_too_large'):
            fetch_sources({'official_urls': [self.LAW], 'entity': '공식 법령'})

    @patch('agents.source_collector._official_get')
    def test_missing_repeated_or_reversed_article_boundaries_fail_closed(self, get):
        brief = self.law_brief()
        for opts in ({'absent': True}, {'duplicate': True}):
            with self.subTest(opts=opts):
                get.return_value = SimpleNamespace(status_code=200, content=self.law_html(**opts))
                with self.assertRaisesRegex(ValueError, 'span_missing_or_ambiguous'):
                    fetch_sources(brief)
        get.return_value = SimpleNamespace(status_code=200, content=self.law_html())
        reversed_brief = self.law_brief()
        selector = reversed_brief['official_source_scopes'][self.LAW]
        selector['start_marker'], selector['end_marker'] = selector['end_marker'], selector['start_marker']
        with self.assertRaisesRegex(ValueError, 'span_reversed'):
            fetch_sources(reversed_brief)

    @patch('agents.source_collector._official_get')
    def test_unverified_version_unapproved_host_and_reference_scope_are_rejected(self, get):
        get.return_value = SimpleNamespace(status_code=200, content=self.law_html())
        brief = self.law_brief()
        brief['official_source_scopes'][self.LAW]['version_marker'] = '2030.01.01'
        with self.assertRaisesRegex(ValueError, 'source_version_missing'):
            fetch_sources(brief)
        brief = self.law_brief()
        brief['official_urls'] = ['https://example.com/law']
        brief['official_source_scopes'] = {brief['official_urls'][0]: brief['official_source_scopes'][self.LAW]}
        with self.assertRaisesRegex(ValueError, 'law_section_selector_invalid'):
            fetch_sources(brief)
        brief = self.law_brief()
        brief['official_urls'] = []
        brief['reference_urls'] = [self.LAW]
        with self.assertRaisesRegex(ValueError, 'scope_url_not_declared'):
            fetch_sources(brief)

    @patch('agents.source_collector._official_get')
    def test_outside_section_change_preserves_quote_but_updates_raw_hash_on_subset(self, get):
        brief = self.law_brief()
        get.return_value = SimpleNamespace(status_code=200, content=self.law_html(extra='외부 원문 A'))
        original = fetch_sources(brief)[0]
        get.return_value = SimpleNamespace(status_code=200, content=self.law_html(extra='외부 원문 B'))
        changed = fetch_sources_subset(brief, [original], ['s0'])[0]
        self.assertEqual(original['sha256'], changed['sha256'])
        self.assertEqual(original['text'], changed['text'])
        self.assertNotEqual(original['raw_sha256'], changed['raw_sha256'])
        self.assertTrue(scoped_source_provenance_valid(changed, brief))

    @patch('agents.source_collector._official_get')
    def test_scope_pdf_pages_keep_page_numbers_and_raw_pdf_identity(self, get):
        brief = {'official_urls': [self.PDF], 'entity': '공식 PDF',
                 'official_source_scopes': {self.PDF: {
                     'kind': 'pdf-pages', 'pages': [2, 3], 'version_marker': '2026.10.01',
                 }}}
        page_content = ['2026.10.01\n' + '표지' * 36000,
                        '둘째 페이지의 공식 표와 지원 요건, 제한 사항입니다.\n' * 6,
                        '셋째 페이지의 신청 절차와 제외 조건입니다.\n' * 6]
        mock_reader = MagicMock()
        mock_reader.pages = [SimpleNamespace(extract_text=lambda extraction_mode, body=body: body)
                             for body in page_content]
        get.return_value = SimpleNamespace(status_code=200, content=b'%PDF-mocked-raw-2026.10.01')
        with patch('pypdf.PdfReader', return_value=mock_reader):
            source = fetch_sources(brief)[0]
            self.assertIn('둘째 페이지', source['text'])
            self.assertIn('셋째 페이지', source['text'])
            self.assertNotIn('표지', source['text'])
            self.assertEqual([2, 3], source['section_selector']['pages'])
            self.assertEqual(hashlib.sha256(b'%PDF-mocked-raw-2026.10.01').hexdigest(),
                             source['raw_sha256'])
            self.assertEqual(hashlib.sha256(source['text'].encode()).hexdigest(), source['sha256'])
            brief['official_source_scopes'][self.PDF]['pages'] = [2, 4]
            with self.assertRaisesRegex(ValueError, 'pdf_page_missing'):
                fetch_sources(brief)

    @patch('agents.source_collector._official_get')
    def test_subset_recheck_retains_multiple_independent_official_scopes(self, get):
        second = 'https://www.law.go.kr/법령/다른법'
        brief = self.law_brief()
        brief['official_urls'].append(second)
        brief['official_source_scopes'][second] = copy.deepcopy(
            brief['official_source_scopes'][self.LAW])
        get.return_value = SimpleNamespace(status_code=200, content=self.law_html())
        original = fetch_sources(brief)
        self.assertEqual(2, len(original))
        updated = fetch_sources_subset(brief, original, ['s1'])
        self.assertEqual(['s1'], [item['id'] for item in updated])
        self.assertEqual(original[1]['raw_sha256'], updated[0]['raw_sha256'])
        self.assertEqual(original[1]['section_selector'], updated[0]['section_selector'])

    @patch('agents.source_collector._official_get')
    def test_reviewed_quotes_cannot_use_unselected_law_text(self, get):
        get.return_value = SimpleNamespace(status_code=200, content=self.law_html())
        official = self.law_brief()
        selected = fetch_sources(official)[0]
        bundle = sample()
        bundle['brief']['official_urls'] = [self.LAW]
        bundle['brief']['official_source_scopes'] = official['official_source_scopes']
        bundle['sources'] = [selected]
        # A quote about the preceding, unselected article is not evidence even
        # though the same original document contains it elsewhere.
        bundle['plan']['lead']['evidence'][0]['quote'] = '법령 머리말과 다른 조항입니다.'
        decision = validate_bundle(bundle, {'checked_on': '2026-09-14', 'posts': []},
                                   now=NOW, require_review=False)
        self.assertIn('quote_not_in_source', decision['reasons'])
        self.assertNotIn('source_hash_mismatch', decision['reasons'])
        self.assertNotIn('official_scoped_source_provenance_invalid', decision['reasons'])

    @patch('agents.source_collector._official_get')
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
