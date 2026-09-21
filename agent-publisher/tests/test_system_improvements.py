import unittest
from config import CATEGORIES, resolve_category
from agents.editorial import render


class SystemImprovementsTest(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {
                'id': 's1',
                'source_type': 'official',
                'url': 'https://www.wetax.go.kr/main/',
                'title': '위택스 공식 누리집'
            },
            {
                'id': 's2',
                'source_type': 'press',
                'url': 'https://news.example.com/article',
                'title': '관련 보도자료'
            }
        ]
        self.plan = {
            'title': '테스트 글 제목',
            'lead': {'text': '3초 핵심 요약 내용입니다.', 'evidence': [{'source_id': 's1', 'quote': '요약'}]},
            'sections': [
                {
                    'heading': '1. STEP 1. 신청 자격 및 대상자 기준 확인하기',
                    'paragraphs': [{'text': '본문 첫 번째 단락입니다.', 'evidence': [{'source_id': 's1', 'quote': '단락1'}]}]
                },
                {
                    'heading': 'STEP 2. 위택스 온라인 신청 방법 총정리',
                    'paragraphs': [{'text': '본문 두 번째 단락입니다.', 'evidence': [{'source_id': 's2', 'quote': '단락2'}]}]
                },
                {
                    'heading': '3. 지급 일정 및 가산세 유의사항',
                    'paragraphs': [{'text': '본문 세 번째 단락입니다.', 'evidence': [{'source_id': 's1', 'quote': '단락3'}]}]
                }
            ],
            'faq': [
                {
                    'question': '자주 묻는 질문 1번인가요?',
                    'answer': {'text': '네, 그렇습니다.', 'evidence': [{'source_id': 's1', 'quote': '답변1'}]}
                }
            ]
        }

    def test_render_step_header_clean(self):
        """STEP 뱃지 옆에 1. STEP 1. 등 중복 번호가 붙지 않고 제목만 깔끔하게 렌더링되는지 검증"""
        html = render(self.plan, self.sources)

        # 1. 헤더에 중복 '1. STEP 1.', 'STEP 2.', '3.' 이 없어야 함
        self.assertNotIn('STEP 1</span>1. STEP 1.', html)
        self.assertNotIn('STEP 2</span>STEP 2.', html)
        self.assertNotIn('STEP 3</span>3.', html)

        # 2. 정제된 제목이 뱃지 옆에 바로 와야 함
        self.assertIn('STEP 1</span>신청 자격 및 대상자 기준 확인하기</h2>', html)
        self.assertIn('STEP 2</span>위택스 온라인 신청 방법 총정리</h2>', html)
        self.assertIn('>지급 일정 및 가산세 유의사항</h2>', html)
        self.assertNotIn('STEP 3</span>지급 일정', html)

        # 3. 목차(TOC)에도 정제된 텍스트가 표시되어야 함
        self.assertIn('STEP 1. 신청 자격 및 대상자 기준 확인하기</a>', html)
        self.assertIn('STEP 2. 위택스 온라인 신청 방법 총정리</a>', html)
        self.assertIn('>지급 일정 및 가산세 유의사항</a>', html)

    def test_informational_sources_are_not_action_buttons(self):
        """출처가 공식 누리집이어도 확인된 신청·예매 목적지가 아니면 버튼으로 만들지 않는다."""
        html = render(self.plan, self.sources)
        self.assertNotIn('class="bloguito-cta"', html)
        self.assertIn('href="https://www.wetax.go.kr/main/"', html)
        self.assertNotIn('위택스 공식 누리집 바로가기', html)

    def test_render_only_explicit_actions_with_functional_destinations(self):
        """공식 원문과 예매·앱 설치 목적지를 분리한다."""
        custom_sources = [
            {'id': 's1', 'source_type': 'official', 'url': 'https://www.tmoney.co.kr/intro', 'title': '티머니 사업 소개',
             'actions': [{'kind': 'booking', 'label': '고속버스 조회·예매', 'url': 'https://www.kobus.co.kr/main.do'},
                         {'kind': 'install', 'label': '티머니GO Android 설치', 'url': 'https://play.google.com/store/apps/details?id=kr.co.tmoney.tia'},
                         {'kind': 'install', 'label': '티머니GO iPhone 설치', 'url': 'https://apps.apple.com/kr/app/id1483433931'}]},
            {'id': 's2', 'source_type': 'press', 'url': 'https://news.example.com/article', 'title': '관련 보도자료', 'cta_label': '잘못된 자동 버튼'},
        ]
        html = render(self.plan, custom_sources)
        self.assertIn('class="bloguito-cta"', html)
        self.assertIn('공식 서비스 바로가기', html)
        self.assertIn('고속버스 조회·예매', html)
        self.assertIn('https://www.kobus.co.kr/main.do', html)
        self.assertIn('https://play.google.com/store/apps/details?id=kr.co.tmoney.tia', html)
        self.assertIn('https://apps.apple.com/kr/app/id1483433931', html)
        self.assertNotIn('잘못된 자동 버튼', html)
        self.assertNotIn('정부·공공기관 누리집', html)
        self.assertIn('티머니 사업 소개', html)

    def test_resolve_category_aliases(self):
        """다양한 카테고리 alias가 올바른 표준 카테고리로 안전 매핑되는지 검증"""
        self.assertEqual(resolve_category('life')['id'], CATEGORIES['life-health']['id'])
        self.assertEqual(resolve_category('health')['id'], CATEGORIES['life-health']['id'])
        self.assertEqual(resolve_category('life_health')['id'], CATEGORIES['life-health']['id'])
        self.assertEqual(resolve_category('welfare-benefit')['id'], CATEGORIES['welfare']['id'])
        self.assertEqual(resolve_category('benefit')['id'], CATEGORIES['welfare']['id'])
        self.assertEqual(resolve_category('taxes')['id'], CATEGORIES['tax']['id'])
        self.assertEqual(resolve_category('taxation')['id'], CATEGORIES['tax']['id'])
        self.assertEqual(resolve_category('ticket')['id'], CATEGORIES['concert']['id'])
        self.assertEqual(resolve_category('tickets')['id'], CATEGORIES['concert']['id'])

    def test_resolve_category_fallback(self):
        """알 수 없는 키 또는 빈 문자열 입력 시 기본 카테고리로 안전 폴백되는지 검증"""
        fallback_cat = resolve_category('unknown_random_category')
        self.assertEqual(fallback_cat['id'], CATEGORIES['life-health']['id'])

        empty_cat = resolve_category('')
        self.assertEqual(empty_cat['id'], CATEGORIES['life-health']['id'])

    def test_interlink_category_isolation(self):
        """생활/건강 글에는 무관한 콘서트 글이 추천되지 않고 생활/복지 글만 추천되는지 검증"""
        html = render(self.plan, self.sources, category_key='life-health')
        self.assertNotIn('무명전설 크리스마스 콘서트', html)
        self.assertNotIn('공연/콘서트 예매', html)
        self.assertNotIn('bloguito-interlink', html)  # No topical match; unrelated flu posts are not useful.

    def test_interlink_concert_isolation(self):
        """콘서트 글에는 콘서트 관련 글만 추천되는지 검증"""
        concert_plan = dict(self.plan)
        concert_plan['title'] = '2026 임영웅 콘서트 티켓 예매 일정'
        html = render(concert_plan, self.sources, category_key='concert')
        self.assertNotIn('bloguito-interlink', html)  # A different performer is not a topical match.
        self.assertNotIn('독감 예방접종', html)


if __name__ == '__main__':
    unittest.main()
