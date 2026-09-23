"""National flu season dates require August period AND September supersession."""
import copy
import unittest
from datetime import datetime

from agents.temporal_validation import KST, validate_legacy_reference_period


PERIOD = ('질병관리청은 오는 9월 21일(월)부터 2027년 4월 30일(금)까지 '
          '’26-’27절기 인플루엔자 국가예방접종을 시작할 계획이라고 밝혔다.')
CHILD = ('- 1회 접종 어린이  9월 28일에서  21일로 조정, '
         '모든 어린이와   임신부 접종  21일 시작')
ELDER = ('또한, 어르신의 경우 75세 이상 10월 6일(화), '
         '70~74세 10월 12일(월), 65~69세 10월 15일(목) 순으로 접종 시작')
PERIOD_URL = 'https://www.kdca.go.kr/bbs/kdca/42/312308/artclView.do'
CHANGE_URL = 'https://www.kdca.go.kr/bbs/kdca/42/309764/download.do'
NOW = datetime(2026, 9, 23, 9, tzinfo=KST)


def sample(post_id=63):
    period = {'id': 's1', 'url': PERIOD_URL, 'source_type': 'official',
              'text': '작성일 2026.08.25\n' + PERIOD}
    latest = {'id': 's0', 'url': CHANGE_URL, 'source_type': 'official',
              'text': '보도시점 2026. 9. 16.\n' + CHILD + '\n' + ELDER}
    brief = {'existing_post_id': post_id, 'category_key': 'life-health',
             'content_type': 'dated', 'official_urls': [CHANGE_URL, PERIOD_URL],
             'useful_until': '2027-04-30'}
    plan = {'title': '독감 무료 예방접종 안내',
            'lead': {'text': ('9월 21일 어린이 시작, 어르신 75세 이상 10월 6일·'
                              '70~74세 10월 12일·65~69세 10월 15일 시작')}}
    info = {'legacy_reference_period': {
        'kind': 'national_flu_season', 'start_date': '2026-09-21',
        'end_date': '2027-04-30', 'evidence': {'source_id': 's1', 'quote': PERIOD},
        'schedule_evidence': {'child': {'source_id': 's0', 'quote': CHILD},
                              'elder': {'source_id': 's0', 'quote': ELDER}}}}
    return brief, [latest, period], info, plan


def reasons(case):
    return validate_legacy_reference_period(*case, NOW)


class NationalFluReferenceTests(unittest.TestCase):
    def test_both_specific_existing_posts_require_both_versions(self):
        for post_id in (63, 81):
            with self.subTest(post_id=post_id):
                self.assertEqual([], reasons(sample(post_id)))

    def test_unrelated_post_cannot_reuse_new_exception(self):
        self.assertIn('legacy_reference_period_not_for_this_existing_post', reasons(sample(103)))

    def test_missing_supersession_or_wrong_lead_fails_closed(self):
        cases = []
        no_revision = sample()
        no_revision[1][0]['text'] = CHILD
        cases.append(no_revision)
        wrong_lead = sample()
        wrong_lead[3]['lead']['text'] = '기존 10월 12일에 75세 이상 접종 시작'
        cases.append(wrong_lead)
        no_child = sample()
        no_child[2]['legacy_reference_period']['schedule_evidence']['child']['quote'] = '가짜 인용'
        cases.append(no_child)
        wrong_source = sample()
        wrong_source[1][0]['url'] = 'https://example.org/unverified.pdf'
        cases.append(wrong_source)
        for index, case in enumerate(cases):
            with self.subTest(case=index):
                self.assertIn('legacy_national_flu_season_not_officially_bound', reasons(case))

    def test_wrong_period_or_misleading_open_statement_fails(self):
        case = sample()
        case[2]['legacy_reference_period']['end_date'] = '2027-05-01'
        self.assertIn('legacy_national_flu_season_not_officially_bound', reasons(case))
        case = sample()
        case[3]['lead']['text'] += '. 현재 모든 대상 접종 가능합니다.'
        self.assertIn('legacy_reference_period_misleading_current_status', reasons(case))


if __name__ == '__main__':
    unittest.main()
