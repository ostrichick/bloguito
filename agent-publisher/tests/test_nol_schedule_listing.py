"""NOL product pages may prove legacy event schedules, never live inventory."""
import hashlib
import unittest

from agents.editorial import validate_bundle
from agents.temporal_validation import extract_nol_product_schedule
from tests.test_editorial_system import NOW, sample, sign


URL = 'https://nol.yanolja.com/ticket/products/26013136'
SOURCE = '''2026 무명전설 크리스마스 콘서트 - 수원앵콜 콘서트 일정 및 예매 | NOL(야놀자)
장소
수원컨벤션센터
기간
2026.12.25
시간
120분
상품 상세
가격
R석
154,000
원
'''


class NolProductScheduleParserTests(unittest.TestCase):
    def test_single_day_product_schedule(self):
        self.assertEqual(
            [{'region': '수원', 'date': '2026.12.25', 'venue': '수원컨벤션센터'}],
            extract_nol_product_schedule(SOURCE, '무명전설', '수원'))

    def test_multi_day_product_schedule(self):
        text = SOURCE.replace('무명전설', '로이킴').replace('수원앵콜', '서울').replace(
            '수원컨벤션센터', 'KSPO DOME').replace('2026.12.25', '2026.11.21 ~ 2026.11.22')
        self.assertEqual(
            [{'region': '서울', 'date': '2026.11.21', 'venue': 'KSPO DOME'},
             {'region': '서울', 'date': '2026.11.22', 'venue': 'KSPO DOME'}],
            extract_nol_product_schedule(text, '로이킴', '서울'))

    def test_artist_and_region_are_source_bound(self):
        self.assertEqual([], extract_nol_product_schedule(SOURCE, '다른가수', '수원'))
        self.assertEqual([], extract_nol_product_schedule(SOURCE, '무명전설', '서울'))

    def test_long_generic_range_is_rejected(self):
        text = SOURCE.replace('2026.12.25', '2026.12.01 ~ 2026.12.25')
        self.assertEqual([], extract_nol_product_schedule(text, '무명전설', '수원'))

    def test_conflicting_venue_is_rejected(self):
        text = SOURCE + '장소\n다른공연장\n'
        self.assertEqual([], extract_nol_product_schedule(text, '무명전설', '수원'))


class NolExistingPostListingModeTests(unittest.TestCase):
    def setUp(self):
        self.bundle = sample()
        self.bundle['brief'].update(
            category_key='concert', entity='무명전설 수원앵콜', content_type='dated',
            useful_until='2026-12-25', official_urls=[URL], existing_post_id=70,
            required_title_terms=['무명전설', '수원앵콜'])
        source = self.bundle['sources'][0]
        source.update(url=URL, text=SOURCE, sha256=hashlib.sha256(SOURCE.encode()).hexdigest())
        source['actions'] = [{'kind': 'booking', 'label': '공식 상품 확인', 'url': URL}]
        schedule_quote = '장소\n수원컨벤션센터\n기간\n2026.12.25'
        self.bundle['plan']['title'] = '2026 무명전설 수원앵콜 콘서트'
        self.bundle['plan']['lead'] = {
            'text': '무명전설 수원앵콜 공연은 수원컨벤션센터에서 열립니다.',
            'evidence': [{'source_id': 's0', 'quote': schedule_quote}], 'answers': ['q1']}
        self.bundle['plan']['sections'] = [{
            'heading': '공연 일정', 'paragraphs': [],
            'table': {'caption': '공연 일정', 'headers': ['지역', '날짜', '공연장'], 'rows': [{
                'cells': ['수원', '2026.12.25', '수원컨벤션센터'],
                'evidence': [{'source_id': 's0', 'quote': schedule_quote}], 'answers': ['q1']}]}},
        ]
        self.bundle['temporal_source'] = {
            'legacy_nol_product_listing': True, 'requires_sale': False,
            'listing_source_url': URL, 'region_hint': '수원',
            'listing_entries': extract_nol_product_schedule(SOURCE, '무명전설', '수원'),
            'evidence': [],
        }
        self.inventory = {'checked_on': '2026-09-14', 'posts': []}

    def reasons(self):
        sign(self.bundle)
        return validate_bundle(self.bundle, self.inventory, NOW, require_review=False)['reasons']

    def test_existing_post_schedule_is_allowed_without_sale_claim(self):
        self.assertEqual([], self.reasons())

    def test_new_post_cannot_use_nol_listing_exception(self):
        self.bundle['brief'].pop('existing_post_id')
        self.assertIn('schedule_listing_provenance_missing', self.reasons())

    def test_other_existing_post_cannot_use_nol_listing_exception(self):
        self.bundle['brief']['existing_post_id'] = 1234
        self.assertIn('schedule_listing_provenance_missing', self.reasons())

    def test_generic_schedule_listing_flag_cannot_open_nol_exception(self):
        self.bundle['temporal_source'].pop('legacy_nol_product_listing')
        self.bundle['temporal_source']['schedule_listing_only'] = True
        self.assertIn('schedule_listing_provenance_missing', self.reasons())

    def test_non_product_nol_url_is_rejected(self):
        bad = 'https://nol.yanolja.com/discovery/list/search/PRODUCT_CATEGORY_ENTERTAINMENT'
        self.bundle['brief']['official_urls'] = [bad]
        self.bundle['sources'][0]['url'] = bad
        self.bundle['temporal_source']['listing_source_url'] = bad
        self.assertIn('schedule_listing_provenance_missing', self.reasons())

    def test_live_sale_language_still_fails(self):
        self.bundle['plan']['lead']['text'] += ' 지금 예매 중입니다.'
        self.assertIn('sale_status_claim_without_evidence', self.reasons())

    def test_seat_availability_language_still_fails(self):
        self.bundle['plan']['lead']['text'] += ' 남은 좌석을 바로 예매할 수 있습니다.'
        self.assertIn('sale_status_claim_without_evidence', self.reasons())

    def test_wrong_title_contract_is_rejected(self):
        self.bundle['brief']['required_title_terms'] = ['무명전설']
        self.assertIn('schedule_listing_provenance_missing', self.reasons())

    def test_wrong_venue_is_rejected(self):
        self.bundle['sources'][0]['text'] = SOURCE.replace('수원컨벤션센터', '다른공연장')
        self.bundle['sources'][0]['sha256'] = hashlib.sha256(
            self.bundle['sources'][0]['text'].encode()).hexdigest()
        self.bundle['temporal_source']['listing_entries'] = extract_nol_product_schedule(
            self.bundle['sources'][0]['text'], '무명전설', '수원')
        self.assertIn('schedule_listing_provenance_missing', self.reasons())

    def test_sale_evidence_conflict_holds_legacy_mode(self):
        self.bundle['sources'][0]['text'] += '\n예매상태: 판매중'
        self.bundle['sources'][0]['sha256'] = hashlib.sha256(
            self.bundle['sources'][0]['text'].encode()).hexdigest()
        self.assertIn('schedule_listing_provenance_missing', self.reasons())

    def test_wrong_useful_until_is_rejected(self):
        self.bundle['brief']['useful_until'] = '2026-12-26'
        self.assertIn('schedule_listing_not_bound', self.reasons())


if __name__ == '__main__':
    unittest.main()
