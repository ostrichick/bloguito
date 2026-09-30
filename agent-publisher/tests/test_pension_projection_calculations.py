"""Pension examples may derive fixed-horizon totals from cited official inputs only."""
import hashlib
import unittest

from agents.editorial import validate_bundle
from tests.test_editorial_system import NOW, sample, sign


class PensionProjectionCalculationTests(unittest.TestCase):
    def setUp(self):
        self.bundle = sample()
        self.source_text = (
            '가입기간 20년의 예상연금월액은 558,300원입니다. '
            '최대 5년 일찍 수급하면 30% 감액되고, 최대 5년 연기하면 36% 가산됩니다.'
        )
        self.bundle['sources'][0]['text'] += '\n' + self.source_text
        self.bundle['sources'][0]['sha256'] = hashlib.sha256(
            self.bundle['sources'][0]['text'].encode()).hexdigest()
        self.block = self.bundle['plan']['lead']
        self.block['text'] = (
            '5년 조기수령 예시의 월액은 390,810원이며, 정상 개시연령보다 10년 뒤 누적은 '
            '70,345,800원, 20년 뒤 누적은 117,243,000원입니다.'
        )
        self.block['evidence'] = [{'source_id': 's0', 'quote': self.source_text}]
        self.block['calculations'] = [{
            'operation': 'pension_projection',
            'unit': '원',
            'base_monthly': 558300,
            'direction': 'decrease',
            'change_percent': 30,
            'start_offset_years': -5,
            'monthly_result': 390810,
            'horizons': [
                {'years_after_normal': 10, 'cumulative_result': 70345800},
                {'years_after_normal': 20, 'cumulative_result': 117243000},
            ],
        }]
        self.inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}

    def check(self):
        sign(self.bundle)
        return validate_bundle(self.bundle, self.inventory, NOW)

    def test_cited_pension_projection_is_allowed(self):
        self.assertEqual('ready', self.check()['status'])

    def test_wrong_monthly_projection_is_rejected(self):
        self.block['calculations'][0]['monthly_result'] = 390811
        self.block['text'] = self.block['text'].replace('390,810원', '390,811원')
        self.assertIn('invalid_derived_calculation', self.check()['reasons'])

    def test_wrong_cumulative_projection_is_rejected(self):
        self.block['calculations'][0]['horizons'][0]['cumulative_result'] = 70345801
        self.block['text'] = self.block['text'].replace('70,345,800원', '70,345,801원')
        self.assertIn('invalid_derived_calculation', self.check()['reasons'])

    def test_uncited_rate_is_rejected(self):
        self.block['calculations'][0]['change_percent'] = 29
        self.assertIn('invalid_derived_calculation', self.check()['reasons'])

    def test_normal_projection_uses_cited_base_without_rate(self):
        self.block['text'] = (
            '정상 수령 예시의 월액은 558,300원이며, 정상 개시연령보다 10년 뒤 누적은 '
            '66,996,000원, 20년 뒤 누적은 133,992,000원입니다.'
        )
        self.block['calculations'] = [{
            'operation': 'pension_projection', 'unit': '원', 'base_monthly': 558300,
            'direction': 'none', 'change_percent': 0, 'start_offset_years': 0,
            'monthly_result': 558300,
            'horizons': [
                {'years_after_normal': 10, 'cumulative_result': 66996000},
                {'years_after_normal': 20, 'cumulative_result': 133992000},
            ],
        }]
        self.assertEqual('ready', self.check()['status'])


if __name__ == '__main__':
    unittest.main()
