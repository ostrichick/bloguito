"""General writer schema must expose every reviewed feature the renderer accepts."""

import unittest

from agents.editorial_writer import GeneralPlan, Plan, writer_plan_schema
from tests.test_editorial_system import sample


class GeneralWriterContractTests(unittest.TestCase):
    def test_plan_schema_accepts_general_reviewed_features(self):
        evidence = [{'source_id': 's0', 'quote': '기본 보험료 2,000원, 추가 보험료 1,000원'}]
        plan = Plan.model_validate({
            'title': '보험료 조회 방법',
            'lead': {
                'text': '공식 금액을 합산한 참고금액은 3,000원입니다.',
                'evidence': evidence,
                'answers': ['q1'],
                'emphasis': ['참고금액은 3,000원'],
                'calculations': [{
                    'operation': 'sum', 'unit': '원', 'operands': [2000, 1000], 'result': 3000,
                }],
            },
            'lead_image': {
                'url': 'https://lifeinfo24.org/wp-content/uploads/insurance.webp',
                'alt': '보험료 조회 화면', 'width': 1200, 'height': 675,
            },
            'sections': [{
                'heading': '비용 비교', 'kind': 'comparison', 'paragraphs': [],
                'facts': [{
                    'label': '참고금액', 'value': '3,000원', 'evidence': evidence,
                    'answers': ['q1'],
                    'calculations': [{
                        'operation': 'sum', 'unit': '원', 'operands': [2000, 1000], 'result': 3000,
                    }],
                }],
                'table': {
                    'caption': '보험료 비교', 'headers': ['구분', '금액'],
                    'rows': [{
                        'cells': ['합계', '3,000원'], 'evidence': evidence, 'answers': ['q1'],
                        'calculations': [{
                            'operation': 'sum', 'unit': '원', 'operands': [2000, 1000], 'result': 3000,
                        }],
                    }],
                },
            }],
            'official_navigation': [{
                'label': '공식 누리집에서 보험료 조회 메뉴 선택',
                'url': 'https://example.go.kr/',
                'note': '첫 화면에서 보험료 조회 메뉴로 진입합니다.',
            }],
            'related_posts': [],
        }).model_dump()

        self.assertEqual(['참고금액은 3,000원'], plan['lead']['emphasis'])
        self.assertEqual('sum', plan['lead']['calculations'][0]['operation'])
        self.assertEqual(1200, plan['lead_image']['width'])
        self.assertEqual('공식 누리집에서 보험료 조회 메뉴 선택', plan['official_navigation'][0]['label'])

    def test_general_generation_schema_excludes_event_only_fields(self):
        schema = GeneralPlan.model_json_schema()
        section_properties = schema['$defs']['BaseSection']['properties']
        location_properties = schema['$defs']['SectionLocation']['properties']
        self.assertNotIn('event_name', section_properties)
        self.assertNotIn('latitude', location_properties)
        self.assertNotIn('longitude', location_properties)
        self.assertIs(writer_plan_schema(sample()), GeneralPlan)

    def test_legacy_plan_parser_still_accepts_event_superset(self):
        plan = Plan.model_validate({
            'title': '행사 안내',
            'lead': {'text': '행사 안내입니다.', 'evidence': [], 'answers': []},
            'sections': [{
                'heading': '행사 상세', 'paragraphs': [], 'event_name': '가을축제',
                'location': {
                    'venue': '시민광장', 'address': '시민광장', 'query': '시민광장',
                    'evidence': [], 'latitude': 37.5, 'longitude': 127.0,
                },
            }],
        }).model_dump()
        self.assertEqual('가을축제', plan['sections'][0]['event_name'])
        self.assertEqual(37.5, plan['sections'][0]['location']['latitude'])


if __name__ == '__main__':
    unittest.main()
