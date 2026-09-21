"""Source attribution is independent of executable booking and install links."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.editorial import render, validate_bundle
from agents.editorial_draft_updater import update_draft
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
