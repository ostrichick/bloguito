import unittest

from agents.search_intent import duplicate_posts


class SharedSourceCitationTests(unittest.TestCase):
    def setUp(self):
        self.url = 'https://official.example/notice?document=one&published=yes'
        self.brief = {
            'existing_post_id': 79,
            'required_title_terms': ['기초연금', '모의계산'],
            'official_urls': [self.url],
        }
        self.footer = (
            '<div><h2 id="sources">공식 출처 및 사실 검증 자료</h2>'
            '<ul class="source-list"><li><a href="https://official.example/notice?'
            'document=one&amp;published=yes">정책 안내</a></li></ul></div>'
        )
        self.post = {
            'ID': 139,
            'post_status': 'publish',
            'post_title': '기초연금 주민센터 대리 신청 안내',
            'post_content': '<article>신청 방법 설명.</article>' + self.footer,
        }

    def test_distinct_article_shared_citation_is_not_duplicate(self):
        self.assertEqual(duplicate_posts(self.brief, [self.post]), [])

    def test_same_topic_title_remains_duplicate_with_shared_citation(self):
        post = {**self.post, 'post_title': '기초연금 소득인정액 모의계산'}
        self.assertEqual(duplicate_posts(self.brief, [post]), [post])

    def test_action_or_body_link_still_triggers_duplicate(self):
        post = {
            **self.post,
            'post_content': (
                '<div class="bloguito-cta"><a href="' + self.url.replace('&', '&amp;')
                + '">조회 시작</a></div>' + self.footer
            ),
        }
        self.assertEqual(duplicate_posts(self.brief, [post]), [post])

    def test_reviewed_related_existing_post_may_share_action_url(self):
        post = {
            **self.post,
            'post_content': (
                '<div class="bloguito-cta"><a href="' + self.url.replace('&', '&amp;')
                + '">조회 시작</a></div>' + self.footer
            ),
        }
        self.assertEqual(
            duplicate_posts(self.brief, [post], related_post_ids={139}),
            [],
        )

    def test_related_post_title_duplicate_still_blocks(self):
        post = {
            **self.post,
            'post_title': '기초연금 소득인정액 모의계산',
            'post_content': (
                '<div class="bloguito-cta"><a href="' + self.url.replace('&', '&amp;')
                + '">조회 시작</a></div>' + self.footer
            ),
        }
        self.assertEqual(
            duplicate_posts(self.brief, [post], related_post_ids={139}),
            [post],
        )

    def test_new_post_cannot_use_related_action_exception(self):
        new_brief = {key: value for key, value in self.brief.items()
                     if key != 'existing_post_id'}
        post = {
            **self.post,
            'post_content': (
                '<div class="bloguito-cta"><a href="' + self.url.replace('&', '&amp;')
                + '">조회 시작</a></div>' + self.footer
            ),
        }
        self.assertEqual(
            duplicate_posts(new_brief, [post], related_post_ids={139}),
            [post],
        )

    def test_legacy_post_with_same_url_remains_duplicate(self):
        post = {**self.post, 'post_content': '<a href="' + self.url + '">공식 안내</a>'}
        self.assertEqual(duplicate_posts(self.brief, [post]), [post])

    def test_new_post_still_blocks_identical_official_citation(self):
        new_brief = {key: value for key, value in self.brief.items()
                     if key != 'existing_post_id'}
        self.assertEqual(duplicate_posts(new_brief, [self.post]), [self.post])


if __name__ == '__main__':
    unittest.main()
