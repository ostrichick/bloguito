
"""Exact-scope regression for the user-approved legacy #85 timeless MENU guide.

The exception must not bypass other welfare/concert dates, invent an active
transaction, drop the original two tables or substitute a dated outage.
"""
import copy
import hashlib
import unittest
from datetime import datetime, timedelta

from agents.editorial import (
    legacy_85_welfare_navigation_exception,
    legacy_85_welfare_navigation_reasons,
    policy,
    topic_reasons,
    validate_bundle,
)
from agents.temporal_validation import KST


def fixture():
    cfg = policy()['legacy_welfare_procedural_exceptions'][
        'legacy-85-timeless-navigation-full-20260923']
    now = datetime.now(KST)
    body = [
        '나의 혜택 | 혜택알리미 | 정부24\n로그인이 필요한 메뉴입니다.\n로그인 메뉴',
        '맞춤형급여안내(복지멤버십)\n제도 안내\n이용 방법\n서비스 신청\n'
        '복지급여 신청\n복지지갑\n서비스 신청 현황\n정식 제도 안내',
        '복지멤버십은 받을 가능성이 있는 서비스를 안내합니다. '
        '실제 조사 결과 수급 여부가 달라질 수 있습니다. '
        '읍면동 주민센터 등 관할기관을 통한 개별 복지급여 신청이 있습니다.',
        '2022.12.16\n쉽고 편하게 보조금24 숨은 나의 혜택 찾기',
    ]
    sources = []
    for i, text in enumerate(body):
        sources.append({'id': f's{i}', 'url': cfg['official_urls'][i],
                        'title': f'공식 근거 {i}', 'text': text,
                        'source_type': 'official',
                        'sha256': hashlib.sha256(text.encode()).hexdigest(),
                        'fetched_at': now.isoformat()})
    def ev(i):
        return [{'source_id': f's{i}', 'quote': body[i]}]
    p = lambda text, i=2: {'text': text, 'evidence': ev(i),
                           'answers': ['q1']}
    first = [
        {'cells': ['복지멤버십', '가능성이 있는 사업 안내',
                   '가입 안내 메뉴와 실제 사업 신청은 분리'],
         'evidence': ev(2), 'answers': ['q1']},
        {'cells': ['정부24 혜택알리미 나의 혜택', '개인 혜택 탐색 메뉴',
                   '로그인 뒤 개별 사업을 확인'],
         'evidence': ev(0), 'answers': ['q1']},
    ]
    second = [
        {'cells': [name, '개별 공고가 명시한 내용을 대조',
                   '확정된 급여 자격이 아님'],
         'evidence': ev(2), 'answers': ['q1']}
        for name in cfg['checklist_rows']
    ]
    plan = {
        'title': cfg['title'], 'official_navigation': cfg['official_navigation'],
        'lead': p('과거 보조금24와 현재 혜택알리미는 메뉴와 목적을 구분합니다. '
                  '로그인 뒤 후보는 개별 조사와 신청이 필요합니다.', 0),
        'sections': [
            {'heading': '두 공식 탐색 서비스',
             'kind': 'overview', 'paragraphs': [
                p('복지로 사이트맵에서 실제 가입 양식 확인되지 않은 메뉴를 '
                  '확정 신청 경로로 부르지 않습니다.', 1)],
             'table': {'caption': '두 서비스 구분',
                       'headers': ['서비스', '역할', '다음 확인'],
                       'rows': first}},
            {'heading': '사업별 확인표',
             'kind': 'comparison', 'paragraphs': [
                p('사업명, 담당 기관, 공식 공고 링크, 대상 조건, '
                  '마감 날짜와 시각, 준비서류, 제출처, 문의한 날짜와 답변, '
                  '제출 완료 여부 및 접수번호를 메모합니다. '
                  '주민센터 방문은 실제 개별 사업 신청 대안입니다.')],
             'table': {'caption': '사업별 다섯 항목',
                       'headers': ['항목', '조건', '메모'],
                       'rows': second}},
        ],
        'faq': [], 'related_posts': [],
    }
    brief = {key: copy.deepcopy(cfg[key]) for key in (
        'existing_post_id', 'category_key', 'content_type', 'entity',
        'question', 'required_title_terms', 'official_urls',
        'evergreen_reason')}
    brief.update(id='legacy-85-timeless-navigation-full-20260923',
                 approved=True, useful_until=None,
                 primary_keyword='복지멤버십 개별 사업 상시 안내',
                 angle='검증한 메뉴만 연결하는 기존 #85 안내',
                 reader_questions=[{'id': 'q1', 'question': cfg['question']}],
                 queries=['복지멤버십 메뉴'], serp_urls=[],
                 reviewed_at=now.date().isoformat(),
                 review_until=now.date().isoformat())
    return {'brief': brief, 'sources': sources, 'plan': plan}, {
        'checked_on': now.date().isoformat(), 'posts': []}


