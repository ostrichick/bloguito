import copy
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from agents.source_validation_cache import revision_source_recheck_plan, verify_sources_unchanged
from test_editorial_system import NOW, sample


class SourceValidationCacheTests(unittest.TestCase):
    def test_standard_recheck_plan_reuses_only_unchanged_fresh_nonlive_sources(self):
        old = sample()
        new = copy.deepcopy(old)
        plan = revision_source_recheck_plan(old, new, now=NOW)
        self.assertEqual([new['sources'][0]['id']], plan['reused_source_ids'])
        self.assertEqual([], plan['refresh_sources'])

        new['sources'][0]['title'] = '수정된 공식 제목'
        plan = revision_source_recheck_plan(old, new, now=NOW)
        self.assertEqual([], plan['reused_source_ids'])
        self.assertEqual([new['sources'][0]['id']], [s['id'] for s in plan['refresh_sources']])

    def test_second_identical_recheck_reuses_short_lived_receipt(self):
        bundle = sample()
        sources = bundle['sources']
        fetch = Mock(return_value=copy.deepcopy(sources))
        with tempfile.TemporaryDirectory() as folder, \
             patch('agents.source_validation_cache._fetcher_fingerprint', return_value='fetcher-v1'):
            root = Path(folder)
            first = verify_sources_unchanged(
                bundle['brief'], sources, root=root, now=NOW, fetch_subset=fetch)
            second = verify_sources_unchanged(
                bundle['brief'], sources, root=root, now=NOW, fetch_subset=fetch)
        self.assertEqual([s['id'] for s in sources], first['refetched_source_ids'])
        self.assertEqual([s['id'] for s in sources], second['reused_source_ids'])
        fetch.assert_called_once()

    def test_current_state_source_bypasses_receipt(self):
        bundle = sample()
        sources = copy.deepcopy(bundle['sources'])
        sources[0]['text'] += '\n예매상태: 예매중'
        import hashlib
        sources[0]['sha256'] = hashlib.sha256(sources[0]['text'].encode()).hexdigest()
        by_id = {source['id']: source for source in sources}
        fetch = Mock(side_effect=lambda brief, existing, ids: [copy.deepcopy(by_id[source_id]) for source_id in ids])
        with tempfile.TemporaryDirectory() as folder, \
             patch('agents.source_validation_cache._fetcher_fingerprint', return_value='fetcher-v1'):
            root = Path(folder)
            verify_sources_unchanged(bundle['brief'], sources, root=root, now=NOW, fetch_subset=fetch)
            verify_sources_unchanged(bundle['brief'], sources, root=root, now=NOW, fetch_subset=fetch)
        self.assertEqual(2, fetch.call_count)

    def test_changed_source_sha_fails_closed(self):
        bundle = sample()
        sources = bundle['sources']
        changed = copy.deepcopy(sources)
        changed[0]['sha256'] = '0' * 64
        fetch = Mock(return_value=changed)
        with tempfile.TemporaryDirectory() as folder, \
             patch('agents.source_validation_cache._fetcher_fingerprint', return_value='fetcher-v1'):
            with self.assertRaisesRegex(ValueError, 'official_sources_changed_since_review'):
                verify_sources_unchanged(
                    bundle['brief'], sources, root=Path(folder), now=NOW, fetch_subset=fetch)

    def test_future_dated_receipt_is_not_reused(self):
        bundle = sample()
        sources = bundle['sources']
        fetch = Mock(return_value=copy.deepcopy(sources))
        with tempfile.TemporaryDirectory() as folder, \
             patch('agents.source_validation_cache._fetcher_fingerprint', return_value='fetcher-v1'):
            root = Path(folder)
            verify_sources_unchanged(
                bundle['brief'], sources, root=root, now=NOW + timedelta(minutes=5), fetch_subset=fetch)
            verify_sources_unchanged(
                bundle['brief'], sources, root=root, now=NOW, fetch_subset=fetch)
        self.assertEqual(2, fetch.call_count)


if __name__ == '__main__':
    unittest.main()
