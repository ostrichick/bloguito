"""Schedule-only YES24 evidence cannot be passed off as live ticket inventory."""
import hashlib
import unittest
from datetime import datetime

from agents.editorial import validate_bundle
from agents.temporal_validation import (KST, extract_ticketlink_bridge_schedule,
                                        extract_yes24_schedule)
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

    def test_yes24_binding_allows_columns_after_region_date_venue(self):
        table = self.bundle['plan']['sections'][0]['table']
        table['headers'].append('공연 시작시간')
        table['rows'][0]['cells'].append('오후 6시')
        table['rows'][1]['cells'].append('오후 5시')
        self.assertNotIn('schedule_listing_not_bound', self.check())

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


class TicketlinkScheduleListingTests(unittest.TestCase):
    def test_bridge_parser_keeps_only_booking_rows_for_artist(self):
        source = ('지역/제목\n경기\n[데뷔 60주년 기념공연] 2026 남진 전국투어 콘서트 - 평택\n'
                  '기간\n2026.10.11 ~\n2026.10.11\n장소\n평택아트센터 대공연장\n예매하기\n'
                  '지역/제목\n전북\n[데뷔 60주년 기념공연] 2026 남진 전국투어 콘서트 - 김제\n'
                  '기간\n2026.11.21 ~\n2026.11.21\n장소\n김제문화예술회관 대공연장\n판매 예정\n')
        self.assertEqual(
            [{'region': '경기', 'date': '2026.10.11', 'venue': '평택아트센터 대공연장'}],
            extract_ticketlink_bridge_schedule(source, '남진'))

    def test_ticketlink_binding_allows_time_column_between_date_and_venue(self):
        bundle = sample()
        url = 'https://www.ticketlink.co.kr/bridge/901'
        source_text = ('지역/제목\n경기\n[데뷔 60주년 기념공연] 2026 남진 전국투어 콘서트 - 평택\n'
                       '기간\n2026.10.11 ~\n2026.10.11\n장소\n평택아트센터 대공연장\n예매하기')
        bundle['brief'].update(category_key='concert', entity='남진 데뷔 60주년 전국투어',
                               content_type='dated', useful_until='2026-10-11', official_urls=[url])
        bundle['sources'][0].update(url=url, text=source_text,
                                    sha256=hashlib.sha256(source_text.encode()).hexdigest())
        entire = [{'source_id': 's0', 'quote': source_text}]
        bundle['plan']['lead'] = {'text': '남진 평택 공연은 2026년 10월 11일에 열립니다.',
                                  'evidence': entire, 'answers': ['q1']}
        bundle['plan']['sections'] = [{
            'heading': '공연 일정', 'paragraphs': [],
            'table': {'caption': '공연 일정', 'headers': ['지역', '날짜', '공연시간', '공연장'], 'rows': [{
                'cells': ['평택', '2026.10.11', '오후 5시', '평택아트센터 대공연장'],
                'evidence': entire, 'answers': ['q1']}]}},
        ]
        bundle['temporal_source'] = {
            'schedule_listing_only': True, 'requires_sale': False,
            'listing_source_url': url,
            'listing_entries': extract_ticketlink_bridge_schedule(source_text, '남진'),
            'evidence': [],
        }
        sign(bundle)
        reasons = validate_bundle(bundle, {'checked_on': '2026-09-14', 'posts': []}, NOW,
                                  require_review=False)['reasons']
        self.assertNotIn('schedule_listing_not_bound', reasons)

    def test_bridge_province_can_bind_to_city_schedule_by_exact_date_and_venue(self):
        url = 'https://www.ticketlink.co.kr/bridge/901'
        source_text = (
            '지역/제목\n경기\n[데뷔 60주년 기념공연] 2026 남진 전국투어 콘서트 - 평택\n'
            '기간\n2026.10.11 ~\n2026.10.11\n장소\n평택아트센터 대공연장\n예매하기\n'
            '지역/제목\n전북\n[데뷔 60주년 기념공연] 2026 남진 전국투어 콘서트 - 김제\n'
            '기간\n2026.11.21 ~\n2026.11.21\n장소\n김제문화예술회관 대공연장\n예매하기')
        bundle = sample()
        bundle['brief'].update(
            category_key='concert', entity='남진 데뷔 60주년 전국투어',
            content_type='dated', useful_until='2026-11-21', official_urls=[url],
            required_title_terms=['남진'], existing_post_id=463)
        src = bundle['sources'][0]
        src.update(url=url, text=source_text,
                   sha256=hashlib.sha256(source_text.encode()).hexdigest())
        evidence = [{'source_id': 's0', 'quote': source_text}]
        bundle['plan']['title'] = '2026 남진 데뷔 60주년 전국투어'
        bundle['plan']['lead'] = {
            'text': '남진 공연은 평택과 김제에서 열립니다.',
            'evidence': evidence, 'answers': ['q1']}
        bundle['plan']['sections'] = [{
            'heading': '지역별 공연 일정', 'paragraphs': [],
            'table': {'caption': '지역별 공연 일정', 'headers': ['지역', '날짜', '공연장'],
                      'rows': [
                          {'cells': ['평택', '2026.10.11', '평택아트센터 대공연장'],
                           'evidence': evidence, 'answers': ['q1']},
                          {'cells': ['김제', '2026.11.21', '김제문화예술회관 대공연장'],
                           'evidence': evidence, 'answers': ['q1']},
                      ]},
        }]
        bundle['temporal_source'] = {
            'schedule_listing_only': True, 'requires_sale': False,
            'listing_source_url': url,
            'listing_entries': extract_ticketlink_bridge_schedule(source_text, '남진'),
            'evidence': [],
        }
        inventory = {'checked_on': '2026-09-14', 'posts': []}
        sign(bundle)
        self.assertEqual([], validate_bundle(
            bundle, inventory, NOW, require_review=False)['reasons'])

    def test_bridge_still_rejects_wrong_city_venue(self):
        url = 'https://www.ticketlink.co.kr/bridge/901'
        source_text = ('지역/제목\n경기\n2026 남진 전국투어 콘서트 - 평택\n'
                       '기간\n2026.10.11 ~\n2026.10.11\n장소\n평택아트센터 대공연장\n예매하기')
        bundle = sample()
        bundle['brief'].update(
            category_key='concert', entity='남진 전국투어', content_type='dated',
            useful_until='2026-11-21', official_urls=[url], required_title_terms=['남진'])
        src = bundle['sources'][0]
        src.update(url=url, text=source_text,
                   sha256=hashlib.sha256(source_text.encode()).hexdigest())
        evidence = [{'source_id': 's0', 'quote': source_text}]
        bundle['plan']['title'] = '2026 남진 전국투어'
        bundle['plan']['lead'] = {
            'text': '남진 공연은 평택에서 열립니다.', 'evidence': evidence, 'answers': ['q1']}
        bundle['plan']['sections'] = [{
            'heading': '공연 일정', 'paragraphs': [],
            'table': {'caption': '공연 일정', 'headers': ['지역', '날짜', '공연장'], 'rows': [{
                'cells': ['평택', '2026.10.11', '다른공연장'],
                'evidence': evidence, 'answers': ['q1']}]}},
        ]
        bundle['temporal_source'] = {
            'schedule_listing_only': True, 'requires_sale': False,
            'listing_source_url': url,
            'listing_entries': extract_ticketlink_bridge_schedule(source_text, '남진'),
            'evidence': [],
        }
        inventory = {'checked_on': '2026-09-14', 'posts': []}
        sign(bundle)
        self.assertIn('schedule_listing_not_bound', validate_bundle(
            bundle, inventory, NOW, require_review=False)['reasons'])


if __name__ == '__main__':
    unittest.main()
