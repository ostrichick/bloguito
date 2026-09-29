import unittest

from agents.editorial_writer import _normalize_busan_junggu_weather


URL = (
    'https://www.bsjunggu.go.kr/tour/index.junggu?'
    'menuCd=DOM_000000203003000000'
)


class BusanJungguSourceNormalizationTests(unittest.TestCase):
    def test_weather_widget_changes_do_not_change_event_source_snapshot(self):
        template = (
            '제33회 부산자갈치 축제\n'
            '10.15.(목)~10.18.(일)\n'
            '자갈치시장, 유라리광장 일원\n'
            '만족도 영역\n매우 만족\n만족\n보통\n불만족\n매우 불만족\n'
            '{temperature}\n℃\n미세먼지\n{dust}\n관광도우미\n관광지도'
        )
        first = template.format(temperature='20', dust='보통')
        second = template.format(temperature='21', dust='좋음')
        self.assertEqual(
            _normalize_busan_junggu_weather(first, URL),
            _normalize_busan_junggu_weather(second, URL),
        )
        normalized = _normalize_busan_junggu_weather(first, URL)
        self.assertIn('10.15.(목)~10.18.(일)', normalized)
        self.assertNotIn('\n20\n', normalized)
        self.assertNotIn('미세먼지', normalized)

    def test_other_urls_are_unchanged(self):
        text = '매우 불만족\n20\n℃\n미세먼지\n보통\n관광도우미'
        self.assertEqual(
            text,
            _normalize_busan_junggu_weather(text, 'https://example.org/tour'),
        )

    def test_exact_page_fails_closed_if_weather_shape_changes(self):
        text = '매우 불만족\n21도\n℃\n미세먼지\n보통\n관광도우미'
        with self.assertRaisesRegex(
                ValueError, 'busan_junggu_weather_widget_structure_changed'):
            _normalize_busan_junggu_weather(text, URL)


if __name__ == '__main__':
    unittest.main()
