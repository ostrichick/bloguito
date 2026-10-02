import base64
import copy
import hashlib
import json
import re
import unittest
from unittest.mock import patch

from agents.editorial import render, validate_bundle
from agents.editorial_writer import Plan
from agents.event_post_standard import (
    event_review_instruction,
    event_writer_instruction,
    readable_event_date_label,
    validate_event_post_standard,
)
from agents.temporal_validation import extract_evidence
from tests.test_editorial_system import NOW


def event_bundle():
    source0_text = (
        '가을 체험축제는 2026-10-14 ~ 2026-10-15 서초공원에서 열립니다. '
        '무료로 입장하며 가족이 전통문화 체험과 공연 프로그램에 참여할 수 있습니다. '
        '사전예약은 선택이며 현장 관람이 가능합니다.'
    )
    source1_text = (
        '도심 문화행사는 2026-10-20 ~ 2026-10-20 시민광장에서 열립니다. '
        '전시와 버스킹 공연, 체험 부스를 운영하며 학생과 방문객이 무료로 관람할 수 있습니다. '
        '운영시간은 10:00~18:00이며 대중교통 이용이 편리합니다.'
    )
    sources = [
        {
            'id': 's0',
            'url': 'https://www.seocho.go.kr/event/fall',
            'title': '2026 가을 체험축제 공식 안내',
            'text': source0_text,
            'sha256': hashlib.sha256(source0_text.encode()).hexdigest(),
            'source_type': 'official',
            'fetched_at': NOW.isoformat(),
            'actions': [{
                'label': '가을 체험축제 예약',
                'url': 'https://www.seocho.go.kr/event/fall/apply',
                'kind': 'booking',
            }],
        },
        {
            'id': 's1',
            'url': 'https://www.seocho.go.kr/event/city',
            'title': '2026 도심 문화행사 공식 안내',
            'text': source1_text,
            'sha256': hashlib.sha256(source1_text.encode()).hexdigest(),
            'source_type': 'official',
            'fetched_at': NOW.isoformat(),
        },
    ]
    brief = {
        'id': 'seocho-october-events-2026',
        'category_key': 'events',
        'approved': True,
        'entity': '2026년 10월 서초 지역 행사',
        'primary_keyword': '10월 서초 행사',
        'question': '2026년 10월 서초에서 무엇을 보고 체험할 수 있는 행사가 열리나요?',
        'angle': '서초 10월 행사 일정과 실제 체험, 비용, 장소를 비교한다.',
        'official_urls': [source['url'] for source in sources],
        'required_title_terms': ['2026년 10월', '서초', '행사'],
        'content_type': 'dated',
        'useful_until': '2026-10-20',
        'reviewed_at': NOW.date().isoformat(),
        'review_until': '2026-10-01',
        'reader_questions': [{
            'id': 'q1',
            'question': '2026년 10월 서초 행사의 날짜, 장소와 체험 내용은?',
        }],
        'seo': {
            'title': '10월 서초 행사 2026: 체험축제와 도심 문화행사 일정',
            'description': '10월 서초 행사 날짜, 장소, 무료 여부와 실제 체험 프로그램을 비교합니다.',
        },
        'event_post_standard_version': 1,
    }
    plan = {
        'title': '2026년 10월 서초 행사 총정리',
        'lead': {
            'text': '2026년 10월 서초 행사는 가을 체험축제와 도심 문화행사로 이어지며, 무료 관람과 체험 프로그램을 비교할 수 있습니다.',
            'evidence': [
                {'source_id': 's0', 'quote': source0_text},
                {'source_id': 's1', 'quote': source1_text},
            ],
            'answers': ['q1'],
        },
        'sections': [
            {
                'heading': '10월 서초 행사 일정 한눈에 보기',
                'kind': 'overview',
                'paragraphs': [],
                'table': {
                    'caption': '2026년 10월 서초 행사 날짜, 볼거리, 장소 비교',
                    'headers': ['날짜', '행사', '주요 볼거리', '장소'],
                    'mobile_cards': True,
                    'rows': [
                        {
                            'cells': ['10/14(수)~15(목)', '가을 체험축제', '전통문화 체험, 공연 프로그램', '서초공원'],
                            'evidence': [{'source_id': 's0', 'quote': source0_text}],
                            'answers': ['q1'],
                        },
                        {
                            'cells': ['10/20(화)', '도심 문화행사', '전시, 버스킹, 체험 부스', '시민광장'],
                            'evidence': [{'source_id': 's1', 'quote': source1_text}],
                            'answers': ['q1'],
                        },
                    ],
                },
            },
            {
                'heading': '가을 체험축제: 전통문화 체험과 공연',
                'event_name': '가을 체험축제',
                'kind': 'general',
                'paragraphs': [{
                    'text': (
                        '가을 체험축제는 10월 14일(수)~10월 15일(목) 서초공원에서 열립니다. '
                        '무료로 입장하며 가족이 전통문화 체험과 공연 프로그램에 참여할 수 있습니다. '
                        '사전예약은 선택이며 현장 관람이 가능합니다.'
                    ),
                    'evidence': [{'source_id': 's0', 'quote': source0_text}],
                    'answers': ['q1'],
                }],
                'image': {
                    'url': 'https://lifeinfo24.org/wp-content/uploads/2026/10/seocho-fall-event.webp',
                    'alt': '가을 체험축제에서 전통문화 체험을 하는 참가자들',
                    'caption': '2026 가을 체험축제 전통문화 체험 현장 사진',
                    'source_id': 's0',
                    'rights': 'open_license',
                    'rights_url': 'https://www.seocho.go.kr/event/fall/photo-license',
                    'year': 2026,
                },
                'location': {
                    'venue': '서초공원',
                    'address': '서초공원',
                    'query': '서울 서초공원',
                    'evidence': [{'source_id': 's0', 'quote': source0_text}],
                    'latitude': 37.4910,
                    'longitude': 127.0050,
                },
                'official_links': [{
                    'label': '가을 체험축제 공식 안내 보기',
                    'url': 'https://www.seocho.go.kr/event/fall',
                }],
                'actions': ['https://www.seocho.go.kr/event/fall/apply'],
            },
            {
                'heading': '도심 문화행사: 전시와 체험 부스',
                'event_name': '도심 문화행사',
                'kind': 'general',
                'paragraphs': [{
                    'text': (
                        '도심 문화행사는 10월 20일(화) 시민광장에서 열립니다. '
                        '전시와 버스킹 공연, 체험 부스를 운영하며 학생과 방문객이 무료로 관람할 수 있습니다. '
                        '운영시간은 10:00~18:00이며 대중교통 이용이 편리합니다.'
                    ),
                    'evidence': [{'source_id': 's1', 'quote': source1_text}],
                    'answers': ['q1'],
                }],
                'image': {
                    'url': 'https://lifeinfo24.org/wp-content/uploads/2026/10/seocho-city-event.webp',
                    'alt': '도심 문화행사에서 버스킹 공연을 보는 관람객',
                    'caption': '2026 도심 문화행사 버스킹 공연 현장 사진',
                    'source_id': 's1',
                    'rights': 'permission_granted',
                    'rights_url': 'https://www.seocho.go.kr/event/city/press-photo',
                    'year': 2026,
                },
                'location': {
                    'venue': '시민광장',
                    'address': '시민광장',
                    'query': '서울 시민광장',
                    'evidence': [{'source_id': 's1', 'quote': source1_text}],
                    'latitude': 37.5663,
                    'longitude': 126.9779,
                },
                'official_links': [{
                    'label': '도심 문화행사 공식 안내 보기',
                    'url': 'https://www.seocho.go.kr/event/city',
                }],
            },
        ],
        'faq': [],
        'related_posts': [],
        'official_navigation': [],
    }
    temporal = {
        'multi_event_schedule': True,
        'event_entries': [
            {
                'name': '가을 체험축제',
                'start_date': '2026-10-14',
                'end_date': '2026-10-15',
                'evidence': {'source_id': 's0', 'quote': source0_text},
            },
            {
                'name': '도심 문화행사',
                'start_date': '2026-10-20',
                'end_date': '2026-10-20',
                'evidence': {'source_id': 's1', 'quote': source1_text},
            },
        ],
        'evidence': [field for source in sources for field in extract_evidence(source['text'], source['url'])],
    }
    return {'brief': brief, 'sources': sources, 'plan': plan, 'temporal_source': temporal}


