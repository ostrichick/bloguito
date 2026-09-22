"""An archived application with cited later routes must not spoof an open window."""
import copy
import hashlib
import unittest
from datetime import datetime

from agents.editorial import validate_bundle
from agents.temporal_validation import KST, validate_legacy_followup

NOW = datetime(2026, 9, 22, 12, tzinfo=KST)
URL = 'https://www.nts.go.kr/nts/notice/2026'
ENDED = ('국세청은 2026년 9월 1일부터 9월 15일까지 근로장려금 상반기 신청을 받았습니다.')
MARCH = ('상반기분 신청을 놓친 경우 하반기 신청(’27.3.1.~3.15.) 또는 '
         '정기 신청(’27.5.1.~5.31.) 기간에 신청할 수 있습니다.')
LATE = ('정기 신청도 놓쳤다면 ’27년 11월 30일까지 기한 후 신청할 수 있습니다.')


def sample():
    text = '\n'.join((ENDED, MARCH, LATE, '신청요건에 맞는 가구에만 적용됩니다.'))
    quote = lambda value: {'source_id': 's0', 'quote': value}
    brief = {'id': 'archive-137', 'existing_post_id': 137, 'category_key': 'welfare',
             'approved': True, 'entity': '근로장려금',
             'primary_keyword': '2026년 근로장려금 다음 신청',
             'question': '놓쳤다면 언제 신청하나요?', 'angle': '종료된 접수 이후 경로',
             'official_urls': [URL], 'required_title_terms': ['근로장려금'],
             'reviewed_at': '2026-09-22', 'review_until': '2026-10-01',
             'content_type': 'dated', 'useful_until': '2027-11-30',
             'reader_questions': [{'id': 'q1', 'question': '놓쳤다면 언제 신청하나요?'}]}
    lead = {'text': '2026년 9월 15일 상반기 신청은 종료됐습니다.',
            'evidence': [quote(ENDED)], 'answers': ['q1']}
    plan = {'title': '2026년 근로장려금 다음 신청 안내', 'lead': lead,
            'sections': [{'heading': '다음 신청기간', 'paragraphs': [
                {'text': MARCH,
                 'evidence': [quote(MARCH)], 'answers': ['q1']}]}], 'faq': []}
    source = {'id': 's0', 'url': URL, 'title': '국세청 안내', 'text': text,
              'source_type': 'official', 'sha256': hashlib.sha256(text.encode()).hexdigest(),
              'fetched_at': NOW.isoformat()}
    followup = {'ended': {'end_date': '2026-09-15', 'evidence': quote(ENDED)},
                'next_windows': [
                    {'start_date': '2027-03-01', 'end_date': '2027-03-15', 'evidence': quote(MARCH)},
                    {'start_date': '2027-05-01', 'end_date': '2027-05-31', 'evidence': quote(MARCH)},
                    {'end_date': '2027-11-30', 'evidence': quote(LATE)}]}
    bundle = {'brief': brief, 'sources': [source], 'plan': plan,
              'temporal_source': {'evidence': [], 'legacy_followup': followup}}
    return bundle


class LegacyTemporalLifecycleTests(unittest.TestCase):
    def test_closed_application_with_real_future_routes_is_reviewable(self):
        bundle = sample()
        self.assertEqual([], validate_legacy_followup(bundle['brief'], bundle['sources'],
                         bundle['temporal_source'], bundle['plan'], NOW))
        report = validate_bundle(bundle, {'checked_on': '2026-09-22', 'posts': []},
                                 NOW, require_review=False)
        self.assertEqual('ready', report['status'], report)

    def test_new_article_cannot_use_existing_post_lifecycle(self):
        bundle = sample()
        bundle['brief'].pop('existing_post_id')
        self.assertIn('legacy_followup_not_for_existing_welfare_post',
                      validate_legacy_followup(bundle['brief'], bundle['sources'],
                                               bundle['temporal_source'], bundle['plan'], NOW))

    def test_fabricated_or_modified_quote_is_rejected(self):
        bundle = sample()
        bundle['temporal_source']['legacy_followup']['next_windows'][0]['evidence']['quote'] = (
            '가짜 자료에 따르면 하반기 신청(’27.3.1.~3.15.)입니다.')
        self.assertIn('legacy_followup_date_or_evidence_unverified',
                      validate_legacy_followup(bundle['brief'], bundle['sources'],
                                               bundle['temporal_source'], bundle['plan'], NOW))

    def test_wrong_year_and_deadline_are_rejected(self):
        bundle = sample()
        bundle['temporal_source']['legacy_followup']['next_windows'][0]['end_date'] = '2028-03-15'
        self.assertIn('legacy_followup_date_or_evidence_unverified',
                      validate_legacy_followup(bundle['brief'], bundle['sources'],
                                               bundle['temporal_source'], bundle['plan'], NOW))
        bundle = sample()
        bundle['brief']['useful_until'] = '2028-01-01'
        self.assertIn('legacy_followup_useful_after_last_official_window',
                      validate_legacy_followup(bundle['brief'], bundle['sources'],
                                               bundle['temporal_source'], bundle['plan'], NOW))

    def test_closed_application_cannot_be_called_open(self):
        bundle = sample()
        bundle['plan']['lead']['text'] += ' 현재 신청 가능합니다.'
        self.assertIn('legacy_followup_misleading_open_claim',
                      validate_legacy_followup(bundle['brief'], bundle['sources'],
                                               bundle['temporal_source'], bundle['plan'], NOW))

    def test_no_lifecycle_cannot_bypass_normal_availability_check(self):
        bundle = sample()
        bundle['temporal_source'] = {'evidence': []}
        report = validate_bundle(bundle, {'checked_on': '2026-09-22', 'posts': []},
                                 NOW, require_review=False)
        self.assertIn('availability_not_verified', report['reasons'])


if __name__ == '__main__':
    unittest.main()
