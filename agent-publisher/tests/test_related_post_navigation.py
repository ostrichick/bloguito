"""Preserve verified internal navigation across reviewed public-post edits."""

import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from agents.editorial import digest, policy, policy_fingerprint, render, validate_bundle
from agents.related_links import internal_post_ids, missing_internal_post_ids
from agents.temporal_validation import KST
from scripts import prepare_post_approval as approval


class RelatedPostNavigationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 23, 12, tzinfo=KST)
        text = '공식 안내 원문은 실제 출생 대상과 접종 일정의 기준을 안내합니다.'
        self.bundle = {
            'brief': {'id': 'related-test', 'existing_post_id': 81, 'category_key': 'life-health',
                      'approved': True, 'entity': '접종', 'primary_keyword': '예방접종 일정',
                      'question': '접종 일정은?', 'angle': '접종 대상별 일정',
                      'official_urls': ['https://www.kdca.go.kr/example'],
                      'required_title_terms': ['예방접종'], 'content_type': 'evergreen',
                      'useful_until': None, 'evergreen_reason': '지속 안내용 합성 검사',
                      'reviewed_at': '2026-09-23', 'review_until': '2026-10-31',
                      'reader_questions': [{'id': 'q1', 'question': '접종 일정은?'}]},
            'sources': [{'id': 's0', 'url': 'https://www.kdca.go.kr/example',
                         'title': '공식 안내', 'text': text,
                         'sha256': hashlib.sha256(text.encode()).hexdigest(),
                         'source_type': 'official', 'fetched_at': self.now.isoformat()}],
            'plan': {'title': '예방접종 일정',
                     'lead': {'text': text, 'evidence': [{'source_id': 's0', 'quote': text}],
                              'answers': ['q1']},
                     'sections': [{'heading': '일정', 'paragraphs': [
                         {'text': text, 'evidence': [{'source_id': 's0', 'quote': text}],
                          'answers': ['q1']}]}], 'faq': [],
                     'related_posts': [{'post_id': 63, 'label': '독감 무료접종 종합 안내',
                                        'url': 'https://lifeinfo24.org/?p=63'}]},
            'temporal_source': {},
        }
        self.inventory = {'checked_on': '2026-09-23', 'posts': [
            {'ID': 63, 'post_title': '독감 무료접종 종합 안내', 'post_status': 'publish',
             'post_content': '<p>related</p>'}]}
        body = {k: self.bundle[k] for k in ('brief', 'sources', 'plan', 'temporal_source')}
        self.bundle['review'] = {'digest': digest(body), 'policy_digest': policy_fingerprint(),
                                 'checked_at': self.now.isoformat(),
                                 'checks': {key: True for key in policy()['review_checks']},
                                 'issues': []}

    def test_valid_explicit_related_link_is_reviewed_and_rendered_not_official_cta(self):
        result = validate_bundle(self.bundle, self.inventory, now=self.now)
        self.assertEqual('ready', result['status'], result['reasons'])
        soup = BeautifulSoup(render(self.bundle['plan'], self.bundle['sources']), 'html.parser')
        self.assertEqual('https://lifeinfo24.org/?p=63', soup.select_one('.bloguito-interlink a')['href'])
        self.assertFalse(soup.select('.bloguito-cta a'))
        self.assertEqual([63], sorted(internal_post_ids(str(soup))))

    def test_missing_unpublished_self_wrong_url_or_unreviewed_link_fails_closed(self):
        for bad in ({'post_id': 64, 'label': '다른 글 링크', 'url': 'https://lifeinfo24.org/?p=64'},
                    {'post_id': 81, 'label': '자기 글 링크', 'url': 'https://lifeinfo24.org/?p=81'},
                    {'post_id': 63, 'label': '독감 종합 안내', 'url': 'https://elsewhere.org/?p=63'},
                    {'post_id': 63, 'label': '<img>', 'url': 'https://lifeinfo24.org/?p=63'}):
            with self.subTest(bad=bad):
                bundle = copy.deepcopy(self.bundle)
                bundle['plan']['related_posts'] = [bad]
                reasons = validate_bundle(bundle, self.inventory, now=self.now)['reasons']
                self.assertIn('invalid_related_post_links', reasons)
        bundle = copy.deepcopy(self.bundle)
        bundle['plan']['related_posts'][0]['label'] = '독감 예방접종 전체 일정'
        self.assertIn('review_not_bound_to_current_content',
                      validate_bundle(bundle, self.inventory, now=self.now)['reasons'])

    def test_original_related_navigation_loss_is_detected_even_with_new_official_cta(self):
        original = '<p>관련 <a href="https://lifeinfo24.org/?p=63">독감 일정</a></p>'
        proposed = '<a href="https://nip.kdca.go.kr/example">지정기관 검색</a>'
        self.assertEqual([63], missing_internal_post_ids(original, proposed))
        self.assertEqual([], missing_internal_post_ids(original,
            proposed + '<a href="https://lifeinfo24.org/?p=63">종합 일정</a>'))
        self.assertEqual([], missing_internal_post_ids(original, original))

    def test_read_only_approval_preflight_blocks_link_deletion_without_wp_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tmp').mkdir()
            bundle_file = root / 'tmp' / 'bundle.json'
            bundle_file.write_text(json.dumps(self.bundle, ensure_ascii=False), encoding='utf-8')
            old = {'ID': 81, 'post_title': '예방접종 일정', 'post_status': 'publish',
                   'post_content': '<p><a href="https://lifeinfo24.org/?p=63">종합</a></p>',
                   'post_name': 'test', 'post_date': '2026-09-01', 'post_excerpt': ''}
            proposed = '<p>어르신 일정</p>'
            with patch.object(approval, 'ROOT', root), \
                 patch.object(approval, 'live_post_and_inventory', return_value=(old, [old, *self.inventory['posts']])), \
                 patch.object(approval, 'render', return_value=proposed), \
                 patch.object(approval, 'validate_bundle', return_value={'status': 'ready', 'reasons': []}), \
                 patch.object(approval, 'fetch_sources', return_value=self.bundle['sources']):
                result = approval.prepare(81, bundle_file, root / 'tmp' / 'approval')
            self.assertEqual('blocked', result['preflight_status'])
            self.assertEqual([63], result['lost_internal_post_ids'])
            self.assertIn('original_internal_post_navigation_missing', result['reasons'])
            self.assertFalse(result['wordpress_write_performed'])


if __name__ == '__main__':
    unittest.main()
