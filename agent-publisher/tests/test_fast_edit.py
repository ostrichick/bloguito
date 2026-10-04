import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from agents.editorial import digest, render
from agents.fast_edit import (
    FULL_REVIEW_REQUIRED,
    _review_delta,
    changed_blocks,
    classify_fast_edit,
    fast_revise_reviewed_draft,
    prepare_fast_delta_review,
    validate_prepared_delta_review,
    validate_fast_edit,
    validate_fast_review_lineage,
)
from test_editorial_system import NOW, sample


def _wp_args(args):
    if args[:6] == ['sudo', 'docker', 'exec', '-i', 'wordpress_app', 'wp']:
        return args[6:]
    if args[:5] == ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']:
        return args[5:]
    return None


class FastEditTests(unittest.TestCase):
    def _pair(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        return old, new

    def test_classifier_allows_scoped_wording_edit_with_same_evidence(self):
        old, new = self._pair()
        result = classify_fast_edit(old, new)
        self.assertEqual('candidate', result['status'])

    def test_classifier_does_not_treat_plain_korean_suffix_word_as_region(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '배출 방법 정리'
        result = classify_fast_edit(old, new)
        self.assertEqual('candidate', result['status'])

    def test_classifier_rejects_new_number(self):
        old, new = self._pair()
        new['plan']['lead']['text'] += ' 999원'
        result = classify_fast_edit(old, new)
        self.assertEqual(FULL_REVIEW_REQUIRED, result['status'])
        self.assertTrue(any(reason.startswith('new_fact_tokens:') for reason in result['reasons']))

    def test_classifier_allows_equivalent_compact_date_format(self):
        old = sample()
        new = copy.deepcopy(old)
        old['plan']['sections'][0]['heading'] = '행사 일정 10월 7일(수)~10월 11일(일)'
        new['plan']['sections'][0]['heading'] = '행사 일정 10/7(수)~10/11(일)'
        result = classify_fast_edit(old, new)
        self.assertEqual('candidate', result['status'], result)

    def test_classifier_rejects_unreviewed_compact_date(self):
        old = sample()
        new = copy.deepcopy(old)
        old['plan']['sections'][0]['heading'] = '행사 일정 10월 7일(수)'
        new['plan']['sections'][0]['heading'] = '행사 일정 10/8(목)'
        result = classify_fast_edit(old, new)
        self.assertEqual(FULL_REVIEW_REQUIRED, result['status'])
        self.assertTrue(any(reason.startswith('new_fact_tokens:') for reason in result['reasons']))

    def test_classifier_rejects_source_or_action_change(self):
        old, new = self._pair()
        new['sources'][0]['url'] = 'https://example.org/changed'
        result = classify_fast_edit(old, new)
        self.assertEqual(FULL_REVIEW_REQUIRED, result['status'])
        self.assertIn('sources_or_actions_changed', result['reasons'])

    def test_classifier_routes_section_official_detail_link_change_to_full_review(self):
        old, new = self._pair()
        new['plan']['sections'][0]['official_links'] = [{
            'label': '행사 상세 프로그램 보기',
            'url': old['sources'][0]['url'],
        }]
        result = classify_fast_edit(old, new)
        self.assertEqual(FULL_REVIEW_REQUIRED, result['status'])
        self.assertIn('section_official_links_changed', result['reasons'])

    def test_classifier_rejects_title_and_related_post_changes(self):
        old, new = self._pair()
        new['plan']['title'] = old['plan']['title'] + ' 최신'
        new['plan']['related_posts'] = [{
            'post_id': 999,
            'label': '관련 글 보기',
            'url': 'https://lifeinfo24.org/?p=999',
        }]
        result = classify_fast_edit(old, new)
        self.assertEqual(FULL_REVIEW_REQUIRED, result['status'])
        self.assertIn('title_changed', result['reasons'])
        self.assertIn('related_posts_changed', result['reasons'])

    def test_classifier_rejects_new_high_risk_claim(self):
        old, new = self._pair()
        new['plan']['lead']['text'] += ' 현재 신청 가능합니다.'
        result = classify_fast_edit(old, new)
        self.assertEqual(FULL_REVIEW_REQUIRED, result['status'])
        self.assertIn('new_high_risk_claim', result['reasons'])

    def test_fast_validator_rejects_stale_base_review(self):
        old, new = self._pair()
        stale = datetime(2030, 1, 1, tzinfo=NOW.tzinfo)
        result = validate_fast_edit(old, new, now=stale)
        self.assertEqual(FULL_REVIEW_REQUIRED, result['status'])
        self.assertIn('base_review_not_current', result['reasons'])

    def test_fast_validator_allows_only_known_event_overview_baseline_migration(self):
        old, new = self._pair()
        old['brief']['event_post_standard_version'] = 1
        new['brief']['event_post_standard_version'] = 1
        ready = {'status': 'ready', 'reasons': [], 'details': []}
        legacy = {
            'status': 'needs_review',
            'reasons': ['event_standard_overview_schedule_layout_invalid'],
            'details': [],
        }
        with patch('agents.fast_edit.validate_bundle', side_effect=[legacy, ready]), \
                patch('agents.fast_edit.validate_fast_review_lineage', return_value={
                    'status': 'ready', 'reasons': [], 'chain_length': 0,
                }):
            result = validate_fast_edit(old, new)
        self.assertEqual('candidate', result['status'], result)
        self.assertEqual(
            ['event_standard_overview_schedule_layout_invalid'],
            result['baseline_migration'],
        )

    def test_fast_validator_does_not_broaden_baseline_migration_allowlist(self):
        old, new = self._pair()
        old['brief']['event_post_standard_version'] = 1
        new['brief']['event_post_standard_version'] = 1
        bad = {
            'status': 'needs_review',
            'reasons': ['event_standard_overview_schedule_layout_invalid', 'number_without_evidence'],
            'details': [],
        }
        with patch('agents.fast_edit.validate_bundle', return_value=bad):
            result = validate_fast_edit(old, new)
        self.assertEqual(FULL_REVIEW_REQUIRED, result['status'])
        self.assertIn('number_without_evidence', result['reasons'])

    def test_delta_reviewer_receives_user_edit_intent(self):
        old, new = self._pair()
        delta = changed_blocks(old, new)
        reviewed = {
            'checks': {
                'meaning_preserved': True,
                'evidence_still_supports': True,
                'conditions_preserved': True,
                'no_new_claims': True,
                'reader_task_preserved': True,
            },
            'issues': [],
        }
        with patch('agents.fast_edit.EditorialWriterAgent.review_delta', return_value=reviewed) as method:
            result = _review_delta(old, new, delta, '표현만 간결하게 수정')
        self.assertEqual(reviewed, result)
        self.assertEqual('표현만 간결하게 수정', method.call_args.args[3])

    def test_delta_includes_section_heading_change(self):
        old, new = self._pair()
        delta = changed_blocks(old, new)
        scopes = {item.get('scope') for item in [*delta['removed'], *delta['added']]}
        self.assertIn('section_heading:0', scopes)

    def test_delta_includes_table_caption_and_header_change(self):
        old = sample()
        evidence = copy.deepcopy(old['plan']['sections'][0]['paragraphs'][0]['evidence'])
        old['plan']['sections'][0]['table'] = {
            'caption': '배출 요약',
            'headers': ['지역', '수수료'],
            'rows': [{'cells': ['서초구', '무료'], 'evidence': evidence, 'answers': ['q1']}],
        }
        old['plan']['sections'][0]['paragraphs'] = []
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['table']['caption'] = '배출 정보'
        new['plan']['sections'][0]['table']['headers'][1] = '비용'
        delta = changed_blocks(old, new)
        changed = [item for item in [*delta['removed'], *delta['added']]
                   if item.get('scope') == 'table_structure:0']
        self.assertEqual(2, len(changed))

    def test_delta_includes_faq_question_change(self):
        old = sample()
        answer = copy.deepcopy(old['plan']['lead'])
        old['plan']['faq'] = [{
            'question_id': 'q1',
            'question': '수수료가 있나요?',
            'answer': answer,
        }]
        new = copy.deepcopy(old)
        new['plan']['faq'][0]['question'] = '배출 비용이 있나요?'
        delta = changed_blocks(old, new)
        scopes = {item.get('scope') for item in [*delta['removed'], *delta['added']]}
        self.assertIn('faq_question:0', scopes)

    def test_prepared_delta_review_is_bound_to_exact_delta_and_intent(self):
        old, new = self._pair()
        report = validate_fast_edit(old, new, now=NOW)
        delta_review = {
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
            'edit_intent_digest': digest({'edit_intent': '소제목 표현만 간단하게 다듬기'}),
        }
        self.assertTrue(validate_prepared_delta_review(
            old, report, delta_review, '소제목 표현만 간단하게 다듬기'))
        self.assertFalse(validate_prepared_delta_review(
            old, report, delta_review, '다른 요청'))

    def test_prepared_delta_review_skips_second_model_call(self):
        old, new = self._pair()
        report = validate_fast_edit(old, new, now=NOW)
        reviewed = {
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
            'edit_intent_digest': digest({'edit_intent': '소제목 표현만 간단하게 다듬기'}),
        }
        with patch('agents.fast_edit._review_delta', return_value=reviewed) as review:
            prepared = prepare_fast_delta_review(
                old, new, report, '소제목 표현만 간단하게 다듬기')
        self.assertEqual(reviewed, prepared)
        review.assert_called_once()

    def test_fast_revision_uses_target_get_plus_guarded_mutation(self):
        old, new = self._pair()
        old_body = render(old['plan'], old['sources'])
        new_body = render(new['plan'], new['sources'])
        live = {
            'ID': 393,
            'post_title': old['plan']['title'],
            'post_status': 'draft',
            'post_name': 'stable-slug',
            'post_content': old_body,
            'post_excerpt': old['plan']['lead']['text'],
        }
        # The test fixture lead can be short enough that excerpt normalization
        # differs; use the production helper's exact value.
        from agents.editorial import excerpt_from_lead
        live['post_excerpt'] = excerpt_from_lead(old['plan']['lead'])

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / 'data'
            data.mkdir()
            index = data / 'draft_posts.json'
            index.write_text(json.dumps([{
                'id': 393,
                'fact_manifest': {'editorial_bundle': old},
            }]), encoding='utf-8')
            calls = []

            def run(args, **kwargs):
                calls.append(args)
                wp = _wp_args(args) or []
                if wp[:2] == ['post', 'get']:
                    self.assertIn(
                        '--fields=post_status,post_title,post_name,post_content,post_excerpt', args)
                    return Mock(stdout=json.dumps(live))
                if wp and wp[0] == 'eval':
                    payload = json.loads(kwargs['input'])
                    live.update(payload['updates'])
                    return Mock(stdout=json.dumps({'status': 'ok', 'saved': live}))
                raise AssertionError(args)

            changed = {'removed': [], 'added': []}
            report = {
                'status': 'candidate',
                'reasons': [],
                'changed_blocks': changed,
                'base_content_digest': digest({
                    key: old[key] for key in ('brief', 'sources', 'plan', 'temporal_source') if key in old
                }),
                'result_content_digest': digest({
                    key: new[key] for key in ('brief', 'sources', 'plan', 'temporal_source') if key in new
                }),
            }
            delta = {
                'mode': 'delta',
                'base_review_digest': old['review']['digest'],
                'base_policy_digest': old['review']['policy_digest'],
                'delta_digest': digest(changed),
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
                'edit_intent_digest': digest({'edit_intent': '소제목 표현만 간단하게 다듬기'}),
                'checked_at': datetime.now().astimezone().isoformat(),
            }
            with patch('agents.fast_edit.ROOT', root), \
                 patch('agents.fast_edit.DRAFTS_INDEX_FILE', index), \
                 patch('agents.fast_edit.validate_fast_edit', return_value=report), \
                 patch('agents.fast_edit._review_delta', return_value=delta), \
                 patch('agents.fast_edit.subprocess.run', side_effect=run):
                result = fast_revise_reviewed_draft(
                    393, new, hashlib.sha256(old_body.encode()).hexdigest(), confirmed=True,
                    edit_intent='소제목 표현만 간단하게 다듬기')

            self.assertEqual(393, result)
            self.assertEqual(new_body, live['post_content'])
            self.assertEqual(2, len(calls))
            self.assertEqual(1, sum((_wp_args(args) or [None])[0] == 'eval' for args in calls))
            self.assertFalse(any((_wp_args(args) or [])[:2] == ['post', 'update'] for args in calls))
            self.assertFalse(any((_wp_args(args) or [])[:2] == ['post', 'list'] for args in calls))
            saved = json.loads(index.read_text(encoding='utf-8'))[0]['fact_manifest']['editorial_bundle']
            self.assertIn('fast_edit_review', saved)
            self.assertEqual(1, len(saved['fast_edit_chain']))
            self.assertEqual(old['review'], saved['review'])

    def test_fast_revision_accepts_renderer_only_location_card_migration(self):
        old, new = self._pair()
        location = {
            'venue': '서초구 행사장',
            'address': '서울 서초구 행사장 1',
            'query': '서울 서초구 행사장',
            'evidence': [{'source_id': 's0', 'quote': old['sources'][0]['text']}],
        }
        old['plan']['sections'][0]['location'] = copy.deepcopy(location)
        new['plan']['sections'][0]['location'] = copy.deepcopy(location)
        old_body = render(old['plan'], old['sources'])
        new_body = render(new['plan'], new['sources'])
        compact = (
            '<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:4px">'
            '📍 행사장 위치: 서초구 행사장</div>'
            '<div style="font-size:14px;color:#475569;margin-bottom:10px;line-height:1.6">'
            '<strong>주소</strong>: 서울 서초구 행사장 1</div>'
        )
        legacy = (
            '<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:8px">'
            '📍 행사장 위치</div>'
            '<div style="font-size:14px;color:#475569;margin-bottom:10px;line-height:1.6">'
            '<strong>장소</strong>: 서초구 행사장<br/>'
            '<strong>위치</strong>: 서울 서초구 행사장 1</div>'
        )
        self.assertIn(compact, old_body)
        live_body = old_body.replace(compact, legacy, 1)
        live = {
            'ID': 393,
            'post_title': old['plan']['title'],
            'post_status': 'draft',
            'post_name': 'stable-slug',
            'post_content': live_body,
            'post_excerpt': old['plan']['lead']['text'],
        }
        from agents.editorial import excerpt_from_lead
        live['post_excerpt'] = excerpt_from_lead(old['plan']['lead'])

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / 'data'
            data.mkdir()
            index = data / 'draft_posts.json'
            index.write_text(json.dumps([{
                'id': 393,
                'fact_manifest': {'editorial_bundle': old},
            }]), encoding='utf-8')

            def run(args, **kwargs):
                wp = _wp_args(args) or []
                if wp[:2] == ['post', 'get']:
                    return Mock(stdout=json.dumps(live))
                if wp and wp[0] == 'eval':
                    payload = json.loads(kwargs['input'])
                    live.update(payload['updates'])
                    return Mock(stdout=json.dumps({'status': 'ok', 'saved': live}))
                raise AssertionError(args)

            changed = {'removed': [], 'added': []}
            report = {
                'status': 'candidate',
                'reasons': [],
                'changed_blocks': changed,
                'base_content_digest': digest({
                    key: old[key] for key in ('brief', 'sources', 'plan', 'temporal_source') if key in old
                }),
                'result_content_digest': digest({
                    key: new[key] for key in ('brief', 'sources', 'plan', 'temporal_source') if key in new
                }),
            }
            delta = {
                'mode': 'delta',
                'base_review_digest': old['review']['digest'],
                'base_policy_digest': old['review']['policy_digest'],
                'delta_digest': digest(changed),
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
                'edit_intent_digest': digest({'edit_intent': '소제목 표현만 간단하게 다듬기'}),
                'checked_at': datetime.now().astimezone().isoformat(),
            }
            with patch('agents.fast_edit.ROOT', root), \
                 patch('agents.fast_edit.DRAFTS_INDEX_FILE', index), \
                 patch('agents.fast_edit.validate_fast_edit', return_value=report), \
                 patch('agents.fast_edit._review_delta', return_value=delta), \
                 patch('agents.fast_edit.subprocess.run', side_effect=run):
                result = fast_revise_reviewed_draft(
                    393, new, hashlib.sha256(live_body.encode()).hexdigest(), confirmed=True,
                    edit_intent='소제목 표현만 간단하게 다듬기')

            self.assertEqual(393, result)
            self.assertEqual(new_body, live['post_content'])

    def test_consecutive_fast_edits_keep_valid_review_lineage(self):
        old = sample()
        first = copy.deepcopy(old)
        first['plan']['sections'][0]['heading'] = '첫 번째 간단한 소제목'
        report_one = validate_fast_edit(old, first, now=NOW)
        self.assertEqual('candidate', report_one['status'])
        intent_one = '첫 번째 표현 정리'
        delta_one = {
            'mode': 'delta',
            'base_review_digest': old['review']['digest'],
            'base_policy_digest': old['review']['policy_digest'],
            'delta_digest': digest(report_one['changed_blocks']),
            'base_content_digest': report_one['base_content_digest'],
            'result_content_digest': report_one['result_content_digest'],
            'checks': {
                'meaning_preserved': True,
                'evidence_still_supports': True,
                'conditions_preserved': True,
                'no_new_claims': True,
                'reader_task_preserved': True,
            },
            'issues': [],
            'edit_intent_digest': digest({'edit_intent': intent_one}),
            'checked_at': NOW.isoformat(),
        }
        first['review'] = old['review']
        first['fast_edit_review'] = delta_one
        first['fast_edit_chain'] = [delta_one]
        lineage = validate_fast_review_lineage(first, now=NOW)
        self.assertEqual('ready', lineage['status'])

        second = copy.deepcopy(first)
        second['plan']['sections'][0]['heading'] = '두 번째 간단한 소제목'
        report_two = validate_fast_edit(first, second, now=NOW)
        self.assertEqual('candidate', report_two['status'])
        self.assertEqual(report_one['result_content_digest'], report_two['base_content_digest'])

    def test_fast_revision_requires_edit_intent(self):
        old, new = self._pair()
        with self.assertRaisesRegex(ValueError, 'fast_edit_intent_required'):
            fast_revise_reviewed_draft(
                393, new, hashlib.sha256(render(old['plan'], old['sources']).encode()).hexdigest(),
                confirmed=True)


if __name__ == '__main__':
    unittest.main()
