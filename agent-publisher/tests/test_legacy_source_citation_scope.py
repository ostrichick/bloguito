"""Old KDCA source lists should not misclassify distinct flu articles."""
import unittest

from agents.search_intent import duplicate_posts


PDF = 'https://www.kdca.go.kr/bbs/kdca/42/309764/download.do'
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

    def test_other_official_links_still_require_explicit_modern_footer(self):
        other = 'https://www.kdca.go.kr/bbs/kdca/42/309764/artclView.do'
        brief = {**BRIEF, 'official_urls': [other]}
        post = existing('<h2>공식 근거 및 확인 경로</h2><ul>'
                        f'<li><a href="{other}">원문</a></li></ul>')
        self.assertEqual(duplicate_posts(brief, [post]), [post])


if __name__ == '__main__':
    unittest.main()
