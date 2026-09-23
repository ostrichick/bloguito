"""Narrow #103 municipal-source conflict regression; synthetic, offline, no review signatures."""
import hashlib
import unittest
from datetime import datetime

from agents.critical_facts import critical_fact_reasons
from agents.editorial import validate_bundle
from agents.temporal_validation import KST


HEALTH = 'https://www.mokpo.go.kr/health/citizen_participation/notice?idx=548678&mode=view'
PRESS = 'https://www.mokpo.go.kr/www/mokpo_news/press_release/report_material?idx=548751&mode=view'
ALTERNATE_PRESS = 'https://seafountain.mokpo.go.kr/www/mokpo_news/press_release/report_material?idx=548751&mode=view&page=2'
REASON = 'mokpo_city_program_age_conflict_unresolved'
NOW = datetime(2026, 9, 23, 10, tzinfo=KST)


def official(identifier, url, text):
    return {'id': identifier, 'url': url, 'text': text, 'source_type': 'official',
            'sha256': hashlib.sha256(text.encode()).hexdigest(), 'title': 'TEST fixture',
            'fetched_at': NOW.isoformat()}


class MokpoMunicipalAgeConflictTests(unittest.TestCase):
    def setUp(self):
        # The source statements below are deliberately synthetic *test inputs*;
        # no review or source-authentication signature is created or reused.
        self.health = official('h', HEALTH,
            '인플루엔자 시 자체사업 무료 예방접종(보건소 접종)\n'
            '지원대상: 15세~65세 목포시민 중 취약계층')
        self.press = official('p', PRESS,
            '목포시 자체사업: 15~64세 취약계층은 10월 12일 보건소에서 접종')
        self.brief = {'existing_post_id': 103, 'category_key': 'life-health',
                      'official_urls': [HEALTH, PRESS], 'entity': '목포 독감',
                      'primary_keyword': '2026 목포 독감'}
        self.plan = {'title': '목포시 자체사업 인플루엔자', 'lead': {'text': '근거 검토 전'},
                     'sections': [], 'faq': []}

    def reasons(self, sources=None, brief=None):
        return critical_fact_reasons(brief or self.brief,
                                     sources if sources is not None else [self.health, self.press],
                                     self.plan)

    def test_current_conflicting_health_notice_and_city_press_block(self):
        self.assertIn(REASON, self.reasons())

    def test_missing_press_is_not_interpreted_as_conflict_resolved(self):
        self.assertIn(REASON, self.reasons([self.health]))
        self.assertIn(REASON, self.reasons([self.press]))
        self.assertIn(REASON, self.reasons([]))

    def test_both_city_pages_must_identify_single_identical_range(self):
        for age in ('64', '65'):
            with self.subTest(age=age):
                corrected = official('p', PRESS, f'목포시 자체사업: 15~{age}세 취약계층')
                health = official('h', HEALTH, f'목포시 자체사업: 15세~{age}세 취약계층')
                self.assertNotIn(REASON, self.reasons([health, corrected]))
        ambiguous = official('p', PRESS, '시 자체사업 15~64세 및 15~65세')
        self.assertIn(REASON, self.reasons([self.health, ambiguous]))

    def test_nonofficial_or_unlisted_press_cannot_clear_gate(self):
        consistent = official('p', PRESS, '목포시 자체사업 15~65세')
        consistent['source_type'] = 'news'
        self.assertIn(REASON, self.reasons([self.health, consistent]))
        consistent['source_type'] = 'official'
        brief = {**self.brief, 'official_urls': [HEALTH]}
        self.assertIn(REASON, self.reasons([self.health, consistent], brief))

    def test_alternate_actual_press_host_is_accepted_only_with_matching_range(self):
        replacement = official('p', ALTERNATE_PRESS, '목포시 자체사업 15~65세')
        brief = {**self.brief, 'official_urls': [HEALTH, ALTERNATE_PRESS]}
        self.assertNotIn(REASON, self.reasons([self.health, replacement], brief))
        different = official('p', ALTERNATE_PRESS, '목포시 자체사업 15~64세')
        self.assertIn(REASON, self.reasons([self.health, different], brief))

    def test_unrelated_national_65_year_statements_do_not_count_as_city_range(self):
        unrelated = official('p', PRESS,
            '목포시 자체사업 대상은 현행 안내를 참고. 국가접종은 65세 이상.')
        self.assertIn(REASON, self.reasons([self.health, unrelated]))

    def test_no_other_post_or_category_is_affected(self):
        for post_id, category in ((104, 'life-health'), (103, 'tax'), (None, 'life-health')):
            with self.subTest(post_id=post_id, category=category):
                brief = {**self.brief, 'existing_post_id': post_id, 'category_key': category}
                self.assertNotIn(REASON, self.reasons([self.health, self.press], brief))

    def test_national_season_only_article_without_city_claim_is_unaffected(self):
        national_plan = {'title': '목포 독감 국가접종 일정',
                         'lead': {'text': '국가접종 어린이·임신부·어르신 대상 기간'},
                         'sections': [], 'faq': []}
        self.assertNotIn(REASON, critical_fact_reasons(
            self.brief, [self.health], national_plan))

    def test_real_preflight_path_cannot_return_ready_with_missing_press(self):
        brief = {**self.brief, 'id': 'test-103', 'approved': True,
                 'question': '목포시 자체사업 대상?', 'angle': '근거 비교',
                 'required_title_terms': ['목포'], 'reader_questions': [{'id': 'q1', 'question': '대상?'}],
                 'content_type': 'dated', 'useful_until': '2027-04-30',
                 'reviewed_at': '2026-09-23', 'review_until': '2026-09-23',
                 'official_urls': [HEALTH]}
        block = {'text': '시 자체사업 지원 연령에는 확인이 필요합니다.',
                 'evidence': [{'source_id': 'h', 'quote': self.health['text']}],
                 'answers': ['q1']}
        bundle = {'brief': brief, 'sources': [self.health],
                  'plan': {'title': '목포 자체사업 안내', 'lead': block,
                           'sections': [{'heading': '지원 대상', 'paragraphs': [block]}], 'faq': []},
                  'temporal_source': {'evidence': []}}
        result = validate_bundle(bundle, {'checked_on': NOW.date().isoformat(), 'posts': []},
                                 now=NOW, require_review=False)
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn(REASON, result['reasons'])


if __name__ == '__main__':
    unittest.main()
