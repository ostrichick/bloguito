"""Only terminal, explicitly marked legacy citation lists are source-only."""
import unittest

from agents.search_intent import duplicate_posts


PDF = 'https://www.kdca.go.kr/bbs/kdca/42/309764/download.do'
NTS = 'https://nts.go.kr/nts/na/ntt/selectNttInfo.do?bbsId=1028&mi=2201&nttSn=1355091'
NHIS = 'https://www.nhis.or.kr/static/html/wbma/c/wbmac0209.html'
FOOTER = ('<h2>공식 근거 및 확인 경로</h2><ul>'
          f'<li><a href="{PDF}">질병관리청 일정 변경 보도자료</a></li>'
          '<li><a href="https://nip.kdca.go.kr/">예방접종도우미</a></li></ul>')
BRIEF = {'existing_post_id': 63, 'required_title_terms': ['독감 무료 예방접종'],
         'official_urls': [PDF]}


def existing(body, title='어르신 독감 무료접종 연령별 날짜'):
    return {'post_status': 'publish', 'post_title': title, 'post_content': body}


class OldCitationScopeTests(unittest.TestCase):
    def test_distinct_article_citing_same_official_attachment_is_allowed(self):
        self.assertEqual(duplicate_posts(BRIEF, [existing(FOOTER)]), [])

    def test_same_title_or_pdf_in_body_still_duplicates(self):
        same_title = existing(FOOTER, '2026 독감 무료 예방접종 안내')
        body_link = existing(f'<p><a href="{PDF}">다운로드</a></p>' + FOOTER)
        action = existing(f'<div class="bloguito-cta"><a href="{PDF}">받기</a></div>' + FOOTER)
        for post in (same_title, body_link, action):
            with self.subTest(post=post['post_content'][:20]):
                self.assertEqual(duplicate_posts(BRIEF, [post]), [post])

    def test_new_articles_and_unmarked_legacy_links_remain_blocked(self):
        new_post = {key: val for key, val in BRIEF.items() if key != 'existing_post_id'}
        self.assertEqual(duplicate_posts(new_post, [existing(FOOTER)]), [existing(FOOTER)])
        ordinary = existing(f'<h2>안내</h2><ul><li><a href="{PDF}">근거</a></li></ul>')
        self.assertEqual(duplicate_posts(BRIEF, [ordinary]), [ordinary])

    def test_non_attachment_source_in_verified_legacy_footer_is_citation_only(self):
        other = 'https://www.kdca.go.kr/bbs/kdca/42/309764/artclView.do'
        brief = {**BRIEF, 'official_urls': [other]}
        post = existing('<h2>공식 근거 및 확인 경로</h2><ul>'
                        f'<li><a href="{other}">원문</a></li></ul>')
        self.assertEqual(duplicate_posts(brief, [post]), [])

    def test_finance_legacy_source_lists_do_not_duplicate_distinct_article(self):
        # WP escapes URL ampersands in the stored HTML; the URL is cited only
        # in each genuine legacy source footer, matching #125/#139 and #220.
        nts_escaped = NTS.replace('&', '&amp;')
        tax_brief = {'existing_post_id': 139,
                     'required_title_terms': ['국세', '지방세', '건강보험', '통신'],
                     'official_urls': [NTS]}
        tax = existing('<h2>공식 근거 및 확인 경로</h2><ul>'
                       f'<li><a href="{nts_escaped}">국세청 자료</a></li></ul>',
                       '국세청 세금포인트 조회·사용처·유효기간')
        health = existing('<h2>공식 자료 및 확인 경로</h2><ul>'
                          f'<li><a href="{NHIS}">국민건강보험공단 안내</a></li></ul>',
                          '건강보험 상한제 환급 안내')
        self.assertEqual(duplicate_posts(tax_brief, [tax]), [])
        self.assertEqual(duplicate_posts({**tax_brief, 'official_urls': [NHIS]}, [health]), [])

    def test_legacy_footer_exemption_does_not_hide_real_overlap(self):
        brief = {'existing_post_id': 139, 'required_title_terms': ['국세', '지방세', '건강보험', '통신'],
                 'official_urls': [NTS]}
        nts_escaped = NTS.replace('&', '&amp;')
        footer = ('<h2>공식 근거 및 확인 경로</h2><ul>'
                  f'<li><a href="{nts_escaped}">국세청 자료</a></li></ul>')
        same_topic = existing(footer, '국세·지방세·건강보험·통신 미환급금')
        body_action = existing(f'<div class="bloguito-cta"><a href="{NTS}">조회하기</a></div>' + footer)
        plain_draft = {**existing(f'<p><a href="{NTS}">국세청 확인</a></p>'), 'post_status': 'draft'}
        for post in (same_topic, body_action, plain_draft):
            with self.subTest(status=post['post_status'], title=post['post_title']):
                self.assertEqual(duplicate_posts(brief, [post]), [post])

    def test_unverified_or_nonterminal_legacy_lists_still_block(self):
        brief = {**BRIEF, 'official_urls': [NTS]}
        citation = f'<ul><li><a href="{NTS}">국세청 자료</a></li></ul>'
        for body in (
            '<h2>공식 사이트 안내</h2>' + citation,
            '<h2>공식 근거 및 확인 경로</h2>' + citation + '<p>이후 본문</p>',
            '<h2>공식 근거 및 확인 경로</h2><ul><li>'
            f'신청 <a href="{NTS}">바로가기</a></li></ul>',
        ):
            with self.subTest(body=body[:45]):
                self.assertEqual(duplicate_posts(brief, [existing(body)]), [existing(body)])


if __name__ == '__main__':
    unittest.main()
