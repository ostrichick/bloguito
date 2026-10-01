import copy
import unittest

from agents.validation_router import build_validation_plan
from tests.test_editorial_system import sample
from tests.test_event_post_standard import event_bundle
from tests.test_multi_event_schedule import roundup_bundle


class ValidationRouterTests(unittest.TestCase):
    def test_wording_only_uses_quick_text_without_unrelated_groups(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        plan = build_validation_plan(old, new)
        self.assertEqual('quick-text', plan['profile'])
        self.assertEqual(['core-safe-edit', 'fast-edit'], plan['test_groups'])
        self.assertEqual('reuse', plan['source_validation'])
        self.assertEqual('delta', plan['semantic_review'])
        self.assertNotIn('ticket', plan['test_groups'])

    def test_image_only_is_narrow(self):
        plan = build_validation_plan(None, None, image_changed=True)
        self.assertEqual('quick-image', plan['profile'])
        self.assertEqual(['core-safe-edit', 'image'], plan['test_groups'])
        self.assertEqual('none', plan['semantic_review'])

    def test_new_number_escalates_to_fact(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['lead']['text'] += ' 999원'
        plan = build_validation_plan(old, new)
        self.assertEqual('standard-fact', plan['profile'])
        self.assertIn('fact', plan['test_groups'])
        self.assertNotIn('source', plan['test_groups'])
        self.assertNotIn('temporal', plan['test_groups'])
        self.assertEqual('full', plan['semantic_review'])

    def test_explicit_fast_route_is_promoted_when_diff_is_not_fast_safe(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['lead']['text'] += ' 999원'

        plan = build_validation_plan(old, new, route='fast')

        self.assertEqual('standard-fact', plan['profile'])
        self.assertTrue(plan['profile_selection']['promoted'])
        self.assertEqual('quick-text', plan['profile_selection']['candidate_profile'])
        self.assertEqual('standard-fact', plan['profile_selection']['minimum_safe_profile'])
        self.assertIn('fact_or_metadata_change_requires_standard_validation', plan['reasons'])

    def test_image_only_route_is_promoted_if_bundle_content_also_changed(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '본문도 함께 바뀐 소제목'

        plan = build_validation_plan(old, new, image_changed=True, route='image-only')

        self.assertEqual('standard-fact', plan['profile'])
        self.assertTrue(plan['profile_selection']['promoted'])
        self.assertEqual('quick-image', plan['profile_selection']['candidate_profile'])
        self.assertIn('image', plan['test_groups'])

    def test_action_only_change_uses_cta_profile(self):
        old = sample()
        new = copy.deepcopy(old)
        new['sources'][0]['actions'] = [{
            'kind': 'lookup', 'label': '공식 조회', 'url': 'https://www.seocho.go.kr/guide'
        }]
        plan = build_validation_plan(old, new)
        self.assertEqual('standard-cta', plan['profile'])
        self.assertIn('cta', plan['test_groups'])
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
        self.assertIn('layout', plan['test_groups'])

    def test_event_and_ticket_domains_add_domain_groups(self):
        old = roundup_bundle()
        new = copy.deepcopy(old)
        new['temporal_source']['event_entries'][0]['end_date'] = '2026-10-05'
        plan = build_validation_plan(old, new, route='standard')
        self.assertEqual('standard-event', plan['profile'])
        self.assertIn('event', plan['test_groups'])

        concert_old = sample()
        concert_old['brief']['category_key'] = 'concert'
        concert_new = copy.deepcopy(concert_old)
        concert_new['plan']['sections'][0]['heading'] = '공연 안내 정리'
        concert_fast = build_validation_plan(concert_old, concert_new, route='fast')
        self.assertEqual('quick-text', concert_fast['profile'])
        self.assertNotIn('ticket', concert_fast['test_groups'])
        concert_new['temporal_source'] = {'requires_sale': True}
        concert_standard = build_validation_plan(concert_old, concert_new, route='standard')
        self.assertEqual('standard-event', concert_standard['profile'])
        self.assertIn('ticket', concert_standard['test_groups'])
        self.assertEqual('affected-or-live', concert_standard['source_validation'])

    def test_content_only_event_standard_route_still_runs_event_contract(self):
        old = roundup_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '10월 행사 일정 다시 보기'
        plan = build_validation_plan(old, new, route='standard')
        self.assertEqual('standard-event', plan['profile'])
        self.assertIn('event', plan['test_groups'])

    def test_event_v1_localized_change_uses_event_delta_and_scoped_qa(self):
        old = event_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][1]['paragraphs'][0]['text'] += ' 우천 시 공식 안내를 확인합니다.'
        new['temporal_source']['event_entries'][0]['end_date'] = '2026-10-16'
        new['sources'][0]['title'] = '2026 가을 체험축제 공식 안내 개정'

        plan = build_validation_plan(old, new, route='standard')

        self.assertEqual('event-delta', plan['profile'])
        self.assertEqual('event-delta', plan['semantic_review'])
        self.assertEqual('affected-or-live', plan['source_validation'])
        self.assertEqual(['가을 체험축제'], plan['affected_event_names'])
        self.assertEqual(['s0'], plan['affected_source_ids'])
        self.assertEqual(
            [{'kind': 'event-section', 'event_name': '가을 체험축제'}],
            plan['qa_targets'],
        )
        self.assertFalse(plan['site_context_required'])
        self.assertIn('event', plan['test_groups'])
        self.assertIn('source', plan['test_groups'])
        self.assertIn('temporal', plan['test_groups'])

    def test_event_v1_localized_change_auto_selects_event_delta(self):
        old = event_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][1]['paragraphs'][0]['text'] += ' 행사 종료일이 하루 연장되었습니다.'
        new['temporal_source']['event_entries'][0]['end_date'] = '2026-10-16'

        plan = build_validation_plan(old, new)

        self.assertEqual('standard', plan['binding']['route'])
        self.assertEqual('event-delta', plan['profile'])
        self.assertEqual('event-delta', plan['semantic_review'])
        self.assertEqual(['가을 체험축제'], plan['affected_event_names'])

    def test_event_delta_allows_matching_overview_row_update_only(self):
        old = event_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][1]['paragraphs'][0]['text'] += ' 행사 종료일이 하루 연장되었습니다.'
        new['temporal_source']['event_entries'][0]['end_date'] = '2026-10-16'
        new['plan']['sections'][0]['table']['rows'][0]['cells'][0] = '10/14~10/16'

        plan = build_validation_plan(old, new, route='standard')

        self.assertEqual('event-delta', plan['profile'])
        self.assertEqual(['가을 체험축제'], plan['affected_event_names'])

    def test_event_v1_membership_or_global_changes_keep_full_event_profile(self):
        cases = []

        removed = event_bundle()
        removed['plan']['sections'].pop()
        removed['temporal_source']['event_entries'].pop()
        cases.append(('event_removed', removed, False))

        title = event_bundle()
        title['plan']['title'] = '2026년 10월 서초 행사 일정 새 제목'
        cases.append(('title', title, True))

        lead = event_bundle()
        lead['plan']['lead']['text'] += ' 방문 전 일정을 확인하세요.'
        cases.append(('lead', lead, False))

        seo = event_bundle()
        seo['brief']['seo']['description'] += ' 최신 일정 기준입니다.'
        cases.append(('seo', seo, False))

        related = event_bundle()
        related['plan']['related_posts'] = [{
            'post_id': 641,
            'label': '관련 생활정보',
            'url': 'https://lifeinfo24.org/000641/',
        }]
        cases.append(('related', related, True))

        overview = event_bundle()
        overview['plan']['sections'][0]['heading'] = '10월 서초 행사 전체 일정'
        cases.append(('global_section', overview, False))

        overview_headers = event_bundle()
        overview_headers['plan']['sections'][0]['table']['headers'][0] = '행사 날짜'
        cases.append(('overview_headers', overview_headers, False))

        unrelated_row = event_bundle()
        unrelated_row['plan']['sections'][1]['paragraphs'][0]['text'] += ' 첫 행사 설명만 수정합니다.'
        unrelated_row['plan']['sections'][0]['table']['rows'][1]['cells'][0] = '10/20 변경'
        cases.append(('unaffected_overview_row', unrelated_row, False))

        for label, new, site_context_required in cases:
            with self.subTest(label=label):
                plan = build_validation_plan(event_bundle(), new, route='standard')
                self.assertEqual('standard-event', plan['profile'])
                self.assertEqual('full', plan['semantic_review'])
                self.assertEqual([], plan['affected_event_names'])
                self.assertEqual([], plan['qa_targets'])
                self.assertEqual(site_context_required, plan['site_context_required'])

    def test_site_context_required_tracks_duplicate_sensitive_fields(self):
        for field in ('required_title_terms', 'official_urls'):
            with self.subTest(field=field):
                old = event_bundle()
                new = copy.deepcopy(old)
                new['brief'][field] = list(new['brief'][field]) + ['추가값']
                plan = build_validation_plan(old, new, route='standard')
                self.assertTrue(plan['site_context_required'])
                self.assertEqual('standard-event', plan['profile'])

    def test_event_v1_fast_wording_change_remains_quick_text(self):
        old = event_bundle()
        new = copy.deepcopy(old)
        new['plan']['sections'][1]['heading'] = '가을 체험축제 프로그램 안내'
        plan = build_validation_plan(old, new, route='fast')
        self.assertEqual('quick-text', plan['profile'])
        self.assertEqual('delta', plan['semantic_review'])

    def test_canonical_standard_route_cannot_downgrade_to_quick(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        plan = build_validation_plan(old, new, route='standard', post_id=641)
        self.assertEqual('standard-fact', plan['profile'])
        self.assertEqual('full', plan['semantic_review'])
        self.assertIn('draft-standard', plan['test_groups'])
        self.assertIn('editorial-contract', plan['test_groups'])

    def test_source_only_change_uses_source_group(self):
        old = sample()
        new = copy.deepcopy(old)
        new['sources'][0]['title'] = '공식 배출 안내 개정판'
        plan = build_validation_plan(old, new, route='standard')
        self.assertEqual('standard-source', plan['profile'])
        self.assertIn('source', plan['test_groups'])
        self.assertEqual('full', plan['source_validation'])

    def test_category_change_adds_catalog_regressions(self):
        old = sample()
        new = copy.deepcopy(old)
        new['brief']['category_key'] = 'welfare'
        plan = build_validation_plan(old, new, route='standard')
        self.assertIn('catalog', plan['test_groups'])

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
        self.assertEqual(['full-regression'], full['test_groups'])
        docs = build_validation_plan(changed_files=['docs/OPERATIONS.md'])
        self.assertEqual('docs-only', docs['profile'])
        self.assertEqual([], docs['test_groups'])


if __name__ == '__main__':
    unittest.main()
