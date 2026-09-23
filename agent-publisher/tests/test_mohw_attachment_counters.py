"""MOHW attachment counters may fluctuate; evidence-bearing text must not."""
import unittest
from unittest.mock import patch

from agents.editorial_writer import fetch_sources


URL = ('https://www.mohw.go.kr/board.es?act=view&bid=0027'
       '&list_no=1488478&mid=a10503010100')


class Response:
    status_code = 200

    def __init__(self, html):
        self.content = html.encode('utf-8')


def board(*, downloads=('2389', '21006'), previews=('2722', '2751'),
          names=('2026년 기초연금 안내.hwpx', '2026년 기초연금 안내.pdf'),
          sizes=('127.32KB', '363.34KB'), amount='247', extra_span=''):
    rows = []
    for index in range(2):
        rows.append(
            '<li><img src="/upload/skin/board/basic/file.png" />'
            + names[index]
            + '<span class="txt">( ' + sizes[index] + ' / 다운로드 '
            + downloads[index] + '회 / 미리보기 ' + previews[index] + '회 )</span>'
            + (extra_span if index == 0 else '')
            + '<span class="link"><a href="/boardDownload.es?seq=' + str(index + 1)
            + '">다운로드</a><a href="/attachPreview.es?seq=' + str(index + 1)
            + '">미리보기/음성듣기</a></span></li>')
    return ('<html><head><title>보건복지부 보도자료</title></head><body>'
            '<ul><li class="hit"><strong>조회수</strong><span>: </span>'
            '<span>123,456</span></li></ul>'
            '<article><p>2026년 기초연금 단독가구 소득인정액은 월 '
            + amount + '만 원 이하입니다. 추가 지급기준도 본문에서 설명합니다.</p>'
            '<p>다른 수치는 중요한 공식 근거이며 누락해서는 안 됩니다.</p></article>'
            '<div class="file"><strong class="title">첨부파일</strong>'
            '<ul class="list">' + ''.join(rows) + '</ul></div></body></html>')


class MohwAttachmentCounterTests(unittest.TestCase):
    def fetch(self, *htmls, url=URL):
        with patch('agents.editorial_writer.requests.get',
                   side_effect=[Response(html) for html in htmls]):
            return [fetch_sources({'official_urls': [url], 'entity': '기초연금'})[0]
                    for _ in htmls]

    def test_only_download_and_preview_in_verified_attachment_span_are_volatile(self):
        previous, current = self.fetch(
            board(), board(downloads=('2390', '21007'), previews=('2723', '2752')))
        self.assertEqual(previous['sha256'], current['sha256'])
        self.assertEqual(previous['text'], current['text'])
        self.assertIn('2026년 기초연금 안내.hwpx', previous['text'])
        self.assertIn('127.32KB', previous['text'])
        self.assertIn('363.34KB', previous['text'])
        self.assertIn('247만 원', previous['text'])
        self.assertNotIn('2389회', previous['text'])
        self.assertNotIn('2751회', previous['text'])

    def test_2026_refund_article_has_same_narrow_counter_normalization(self):
        refund_url = URL.replace('list_no=1488478', 'list_no=1491727')
        before, after = self.fetch(
            board(),
            board(downloads=('2391', '21008'), previews=('2724', '2753')),
            url=refund_url)
        self.assertEqual(before['sha256'], after['sha256'])
        self.assertIn('127.32KB', before['text'])
        self.assertIn('2026년 기초연금 안내.pdf', before['text'])
        self.assertIn('247만 원', before['text'])
        self.assertNotIn('2391회', after['text'])

    def test_2026_refund_article_file_or_article_change_still_changes_sha(self):
        refund_url = URL.replace('list_no=1488478', 'list_no=1491727')
        initial, renamed, resized, amount_changed = self.fetch(
            board(), board(names=('보도자료 교체.hwpx', '2026년 기초연금 안내.pdf')),
            board(sizes=('127.34KB', '363.34KB')), board(amount='249'),
            url=refund_url)
        for changed in (renamed, resized, amount_changed):
            self.assertNotEqual(initial['sha256'], changed['sha256'])

    def test_filename_size_and_body_number_each_change_source_digest(self):
        original, name_changed, size_changed, body_changed = self.fetch(
            board(),
            board(names=('2026년 기초연금 수정안.hwpx', '2026년 기초연금 안내.pdf')),
            board(sizes=('127.33KB', '363.34KB')),
            board(amount='248'))
        for modified in (name_changed, size_changed, body_changed):
            self.assertNotEqual(original['sha256'], modified['sha256'])
        self.assertIn('수정안.hwpx', name_changed['text'])
        self.assertIn('127.33KB', size_changed['text'])
        self.assertIn('248만 원', body_changed['text'])

    def test_does_not_normalize_other_mohw_board_article(self):
        other_url = URL.replace('list_no=1488478', 'list_no=1488479')
        first, second = self.fetch(board(), board(downloads=('2390', '21007')),
                                   url=other_url)
        self.assertNotEqual(first['sha256'], second['sha256'])
        self.assertIn('2389회', first['text'])

    def test_unknown_counter_format_and_ambiguous_spans_fail_closed(self):
        invalid = board().replace('다운로드 2389회', '다운로드 확인 중')
        duplicate = board(extra_span='<span class="txt">( 1KB / 다운로드 2회 / 미리보기 3회 )</span>')
        missing = board().replace('<ul class="list">', '<ul class="attachments">')
        for html in (invalid, duplicate, missing):
            with self.subTest(html=html[-140:]):
                with self.assertRaisesRegex(ValueError, 'mohw_attachment_'):
                    self.fetch(html)


if __name__ == '__main__':
    unittest.main()
