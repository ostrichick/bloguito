import copy
import unittest

from agents.editorial import render, supported_official_number_notations, validate_bundle
from tests.test_editorial_system import NOW, sample


class EventSectionAssetsTests(unittest.TestCase):
    def setUp(self):
        self.bundle = sample()
        source = self.bundle['sources'][0]
        section = self.bundle['plan']['sections'][0]
        section['image'] = {
            'url': 'https://www.seocho.go.kr/images/event.jpg',
            'alt': '행사 현장 공식 이미지',
            'caption': '행사 현장 모습',
            'source_id': source['id'],
        }
        section['location'] = {
            'venue': '서초 행사장',
            'address': '서울 서초구 안내로 1',
            'query': '서울 서초구 안내로 1 서초 행사장',
            'evidence': [],
        }
        source['text'] += ' 서울 서초구 안내로 1 서초 행사장.'
        section['location']['evidence'] = [{'source_id': source['id'], 'quote': source['text']}]
        import hashlib
        source['sha256'] = hashlib.sha256(source['text'].encode()).hexdigest()

    def report(self):
        return validate_bundle(
            self.bundle,
            {'checked_on': NOW.date().isoformat(), 'posts': []},
            NOW,
            require_review=False,
        )

    def test_event_image_and_location_render_with_keyless_map_links(self):
        report = self.report()
        self.assertEqual('ready', report['status'], report)
        page = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn('bloguito-event-image', page)
        self.assertIn('행사 현장 모습', page)
        self.assertIn('행사 현장 모습, ', page)
        self.assertNotIn('행사 현장 모습 · ', page)
        self.assertIn('festival-location-card', page)
        self.assertIn('<strong>위치</strong>:', page)
        self.assertIn('map.kakao.com/link/search/', page)
        self.assertIn('map.naver.com/v5/search/', page)
        self.assertNotIn('www.google.com/maps/dir/?api=1', page)
        self.assertNotIn('<iframe', page)
        self.assertNotIn('dapi.kakao.com/v2/maps/sdk.js', page)

    def test_unofficial_image_source_is_rejected(self):
        self.bundle['sources'][0]['source_type'] = 'reference'
        report = self.report()
        self.assertIn('invalid_section_assets', report['reasons'])

    def test_location_evidence_must_be_bound_to_source(self):
        self.bundle['plan']['sections'][0]['location']['evidence'][0]['quote'] = '없는 인용문입니다'
        report = self.report()
        self.assertIn('invalid_section_assets', report['reasons'])

    def test_raw_provider_urls_are_not_accepted_as_location_schema(self):
        location = self.bundle['plan']['sections'][0]['location']
        location['map_url'] = 'https://example.com'
        report = self.report()
        self.assertIn('invalid_section_assets', report['reasons'])

    def test_iso_and_dotted_official_dates_support_korean_reader_notation(self):
        text = '2026년 10월 9일과 2026년 10월 17일 일정입니다.'
        quote = '2026-10-09 ~ 2026-10-11 / 2026.10.17.(토)'
        candidates = {'2026', '10', '9', '17'}
        self.assertEqual(candidates, supported_official_number_notations(text, quote, candidates))

    def test_official_dates_support_compact_month_day_notation(self):
        text = '10/9~10/11, 10/17~10/18'
        quote = '2026-10-09 ~ 2026-10-11 / 2026.10.17.(토) ~ 2026.10.18.(일)'
        candidates = {'10', '9', '11', '17', '18'}
        self.assertEqual(candidates, supported_official_number_notations(text, quote, candidates))

    def test_section_facts_render_before_event_image(self):
        section = self.bundle['plan']['sections'][0]
        source = self.bundle['sources'][0]
        section['facts'] = [{
            'label': '비용',
            'value': '배출수수료 면제',
            'evidence': [{'source_id': source['id'], 'quote': source['text']}],
            'answers': ['q1'],
        }]
        report = self.report()
        self.assertEqual('ready', report['status'], report)
        page = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn('class="festival-facts"', page)
        self.assertLess(page.index('class="festival-facts"'), page.index('class="bloguito-event-image"'))

    def test_overview_table_can_render_mobile_cards(self):
        section = self.bundle['plan']['sections'][0]
        section['table'] = {
            'caption': '행사 비교',
            'headers': ['날짜', '행사', '비용'],
            'mobile_cards': True,
            'rows': [{
                'cells': ['9/14', '가을 행사', '무료'],
                'evidence': [{'source_id': 's0', 'quote': self.bundle['sources'][0]['text']}],
                'answers': ['q1'],
            }],
        }
        self.bundle['sources'][0]['text'] += ' 9/14 가을 행사 무료.'
        import hashlib
        self.bundle['sources'][0]['sha256'] = hashlib.sha256(self.bundle['sources'][0]['text'].encode()).hexdigest()
        section['table']['rows'][0]['evidence'][0]['quote'] = self.bundle['sources'][0]['text']
        report = self.report()
        self.assertEqual('ready', report['status'], report)
        page = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn('bloguito-overview-desktop', page)
        self.assertIn('bloguito-overview-mobile', page)
        self.assertIn('가을 행사', page)


if __name__ == '__main__':
    unittest.main()
