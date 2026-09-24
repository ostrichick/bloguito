"""Evidence-based year/season references never assert open applications."""

import hashlib
import unittest
from datetime import datetime

from agents.editorial import validate_bundle
from agents.temporal_validation import KST, validate_legacy_reference_period


NOW = datetime(2026, 9, 22, 13, tzinfo=KST)
PENSION_URL = 'https://basicpension.mohw.go.kr/menu.es?mid=a10103010000'
PENSION_QUOTE = '※ 2026년 1월 ~ 2026년 12월: 월 349,700원'
MOKPO_URL = 'https://www.mokpo.go.kr/health/citizen_participation/notice?idx=548678&mode=view'
FLU_QUOTE = '- 접종일정: 2026. 9. 21.(월) ~ 2027. 4. 30.(금)'
HEALTH_URL = 'https://www.nhis.or.kr/nhis/minwon/wbhapa01000m01.do?mode=view&articleNo=10946900'
HEALTH_PERIOD_QUOTE = ('과도한 의료비로 인한 가계부담 완화를 위하여 가입자(피부양자 포함)가 '
                       '연간(1.1.~12.31.) 요양기관에 지출한 본인 일부부담금총액이 개인별 본인부담 상한액을 초과하는 경우')
HEALTH_VALUES_QUOTE = ('2026년 90만원 112만원 173만원 326만원 446만원 536만원 843만원 '
                       '요양병원 120일 초과 입원 143만원 181만원 245만원 404만원 580만원 698만원 1,096만원')


def case(post_id=55):
    flu = post_id == 103
    quote = FLU_QUOTE if flu else PENSION_QUOTE
    url = MOKPO_URL if flu else PENSION_URL
    category = 'life-health' if flu else 'welfare'
    until = '2027-04-30' if flu else '2026-12-31'
    start = '2026-09-21' if flu else '2026-01-01'
    source_text = (('목포 2026-2027절기 어린이 임신부 어르신 접종 안내. ' * 2)
                   if flu else ('기초연금 2026년 기준연금액 349700원, 선정기준액 '
                                '단독가구 247만 원·부부가구 395만 2천 원. ' * 2)) + quote
    proof = {'source_id': 's0', 'quote': quote}
    brief = {'id': 'legacy-test', 'existing_post_id': post_id,
             'category_key': category, 'approved': True,
             'entity': '독감' if flu else '기초연금',
             'primary_keyword': '목포 독감 무료접종' if flu else '기초연금 신청',
             'question': '언제 적용하나요?', 'angle': '공식 기준기간별 현행 정보',
             'official_urls': [url],
             'required_title_terms': ['독감'] if flu else ['기초연금'],
             'reader_questions': [{'id': 'q1', 'question': '언제 적용하나요?'}],
             'reviewed_at': '2026-09-22', 'review_until': '2026-09-23',
             'content_type': 'dated', 'useful_until': until}
    lead = {'text': ('독감 무료접종 일정은 2026년 9월 21일부터 2027년 4월 30일까지입니다.'
                     if flu else '2026년 기초연금 기준연금액은 월 349,700원입니다.'),
            'evidence': [proof], 'answers': ['q1']}
    plan = {'title': ('목포 독감 무료접종 안내' if flu else '2026 기초연금 신청 안내'),
            'lead': lead, 'sections': [{'heading': '공식 적용기간',
             'paragraphs': [lead]}], 'faq': []}
    source = {'id': 's0', 'url': url, 'source_type': 'official',
              'title': '공식 안내', 'text': source_text,
              'sha256': hashlib.sha256(source_text.encode()).hexdigest(),
              'fetched_at': NOW.isoformat()}
    temporal = {'evidence': [], 'legacy_reference_period': {
        'kind': 'flu_season' if flu else 'annual_pension',
        'start_date': start, 'end_date': until, 'evidence': proof}}
    return {'brief': brief, 'sources': [source], 'plan': plan,
            'temporal_source': temporal}