class Legacy85NavigationScopeTests(unittest.TestCase):
    def setUp(self):
        self.bundle, self.inventory = fixture()

    def test_exact_85_timeline_exception_full_bundle_ready_without_review(self):
        b = self.bundle
        self.assertTrue(legacy_85_welfare_navigation_exception(b['brief']))
        self.assertEqual(topic_reasons(b['brief']), [])
        self.assertEqual(legacy_85_welfare_navigation_reasons(
            b['brief'], b['sources'], b['plan']), [])
        self.assertEqual(validate_bundle(
            b, self.inventory, require_review=False)['status'], 'ready')

    def test_full_review_and_digest_still_required(self):
        report = validate_bundle(self.bundle, self.inventory)
        self.assertIn('review_not_bound_to_current_content', report['reasons'])
        self.assertIn('review_stale', report['reasons'])
        self.assertIn('semantic_review_failed', report['reasons'])

    def test_only_exact_existing_post_and_topic_contract_qualify(self):
        for key, bad in [
            ('existing_post_id', 86),
            ('existing_post_id', True),
            ('id', 'another-welfare-post'),
            ('entity', '다른 복지사업'),
            ('question', '2026년 신규 지원금 신청'),
            ('content_type', 'dated'),
            ('evergreen_reason', 'general benefits, no proof'),
        ]:
            with self.subTest(key=key):
                brief = copy.deepcopy(self.bundle['brief'])
                brief[key] = bad
                self.assertFalse(legacy_85_welfare_navigation_exception(brief))
                self.assertNotEqual(topic_reasons(brief), [])

    def test_official_urls_cannot_be_swapped_added_or_reordered(self):
        cfg = self.bundle['brief']['official_urls']
        for bad in [list(reversed(cfg)), cfg[:-1], [*cfg, 'https://www.gov.kr/']]:
            with self.subTest(urls=bad):
                brief = copy.deepcopy(self.bundle['brief'])
                brief['official_urls'] = bad
                self.assertFalse(legacy_85_welfare_navigation_exception(brief))
                self.assertIn('dated_category_cannot_bypass_time_check',
                              topic_reasons(brief))

    def test_zero_actions_and_exact_menu_navigation(self):
        b = self.bundle
        b['sources'][1]['actions'] = [{
            'label': '가입 완료', 'url': b['sources'][1]['url'], 'kind': 'apply'}]
        self.assertIn('legacy_85_navigation_or_action_contract_invalid',
                      legacy_85_welfare_navigation_reasons(
                          b['brief'], b['sources'], b['plan']))
        b['sources'][1].pop('actions')
        b['plan']['official_navigation'][0]['label'] = '복지멤버십 직접 신청'
        self.assertIn('legacy_85_navigation_or_action_contract_invalid',
                      legacy_85_welfare_navigation_reasons(
                          b['brief'], b['sources'], b['plan']))

    def test_official_role_source_text_must_contain_disclaimers(self):
        b = self.bundle
        b['sources'][2]['text'] = b['sources'][2]['text'].replace(
            '실제 조사 결과', '안내 결과')
        self.assertIn('legacy_85_official_role_evidence_missing',
                      legacy_85_welfare_navigation_reasons(
                          b['brief'], b['sources'], b['plan']))

    def test_original_tables_and_visit_memo_mandatory(self):
        b = self.bundle
        b['plan']['sections'][1]['table']['rows'].pop()
        self.assertIn('legacy_85_original_tables_not_preserved',
                      legacy_85_welfare_navigation_reasons(
                          b['brief'], b['sources'], b['plan']))
        b, _ = fixture()
        p = b['plan']['sections'][1]['paragraphs'][0]
        p['text'] = p['text'].replace('접수번호', '')
        self.assertIn('legacy_85_original_explanations_or_fallback_missing',
                      legacy_85_welfare_navigation_reasons(
                          b['brief'], b['sources'], b['plan']))

    def test_future_outage_and_false_live_availability_not_permitted(self):
        for injected in [
            '2026년 9월 27일 서비스 점검 예정',
            '로그인 중단 일정이 있습니다',
            '현재 가입 가능',
            '누구나 신청 가능',
        ]:
            with self.subTest(injected=injected):
                b, _ = fixture()
                b['plan']['sections'][0]['paragraphs'][0]['text'] += injected
                self.assertIn('legacy_85_time_or_availability_claim_not_allowed',
                              legacy_85_welfare_navigation_reasons(
                                  b['brief'], b['sources'], b['plan']))

    def test_existing_welfare_30_day_and_concert_evergreen_unchanged(self):
        b = copy.deepcopy(self.bundle['brief'])
        b['content_type'] = 'dated'
        b['useful_until'] = (datetime.now(KST).date()
                             + timedelta(days=7)).isoformat()
        self.assertIn('insufficient_useful_lifetime', topic_reasons(b))
        b = copy.deepcopy(self.bundle['brief'])
        b['id'] = 'unrelated-concert-evergreen'
        b['category_key'] = 'concert'
        self.assertIn('dated_category_cannot_bypass_time_check',
                      topic_reasons(b))


if __name__ == '__main__':
    unittest.main()
