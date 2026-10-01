import copy
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from agents.editorial import digest, policy_fingerprint
from agents.editorial_writer import EditorialWriterAgent, Review
from agents.review_cache import load_cached_review, store_cached_review
from agents.temporal_validation import KST
from test_editorial_system import NOW, sample
from test_event_post_standard import event_bundle


class ReviewCacheTests(unittest.TestCase):
    def test_exact_review_body_reuses_cached_review(self):
        bundle = sample()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store_cached_review(bundle, bundle['review'], root=root)
            cached = load_cached_review(bundle, root=root, now=NOW)
        self.assertEqual(bundle['review'], cached)

    def test_changed_content_does_not_reuse_cached_review(self):
        bundle = sample()
        changed = copy.deepcopy(bundle)
        changed['plan']['sections'][0]['heading'] = '다른 소제목'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store_cached_review(bundle, bundle['review'], root=root)
            cached = load_cached_review(changed, root=root, now=NOW)
        self.assertIsNone(cached)

    def test_malformed_cache_root_is_a_miss_not_an_exception(self):
        bundle = sample()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            from agents.review_cache import review_cache_path
            target = review_cache_path(bundle, root=root)
            target.parent.mkdir(parents=True)
            target.write_text('[]', encoding='utf-8')
            cached = load_cached_review(bundle, root=root, now=NOW)
        self.assertIsNone(cached)

    def test_writer_skips_model_when_exact_cached_review_is_available(self):
        bundle = sample()
        agent = EditorialWriterAgent(client=Mock(), writing_enabled=False, review_cache_enabled=True)
        with patch('agents.editorial_writer.load_cached_review', return_value=bundle['review']), \
             patch.object(agent, '_call') as call:
            result = agent.review(bundle)
        self.assertEqual(bundle['review'], result)
        call.assert_not_called()

    def test_retryable_provider_error_falls_back_to_next_model(self):
        class ServiceUnavailable(Exception):
            code = 503

        client = Mock()
        client.models.generate_content.side_effect = [
            ServiceUnavailable('503 unavailable'),
            Mock(parsed=Review.model_validate({
                'checks': {
                    'source_support': True,
                    'conditions_preserved': True,
                    'question_answered': True,
                    'useful_lifetime': True,
                    'no_reader_deflection': True,
                    'no_unsupported_claims': True,
                },
                'issues': [],
            })),
        ]
        agent = EditorialWriterAgent(client=client, writing_enabled=False, review_cache_enabled=False)
        with patch('agents.quota_tracker.get_model_cascade', return_value=['primary', 'fallback']), \
             patch('agents.quota_tracker.record_usage'):
            result = agent._call('review', {}, Review, 'reviewer')
        self.assertEqual([], result['issues'])
        self.assertEqual(2, client.models.generate_content.call_count)
        self.assertEqual('primary', client.models.generate_content.call_args_list[0].kwargs['model'])
        self.assertEqual('fallback', client.models.generate_content.call_args_list[1].kwargs['model'])

    def test_event_delta_review_composes_scoped_review_onto_current_base(self):
        old = event_bundle()
        old_body = {key: old[key] for key in ('brief', 'sources', 'plan', 'temporal_source')}
        old['review'] = {
            'checks': {
                'source_support': True,
                'conditions_preserved': True,
                'question_answered': True,
                'useful_lifetime': True,
                'no_reader_deflection': True,
                'no_unsupported_claims': True,
            },
            'issues': [],
            'digest': digest(old_body),
            'policy_digest': policy_fingerprint(old),
            'checked_at': datetime.now(KST).isoformat(),
        }
        new = copy.deepcopy(old)
        new['plan']['sections'][1]['paragraphs'][0]['text'] += ' 현장 체험 정보를 보강했습니다.'
        agent = EditorialWriterAgent(client=Mock(), writing_enabled=False, review_cache_enabled=False)
        scoped = {
            'checks': {
                'source_support': True,
                'conditions_preserved': True,
                'question_answered': True,
                'no_unsupported_claims': True,
                'event_scope_preserved': True,
            },
            'issues': [],
        }
        with patch.object(agent, '_call', return_value=scoped) as call:
            result = agent.review_event_delta(old, new, ['가을 체험축제'])
        new_body = {key: new[key] for key in ('brief', 'sources', 'plan', 'temporal_source')}
        self.assertEqual('event_delta_composite', result['mode'])
        self.assertEqual(digest(new_body), result['digest'])
        self.assertEqual(policy_fingerprint(new), result['policy_digest'])
        self.assertEqual(['가을 체험축제'], result['affected_event_names'])
        self.assertEqual(1, result['event_delta_chain_length'])
        self.assertEqual(scoped['checks'], result['event_delta_checks'])
        payload = call.call_args.args[1]
        self.assertEqual(['가을 체험축제'], payload['affected_event_names'])
        self.assertEqual(['s0'], [source['id'] for source in payload['sources']])

    def test_event_delta_falls_back_to_full_when_base_policy_is_stale(self):
        old = event_bundle()
        old_body = {key: old[key] for key in ('brief', 'sources', 'plan', 'temporal_source')}
        old['review'] = {
            'checks': {key: True for key in (
                'source_support', 'conditions_preserved', 'question_answered',
                'useful_lifetime', 'no_reader_deflection', 'no_unsupported_claims')},
            'issues': [],
            'digest': digest(old_body),
            'policy_digest': '0' * 64,
            'checked_at': NOW.isoformat(),
        }
        new = copy.deepcopy(old)
        new['plan']['sections'][1]['paragraphs'][0]['text'] += ' 변경된 행사 안내입니다.'
        agent = EditorialWriterAgent(client=Mock(), writing_enabled=False, review_cache_enabled=False)
        full_review = {
            'checks': old['review']['checks'], 'issues': [],
            'digest': 'f' * 64, 'policy_digest': policy_fingerprint(new),
            'checked_at': NOW.isoformat(),
        }
        with patch.object(agent, 'review', return_value=full_review) as full:
            result, mode = agent.review_event_delta_or_full(old, new, ['가을 체험축제'])
        self.assertEqual(full_review, result)
        self.assertEqual('full-fallback:event_delta_base_review_not_current', mode)
        full.assert_called_once_with(new)


if __name__ == '__main__':
    unittest.main()
