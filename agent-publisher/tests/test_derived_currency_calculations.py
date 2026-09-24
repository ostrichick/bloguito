"""Derived reference prices may only be exact sums of cited official won amounts."""
import unittest

from agents.editorial import validate_bundle
from tests.test_editorial_system import NOW, sample, sign


class DerivedCurrencyCalculationTests(unittest.TestCase):
    def setUp(self):
        self.bundle = sample()
        self.source_text = ('만 30세 이상, 1일 요율은 1.000입니다. 기본 보험료는 대인 2,260원, 대물 4,130원, '
                            '자기신체 240원, 수리 1,520원입니다.')
        self.bundle['sources'][0]['text'] += '\n' + self.source_text
        import hashlib
        self.bundle['sources'][0]['sha256'] = hashlib.sha256(
            self.bundle['sources'][0]['text'].encode()).hexdigest()
        self.block = self.bundle['plan']['lead']
        self.block['text'] = '공식 기본 담보를 단순 합산한 1일 참고금액은 약 8,150원입니다.'
        self.block['evidence'] = [{'source_id': 's0', 'quote': self.source_text}]
        self.block['calculations'] = [{
            'operation': 'sum', 'unit': '원',
            'operands': [2260, 4130, 240, 1520], 'result': 8150,
        }]
        self.inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}

    def check(self):
        sign(self.bundle)
        return validate_bundle(self.bundle, self.inventory, NOW)

    def test_exact_cited_won_sum_is_allowed(self):
        self.assertEqual('ready', self.check()['status'])

    def test_wrong_sum_is_rejected(self):
        self.block['calculations'][0]['result'] = 9000
        self.block['text'] = '공식 기본 담보를 단순 합산한 1일 참고금액은 약 9,000원입니다.'
        self.assertIn('invalid_derived_calculation', self.check()['reasons'])

    def test_uncited_operand_is_rejected(self):
        self.block['calculations'][0]['operands'][-1] = 1600
        self.block['calculations'][0]['result'] = 8230
        self.block['text'] = '공식 기본 담보를 단순 합산한 1일 참고금액은 약 8,230원입니다.'
        self.assertIn('invalid_derived_calculation', self.check()['reasons'])

    def test_non_sum_operation_is_rejected(self):
        self.block['calculations'][0]['operation'] = 'average'
        self.assertIn('invalid_derived_calculation', self.check()['reasons'])

    def test_table_row_calculation_is_preserved(self):
        self.block.pop('calculations')
        self.block['text'] = self.source_text
        self.bundle['plan']['sections'][0]['table'] = {
            'caption': '참고 보험료',
            'headers': ['연령', '1일 참고금액'],
            'rows': [{
                'cells': ['만 30세 이상', '약 8,150원'],
                'evidence': [{'source_id': 's0', 'quote': self.source_text}],
                'answers': ['q1'],
                'calculations': [{
                    'operation': 'sum', 'unit': '원',
                    'operands': [2260, 4130, 240, 1520], 'result': 8150,
                }],
            }],
        }
        self.assertEqual('ready', self.check()['status'])


if __name__ == '__main__':
    unittest.main()