def health_case():
    source_text = f'{HEALTH_PERIOD_QUOTE}\n진료연도별 본인부담상한액(2023~2026년)\n{HEALTH_VALUES_QUOTE}'
    period = {'source_id': 's0', 'quote': HEALTH_PERIOD_QUOTE}
    values = {'source_id': 's0', 'quote': HEALTH_VALUES_QUOTE}
    brief = {'id': 'legacy-health-220', 'existing_post_id': 220,
             'category_key': 'welfare', 'approved': True,
             'entity': '국민건강보험 본인부담상한제',
             'primary_keyword': '2026 본인부담상한제 환급금',
             'question': '2026년 진료분 상한액은 얼마인가요?',
             'angle': '진료연도 기준 상한액과 환급 절차',
             'official_urls': [HEALTH_URL],
             'required_title_terms': ['2026', '본인부담상한제'],
             'reader_questions': [{'id': 'q1', 'question': '2026년 진료분 상한액은 얼마인가요?'}],
             'reviewed_at': '2026-09-22', 'review_until': '2026-09-23',
             'content_type': 'dated', 'useful_until': '2026-12-31'}
    lead = {'text': '2026년 진료분의 진료연도 본인부담상한액은 소득분위별로 다릅니다.',
            'evidence': [values], 'answers': ['q1']}
    plan = {'title': '2026 본인부담상한제 환급금 안내', 'lead': lead,
            'sections': [{'heading': '2026년 진료연도 상한액', 'paragraphs': [lead]}],
            'faq': []}
    source = {'id': 's0', 'url': HEALTH_URL, 'source_type': 'official',
              'title': '본인부담상한제', 'text': source_text,
              'sha256': hashlib.sha256(source_text.encode()).hexdigest(),
              'fetched_at': NOW.isoformat()}
    temporal = {'evidence': [], 'legacy_reference_period': {
        'kind': 'annual_health_ceiling', 'start_date': '2026-01-01',
        'end_date': '2026-12-31', 'evidence': period, 'values_evidence': values}}
    return {'brief': brief, 'sources': [source], 'plan': plan,
            'temporal_source': temporal}


class LegacyReferencePeriodTests(unittest.TestCase):
    def reasons(self, b):
        return validate_legacy_reference_period(b['brief'], b['sources'],
                      b['temporal_source'], b['plan'], NOW)

    def test_annual_pension_year_explicitly_quoted_and_reviewable(self):
        for post_id in (55, 79, 101):
            with self.subTest(post_id=post_id):
                b = case(post_id)
                self.assertEqual([], self.reasons(b))
                result = validate_bundle(b, {'checked_on': '2026-09-22', 'posts': []},
                                         NOW, require_review=False)
                self.assertEqual('ready', result['status'], result)

    def test_annual_health_ceiling_is_bound_to_current_nhis_year(self):
        b = health_case()
        self.assertEqual([], self.reasons(b))
        result = validate_bundle(b, {'checked_on': '2026-09-22', 'posts': []},
                                 NOW, require_review=False)
        self.assertEqual('ready', result['status'], result)
        b['temporal_source']['legacy_reference_period']['values_evidence']['quote'] = \
            HEALTH_VALUES_QUOTE.replace('843만원', '826만원')
        self.assertIn('legacy_health_ceiling_annual_range_not_officially_bound', self.reasons(b))

    def test_official_mokpo_season_dates_reviewable_without_universal_claim(self):
        b = case(103)
        self.assertEqual([], self.reasons(b))
        self.assertEqual('ready', validate_bundle(b,
            {'checked_on': '2026-09-22', 'posts': []}, NOW,
            require_review=False)['status'])

    def test_cannot_use_mode_for_new_or_different_published_post(self):
        for post_id in (None, 219, 137):
            b = case(55)
            if post_id is None:
                b['brief'].pop('existing_post_id')
            else:
                b['brief']['existing_post_id'] = post_id
            self.assertIn('legacy_reference_period_not_for_this_existing_post',
                          self.reasons(b))

    def test_fabricated_quote_wrong_year_or_excess_lifetime_fail(self):
        b = case(55)
        b['temporal_source']['legacy_reference_period']['evidence']['quote'] += ' 허위'
        self.assertIn('legacy_reference_period_dates_or_source_unverified',
                      self.reasons(b))
        b = case(55)
        b['temporal_source']['legacy_reference_period']['end_date'] = '2027-12-31'
        self.assertIn('legacy_pension_annual_range_not_officially_bound', self.reasons(b))
        b = case(55)
        b['brief']['useful_until'] = '2027-01-01'
        self.assertIn('legacy_reference_period_useful_until_invalid', self.reasons(b))

    def test_season_old_or_changed_dates_fail(self):
        b = case(103)
        b['temporal_source']['legacy_reference_period']['start_date'] = '2026-09-28'
        self.assertIn('legacy_flu_season_range_not_officially_bound', self.reasons(b))
        b = case(103)
        b['temporal_source']['legacy_reference_period']['end_date'] = '2027-05-01'
        self.assertIn('legacy_flu_season_range_not_officially_bound', self.reasons(b))

    def test_no_context_remains_blocked_and_false_open_claim_fails(self):
        b = case(55)
        b['temporal_source'] = {'evidence': []}
        self.assertIn('availability_not_verified', validate_bundle(b,
            {'checked_on': '2026-09-22', 'posts': []}, NOW,
            require_review=False)['reasons'])
        b = case(103)
        b['plan']['lead']['text'] += ' 현재 모든 대상 접종 가능합니다.'
        self.assertIn('legacy_reference_period_misleading_current_status', self.reasons(b))

    def test_past_year_or_less_than_thirty_days_is_not_current(self):
        b = case(55)
        future = datetime(2026, 12, 20, 13, tzinfo=KST)
        self.assertIn('legacy_reference_period_not_current_or_too_short',
            validate_legacy_reference_period(b['brief'], b['sources'],
                b['temporal_source'], b['plan'], future))


if __name__ == '__main__':
    unittest.main()
