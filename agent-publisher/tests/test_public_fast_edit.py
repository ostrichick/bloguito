import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from agents.editorial import (
    _previous_responsive_layout_variant, digest, recognized_renderer_hashes, render,
)
from agents.fast_edit import validate_fast_edit
from agents.public_fast_edit import (
    classify_public_fast_edit,
    fast_update_public_post,
    migrate_public_renderer,
)
from agents.temporal_validation import KST
from test_editorial_system import sample


def _wp_args(args):
    if args[:6] == ['sudo', 'docker', 'exec', '-i', 'wordpress_app', 'wp']:
        return args[6:]
    if args[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']:
        return args[5:]
    return None


def current_bundle():
    bundle = sample()
    now = datetime.now(KST)
    bundle['brief']['reviewed_at'] = now.date().isoformat()
    bundle['brief']['review_until'] = (now.date() + timedelta(days=7)).isoformat()
    for source in bundle['sources']:
        source['fetched_at'] = now.isoformat()
    body = {k: bundle[k] for k in ('brief', 'sources', 'plan', 'temporal_source')}
    bundle['review']['digest'] = digest(body)
    bundle['review']['checked_at'] = now.isoformat()
    return bundle


def delta_review(old, new, report, intent):
    return {
        'mode': 'delta',
        'base_review_digest': old['review']['digest'],
        'base_policy_digest': old['review']['policy_digest'],
        'delta_digest': digest(report['changed_blocks']),
        'base_content_digest': report['base_content_digest'],
        'result_content_digest': report['result_content_digest'],
        'checks': {
            'meaning_preserved': True,
            'evidence_still_supports': True,
            'conditions_preserved': True,
            'no_new_claims': True,
            'reader_task_preserved': True,
        },
        'issues': [],
        'edit_intent_digest': digest({'edit_intent': intent}),
        'checked_at': datetime.now(KST).isoformat(),
    }


class PublicFastEditTests(unittest.TestCase):
    def test_public_fast_uses_target_get_plus_guarded_mutation_and_preserves_manual_excerpt(self):
        old = current_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '버리는 순서'
        old_body = render(old['plan'], old['sources'])
        new_body = render(new['plan'], new['sources'])
        report = validate_fast_edit(old, new)
        self.assertEqual('candidate', report['status'])
        intent = '소제목 표현만 간결하게 정리'
        prepared = delta_review(old, new, report, intent)
        live = {
            'ID': 243,
            'post_status': 'publish',
            'post_title': old['plan']['title'],
            'post_name': 'stable-slug',
            'post_content': old_body,
            'post_excerpt': '사람이 직접 작성한 요약',
        }

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / 'data'
            data.mkdir()
            index = data / 'published_posts.json'
            index.write_text(json.dumps([{
                'id': 243, 'status': 'publish',
                'fact_manifest': {'editorial_bundle': old},
            }], ensure_ascii=False), encoding='utf-8')
            calls = []

            def run(args, **kwargs):
                calls.append(args)
                wp = _wp_args(args) or []
                if wp[:2] == ['post', 'get']:
                    return Mock(stdout=json.dumps(live, ensure_ascii=False))
                if wp and wp[0] == 'eval':
                    payload = json.loads(kwargs['input'])
                    self.assertNotIn('post_excerpt', payload['updates'])
                    live.update(payload['updates'])
                    return Mock(stdout=json.dumps({'status': 'ok', 'saved': live}, ensure_ascii=False))
                raise AssertionError(args)

            with patch('agents.public_fast_edit.ROOT', root), \
                 patch('agents.public_fast_edit.POSTS_INDEX_FILE', index), \
                 patch('agents.public_fast_edit.invalidate_inventory') as invalidate, \
                 patch('agents.wordpress_mutation.subprocess.run', side_effect=run):
                result = fast_update_public_post(
                    243, new, hashlib.sha256(old_body.encode()).hexdigest(),
                    confirmed=True, edit_intent=intent,
                    prepared_delta_review=prepared)

            self.assertEqual(243, result)
            self.assertEqual(new_body, live['post_content'])
            self.assertEqual('사람이 직접 작성한 요약', live['post_excerpt'])
            self.assertEqual(2, len(calls))
            self.assertEqual(1, sum((_wp_args(call) or [None])[0] == 'eval' for call in calls))
            saved = json.loads(index.read_text(encoding='utf-8'))[0]['fact_manifest']['editorial_bundle']
            self.assertEqual(1, len(saved['fast_edit_chain']))
            invalidate.assert_called_once_with()

    def test_classifier_exposes_tracked_content_binding(self):
        old = current_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '간단한 소제목'
        with tempfile.TemporaryDirectory() as folder:
            index = Path(folder) / 'published_posts.json'
            index.write_text(json.dumps([{
                'id': 243, 'fact_manifest': {'editorial_bundle': old},
            }], ensure_ascii=False), encoding='utf-8')
            with patch('agents.public_fast_edit.POSTS_INDEX_FILE', index):
                decision = classify_public_fast_edit(243, new)
        self.assertEqual('fast', decision['route'])
        self.assertEqual(
            hashlib.sha256(render(old['plan'], old['sources']).encode()).hexdigest(),
            decision['tracked_content_sha256'])

    def test_renderer_classification_refuses_unbound_semantic_review(self):
        old = current_bundle()
        old['review']['digest'] = '0' * 64
        expected = hashlib.sha256(render(old['plan'], old['sources']).encode()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            index = Path(folder) / 'published_posts.json'
            index.write_text(json.dumps([{
                'id': 243, 'fact_manifest': {'editorial_bundle': old},
            }], ensure_ascii=False), encoding='utf-8')
            with patch('agents.public_fast_edit.POSTS_INDEX_FILE', index):
                with self.assertRaisesRegex(ValueError, 'review_not_bound'):
                    classify_public_fast_edit(
                        243, old, expected_content_sha256=expected)

    def test_classifier_routes_exact_previous_renderer_as_migration_without_freshness_review(self):
        old = current_bundle()
        stale = copy.deepcopy(old)
        stale['brief']['review_until'] = '2020-01-01'
        stale['review']['digest'] = digest({
            key: stale[key]
            for key in ('brief', 'sources', 'plan', 'temporal_source')
            if key in stale
        })
        previous = _previous_responsive_layout_variant(render(stale['plan'], stale['sources']))
        expected = hashlib.sha256(previous.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            index = Path(folder) / 'published_posts.json'
            index.write_text(json.dumps([{
                'id': 243, 'fact_manifest': {'editorial_bundle': stale},
            }], ensure_ascii=False), encoding='utf-8')
            with patch('agents.public_fast_edit.POSTS_INDEX_FILE', index):
                decision = classify_public_fast_edit(
                    243, stale, expected_content_sha256=expected)
        self.assertEqual('fast', decision['route'])
        self.assertTrue(decision['renderer_migration'])
        self.assertEqual('pre-responsive-layout-v1', decision['renderer_variant'])
        self.assertIn(expected, decision['tracked_content_sha256s'])

    def test_historical_registry_is_bound_to_post_and_current_bundle_sha(self):
        old = current_bundle()
        current = render(old['plan'], old['sources'])
        current_sha = hashlib.sha256(current.encode()).hexdigest()
        historical_sha = '1' * 64
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder) / 'renderer_provenance.json'
            registry.write_text(json.dumps({
                'schema_version': 1,
                'entries': [{
                    'post_id': 243,
                    'current_sha256': current_sha,
                    'historical_sha256': historical_sha,
                    'renderer_revision': '44af7c6',
                    'variant': 'historical-test',
                }],
            }), encoding='utf-8')
            with patch('agents.editorial.RENDERER_PROVENANCE_FILE', registry):
                hashes = recognized_renderer_hashes(
                    old['plan'], old['sources'], post_id=243)
                wrong_post = recognized_renderer_hashes(
                    old['plan'], old['sources'], post_id=244)
                changed = copy.deepcopy(old)
                changed['plan']['lead']['text'] += ' 변경'
                wrong_bundle = recognized_renderer_hashes(
                    changed['plan'], changed['sources'], post_id=243)
        self.assertEqual(historical_sha, hashes['historical-test'])
        self.assertNotIn('historical-test', wrong_post)
        self.assertNotIn('historical-test', wrong_bundle)

    def test_fast_public_refuses_stale_manifest_binding(self):
        old = current_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '간단한 소제목'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            index = root / 'data' / 'published_posts.json'
            index.write_text(json.dumps([{
                'id': 243, 'fact_manifest': {'editorial_bundle': old},
            }], ensure_ascii=False), encoding='utf-8')
            with patch('agents.public_fast_edit.ROOT', root), \
                 patch('agents.public_fast_edit.POSTS_INDEX_FILE', index):
                with self.assertRaisesRegex(ValueError, 'public_manifest_not_bound'):
                    fast_update_public_post(
                        243, new, '0' * 64, confirmed=True,
                        edit_intent='표현만 간단히 정리')

    def test_fast_public_accepts_exact_known_previous_renderer_baseline(self):
        old = current_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '버리는 순서'
        current_old = render(old['plan'], old['sources'])
        previous_old = _previous_responsive_layout_variant(current_old)
        self.assertNotEqual(current_old, previous_old)
        new_body = render(new['plan'], new['sources'])
        report = validate_fast_edit(old, new)
        intent = '과거 renderer 레이아웃을 현행 반응형 renderer로 정규화'
        prepared = delta_review(old, new, report, intent)
        live = {
            'ID': 243,
            'post_status': 'publish',
            'post_title': old['plan']['title'],
            'post_name': 'stable-slug',
            'post_content': previous_old,
            'post_excerpt': '사람이 직접 작성한 요약',
        }

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / 'data'
            data.mkdir()
            index = data / 'published_posts.json'
            index.write_text(json.dumps([{
                'id': 243, 'status': 'publish',
                'fact_manifest': {'editorial_bundle': old},
            }], ensure_ascii=False), encoding='utf-8')

            def run(args, **kwargs):
                wp = _wp_args(args) or []
                if wp[:2] == ['post', 'get']:
                    return Mock(stdout=json.dumps(live, ensure_ascii=False))
                if wp and wp[0] == 'eval':
                    payload = json.loads(kwargs['input'])
                    live.update(payload['updates'])
                    return Mock(stdout=json.dumps({'status': 'ok', 'saved': live}, ensure_ascii=False))
                raise AssertionError(args)

            with patch('agents.public_fast_edit.ROOT', root), \
                 patch('agents.public_fast_edit.POSTS_INDEX_FILE', index), \
                 patch('agents.public_fast_edit.invalidate_inventory'), \
                 patch('agents.wordpress_mutation.subprocess.run', side_effect=run):
                result = fast_update_public_post(
                    243,
                    new,
                    hashlib.sha256(previous_old.encode()).hexdigest(),
                    confirmed=True,
                    edit_intent=intent,
                    prepared_delta_review=prepared,
                )

        self.assertEqual(243, result)
        self.assertEqual(new_body, live['post_content'])

    def test_renderer_migration_changes_only_exact_known_previous_output(self):
        old = current_bundle()
        current = render(old['plan'], old['sources'])
        previous = _previous_responsive_layout_variant(current)
        live = {
            'ID': 243,
            'post_status': 'publish',
            'post_title': old['plan']['title'],
            'post_name': 'stable-slug',
            'post_content': previous,
            'post_excerpt': '사람이 직접 작성한 요약',
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / 'data'
            data.mkdir()
            index = data / 'published_posts.json'
            index.write_text(json.dumps([{
                'id': 243, 'status': 'publish',
                'fact_manifest': {'editorial_bundle': old},
            }], ensure_ascii=False), encoding='utf-8')

            def run(args, **kwargs):
                wp = _wp_args(args) or []
                if wp[:2] == ['post', 'get']:
                    return Mock(stdout=json.dumps(live, ensure_ascii=False))
                if wp and wp[0] == 'eval':
                    payload = json.loads(kwargs['input'])
                    self.assertEqual({'post_content'}, set(payload['updates']))
                    live.update(payload['updates'])
                    return Mock(stdout=json.dumps({'status': 'ok', 'saved': live}, ensure_ascii=False))
                raise AssertionError(args)

            with patch('agents.public_fast_edit.ROOT', root), \
                 patch('agents.public_fast_edit.POSTS_INDEX_FILE', index), \
                 patch('agents.public_fast_edit.invalidate_inventory') as invalidate, \
                 patch('agents.wordpress_mutation.subprocess.run', side_effect=run):
                result = migrate_public_renderer(
                    243,
                    old,
                    hashlib.sha256(previous.encode()).hexdigest(),
                    confirmed=True,
                )

        self.assertEqual(243, result)
        self.assertEqual(current, live['post_content'])
        self.assertEqual('사람이 직접 작성한 요약', live['post_excerpt'])
        invalidate.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
