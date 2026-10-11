import copy
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from agents.editorial import assert_review_digest_bound, digest
from agents.review_cache import review_cache_key
from agents.validation_reuse import assess_validation_reuse
from agents.source_extractors import OFFICIAL_SCOPE_EXTRACTOR_VERSION

from agents.source_validation_cache import (
    revision_source_recheck_plan,
    verify_explicit_live_sources,
    verify_sources_unchanged,
)
from test_editorial_system import NOW, sample


class SourceValidationCacheTests(unittest.TestCase):
    def scoped_bundle(self):
        bundle = sample()
        url = 'https://www.law.go.kr/법령/테스트법'
        selector = {'kind': 'law-section', 'start_marker': '제2조(정의)',
                    'end_marker': '제3조(적용범위)', 'version_marker': '2026.10.01'}
        bundle['brief']['official_urls'] = [url]
        bundle['brief']['official_source_scopes'] = {url: selector}
        s = bundle['sources'][0]
        s.update(url=url, source_type='official', raw_sha256='a' * 64,
                 raw_url=url, raw_source_version='2026.10.01',
                 section_selector=copy.deepcopy(selector),
                 section_extractor_version=OFFICIAL_SCOPE_EXTRACTOR_VERSION)
        return bundle

    def test_raw_outside_excerpt_change_blocks_recheck_and_review_reuse(self):
        original = self.scoped_bundle()
        changed = copy.deepcopy(original)
        changed['sources'][0]['raw_sha256'] = 'b' * 64
        self.assertEqual(original['sources'][0]['sha256'], changed['sources'][0]['sha256'])
        self.assertFalse(assess_validation_reuse(original, changed)['reuse_full_semantic_review'])
        self.assertNotEqual(review_cache_key(original), review_cache_key(changed))
        plan = revision_source_recheck_plan(original, changed, now=NOW)
        self.assertEqual(['s0'], [item['id'] for item in plan['refresh_sources']])
        with tempfile.TemporaryDirectory() as folder, \
             patch('agents.source_validation_cache._fetcher_fingerprint', return_value='fetcher-v1'):
            root = Path(folder)
            fetched = Mock(return_value=copy.deepcopy(original['sources']))
            verify_sources_unchanged(original['brief'], original['sources'],
                                     root=root, now=NOW, fetch_subset=fetched)
            # The old successful receipt must not validate an identical excerpt
            # from a changed complete source. Network verifies and rejects.
            with self.assertRaisesRegex(ValueError, 'official_sources_changed_since_review'):
                verify_sources_unchanged(changed['brief'], changed['sources'],
                                         root=root, now=NOW, fetch_subset=fetched)
            self.assertEqual(2, fetched.call_count)

    def test_same_scoped_excerpt_still_refetches_raw_original_on_each_check(self):
        bundle = self.scoped_bundle()
        sources = bundle['sources']
        fetch = Mock(return_value=copy.deepcopy(sources))
        with tempfile.TemporaryDirectory() as folder, \
             patch('agents.source_validation_cache._fetcher_fingerprint', return_value='fetcher-v1'):
            root = Path(folder)
            first = verify_sources_unchanged(bundle['brief'], sources, root=root,
                                             now=NOW, fetch_subset=fetch)
            second = verify_sources_unchanged(bundle['brief'], sources, root=root,
                                              now=NOW, fetch_subset=fetch)
        self.assertEqual(['s0'], first['refetched_source_ids'])
        self.assertEqual(['s0'], second['refetched_source_ids'])
        self.assertEqual(2, fetch.call_count)

    def test_page_selection_or_extractor_version_change_invalidates_receipt(self):
        bundle = self.scoped_bundle()
        source = bundle['sources'][0]
        with tempfile.TemporaryDirectory() as folder, \
             patch('agents.source_validation_cache._fetcher_fingerprint', return_value='fetcher-v1'):
            root = Path(folder)
            fetch = Mock(return_value=copy.deepcopy(bundle['sources']))
            verify_sources_unchanged(bundle['brief'], bundle['sources'],
                                     root=root, now=NOW, fetch_subset=fetch)
            changed = copy.deepcopy(bundle)
            changed['brief']['official_source_scopes'][source['url']]['start_marker'] = '제4조(다른정의)'
            changed['sources'][0]['section_selector']['start_marker'] = '제4조(다른정의)'
            with self.assertRaisesRegex(ValueError, 'official_sources_changed_since_review'):
                verify_sources_unchanged(changed['brief'], changed['sources'],
                                         root=root, now=NOW, fetch_subset=fetch)
            self.assertNotEqual(review_cache_key(bundle), review_cache_key(changed))
            invalid = copy.deepcopy(bundle)
            invalid['sources'][0]['section_extractor_version'] += 1
            with self.assertRaisesRegex(ValueError, 'official_scoped_source_provenance_missing_or_changed'):
                verify_sources_unchanged(invalid['brief'], invalid['sources'],
                                         root=root, now=NOW, fetch_subset=fetch)

    def test_review_digest_bindings_include_raw_sha_and_selected_scope(self):
        bundle = self.scoped_bundle()
        bundle['review'] = {
            'digest': digest({key: bundle[key] for key in
                              ('brief', 'sources', 'plan', 'temporal_source') if key in bundle}),
            'checks': {'source_support': True}, 'issues': [],
        }
        self.assertEqual(bundle['review']['digest'], assert_review_digest_bound(bundle))
        altered = copy.deepcopy(bundle)
        altered['sources'][0]['raw_sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'review'):
            assert_review_digest_bound(altered)

    def test_scoped_semantic_review_contract_tracks_extractor_code(self):
        from agents.review_cache import reviewer_contract_digest
        bundle = self.scoped_bundle()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'agents').mkdir()
            for name in ('editorial_writer.py', 'editorial_schema.py',
                         'source_collector.py', 'source_extractors.py'):
                (root / 'agents' / name).write_bytes(b'initial')
            with patch('agents.review_cache.ROOT', root):
                original = reviewer_contract_digest(bundle)
                (root / 'agents/source_extractors.py').write_bytes(b'updated extractor code')
                self.assertNotEqual(original, reviewer_contract_digest(bundle))
        # A distinct version in the scoped source always changes its review key
        # even if its quoted article text itself remains byte-for-byte equal.
        revision = copy.deepcopy(bundle)
        revision['sources'][0]['section_extractor_version'] += 1
        self.assertNotEqual(review_cache_key(bundle), review_cache_key(revision))
        altered = copy.deepcopy(bundle)
        altered['sources'][0]['section_selector']['end_marker'] = '제4조(적용범위)'
        with self.assertRaisesRegex(ValueError, 'review'):
            assert_review_digest_bound(altered)
    def test_source_adapter_change_invalidates_receipt_fingerprint(self):
        from agents.source_validation_cache import _fetcher_fingerprint
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'agents').mkdir()
            for name in ('source_collector.py', 'source_extractors.py', 'fact_validation.py', 'temporal_validation.py'):
                (root / 'agents' / name).write_bytes(b'original')
            before = _fetcher_fingerprint(root)
            (root / 'agents/source_extractors.py').write_bytes(b'changed adapter')
            self.assertNotEqual(before, _fetcher_fingerprint(root))

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

    def test_explicit_post_live_state_forces_refresh_even_without_text_marker(self):
        bundle = sample()
        bundle['brief']['requires_live_state'] = True
        old = copy.deepcopy(bundle)
        new = copy.deepcopy(bundle)
        plan = revision_source_recheck_plan(old, new, now=NOW)
        self.assertEqual([], plan['reused_source_ids'])
        self.assertEqual([new['sources'][0]['id']], [s['id'] for s in plan['refresh_sources']])

        sources = bundle['sources']
        by_id = {source['id']: source for source in sources}
        fetch = Mock(side_effect=lambda brief, existing, ids: [copy.deepcopy(by_id[source_id]) for source_id in ids])
        with tempfile.TemporaryDirectory() as folder, \
             patch('agents.source_validation_cache._fetcher_fingerprint', return_value='fetcher-v1'):
            root = Path(folder)
            verify_sources_unchanged(bundle['brief'], sources, root=root, now=NOW, fetch_subset=fetch)
            verify_sources_unchanged(bundle['brief'], sources, root=root, now=NOW, fetch_subset=fetch)
        self.assertEqual(2, fetch.call_count)

    def test_new_draft_explicit_live_recheck_is_forced(self):
        bundle = sample()
        bundle['brief']['requires_live_state'] = True
        by_id = {source['id']: source for source in bundle['sources']}
        fetch = Mock(side_effect=lambda brief, existing, ids: [copy.deepcopy(by_id[source_id]) for source_id in ids])
        with tempfile.TemporaryDirectory() as folder, \
             patch('agents.source_validation_cache._fetcher_fingerprint', return_value='fetcher-v1'):
            root = Path(folder)
            first = verify_explicit_live_sources(
                bundle, root=root, now=NOW, fetch_subset=fetch)
            second = verify_explicit_live_sources(
                bundle, root=root, now=NOW, fetch_subset=fetch)
        self.assertEqual([bundle['sources'][0]['id']], first['refetched_source_ids'])
        self.assertEqual([bundle['sources'][0]['id']], second['refetched_source_ids'])
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