class EventPostStandardTests(unittest.TestCase):
    def setUp(self):
        self.bundle = event_bundle()

    def test_valid_v1_event_roundup_passes_shared_validator(self):
        report = validate_bundle(
            self.bundle,
            {'checked_on': NOW.date().isoformat(), 'posts': []},
            NOW,
            require_review=False,
        )
        self.assertEqual('ready', report['status'], report)

    def test_legacy_multi_event_bundle_is_not_silently_migrated(self):
        del self.bundle['brief']['event_post_standard_version']
        self.assertEqual([], validate_event_post_standard(self.bundle))

    def test_unsupported_event_standard_version_fails_contract_but_skips_semantic_prompt(self):
        self.bundle['brief']['event_post_standard_version'] = 2
        self.assertIn('event_standard_contract_invalid', validate_event_post_standard(self.bundle))
        self.assertEqual('', event_review_instruction(self.bundle))

    def test_every_event_entry_requires_exactly_one_detailed_section_binding(self):
        del self.bundle['plan']['sections'][2]['event_name']
        self.assertIn(
            'event_standard_event_section_binding_invalid',
            validate_event_post_standard(self.bundle),
        )

    def test_event_section_needs_activity_and_decision_support_not_date_place_only(self):
        self.bundle['plan']['sections'][1]['paragraphs'][0]['text'] = (
            '가을 체험축제는 2026년 10월 14일부터 15일까지 서초공원에서 열립니다.'
        )
        self.assertIn(
            'event_standard_decision_support_missing',
            validate_event_post_standard(self.bundle),
        )

    def test_event_booking_action_must_be_section_scoped(self):
        self.bundle['plan']['sections'][1]['actions'] = []
        self.assertIn(
            'event_standard_event_action_not_section_scoped',
            validate_event_post_standard(self.bundle),
        )

    def test_event_action_must_be_bound_to_source_used_by_that_event_section(self):
        action_url = self.bundle['plan']['sections'][1]['actions'].pop()
        self.bundle['plan']['sections'][2]['actions'] = [action_url]
        self.assertIn(
            'event_standard_action_source_mismatch',
            validate_event_post_standard(self.bundle),
        )

    def test_event_official_detail_link_must_match_official_source_used_by_section(self):
        section = self.bundle['plan']['sections'][1]
        section['official_links'] = [{
            'label': '가을 체험축제 상세 프로그램 보기',
            'url': self.bundle['sources'][0]['url'],
        }]
        self.assertNotIn(
            'event_standard_official_link_source_mismatch',
            validate_event_post_standard(self.bundle),
        )
        section['official_links'][0]['url'] = self.bundle['sources'][1]['url']
        self.assertIn(
            'event_standard_official_link_source_mismatch',
            validate_event_post_standard(self.bundle),
        )

    def test_each_event_section_requires_official_detail_link(self):
        self.bundle['plan']['sections'][2]['official_links'] = []
        self.assertIn(
            'event_standard_official_link_missing',
            validate_event_post_standard(self.bundle),
        )

    def test_event_section_does_not_allow_facts_card(self):
        self.bundle['plan']['sections'][1]['facts'] = [{
            'label': '비용',
            'value': '무료',
            'evidence': [{'source_id': 's0', 'quote': self.bundle['sources'][0]['text']}],
            'answers': ['q1'],
        }]
        self.assertIn(
            'event_standard_event_facts_not_allowed',
            validate_event_post_standard(self.bundle),
        )

    def test_renderer_event_section_order_is_image_body_table_official_link_location(self):
        section = self.bundle['plan']['sections'][2]
        section['table'] = {
            'caption': '도심 문화행사 프로그램 일정',
            'headers': ['프로그램', '시간'],
            'rows': [{
                'cells': ['버스킹 공연', '14:00'],
                'evidence': [{'source_id': 's1', 'quote': self.bundle['sources'][1]['text']}],
                'answers': ['q1'],
            }],
        }
        content = render(self.bundle['plan'], self.bundle['sources'])
        image_pos = content.index('bloguito-event-image', content.index('도심 문화행사: 전시와 체험 부스'))
        body_pos = content.index('도심 문화행사는 10월 20일', image_pos)
        table_pos = content.index('도심 문화행사 프로그램 일정', body_pos)
        official_pos = content.index('도심 문화행사 공식 안내 보기', table_pos)
        location_pos = content.index('📍 행사장 위치: 시민광장', official_pos)
        self.assertLess(image_pos, body_pos)
        self.assertLess(body_pos, table_pos)
        self.assertLess(table_pos, official_pos)
        self.assertLess(official_pos, location_pos)

    def test_renderer_places_official_detail_link_inside_event_section_without_action_cta(self):
        section = self.bundle['plan']['sections'][1]
        section['official_links'] = [{
            'label': '가을 체험축제 상세 프로그램 보기',
            'url': self.bundle['sources'][0]['url'],
        }]
        with patch('agents.editorial.KAKAO_MAP_JAVASCRIPT_KEY', 'public_test_key_1234567890'):
            content = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn('bloguito-section-official-links', content)
        self.assertIn('가을 체험축제 상세 프로그램 보기', content)
        self.assertLess(
            content.index('가을 체험축제 상세 프로그램 보기'),
            content.index('카카오맵 위치 보기'),
        )

    def test_previous_year_official_image_requires_year_and_reference_caption(self):
        section = self.bundle['plan']['sections'][1]
        section['image'] = {
            'url': 'https://www.seocho.go.kr/images/fall-2025.jpg',
            'alt': '가을 체험축제 가족 참여 프로그램 현장',
            'caption': '가을 체험축제 가족 참여 프로그램 현장',
            'source_id': 's0',
            'rights': 'open_license',
            'rights_url': 'https://www.seocho.go.kr/copyright',
            'year': 2025,
        }
        self.bundle['sources'][0]['title'] = '2025 가을 체험축제 현장 사진'
        self.assertIn(
            'event_standard_previous_year_image_disclosure_missing',
            validate_event_post_standard(self.bundle),
        )
        section['image']['caption'] = '2025 행사 현장 사진, 2026 행사 분위기 참고'
        self.assertNotIn(
            'event_standard_previous_year_image_disclosure_missing',
            validate_event_post_standard(self.bundle),
        )

    def test_reader_punctuation_spacing_lint_does_not_scan_source_quotes(self):
        self.bundle['plan']['sections'][2]['paragraphs'][0]['text'] = (
            '전시,체험 부스를 운영하며 무료로 관람할 수 있습니다. 방문객에게 좋은 행사입니다.'
        )
        self.assertIn(
            'event_standard_reader_punctuation_spacing',
            validate_event_post_standard(self.bundle),
        )
        self.bundle = event_bundle()
        self.bundle['sources'][0]['text'] += ' 공식 원문에는 전시,체험처럼 붙은 표현이 있을 수 있습니다.'
        self.assertNotIn(
            'event_standard_reader_punctuation_spacing',
            validate_event_post_standard(self.bundle),
        )

    def test_editor_notes_are_not_reader_copy(self):
        self.bundle['plan']['sections'][2]['paragraphs'][0]['text'] += ' 종료시간은 미표기입니다.'
        self.assertIn('event_standard_editor_note_exposed', validate_event_post_standard(self.bundle))

    def test_source_provenance_language_is_not_reader_copy(self):
        self.bundle['plan']['sections'][2]['paragraphs'][0]['text'] += ' 공식 카드뉴스 기준으로 확인했습니다.'
        self.assertIn('event_standard_editor_note_exposed', validate_event_post_standard(self.bundle))
        self.bundle = event_bundle()
        self.bundle['plan']['sections'][2]['paragraphs'][0]['text'] += ' 확인된 보조 자료에는 공연 정보가 있습니다.'
        self.assertIn('event_standard_editor_note_exposed', validate_event_post_standard(self.bundle))

    def test_seo_keyword_aligns_title_description_lead_and_one_heading(self):
        self.bundle['brief']['seo']['title'] = '2026 서초 가을축제 총정리'
        self.assertIn(
            'event_standard_keyword_alignment_missing',
            validate_event_post_standard(self.bundle),
        )

    def test_overview_requires_mobile_cards_and_decision_column(self):
        table = self.bundle['plan']['sections'][0]['table']
        table['mobile_cards'] = False
        self.assertIn('event_standard_overview_missing', validate_event_post_standard(self.bundle))

        self.bundle = event_bundle()
        self.bundle['plan']['sections'][0]['table']['headers'] = ['날짜', '행사', '장소', '지역', '주소']
        self.assertIn('event_standard_overview_missing', validate_event_post_standard(self.bundle))

    def test_overview_excludes_time_price_and_unhelpful_placeholders(self):
        table = self.bundle['plan']['sections'][0]['table']
        table['rows'][1]['cells'][2] = '전시, 버스킹, 10:00~18:00'
        self.assertIn(
            'event_standard_overview_schedule_layout_invalid',
            validate_event_post_standard(self.bundle),
        )
        self.bundle = event_bundle()
        self.bundle['plan']['sections'][0]['table']['rows'][1]['cells'][2] = '주요 일정별 상이'
        self.assertIn(
            'event_standard_overview_schedule_layout_invalid',
            validate_event_post_standard(self.bundle),
        )
        self.bundle = event_bundle()
        self.bundle['plan']['sections'][0]['table']['rows'][0]['cells'][2] = '공연, 10,000원'
        self.assertIn(
            'event_standard_overview_schedule_layout_invalid',
            validate_event_post_standard(self.bundle),
        )

    def test_reader_dates_reject_source_style_iso_and_dotted_formats(self):
        section = self.bundle['plan']['sections'][2]
        section['paragraphs'][0]['text'] = (
            '도심 문화행사는 2026-10-20 시민광장에서 열립니다. '
            '전시와 체험 부스를 10:00~18:00 운영하며 무료로 관람할 수 있습니다.'
        )
        self.assertIn(
            'event_standard_reader_date_format_inconsistent',
            validate_event_post_standard(self.bundle),
        )
        section['paragraphs'][0]['text'] = section['paragraphs'][0]['text'].replace('2026-10-20', '10.20.(화)')
        self.assertIn(
            'event_standard_reader_date_format_inconsistent',
            validate_event_post_standard(self.bundle),
        )

    def test_reader_date_formatter_compresses_only_redundant_same_month(self):
        self.assertEqual('10/14(수)~15(목)', readable_event_date_label('2026-10-14', '2026-10-15'))
        self.assertEqual('10/30(금)~11/1(일)', readable_event_date_label('2026-10-30', '2026-11-01'))
        self.assertEqual('2026/12/31(목)~2027/1/1(금)', readable_event_date_label('2026-12-31', '2027-01-01'))

    def test_overview_rejects_vague_reader_header(self):
        self.bundle['plan']['sections'][0]['table']['headers'] = [
            '날짜', '행사', '확인된 실전 조건', '장소'
        ]
        reasons = validate_event_post_standard(self.bundle)
        self.assertIn('event_standard_overview_header_vague', reasons)

    def test_each_event_section_requires_image_location_and_image_rights(self):
        section = self.bundle['plan']['sections'][1]
        image = section.pop('image')
        self.assertIn('event_standard_section_assets_missing', validate_event_post_standard(self.bundle))
        section['image'] = image
        location = section.pop('location')
        self.assertIn('event_standard_section_assets_missing', validate_event_post_standard(self.bundle))
        section['location'] = location
        del section['image']['rights']
        self.assertIn('event_standard_image_rights_missing', validate_event_post_standard(self.bundle))

    def test_interactive_map_requires_coordinates_for_every_event(self):
        del self.bundle['plan']['sections'][1]['location']['latitude']
        self.assertIn(
            'event_standard_interactive_map_invalid',
            validate_event_post_standard(self.bundle),
        )

    def test_interactive_map_requires_overview_row_for_every_event(self):
        self.bundle['plan']['sections'][0]['table']['rows'][1]['cells'][1] = '다른 행사'
        self.assertIn(
            'event_standard_interactive_map_invalid',
            validate_event_post_standard(self.bundle),
        )

    def test_renderer_builds_common_kakao_map_after_overview(self):
        with patch('agents.editorial.KAKAO_MAP_JAVASCRIPT_KEY', 'public_test_key_1234567890'):
            content = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn('class="bloguito-kakao-map-container"', content)
        self.assertIn('https://dapi.kakao.com/v2/maps/sdk.js?appkey=', content)
        self.assertIn('map.setBounds(bounds)', content)
        encoded = re.search(r'JSON\.parse\(atob\("([A-Za-z0-9+/=]+)"\)\)', content).group(1)
        groups = json.loads(base64.b64decode(encoded).decode('utf-8'))
        serialized_groups = json.dumps(groups, ensure_ascii=False)
        self.assertIn('가을 체험축제', serialized_groups)
        self.assertIn('10/14(수)~15(목)', serialized_groups)
        self.assertIn('#step-2', serialized_groups)
        self.assertNotIn('"content":"<div', content)
        self.assertLess(content.index('bloguito-info-table'), content.index('bloguito-kakao-map-container'))
        self.assertLess(content.index('bloguito-kakao-map-container'), content.index('id="step-2"'))

    def test_renderer_groups_events_sharing_one_coordinate(self):
        second = self.bundle['plan']['sections'][2]['location']
        first = self.bundle['plan']['sections'][1]['location']
        second['latitude'] = first['latitude']
        second['longitude'] = first['longitude']
        with patch('agents.editorial.KAKAO_MAP_JAVASCRIPT_KEY', 'public_test_key_1234567890'):
            content = render(self.bundle['plan'], self.bundle['sources'])
        encoded = re.search(r'JSON\.parse\(atob\("([A-Za-z0-9+/=]+)"\)\)', content).group(1)
        groups = json.loads(base64.b64decode(encoded).decode('utf-8'))
        self.assertEqual('가을 체험축제 / 도심 문화행사', groups[0]['title'])

    def test_generated_original_is_not_allowed_for_event_section_images(self):
        section = self.bundle['plan']['sections'][1]
        section['image']['rights'] = 'generated_original'
        section['image'].pop('rights_url', None)
        self.assertIn('event_standard_image_rights_missing', validate_event_post_standard(self.bundle))

    def test_event_photo_source_link_is_conditional_for_site_owned_images(self):
        with patch('agents.editorial.KAKAO_MAP_JAVASCRIPT_KEY', 'public_test_key_1234567890'):
            content = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn('사진 출처', content)

        for section in self.bundle['plan']['sections'][1:]:
            section['image']['rights'] = 'site_owned'
            section['image'].pop('rights_url', None)
        with patch('agents.editorial.KAKAO_MAP_JAVASCRIPT_KEY', 'public_test_key_1234567890'):
            content = render(self.bundle['plan'], self.bundle['sources'])
        self.assertNotIn('사진 출처', content)
        self.assertIn('2026 가을 체험축제 전통문화 체험 현장 사진', content)

    def test_existing_generated_image_can_be_explicitly_deferred_without_allowing_new_ones(self):
        section = self.bundle['plan']['sections'][1]
        section['image']['rights'] = 'generated_original'
        section['image'].pop('rights_url', None)
        self.bundle['brief']['existing_post_id'] = 665
        self.bundle['brief']['deferred_generated_event_image_urls'] = [section['image']['url']]
        reasons = validate_event_post_standard(self.bundle)
        self.assertNotIn('event_standard_image_rights_missing', reasons)
        self.assertNotIn('event_standard_deferred_generated_image_invalid', reasons)

        other = self.bundle['plan']['sections'][2]
        other['image']['rights'] = 'generated_original'
        other['image'].pop('rights_url', None)
        reasons = validate_event_post_standard(self.bundle)
        self.assertIn('event_standard_image_rights_missing', reasons)

    def test_selection_guide_requires_explicit_brief_opt_in(self):
        self.bundle['plan']['sections'].insert(1, {
            'heading': '어떤 행사를 고를까',
            'kind': 'comparison',
            'paragraphs': [{'text': '체험과 공연을 비교합니다.', 'evidence': [], 'answers': []}],
        })
        self.assertIn('event_standard_unrequested_selection_guide', validate_event_post_standard(self.bundle))
        self.bundle['brief']['allow_selection_guide'] = True
        self.assertNotIn('event_standard_unrequested_selection_guide', validate_event_post_standard(self.bundle))

    def test_writer_schema_and_prompts_include_event_v1_contract(self):
        parsed = Plan.model_validate(copy.deepcopy(self.bundle['plan'])).model_dump()
        self.assertEqual('가을 체험축제', parsed['sections'][1]['event_name'])
        self.assertTrue(parsed['sections'][0]['table']['mobile_cards'])
        writer = event_writer_instruction(self.bundle['brief'], self.bundle['temporal_source'])
        reviewer = event_review_instruction(self.bundle)
        self.assertIn('event_name', writer)
        self.assertIn('section.actions', writer)
        self.assertIn('section.official_links', writer)
        self.assertIn('날짜, 행사, 주요 볼거리, 장소', writer)
        self.assertIn('10/9(금)~11(일)', writer)
        self.assertIn('실제 볼거리·체험', reviewer)
        self.assertIn('중복하지 않는지', reviewer)


if __name__ == '__main__':
    unittest.main()
