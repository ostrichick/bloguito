import copy
import unittest

from agents.validation_router import build_validation_plan
from tests.test_editorial_system import sample
from tests.test_multi_event_schedule import roundup_bundle


class ValidationRouterTests(unittest.TestCase):
    def test_wording_only_uses_quick_text_without_unrelated_groups(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        plan = build_validation_plan(old, new)
        self.assertEqual('quick-text', plan['profile'])
        self.assertEqual('reuse', plan['source_validation'])
        self.assertEqual('delta', plan['semantic_review'])
        self.assertFalse(plan['full_regression_required'])

    def test_image_only_is_narrow(self):
        plan = build_validation_plan(None, None, image_changed=True)
        self.assertEqual('quick-image', plan['profile'])
        self.assertEqual('none', plan['semantic_review'])

    def test_new_number_escalates_to_fact(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['lead']['text'] += ' 999원'
        plan = build_validation_plan(old, new)
        self.assertEqual('standard-fact', plan['profile'])
        self.assertEqual('full', plan['semantic_review'])

    def test_action_only_change_uses_cta_profile(self):
        old = sample()
        new = copy.deepcopy(old)
        new['sources'][0]['actions'] = [{
            'kind': 'lookup', 'label': '공식 조회', 'url': 'https://www.seocho.go.kr/guide'
        }]
        plan = build_validation_plan(old, new)
        self.assertEqual('standard-cta', plan['profile'])
        self.assertEqual('affected-or-live', plan['source_validation'])

    def test_layout_change_uses_layout_profile(self):
        old = sample()
        new = copy.deepcopy(old)
        evidence = copy.deepcopy(new['plan']['sections'][0]['paragraphs'][0]['evidence'])
        new['plan']['sections'][0]['table'] = {
            'caption': '배출 요약', 'headers': ['구분', '방법'],
            'rows': [{'cells': ['선풍기', '아파트 단지 수집 거치대'],
                      'evidence': evidence, 'answers': ['q1']}],
        }
        plan = build_validation_plan(old, new)
        self.assertEqual('standard-layout', plan['profile'])

    def test_event_and_ticket_domains_add_domain_groups(self):
        old = roundup_bundle()
        new = copy.deepcopy(old)
        new['temporal_source']['event_entries'][0]['end_date'] = '2026-10-05'
        plan = build_validation_plan(old, new, route='standard')
        self.assertEqual('standard-event', plan['profile'])

        concert_old = sample()
        concert_old['brief']['category_key'] = 'concert'
        concert_new = copy.deepcopy(concert_old)
        concert_new['plan']['sections'][0]['heading'] = '공연 안내 정리'
        concert_fast = build_validation_plan(concert_old, concert_new, route='fast')
        self.assertEqual('quick-text', concert_fast['profile'])
        self.assertFalse(concert_fast['full_regression_required'])
        concert_new['temporal_source'] = {'requires_sale': True}
        concert_standard = build_validation_plan(concert_old, concert_new, route='standard')
        self.assertEqual('standard-event', concert_standard['profile'])
        self.assertEqual('affected-or-live', concert_standard['source_validation'])

    def test_content_only_event_standard_route_still_runs_event_contract(self):
        old = roundup_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '10월 행사 일정 다시 보기'
        plan = build_validation_plan(old, new, route='standard')
        self.assertEqual('standard-event', plan['profile'])

    def test_canonical_standard_route_cannot_downgrade_to_quick(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        plan = build_validation_plan(old, new, route='standard', post_id=641)
        self.assertEqual('standard-fact', plan['profile'])
        self.assertEqual('full', plan['semantic_review'])

    def test_source_only_change_uses_source_group(self):
        old = sample()
        new = copy.deepcopy(old)
        new['sources'][0]['title'] = '공식 배출 안내 개정판'
        plan = build_validation_plan(old, new, route='standard')
        self.assertEqual('standard-source', plan['profile'])
        self.assertEqual('full', plan['source_validation'])

    def test_category_change_adds_catalog_regressions(self):
        old = sample()
        new = copy.deepcopy(old)
        new['brief']['category_key'] = 'welfare'
        plan = build_validation_plan(old, new, route='standard')
        self.assertFalse(plan['full_regression_required'])

    def test_unknown_bundle_key_fails_closed(self):
        old = sample()
        new = copy.deepcopy(old)
        new['mystery_contract'] = {'enabled': True}
        plan = build_validation_plan(old, new)
        self.assertEqual('full-regression', plan['profile'])
        self.assertTrue(plan['full_regression_required'])

    def test_plan_is_bound_to_post_route_and_content_and_digest_is_stable(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        expected = 'a' * 64
        first = build_validation_plan(
            old, new, route='fast', post_id=641, expected_content_sha256=expected)
        second = build_validation_plan(
            old, new, route='fast', post_id=641, expected_content_sha256=expected)
        self.assertEqual(first['plan_digest'], second['plan_digest'])
        self.assertEqual(641, first['binding']['post_id'])
        self.assertEqual('fast', first['binding']['route'])
        self.assertEqual(expected, first['binding']['before_content_sha256'])
        self.assertRegex(first['binding']['after_content_sha256'], r'^[0-9a-f]{64}$')

    def test_repository_code_requires_full_but_docs_do_not(self):
        full = build_validation_plan(changed_files=['agent-publisher/agents/editorial.py'])
        self.assertEqual('full-regression', full['profile'])
        self.assertTrue(full['full_regression_required'])
        docs = build_validation_plan(changed_files=['docs/OPERATIONS.md'])
        self.assertEqual('docs-only', docs['profile'])
        self.assertFalse(docs['full_regression_required'])


if __name__ == '__main__':
    unittest.main()
