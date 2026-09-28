"""Monthly event roundups bind each dated event without merging unrelated windows."""
import hashlib
import unittest
from datetime import datetime

from agents.editorial import validate_bundle
from agents.temporal_validation import KST, extract_evidence
from tests.test_editorial_system import sample


NOW = datetime(2026, 9, 14, 12, tzinfo=KST)
URL = 'https://www.daejeon.go.kr/events/october'
FIRST = '행사기간: 2026년 10월 2일부터 4일까지\n가을축제는 뿌리공원에서 열립니다.'
SECOND = '행사기간: 2026.10.17 ~ 2026.11.01\n국화축제는 유림공원에서 열립니다.'
SOURCE = FIRST + '\n' + SECOND


def roundup_bundle():
    bundle = sample()
    brief = bundle['brief']
    brief.update(
        id='daejeon-october-roundup-test',
        category_key='life',
        entity='2026년 10월 대전 행사',
        primary_keyword='대전 10월 행사',
        question='10월 대전 행사는 언제 열리나요?',
        angle='공식 일정별 월간 행사 정리',
        official_urls=[URL],
        required_title_terms=['대전', '행사'],
        content_type='dated',
        useful_until='2026-10-31',
        evergreen_reason=None,
        reviewed_at='2026-09-14',
        review_until='2026-09-15',
        reader_questions=[{'id': 'q1', 'question': '10월 대전 행사는 언제 열리나요?'}],
    )
    source = bundle['sources'][0]
    source.update(
        url=URL,
        title='대전 10월 행사',
        text=SOURCE,
        sha256=hashlib.sha256(SOURCE.encode()).hexdigest(),
        source_type='official',
        fetched_at=NOW.isoformat(),
    )
    lead = {
        'text': '대전의 가을 행사는 가을축제와 국화축제로 이어집니다.',
        'evidence': [{'source_id': 's0', 'quote': SOURCE}],
        'answers': ['q1'],
    }
    bundle['plan'] = {
        'title': '2026년 10월 대전 행사 일정',
        'lead': lead,
        'sections': [{
            'heading': '10월 행사 한눈에 보기',
            'kind': 'overview',
            'paragraphs': [],
            'table': {
                'caption': '10월 대전 행사 일정',
                'headers': ['행사', '날짜', '장소'],
                'rows': [
                    {
                        'cells': ['가을축제', '2026년 10월 2~4일', '뿌리공원'],
                        'evidence': [{'source_id': 's0', 'quote': FIRST}],
                        'answers': ['q1'],
                    },
                    {
                        'cells': ['국화축제', '2026.10.17 ~ 2026.11.01', '유림공원'],
                        'evidence': [{'source_id': 's0', 'quote': SECOND}],
                        'answers': ['q1'],
                    },
                ],
            },
        }],
        'faq': [],
    }
    bundle['temporal_source'] = {
        'multi_event_schedule': True,
        'evidence': extract_evidence(SOURCE, URL),
        'event_entries': [
            {
                'name': '가을축제',
                'start_date': '2026-10-02',
                'end_date': '2026-10-04',
                'evidence': {'source_id': 's0', 'quote': FIRST},
            },
            {
                'name': '국화축제',
                'start_date': '2026-10-17',
                'end_date': '2026-11-01',
                'evidence': {'source_id': 's0', 'quote': SECOND},
            },
        ],
    }
    return bundle


class MultiEventScheduleTests(unittest.TestCase):
    def reasons(self, bundle=None, now=NOW):
        bundle = bundle or roundup_bundle()
        inventory = {'checked_on': now.date().isoformat(), 'posts': []}
        return validate_bundle(bundle, inventory, now, require_review=False)['reasons']

    def test_multiple_official_event_ranges_can_share_one_roundup(self):
        self.assertEqual([], self.reasons())

    def test_forged_event_date_is_rejected(self):
        bundle = roundup_bundle()
        bundle['temporal_source']['event_entries'][0]['end_date'] = '2026-10-05'
        self.assertIn('multi_event_schedule_date_or_evidence_unverified', self.reasons(bundle))

    def test_entry_must_be_visible_in_article(self):
        bundle = roundup_bundle()
        bundle['temporal_source']['event_entries'][0]['name'] = '숨겨진축제'
        self.assertIn('multi_event_schedule_entry_invalid', self.reasons(bundle))

    def test_roundup_useful_until_cannot_outlive_all_events(self):
        bundle = roundup_bundle()
        bundle['brief']['useful_until'] = '2026-11-15'
        self.assertIn('multi_event_schedule_useful_until_unbound', self.reasons(bundle))

    def test_roundup_still_obeys_minimum_remaining_lifetime(self):
        self.assertIn(
            'source_deadline_too_close',
            self.reasons(now=datetime(2026, 10, 10, 12, tzinfo=KST)),
        )

    def test_mode_does_not_bypass_concert_sale_contract(self):
        bundle = roundup_bundle()
        bundle['brief']['category_key'] = 'concert'
        self.assertIn('multi_event_schedule_not_for_this_topic', self.reasons(bundle))

    def test_without_roundup_mode_conflicting_periods_still_fail_closed(self):
        bundle = roundup_bundle()
        bundle['temporal_source'].pop('multi_event_schedule')
        self.assertIn('availability_not_verified', self.reasons(bundle))


if __name__ == '__main__':
    unittest.main()
