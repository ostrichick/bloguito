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

    def test_exact_30_day_month_equivalent_is_allowed(self):
        from agents.editorial import supported_currency_sums
        supported, errors = supported_currency_sums(
            '150일 (약 5개월)', '공식 예상 지급일수 150일',
            [{'operation': 'days_to_months', 'days': 150, 'months': 5}],
        )
        self.assertEqual({'5'}, supported)
        self.assertEqual([], errors)

    def test_non_exact_month_equivalent_is_rejected(self):
        from agents.editorial import supported_currency_sums
        supported, errors = supported_currency_sums(
            '150일 (약 6개월)', '공식 예상 지급일수 150일',
            [{'operation': 'days_to_months', 'days': 150, 'months': 6}],
        )
        self.assertEqual(set(), supported)
        self.assertIn('invalid_derived_calculation', errors)


if __name__ == '__main__':
    unittest.main()
