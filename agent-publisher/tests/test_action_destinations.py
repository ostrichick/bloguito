"""Source attribution is independent of executable booking and install links."""
import copy
import unittest
from bs4 import BeautifulSoup

from agents.editorial import render, validate_bundle
from test_editorial_system import NOW, sample


class ActionDestinationsTests(unittest.TestCase):
    def test_unverified_official_source_only_appears_in_citations(self):
        bundle = sample()
        html = render(bundle['plan'], bundle['sources'])
        self.assertNotIn('class="bloguito-cta"', html)
        self.assertIn('class="source-list"', html)
        self.assertIn(bundle['sources'][0]['url'], html)

    def test_install_is_specific_store_listing_and_malformed_action_is_blocked(self):
        bundle = sample()
        bundle['sources'][0]['actions'] = [{'kind': 'install', 'label': '앱 설치하기',
                                           'url': 'https://play.google.com/store/apps/details?id=kr.co.tmoney.tia'}]
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        self.assertNotIn('invalid_action_links', validate_bundle(bundle, inventory, NOW, require_review=False)['reasons'])
        bundle['sources'][0]['actions'][0]['url'] = 'https://www.tmoney.co.kr/aeb/biz/platformService/tmoneyGo.dev'
        self.assertIn('invalid_action_links', validate_bundle(bundle, inventory, NOW, require_review=False)['reasons'])

    def test_six_distinct_regional_booking_actions_are_allowed(self):
        bundle = sample()
        bundle['sources'][0]['actions'] = [
            {'kind': 'booking', 'label': f'{city} 공연 예매',
             'url': f'https://ticket.yes24.com/Perf/{product_id}'}
            for city, product_id in (
                ('서울', '60153'), ('부산', '60154'), ('대구', '60208'),
                ('대전', '60209'), ('광주', '60212'), ('인천', '60215'),
            )
        ]
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        self.assertNotIn(
            'invalid_action_links',
            validate_bundle(bundle, inventory, NOW, require_review=False)['reasons'],
        )
        content = render(bundle['plan'], bundle['sources'])
        for action in bundle['sources'][0]['actions']:
            self.assertIn(action['url'], content)

    def test_more_than_eight_actions_are_rejected(self):
        bundle = sample()
        bundle['sources'][0]['actions'] = [
            {'kind': 'booking', 'label': f'지역 {index} 공연 예매',
             'url': f'https://ticket.yes24.com/Perf/{61000 + index}'}
            for index in range(1, 10)
        ]
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        self.assertIn(
            'invalid_action_links',
            validate_bundle(bundle, inventory, NOW, require_review=False)['reasons'],
        )

    def test_section_scoped_action_renders_only_inside_target_section(self):
        bundle = sample()
        action = {
            'kind': 'booking',
            'label': '탄동천 탐사 신청',
            'url': 'https://rsvn.science.go.kr/nsm/edcarsvn/edcarsvnDetail?edcPrgmid=2782',
        }
        bundle['sources'][0]['actions'] = [action]
        bundle['plan']['sections'][0]['actions'] = [action['url']]
        content = render(bundle['plan'], bundle['sources'])
        soup = BeautifulSoup(content, 'html.parser')
        self.assertEqual(1, len(soup.select('.bloguito-section-cta a[href]')))
        self.assertEqual(action['url'], soup.select_one('.bloguito-section-cta a')['href'])
        self.assertIsNone(soup.select_one('.bloguito-cta'))
        section_heading = soup.find('h2', string=lambda value: value and bundle['plan']['sections'][0]['heading'] in value)
        self.assertIsNotNone(section_heading)
        self.assertIsNotNone(section_heading.find_next('div', class_='bloguito-section-cta'))

    def test_section_action_must_reference_verified_source_action(self):
        bundle = sample()
        bundle['plan']['sections'][0]['actions'] = ['https://example.com/unreviewed']
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        report = validate_bundle(bundle, inventory, NOW, require_review=False)
        self.assertIn('invalid_section_actions', report['reasons'])

    def test_footer_omits_exact_cta_url_and_uses_descriptive_evidence_label(self):
        bundle = sample()
        action_source = bundle['sources'][0]
        action_source['actions'] = [{
            'kind': 'lookup',
            'label': '공식 조회 서비스',
            'url': action_source['url'],
        }]
        evidence_source = copy.deepcopy(action_source)
        evidence_source.update({
            'id': 's1',
            'url': 'https://www.seocho.go.kr/procedure',
            'title': '서초구',
            'citation_label': '서초구 선풍기 배출 절차 안내',
        })
        evidence_source.pop('actions')
        bundle['sources'].append(evidence_source)
        bundle['plan']['sections'][0]['paragraphs'][0]['evidence'].append({
            'source_id': 's1',
            'quote': evidence_source['text'],
        })

        content = render(bundle['plan'], bundle['sources'])
        soup = BeautifulSoup(content, 'html.parser')
        footer = soup.select_one('ul.source-list')
        self.assertIsNotNone(footer)
        footer_links = {a['href']: a.get_text(' ', strip=True) for a in footer.select('a[href]')}
        self.assertNotIn(action_source['url'], footer_links)
        self.assertEqual('서초구 선풍기 배출 절차 안내',
                         footer_links[evidence_source['url']])

    def test_footer_preserves_provenance_when_every_evidence_url_is_already_a_cta(self):
        bundle = sample()
        source = bundle['sources'][0]
        source['actions'] = [{
            'kind': 'lookup',
            'label': '공식 조회 서비스',
            'url': source['url'],
        }]
        content = render(bundle['plan'], bundle['sources'])
        soup = BeautifulSoup(content, 'html.parser')
        footer = soup.select_one('ul.source-list')
        self.assertIsNotNone(footer)
        self.assertEqual([source['url']], [a['href'] for a in footer.select('a[href]')])
        self.assertEqual(1, len(soup.select('#sources')))

    def test_repeated_evidence_blocks_do_not_duplicate_fallback_citations(self):
        bundle = sample()
        source = bundle['sources'][0]
        source['actions'] = [{'kind': 'lookup', 'label': '공식 조회 서비스', 'url': source['url']}]
        bundle['plan']['sections'][0]['paragraphs'].append(copy.deepcopy(bundle['plan']['lead']))
        footer = BeautifulSoup(render(bundle['plan'], bundle['sources']), 'html.parser').select_one('ul.source-list')
        self.assertEqual(1, len(footer.select('a[href]')))

    def test_invalid_citation_label_is_rejected(self):
        bundle = sample()
        bundle['sources'][0]['citation_label'] = 'x'
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        report = validate_bundle(bundle, inventory, NOW, require_review=False)
        self.assertIn('invalid_source_citation_label', report['reasons'])

    def test_footer_can_use_reader_facing_citation_url_separate_from_fetch_url(self):
        bundle = sample()
        source = bundle['sources'][0]
        source['citation_url'] = 'https://www.korea.kr/briefing/pressReleaseView.do?newsId=156782886'
        content = render(bundle['plan'], bundle['sources'])
        soup = BeautifulSoup(content, 'html.parser')
        footer = soup.select_one('ul.source-list')
        self.assertIsNotNone(footer)
        hrefs = [a['href'] for a in footer.select('a[href]')]
        self.assertIn(source['citation_url'], hrefs)
        self.assertNotIn(source['url'], hrefs)

    def test_invalid_citation_url_is_rejected(self):
        bundle = sample()
        bundle['sources'][0]['citation_url'] = 'javascript:alert(1)'
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        report = validate_bundle(bundle, inventory, NOW, require_review=False)
        self.assertIn('invalid_source_citation_url', report['reasons'])

if __name__ == '__main__':
    unittest.main()
