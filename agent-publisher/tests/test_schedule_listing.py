"""Schedule-only YES24 evidence cannot be passed off as live ticket inventory."""
import hashlib
import unittest
from datetime import datetime

from agents.editorial import validate_bundle
from agents.temporal_validation import KST, extract_yes24_schedule
from tests.test_editorial_system import NOW, sample, sign

URL = 'https://m.ticket.yes24.com/Genre/GenreBridge.aspx?genre=15456&id=1560'
SOURCE = ('[대구] 김건모. 35TH ANNIVERSARY LIVE TOUR\n'
          '2026.10.10 ~ 2026.10.10ㅣ대구 엑스코 동관 6홀\n예매\n'
          '[고양] 김건모. 35TH ANNIVERSARY LIVE TOUR\n'
          '2026.12.26 ~ 2026.12.26ㅣ킨텍스 2전시장 9A홀\n예매')


class ScheduleListingTests(unittest.TestCase):
    def setUp(self):
        self.bundle = sample()
        brief = self.bundle['brief']
        brief.update(category_key='concert', entity='김건모 35주년 콘서트',
                     content_type='dated', useful_until='2026-12-26', official_urls=[URL])
        source = self.bundle['sources'][0]
        source.update(url=URL, text=SOURCE, sha256=hashlib.sha256(SOURCE.encode()).hexdigest())
        entire = [{'source_id': 's0', 'quote': SOURCE}]
        self.bundle['plan']['lead'] = {'text': '김건모 공연은 대구와 고양에서 열립니다.',
                                      'evidence': entire, 'answers': ['q1']}
        self.bundle['plan']['sections'] = [{
            'heading': '지역별 공연 일정', 'paragraphs': [],
            'table': {'caption': '지역별 공연 일정', 'headers': ['지역', '날짜', '공연장'],
                      'rows': [
                          {'cells': ['대구', '2026.10.10', '대구 엑스코 동관 6홀'],
                           'evidence': [{'source_id': 's0', 'quote': SOURCE.split('\n[고양]')[0]}], 'answers': ['q1']},
                          {'cells': ['고양', '2026.12.26', '킨텍스 2전시장 9A홀'],
                           'evidence': [{'source_id': 's0', 'quote': '[고양]' + SOURCE.split('[고양]')[1]}],
                           'answers': ['q1']},
                      ]},
        }]
        self.bundle['temporal_source'] = {
            'schedule_listing_only': True, 'requires_sale': False,
            'listing_source_url': URL,
            'listing_entries': extract_yes24_schedule(SOURCE, '김건모'), 'evidence': [],
        }
        self.inventory = {'checked_on': '2026-09-14', 'posts': []}

    def check(self, now=NOW):
        sign(self.bundle)
        return validate_bundle(self.bundle, self.inventory, now, require_review=False)['reasons']

    def test_verified_upcoming_schedule_is_valid_without_sale_deadline(self):
        self.assertEqual([], self.check())

    def test_forged_or_missing_listings_are_rejected(self):
        self.bundle['temporal_source']['listing_entries'][0]['date'] = '2026.10.11'
        self.assertIn('schedule_listing_not_bound', self.check())

    def test_table_row_must_match_official_venue(self):
        self.bundle['plan']['sections'][0]['table']['rows'][0]['cells'][2] = '미확인 공연장'
        self.assertIn('schedule_listing_not_bound', self.check())

    def test_no_live_sale_status_claim_without_sale_evidence(self):
        self.bundle['plan']['lead']['text'] += ' 지금 예매중입니다.'
        self.assertIn('sale_status_claim_without_evidence', self.check())

    def test_wrong_host_cannot_enter_listing_only_mode(self):
        self.bundle['temporal_source']['listing_source_url'] = 'https://example.com/list'
        self.assertIn('schedule_listing_provenance_missing', self.check())

    def test_expired_schedule_is_rejected(self):
        self.assertIn('availability_not_verified', self.check(datetime(2026, 12, 27, tzinfo=KST)))

    def test_short_remaining_lifetime_is_rejected(self):
        self.assertIn('source_deadline_too_close', self.check(datetime(2026, 12, 1, tzinfo=KST)))

    def test_no_dates_for_wrong_artist(self):
        self.assertEqual([], extract_yes24_schedule(SOURCE, '다른가수'))


if __name__ == '__main__':
    unittest.main()
