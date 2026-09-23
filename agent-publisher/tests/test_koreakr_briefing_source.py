"""The exact One-Click briefing source excludes news rails, not source facts."""
import hashlib
import unittest
from unittest.mock import patch

from agents.editorial_writer import fetch_sources


URL = 'https://www.korea.kr/briefing/policyBriefingView.do?newsId=156681719'
FILENAMES = ('속기자료.hwp', '속기자료.pdf', '원클릭_환급_안내.hwp',
             '원클릭_환급_안내.hwpx')


class Response:
    status_code = 200

    def __init__(self, markup):
        self.content = markup.encode('utf-8')


def page(*, title="원클릭 환급 서비스", date='2025.03.31', author='국세청 담당자',
         amount='5년', rail='실시간 인기뉴스 09.22. 14:37', filenames=FILENAMES,
         file_ids=(101, 102, 103, 104), duplicate_body=False,
         include_files=True):
    rows = ''.join(
        '<p><span><a href="/common/download.do?fileId=' + str(file_id) + '">'
        + name + '</a></span><span><a class="view">바로보기</a>'
        '<a class="down">내려받기</a></span></p>'
        for name, file_id in zip(filenames, file_ids))
    files = ('<div class="filedown"><dl><dt>첨부파일</dt><dd>' + rows
             + '</dd></dl></div>') if include_files else ''
    body = ('<div class="article_body"><div class="view_cont">'
            '<p>국세청은 3월 31일 공식 원클릭 서비스 안내를 발표했습니다.</p>'
            f'<p>신청 가능한 환급금은 최대 {amount} 치로 설명했습니다.</p>'
            '</div></div>')
    if duplicate_body:
        body += '<div class="article_body"><div class="view_cont">중복</div></div>'
    return ('<html><head><title>정책브리핑</title></head><body>'
            '<main id="main"><section id="container">'
            f'<div class="view_title"><h1>{title}</h1></div>'
            '<div class="article_wrap"><div class="container">'
            '<div class="article_head"><div class="variety"><div class="info">'
            f'<span>{date}</span><span>{author}</span></div>'
            '<div class="tool"><span>글자크기 설정</span></div></div>'
            + files + '</div>' + body + '</div></div>'
            '<aside class="as_side"><div class="side_row trend">'
            f'<h2>{rail}</h2><ol><li>인기뉴스 1위</li></ol></div>'
            '<div class="side_row latest">최신뉴스 변경</div></aside>'
            '</section></main></body></html>')


def fetch_one(markup, url=URL):
    with patch('agents.editorial_writer.requests.get', return_value=Response(markup)):
        return fetch_sources({'official_urls': [url], 'entity': '국세 환급금'})[0]


class KoreaKrBriefingSourceTests(unittest.TestCase):
    def test_sidebar_rotation_does_not_change_source_hash(self):
        first = fetch_one(page(rail='실시간 인기뉴스 09.22. 14:37'))
        second = fetch_one(page(rail='실시간 인기뉴스 09.22. 16:01'))
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual(first['sha256'], hashlib.sha256(first['text'].encode()).hexdigest())
        for fact in ('원클릭 환급 서비스', '2025.03.31', '국세청 담당자',
                     '첨부파일', *FILENAMES, '최대 5년 치', '/common/download.do?fileId=101'):
            self.assertIn(fact, first['text'])
        for excluded in ('실시간 인기뉴스', '인기뉴스 1위', '최신뉴스', '글자크기'):
            self.assertNotIn(excluded, first['text'])

    def test_evidence_bearing_edits_change_hash(self):
        baseline = fetch_one(page())
        modifications = (
            page(title='원클릭 환급 서비스 수정'),
            page(date='2025.04.01'),
            page(author='국세청 다른 담당자'),
            page(amount='4년'),
            page(filenames=('속기자료_수정.hwp', *FILENAMES[1:])),
            page(file_ids=(999, 102, 103, 104)),
        )
        for markup in modifications:
            with self.subTest(edit=markup[markup.find('class="filedown"'):][:110]):
                self.assertNotEqual(baseline['sha256'], fetch_one(markup)['sha256'])

    def test_missing_ambiguous_and_bad_attachment_structure_fails_closed(self):
        invalid = (
            page().replace('<h1>원클릭 환급 서비스</h1>', ''),
            page().replace('<span>2025.03.31</span>', '<span>날짜 미상</span>'),
            page(duplicate_body=True),
            page(include_files=False),
            page(filenames=('자료.txt', *FILENAMES[1:])),
            page(file_ids=('invalid', 102, 103, 104)),
        )
        for markup in invalid:
            with self.subTest(markup=markup[-150:]):
                with self.assertRaisesRegex(ValueError, 'koreakr_briefing_'):
                    fetch_one(markup)

    def test_other_briefing_ids_keep_existing_generic_extraction(self):
        source = fetch_one(page(rail='실시간 인기뉴스 기준 변동'),
                           url=URL.replace('156681719', '156681720'))
        self.assertIn('실시간 인기뉴스', source['text'])


if __name__ == '__main__':
    unittest.main()
