import copy
import hashlib
import unittest

from agents.editorial import validate_bundle
from agents.editorial_writer import Plan
from agents.event_post_standard import (
    event_review_instruction,
    event_writer_instruction,
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
        'category_key': 'life-health',
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
                    'caption': '2026년 10월 서초 행사 날짜, 체험, 비용, 장소 비교',
                    'headers': ['날짜', '행사', '볼거리와 체험', '티켓과 예약', '장소'],
                    'mobile_cards': True,
                    'rows': [
                        {
                            'cells': ['10/14~10/15', '가을 체험축제', '전통문화 체험, 공연 프로그램', '무료, 예약 선택', '서초공원'],
                            'evidence': [{'source_id': 's0', 'quote': source0_text}],
                            'answers': ['q1'],
                        },
                        {
                            'cells': ['10/20', '도심 문화행사', '전시, 버스킹, 체험 부스', '무료, 10:00~18:00', '시민광장'],
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
                    'text': source0_text,
                    'evidence': [{'source_id': 's0', 'quote': source0_text}],
                    'answers': ['q1'],
                }],
                'image': {
                    'url': 'https://lifeinfo24.org/wp-content/uploads/2026/10/seocho-fall-event.webp',
                    'alt': '가을 체험축제 전통문화 체험과 공연을 표현한 행사 안내 이미지',
                    'caption': '2026 공식 프로그램을 바탕으로 제작한 행사 안내 이미지',
                    'source_id': 's0',
                    'rights': 'generated_original',
                    'year': 2026,
                },
                'location': {
                    'venue': '서초공원',
                    'address': '서초공원',
                    'query': '서울 서초공원',
                    'evidence': [{'source_id': 's0', 'quote': source0_text}],
                },
                'actions': ['https://www.seocho.go.kr/event/fall/apply'],
            },
            {
                'heading': '도심 문화행사: 전시와 체험 부스',
                'event_name': '도심 문화행사',
                'kind': 'general',
                'paragraphs': [{
                    'text': source1_text,
                    'evidence': [{'source_id': 's1', 'quote': source1_text}],
                    'answers': ['q1'],
                }],
                'image': {
                    'url': 'https://lifeinfo24.org/wp-content/uploads/2026/10/seocho-city-event.webp',
                    'alt': '도심 문화행사 전시와 버스킹, 체험 부스를 표현한 행사 안내 이미지',
                    'caption': '2026 공식 프로그램을 바탕으로 제작한 행사 안내 이미지',
                    'source_id': 's1',
                    'rights': 'generated_original',
                    'year': 2026,
                },
                'location': {
                    'venue': '시민광장',
                    'address': '시민광장',
                    'query': '서울 시민광장',
                    'evidence': [{'source_id': 's1', 'quote': source1_text}],
                },
            },
            {
                'heading': '10월 서초 행사, 체험과 도심 문화 프로그램을 함께 비교하세요',
                'kind': 'general',
                'paragraphs': [{
                    'text': '전통문화 체험과 공연이 중심인 행사 뒤에 전시, 버스킹, 체험 부스 중심의 도심 문화행사가 이어져 프로그램 성격이 다릅니다.',
                    'evidence': [
                        {'source_id': 's0', 'quote': source0_text},
                        {'source_id': 's1', 'quote': source1_text},
                    ],
                    'answers': ['q1'],
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

    def test_event_roundup_requires_closing_summary_after_event_sections(self):
        self.bundle['plan']['sections'].pop()
        self.assertIn(
            'event_standard_closing_summary_missing',
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

    def test_overview_rejects_vague_reader_header(self):
        self.bundle['plan']['sections'][0]['table']['headers'] = [
            '날짜', '행사', '볼거리와 체험', '확인된 실전 조건', '장소'
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

    def test_generated_image_caption_must_disclose_that_it_is_created(self):
        section = self.bundle['plan']['sections'][1]
        section['image']['caption'] = '2026 가을 체험축제 현장 사진'
        self.assertIn('event_standard_image_rights_missing', validate_event_post_standard(self.bundle))

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
        self.assertIn('대표 이미지와 위치 카드', writer)
        self.assertIn('실제 작품명', writer)
        self.assertIn('출연자', writer)
        self.assertIn('대표곡', writer)
        self.assertIn('공식 세트리스트', writer)
        self.assertIn('강변 풍경', writer)
        self.assertIn('마무리 section', writer)
        self.assertIn('방문 목적', reviewer)
        self.assertIn('수량·범주', reviewer)
        self.assertIn('빈 공연장', reviewer)
        self.assertIn('마지막 마무리 section', reviewer)


if __name__ == '__main__':
    unittest.main()
