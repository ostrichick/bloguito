"""Verify official menu-entry links do not masquerade as direct service CTAs."""
import unittest

from agents.editorial import official_navigation_links, render


OFFICIAL = 'https://www.nts.go.kr/'
DIRECT = 'https://mob.tbht.hometax.go.kr/jsonAction.do?actionId=UTBRDAAA03F001'


def sample():
    sources = [{'id': 's0', 'source_type': 'official', 'url': OFFICIAL,
                'text': '국세청 공식 홈페이지 국세환급금 찾기', 'title': '국세청'}]
    evidence = [{'source_id': 's0', 'quote': '국세청 공식 홈페이지 국세환급금 찾기'}]
    plan = {'title': '국세환급금 조회', 'lead': {
                'text': '국세청에서 메뉴로 이동합니다.', 'evidence': evidence},
            'sections': [{'heading': '확인 방법', 'kind': 'procedure',
                          'paragraphs': [{'text': '국세청 메뉴에서 찾습니다.',
                                          'evidence': evidence}]}],
            'official_navigation': [{
                'label': '국세청 누리집에서 국세환급금 찾기 메뉴 선택',
                'url': OFFICIAL,
                'note': '국세청 첫 화면에서 국세환급금 찾기 메뉴를 선택합니다.'}]}
    return plan, sources


class OfficialSiteNavigationTests(unittest.TestCase):
    def test_official_site_menu_is_plain_navigation_not_direct_cta(self):
        plan, sources = sample()
        self.assertEqual(official_navigation_links(plan, sources), plan['official_navigation'])
        markup = render(plan, sources)
        self.assertIn('class="bloguito-official-navigation"', markup)
        self.assertIn('국세청 첫 화면에서', markup)
        self.assertNotIn('class="bloguito-cta"', markup)

    def test_only_exact_reviewed_official_source_url_allowed(self):
        plan, sources = sample()
        for other in ('https://example.org/', OFFICIAL + 'query/', DIRECT):
            with self.subTest(url=other):
                plan['official_navigation'][0]['url'] = other
                with self.assertRaisesRegex(ValueError, 'invalid_official_navigation'):
                    official_navigation_links(plan, sources)

    def test_cannot_relabel_same_destination_as_action_and_navigation(self):
        plan, sources = sample()
        sources[0]['actions'] = [{'label': '국세환급금 찾기', 'url': OFFICIAL, 'kind': 'lookup'}]
        with self.assertRaisesRegex(ValueError, 'invalid_official_navigation'):
            official_navigation_links(plan, sources)

    def test_misleading_label_or_missing_menu_step_fails_closed(self):
        plan, sources = sample()
        for label, note in [
                ('국세환급금 직접 조회', '첫 화면에서 검색할 수 있습니다.'),
                ('국세환급금 메뉴 찾기', '즉시 조회를 마칠 수 있습니다.'),
                ('국세환급금 메뉴 찾기', '<script>alert(1)</script> 첫 화면')]:
            with self.subTest(label=label, note=note):
                plan['official_navigation'][0].update(label=label, note=note)
                with self.assertRaisesRegex(ValueError, 'invalid_official_navigation'):
                    official_navigation_links(plan, sources)

    def test_legacy_renderer_unchanged_without_optional_navigation(self):
        plan, sources = sample()
        del plan['official_navigation']
        self.assertEqual(official_navigation_links(plan, sources), [])
        self.assertNotIn('bloguito-official-navigation', render(plan, sources))


if __name__ == '__main__':
    unittest.main()
