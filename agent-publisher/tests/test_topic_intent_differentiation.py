"""T1: separate human-approved question intent from shared official citations.

The #928/#139/#926 regression is a labelled collision scenario, not a
claim that these synthetic fixtures reproduce the live WordPress HTML.
"""

import copy
from datetime import date, datetime
import hashlib
import unittest
from unittest.mock import patch

from agents.search_intent import (
    classify_topic_conflicts, duplicate_posts, intent_brief_digest,
)
from agents.editorial import validate_bundle
from agents.temporal_validation import KST


TODAY = date(2026, 10, 11)
URL = 'https://official.example.go.kr/welfare/medical-expenses'


def post(post_id, title, *, include_cta=False, legacy=False):
    footer = ('<h2 id="sources">공식 출처 및 사실 검증 자료</h2>'
              '<ul class="source-list"><li><a href="' + URL
              + '">공식 자료</a></li></ul>')
    content = ('<p>독립적인 안내에 필요한 질문과 답변.</p>' +
               ('<a class="apply-button" href="' + URL + '">신청하기</a>'
                if include_cta else '') +
               (('<p><a href="' + URL + '">원문</a></p>') if legacy else footer))
    return {'ID': post_id, 'post_title': title, 'post_status': 'publish',
            'post_content': content, 'content_urls': [URL],
            'content_sha256': hashlib.sha256(content.encode()).hexdigest()}


