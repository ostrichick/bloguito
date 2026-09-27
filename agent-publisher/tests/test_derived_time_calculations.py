import unittest

from agents.editorial import supported_currency_sums


class DerivedTimeCalculationTests(unittest.TestCase):
    def test_start_time_plus_running_minutes_supports_scheduled_end_time(self):
        text = '오후 6시 30분~오후 8시 30분, 총 120분'
        evidence = '운영 시간 11월 8일(일) 오후 6시 30분 시간 120분'
        supported, errors = supported_currency_sums(text, evidence, [{
            'operation': 'add_duration',
            'unit': '분',
            'start': '오후 6시 30분',
            'duration': 120,
            'result': '오후 8시 30분',
        }])
        self.assertEqual([], errors)
        self.assertTrue({'8', '30'}.issubset(supported))

    def test_wrong_scheduled_end_time_is_rejected(self):
        text = '오후 6시 30분~오후 9시 30분, 총 120분'
        evidence = '운영 시간 11월 8일(일) 오후 6시 30분 시간 120분'
        _, errors = supported_currency_sums(text, evidence, [{
            'operation': 'add_duration',
            'unit': '분',
            'start': '오후 6시 30분',
            'duration': 120,
            'result': '오후 9시 30분',
        }])
        self.assertEqual(['invalid_derived_calculation'], errors)


if __name__ == '__main__':
    unittest.main()
