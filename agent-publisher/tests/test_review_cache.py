import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.editorial_writer import EditorialWriterAgent, Review
from agents.review_cache import load_cached_review, store_cached_review
from test_editorial_system import NOW, sample


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


if __name__ == '__main__':
    unittest.main()