class T1IntentReceiptTests(unittest.TestCase):
    def setUp(self):
        self.brief = {
            'id': 'post-928-medical-support',
            'question': '2026 재난적의료비 지원 신청 방법은 무엇인가요?',
            'primary_keyword': '2026 재난적의료비 지원 신청 방법',
            'required_title_terms': ['재난적의료비', '신청'],
            'official_urls': [URL],
            'review_until': '2026-10-31',
        }
        self.existing = [
            post(139, '2026 건강보험 본인부담상한제 환급 조건'),
            post(926, '2026 의료급여와 건강보험 지원 범위 비교'),
        ]
        self.receipt = {
            'schema_version': 1,
            'brief_sha256': intent_brief_digest(self.brief),
            'reviewer': 'user',
            'approved': True,
            'reviewed_on': '2026-10-11',
            'valid_until': '2026-10-12',
            'comparisons': [
                {'post_id': row['ID'], 'post_content_sha256': row['content_sha256'],
                 'post_title': row['post_title'],
                 'post_status': row['post_status'],
                 'new_reader_question': self.brief['question'],
                 'existing_reader_question': '건강보험 제도 관련 해당 보장과 환급 범위는?',
                 'existing_answer_scope': '기존 제도 관련 보장 대상과 환급을 설명하는 본문 범위',
                 'differentiation_reason': '신규 글은 별도의 재난적의료비 지원 제도 신청 질문을 다루며 동일 신청 행동을 반복하지 않습니다.',
                 'decision': 'distinct_reader_question',
                 'shared_action_or_answer': False}
                for row in self.existing
            ],
        }

    def dup(self, *, brief=None, posts=None, receipt=None, when=TODAY):
        return duplicate_posts(
            brief if brief is not None else self.brief,
            posts if posts is not None else self.existing,
            intent_receipt=receipt, today=when)

    def test_928_vs_139_and_926_distinct_only_when_explicitly_reviewed(self):
        self.assertEqual(self.existing, self.dup())
        self.assertEqual([], self.dup(receipt=self.receipt))
        report = classify_topic_conflicts(
            self.brief, self.existing, intent_receipt=self.receipt, today=TODAY)
        self.assertEqual([139, 926], [row['post_id'] for row in report])
        self.assertTrue(all(row['reason'] == 'reviewed_distinct_source_citation'
                            and row['blocking'] is False for row in report))

    def test_site_validator_only_exempts_cited_question_no_review_shortcut(self):
        now = datetime(2026, 10, 11, 15, tzinfo=KST)
        bundle = {'brief': self.brief, 'sources': [],
                  'plan': {'related_posts': []}, 'review': {}}
        inventory = {'checked_on': TODAY.isoformat(), 'posts': self.existing}
        original = validate_bundle(bundle, inventory, now=now, scopes={'site'})
        reviewed = validate_bundle(bundle, inventory, now=now, scopes={'site'},
                                   intent_receipt=self.receipt)
        self.assertIn('duplicate_topic', original['reasons'])
        self.assertNotIn('duplicate_topic', reviewed['reasons'])
        # Passing the same receipt must not cure stale/invalid independent review.
        other = validate_bundle(bundle, inventory, now=now,
                                scopes={'site', 'review'},
                                intent_receipt=self.receipt)
        self.assertIn('review_not_bound_to_current_content', other['reasons'])
        self.assertNotEqual('ready', other['status'])
        stale = validate_bundle(bundle, {'checked_on': '2026-10-10',
                                         'posts': self.existing}, now=now,
                                scopes={'site'}, intent_receipt=self.receipt)
        self.assertIn('fresh_inventory_required', stale['reasons'])

    def test_mid_article_forged_footer_is_not_an_exception(self):
        row = copy.deepcopy(self.existing[0])
        row['post_content'] = row['post_content'] + '<p>More substantive prose afterwards</p>'
        row['content_sha256'] = hashlib.sha256(row['post_content'].encode()).hexdigest()
        receipt = copy.deepcopy(self.receipt)
        receipt['comparisons'][0]['post_content_sha256'] = row['content_sha256']
        self.assertEqual([row], self.dup(posts=[row], receipt=receipt))
        reason = classify_topic_conflicts(
            self.brief, [row], intent_receipt=receipt, today=TODAY)[0]['reason']
        self.assertEqual('shared_body_or_action_url', reason)

    @patch('agents.publisher.datetime')
    def test_publisher_rechecks_every_compared_post_before_wordpress_write(self, publisher_clock):
        from agents.publisher import PublisherAgent
        # Keep this deliberately short-lived 2026-10-11 receipt within its
        # historical test clock. Production must reject it after 2026-10-12.
        publisher_clock.now.return_value = datetime(2026, 10, 11, 15, tzinfo=KST)
        # Simulate the one authoritative site inventory and delayed hydration
        # without ever opening SSH or creating a WordPress post.
        lightweight = [{k: v for k, v in row.items() if k != 'post_content'}
                       for row in self.existing]
        inventory = {'checked_on': TODAY.isoformat(), 'posts': lightweight}
        bundle = {'brief': self.brief, 'sources': [],
                  'plan': {'title': '2026 재난적의료비 지원 신청 방법',
                           'lead': {'text': 'intro'}}}
        article = {'editorial_bundle': bundle, 'tags': [],
                   'title': bundle['plan']['title'], 'content': '<p>approved</p>',
                   'topic_intent_receipt': self.receipt}

        def hydrate(current, post_id):
            updated = copy.deepcopy(current)
            for row in updated['posts']:
                if row['ID'] == post_id:
                    row['post_content'] = next(
                        item['post_content'] for item in self.existing
                        if item['ID'] == post_id)
            return updated

        with patch('agents.editorial.render', return_value='<p>approved</p>'), \
             patch('agents.editorial.excerpt_from_lead', return_value='intro'), \
             patch('agents.draft_create_journal.DraftCreateJournal') as journal, \
             patch('sync_wordpress_inventory.sync_inventory'), \
             patch('agents.editorial_writer.load_inventory', return_value=inventory), \
             patch('sync_wordpress_inventory.hydrate_post', side_effect=hydrate) as hydration, \
             patch('agents.editorial.validate_bundle',
                   side_effect=RuntimeError('intercept_after_receipt_validation')) as validator, \
             patch('agents.publisher.run_wordpress') as remote:
            journal.return_value.read.return_value = None
            with self.assertRaisesRegex(RuntimeError, 'intercept_after_receipt_validation'):
                PublisherAgent()._publish_editorial(article)
        self.assertEqual(2, hydration.call_count)
        self.assertIs(validator.call_args.kwargs['intent_receipt'], self.receipt)
        self.assertTrue(all('post_content' in row
                            for row in validator.call_args.args[1]['posts']))
        remote.assert_not_called()

        invalid = copy.deepcopy(article)
        invalid['topic_intent_receipt'] = copy.deepcopy(self.receipt)
        invalid['topic_intent_receipt']['comparisons'][0]['post_content_sha256'] = 'b' * 64
        with patch('agents.editorial.render', return_value='<p>approved</p>'), \
             patch('agents.editorial.excerpt_from_lead', return_value='intro'), \
             patch('agents.draft_create_journal.DraftCreateJournal') as journal, \
             patch('sync_wordpress_inventory.sync_inventory'), \
             patch('agents.editorial_writer.load_inventory', return_value=inventory), \
             patch('sync_wordpress_inventory.hydrate_post', side_effect=hydrate), \
             patch('agents.publisher.run_wordpress') as remote:
            journal.return_value.read.return_value = None
            with self.assertRaisesRegex(ValueError, 'topic_intent_receipt_stale_or_post_changed'):
                PublisherAgent()._publish_editorial(invalid)
        remote.assert_not_called()

    def test_unapproved_scheduler_remains_blocked_and_diagnoses(self):
        report = classify_topic_conflicts(self.brief, self.existing, today=TODAY)
        self.assertTrue(all(row['reason'] == 'shared_source_citation_needs_review'
                            and row['blocking'] for row in report))
        self.assertEqual(self.existing, self.dup(receipt=None))
        # A manually supplied receipt must not appear in the reviewed brief.
        self.assertNotIn('topic_intent_receipt', self.brief)

    def test_same_search_query_or_action_always_duplicate(self):
        equal_title = post(139, '2026 재난적의료비 지원 신청 방법')
        self.assertEqual([equal_title], self.dup(
            posts=[equal_title], receipt=self.receipt))
        cta = post(139, self.existing[0]['post_title'], include_cta=True)
        stale = copy.deepcopy(self.receipt)
        stale['comparisons'][0]['post_content_sha256'] = cta['content_sha256']
        self.assertEqual([cta], self.dup(posts=[cta], receipt=stale))
        legacy = post(139, self.existing[0]['post_title'], legacy=True)
        self.assertEqual([legacy], self.dup(posts=[legacy], receipt=stale))

    def test_missing_compared_post_authorization_does_not_exempt_other_post(self):
        partial = copy.deepcopy(self.receipt)
        partial['comparisons'] = partial['comparisons'][:1]
        self.assertEqual([self.existing[1]], self.dup(receipt=partial))
        unhydrated = [{key: value for key, value in row.items()
                       if key not in ('post_content', 'content_sha256')}
                      for row in self.existing]
        self.assertEqual(unhydrated, self.dup(receipt=self.receipt, posts=unhydrated))

    def test_receipt_invalidated_by_title_body_and_live_sha_drift(self):
        changed = {**self.existing[0], 'post_title': '수정된 제목'}
        self.assertEqual([changed], self.dup(posts=[changed], receipt=self.receipt))
        changed_status = {**self.existing[0], 'post_status': 'draft'}
        self.assertEqual([changed_status], self.dup(posts=[changed_status], receipt=self.receipt))
        tampered = {**self.existing[0], 'post_content': '<p>새 내용</p>'}
        self.assertEqual([tampered], self.dup(posts=[tampered], receipt=self.receipt))
        corrupted_sha = {**self.existing[0], 'content_sha256': 'z' * 64}
        self.assertEqual([corrupted_sha], self.dup(posts=[corrupted_sha], receipt=self.receipt))

    def test_receipt_invalidated_by_brief_changes_and_expiry(self):
        modified = dict(self.brief, question='신청 대상은 누구인가요?')
        self.assertEqual(self.existing, self.dup(
            brief=modified, receipt=self.receipt))
        self.assertEqual(self.existing, self.dup(
            receipt=self.receipt, when=date(2026, 10, 13)))
        self.assertEqual(self.existing, self.dup(
            receipt=self.receipt, when=date(2026, 10, 10)))
        changed = dict(self.brief, official_urls=[URL, 'https://official.example.go.kr/new'])
        self.assertEqual(self.existing, self.dup(brief=changed, receipt=self.receipt))

    def test_only_real_human_approval_and_distinct_answer_scopes_allowed(self):
        for path, value in (
                (('reviewer',), 'automatic'),
                (('approved',), False),
                (('comparisons', 0, 'decision'), 'duplicate'),
                (('comparisons', 0, 'shared_action_or_answer'), True),
                (('comparisons', 0, 'existing_reader_question'), self.brief['question']),
                (('comparisons', 0, 'differentiation_reason'), 'different'),
        ):
            with self.subTest(path=path):
                record = copy.deepcopy(self.receipt)
                obj = record
                for part in path[:-1]:
                    obj = obj[part]
                obj[path[-1]] = value
                self.assertIn(self.existing[0], self.dup(receipt=record))

    def test_legacy_or_unhydrated_status_and_other_posts_fail_closed(self):
        unhydrated = {key: value for key, value in self.existing[0].items()
                      if key != 'post_content'}
        self.assertEqual([unhydrated], self.dup(
            posts=[unhydrated], receipt=self.receipt))
        new_post = post(550, '건강보험 신청과 지원 대상 안내')
        self.assertEqual([new_post], self.dup(
            posts=[new_post], receipt=self.receipt))
        trash = dict(self.existing[0], post_status='trash')
        self.assertEqual([], self.dup(posts=[trash], receipt=self.receipt))


if __name__ == '__main__':
    unittest.main()
