"""Reject ungrounded rent-benefit rates and arithmetic in decision comparisons."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.rent_benefit_math import validate_rent_benefit
from agents.editorial import supported_currency_sums


class RentBenefitMathTests(unittest.TestCase):
    LAW = ('조특법: 공제율 100분의 17 또는 100분의 15, 현금영수증 100분의 30, 최저사용액 100분의 25. '
           '표준세액공제 연 13만원. 국세청 과세표준과 기본세율의 표: 15%, 24%.')

    def sample(self, salary, rent, marginal, credit):
        return {'operation':'rent_benefit_example','salary_man':salary,
                'monthly_rent_man':rent,'months':12,'credit_percent':credit,
                'marginal_percent':marginal,'standard_credit_man':13}

    def test_credit_favored_full_cash_and_standard_credit_comparison(self):
        data=self.sample(4000,50,15,17)
        text='총급여 4000만원, 월세 50만원 × 12개월(가정). 세액공제 102만원, 현금영수증 27만원 + 표준세액공제 13만원 = 40만원, 차이 62만원.'
        allowed,faults=validate_rent_benefit(data,text,self.LAW)
        self.assertEqual([],faults)
        self.assertTrue({'102','27','40','62','4000','50'}.issubset(allowed))
        self.assertEqual((set(),[]),supported_currency_sums(text,self.LAW,[]))
        amounts,errors=supported_currency_sums(text,self.LAW,[data])
        self.assertEqual([],errors)
        self.assertIn('62',amounts)

    def test_credit_ineligible_and_cash_savings(self):
        data=self.sample(9000,50,24,0)
        text='총급여 9000만원, 월세 50만원 × 12개월(가정). 현금영수증 공제 효과 43.2만원 + 표준세액공제 13만원 = 합계 56.2만원.'
        allowed,errors=validate_rent_benefit(data,text,self.LAW)
        self.assertFalse(errors)
        self.assertIn('43.2',allowed)
        self.assertIn('56.2',allowed)

    def test_small_rent_and_conditional_break_even(self):
        data=self.sample(4000,6,15,17)
        text='총급여 4000만원, 월세 6만원 × 12개월(가정). 세액공제 12.24만원, 현금영수증 3.24만원 + 표준세액공제 13만원 = 16.24만원, 차이 4만원, 손익분기 연 104만원(월 약 8.67만원).'
        allowed,errors=validate_rent_benefit(data,text,self.LAW)
        self.assertFalse(errors)
        self.assertTrue({'12.24','3.24','16.24','4','104','8.67'}.issubset(allowed))

    def test_no_unproven_legal_rate_or_unlabelled_input(self):
        data=self.sample(4000,50,15,17)
        text='총급여 4000만원, 월세 50만원 × 12개월. 현금영수증 27만원.'
        self.assertIn('invalid_derived_calculation',validate_rent_benefit(data,text,self.LAW)[1])
        text += ' 가정.'
        self.assertIn('invalid_derived_calculation',validate_rent_benefit(data,text,'현금영수증 100분의 30 100분의 25. 2018.12.24. 표준세액공제 13만원')[1])

    def test_salary_above_eligibility_cannot_claim_credit(self):
        data=self.sample(9000,50,24,17)
        text='총급여 9000만원, 월세 50만원 × 12개월 가정. 현금영수증.'
        self.assertIn('invalid_derived_calculation',validate_rent_benefit(data,text,self.LAW)[1])


if __name__=='__main__':
    unittest.main()
