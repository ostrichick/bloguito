"""Source attribution is independent of executable booking and install links."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup

from agents.editorial import render, validate_bundle
from agents.editorial_draft_updater import update_draft
from test_editorial_system import NOW, sample


class ActionDestinationsTests(unittest.TestCase):
    def test_six_regional_booking_actions_are_supported_but_seven_are_rejected(self):
        bundle = sample()
        bundle['sources'][0]['actions'] = [
            {'kind': 'booking', 'label': f'{i}지역 공연 예매',
             'url': f'https://tickets.example.com/product/{i}'}
            for i in range(1, 7)
        ]
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        self.assertNotIn('invalid_action_links', validate_bundle(
            bundle, inventory, NOW, require_review=False)['reasons'])
        bundle['sources'][0]['actions'].append(
            {'kind': 'booking', 'label': '7지역 공연 예매',
             'url': 'https://tickets.example.com/product/7'})
        self.assertIn('invalid_action_links', validate_bundle(
            bundle, inventory, NOW, require_review=False)['reasons'])

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

    def test_footer_is_omitted_when_every_evidence_url_is_already_a_cta(self):
        bundle = sample()
        source = bundle['sources'][0]
        source['actions'] = [{
            'kind': 'lookup',
            'label': '공식 조회 서비스',
            'url': source['url'],
        }]
        content = render(bundle['plan'], bundle['sources'])
        self.assertNotIn('class="source-list"', content)
        self.assertNotIn('id="sources"', content)

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

    def test_draft_update_preserves_status_prose_and_reviewed_manifest(self):
        original = sample()
        new = copy.deepcopy(original)
        new['sources'][0]['actions'] = [{'kind': 'booking', 'label': '고속버스 조회·예매',
                                         'url': 'https://www.kobus.co.kr/main.do'}]
        previous_body = render(original['plan'], original['sources'])
        previous_body = previous_body.replace(
            '<div class="bloguito-toc"',
            '<div class="bloguito-cta"><div><a href="https://www.tmoney.co.kr/intro">소개 바로가기</a></div></div>'
            '<div class="bloguito-toc"', 1)
        expected_body = render(new['plan'], new['sources'])
        live = {'ID': 345, 'post_title': original['plan']['title'], 'post_status': 'draft',
                'post_name': 'original-slug', 'post_content': previous_body}
        original_bundle = copy.deepcopy(original)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            index = root / 'draft_posts.json'
            index.write_text(json.dumps([{'id': 345, 'fact_manifest': {'editorial_bundle': original_bundle}}]), encoding='utf-8')

            def run(args, **kwargs):
                if args[5:7] == ['post', 'get']:
                    return Mock(stdout=json.dumps(live))
                if args[5:7] == ['post', 'update']:
                    live['post_content'] = next(arg.split('=', 1)[1] for arg in args if arg.startswith('--post_content='))
                    return Mock(stdout='Success')
                raise AssertionError(args)

            inv = {'checked_on': NOW.date().isoformat(), 'posts': [live]}
            with patch('agents.editorial_draft_updater.ROOT', root), \
                 patch('agents.editorial_draft_updater.DRAFTS_INDEX_FILE', index), \
                 patch('agents.editorial_draft_updater.sync_inventory'), \
                 patch('agents.editorial_draft_updater.load_inventory', return_value=inv), \
                 patch('agents.editorial_draft_updater.validate_bundle', return_value={'status': 'ready', 'reasons': []}), \
                 patch('agents.editorial_draft_updater.fetch_sources', return_value=original['sources']), \
                 patch('agents.editorial_draft_updater.save_report'), \
                 patch('agents.editorial_draft_updater.subprocess.run', side_effect=run):
                self.assertEqual(update_draft(345, new, hashlib.sha256(previous_body.encode()).hexdigest()), 345)
            self.assertEqual(live['post_status'], 'draft')
            self.assertEqual(live['post_name'], 'original-slug')
            self.assertEqual(live['post_content'], expected_body)
            self.assertEqual(json.loads(index.read_text(encoding='utf-8'))[0]['fact_manifest']['editorial_bundle'], new)
            self.assertEqual(len(list((root / 'data' / 'editorial_runs').glob('draft-action-*.json'))), 1)


if __name__ == '__main__':
    unittest.main()
