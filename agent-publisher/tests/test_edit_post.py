import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from agents.edit_post import (
    _validated_prepared_decision,
    classify_reviewed_post_route,
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


if __name__ == '__main__':
    unittest.main()
