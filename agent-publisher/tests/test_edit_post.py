import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from agents.edit_post import (
    _stale_draft_public_recovery_decision,
    _verified_public_edit_receipt,
    _validated_prepared_decision,
    classify_reviewed_post_route,
    edit_reviewed_post,
    reviewed_target_kind,
)
from agents.editorial import digest, render
from agents.temporal_validation import KST
from test_editorial_system import sample


def current_bundle():
    bundle = sample()
    now = datetime.now(KST)
    bundle['brief']['reviewed_at'] = now.date().isoformat()
    bundle['brief']['review_until'] = (now.date() + timedelta(days=7)).isoformat()
    for source in bundle['sources']:
        source['fetched_at'] = now.isoformat()
    body = {key: bundle[key] for key in ('brief', 'sources', 'plan', 'temporal_source')}
    bundle['review']['digest'] = digest(body)
    bundle['review']['checked_at'] = now.isoformat()
    return bundle


class UnifiedEditPostTests(unittest.TestCase):
    def test_public_edit_receipt_is_bound_to_exact_live_reviewed_readback(self):
        bundle = current_bundle()
        html = render(bundle['plan'], bundle['sources'])
        live = {
            'post_status': 'publish', 'post_title': bundle['plan']['title'],
            'post_name': 'stable-slug', 'post_content': html, 'post_excerpt': '',
        }
        with patch('agents.edit_post.get_post', return_value=live), \
             patch('agents.edit_post.load_tracked_public_bundle', return_value=bundle):
            receipt = _verified_public_edit_receipt(243, 'a' * 64)
        self.assertEqual('a' * 64, receipt['before_content_sha256'])
        self.assertEqual(hashlib.sha256(html.encode()).hexdigest(), receipt['after_content_sha256'])
        self.assertEqual(bundle['review']['digest'], receipt['review_digest'])
        self.assertTrue(receipt['readback_verified'])

    def test_legacy_public_without_manifest_is_full_standard_only_when_id_bound(self):
        bundle = current_bundle()
        bundle['brief']['existing_post_id'] = 345
        with tempfile.TemporaryDirectory() as folder:
            draft = Path(folder) / 'draft_posts.json'
            public = Path(folder) / 'published_posts.json'
            draft.write_text('[]', encoding='utf-8')
            public.write_text('[]', encoding='utf-8')
            with patch('agents.edit_post.DRAFTS_INDEX_FILE', draft), \
                 patch('agents.edit_post.POSTS_INDEX_FILE', public):
                decision = classify_reviewed_post_route(
                    345, bundle, expected_content_sha256='a' * 64)
                with self.assertRaisesRegex(ValueError, 'reviewed_post_manifest_required'):
                    classify_reviewed_post_route(
                        346, bundle, expected_content_sha256='a' * 64)
        self.assertEqual('standard', decision['route'])
        self.assertEqual('publish', decision['target_status'])
        self.assertTrue(decision['legacy_public_adoption'])
        self.assertIn('legacy_public_without_reviewed_manifest', decision['reasons'])
        self.assertEqual('full', decision['validation_plan']['source_validation'])
        self.assertEqual('full', decision['validation_plan']['semantic_review'])
        self.assertIn('public-page', decision['qa_requirements'])

    def test_public_wording_edit_routes_fast_only_when_manifest_matches_expected_sha(self):
        old = current_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '간단한 안내'
        expected = hashlib.sha256(render(old['plan'], old['sources']).encode()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            draft = Path(folder) / 'draft_posts.json'
            public = Path(folder) / 'published_posts.json'
            draft.write_text('[]', encoding='utf-8')
            public.write_text(json.dumps([{
                'id': 243, 'fact_manifest': {'editorial_bundle': old},
            }], ensure_ascii=False), encoding='utf-8')
            with patch('agents.edit_post.DRAFTS_INDEX_FILE', draft), \
                 patch('agents.edit_post.POSTS_INDEX_FILE', public), \
                 patch('agents.public_fast_edit.POSTS_INDEX_FILE', public):
                fast = classify_reviewed_post_route(
                    243, new, expected_content_sha256=expected)
                stale = classify_reviewed_post_route(
                    243, new, expected_content_sha256='0' * 64)
        self.assertEqual('publish', fast['target_status'])
        self.assertEqual('fast', fast['route'])
        self.assertEqual('standard', stale['route'])
        self.assertIn('public_manifest_not_bound_to_expected_content', stale['reasons'])

    def test_duplicate_reviewed_target_across_indexes_fails_closed(self):
        bundle = current_bundle()
        row = json.dumps([{'id': 243, 'fact_manifest': {'editorial_bundle': bundle}}], ensure_ascii=False)
        with tempfile.TemporaryDirectory() as folder:
            draft = Path(folder) / 'draft_posts.json'
            public = Path(folder) / 'published_posts.json'
            draft.write_text(row, encoding='utf-8')
            public.write_text(row, encoding='utf-8')
            with patch('agents.edit_post.DRAFTS_INDEX_FILE', draft), \
                 patch('agents.edit_post.POSTS_INDEX_FILE', public):
                with self.assertRaisesRegex(ValueError, 'both_indexes'):
                    reviewed_target_kind(243)

    def test_prepared_decision_is_bound_to_target_and_content(self):
        bundle = current_bundle()
        body_sha = hashlib.sha256(render(bundle['plan'], bundle['sources']).encode()).hexdigest()
        decision = {
            'validation_plan': {
                'binding': {
                    'post_id': 243,
                    'target_status': 'publish',
                    'before_content_sha256': body_sha,
                    'after_content_sha256': body_sha,
                },
                'scope': {'image_changed': False, 'resume': False},
            },
        }
        self.assertIs(decision, _validated_prepared_decision(
            decision,
            post_id=243,
            bundle=bundle,
            expected_content_sha256=body_sha,
            image_path=None,
            resume=False,
            target_status='publish',
        ))
        with self.assertRaisesRegex(ValueError, 'binding_mismatch'):
            _validated_prepared_decision(
                decision,
                post_id=244,
                bundle=bundle,
                expected_content_sha256=body_sha,
                image_path=None,
                resume=False,
                target_status='publish',
            )

    def test_stale_draft_index_with_exact_live_publish_routes_full_public_standard(self):
        old = current_bundle()
        old['brief']['existing_post_id'] = 243
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '공식 자료로 다시 검토한 내용'
        live_content = 'manual public content that bypassed the reviewed draft index'
        expected = hashlib.sha256(live_content.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            draft = data / 'draft_posts.json'
            public = data / 'published_posts.json'
            draft.write_text(json.dumps([{
                'id': 243, 'status': 'draft',
                'fact_manifest': {'editorial_bundle': old},
            }], ensure_ascii=False), encoding='utf-8')
            public.write_text('[]', encoding='utf-8')
            live = {
                'post_status': 'publish',
                'post_title': old['plan']['title'],
                'post_content': live_content,
            }
            with patch('agents.edit_post.DRAFTS_INDEX_FILE', draft), \
                 patch('agents.edit_post.POSTS_INDEX_FILE', public), \
                 patch('agents.edit_post.get_post', return_value=live):
                decision = _stale_draft_public_recovery_decision(
                    243, new, expected, image_path=None, resume=False)
        self.assertEqual('standard', decision['route'])
        self.assertEqual('publish', decision['target_status'])
        self.assertTrue(decision['legacy_public_adoption'])
        self.assertTrue(decision['stale_draft_public_recovery'])
        self.assertIn('full_review_required', decision['reasons'])
        self.assertEqual('full', decision['validation_plan']['semantic_review'])

    def test_stale_draft_public_recovery_refuses_live_sha_mismatch(self):
        old = current_bundle()
        old['brief']['existing_post_id'] = 243
        new = copy.deepcopy(old)
        expected = hashlib.sha256(b'expected').hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            draft = data / 'draft_posts.json'
            public = data / 'published_posts.json'
            draft.write_text(json.dumps([{
                'id': 243, 'status': 'draft',
                'fact_manifest': {'editorial_bundle': old},
            }], ensure_ascii=False), encoding='utf-8')
            public.write_text('[]', encoding='utf-8')
            live = {
                'post_status': 'publish',
                'post_title': old['plan']['title'],
                'post_content': 'different live content',
            }
            with patch('agents.edit_post.DRAFTS_INDEX_FILE', draft), \
                 patch('agents.edit_post.POSTS_INDEX_FILE', public), \
                 patch('agents.edit_post.get_post', return_value=live):
                with self.assertRaisesRegex(ValueError, 'stale_draft_public_live_sha_mismatch'):
                    _stale_draft_public_recovery_decision(
                        243, new, expected, image_path=None, resume=False)

    def test_unbound_candidate_cannot_trigger_stale_draft_public_recovery(self):
        old = current_bundle()
        new = copy.deepcopy(old)
        new['brief']['existing_post_id'] = 244
        with tempfile.TemporaryDirectory() as folder:
            draft = Path(folder) / 'draft_posts.json'
            draft.write_text(json.dumps([{
                'id': 243, 'status': 'draft',
                'fact_manifest': {'editorial_bundle': old},
            }], ensure_ascii=False), encoding='utf-8')
            with patch('agents.edit_post.DRAFTS_INDEX_FILE', draft), \
                 patch('agents.edit_post.get_post') as get_post:
                self.assertIsNone(_stale_draft_public_recovery_decision(
                    243, new, 'a' * 64, image_path=None, resume=False))
        get_post.assert_not_called()

    def test_edit_post_dispatches_stale_draft_live_publish_to_public_path(self):
        bundle = current_bundle()
        bundle['brief']['existing_post_id'] = 243
        expected = 'a' * 64
        decision = {'route': 'standard', 'target_status': 'publish'}
        with patch('agents.edit_post.reviewed_target_kind', return_value='draft'), \
             patch('agents.edit_post._stale_draft_public_recovery_decision',
                   return_value=decision), \
             patch('agents.edit_post._edit_reviewed_public_post',
                   return_value={'post_id': 243, 'target_status': 'publish'}) as public_edit, \
             patch('agents.edit_post.edit_reviewed_draft') as draft_edit:
            result = edit_reviewed_post(
                243, bundle, expected, confirmed=True, edit_intent='fresh full review')
        self.assertEqual('publish', result['target_status'])
        public_edit.assert_called_once()
        draft_edit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
