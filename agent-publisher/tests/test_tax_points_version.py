"""Tax-point cohort checks accept the NTS official shortened Korean year form."""
import hashlib
import unittest
from datetime import datetime

from agents.critical_facts import critical_fact_reasons
from agents.temporal_validation import KST


def source(text):
    return {
        'id': 's0',
        'url': 'https://nts.go.kr/nts/na/ntt/selectNttInfo.do?bbsId=1028&mi=2201&nttSn=1355091',
        'title': '국세청 보도자료',
        'text': text,
        'sha256': hashlib.sha256(text.encode()).hexdigest(),
        'source_type': 'official',
        'fetched_at': datetime(2026, 9, 23, 15, tzinfo=KST).isoformat(),
    }


class TaxPointVersionTests(unittest.TestCase):
    def test_official_short_year_satisfies_version_and_body_cohort(self):
        text = ('세금포인트 소멸 기한 5년. 개인납세자는 ’25년에 부여하는 포인트부터 적용. '
                '1년에 개인·법인 인당 1,000포인트 한도로 부여.')
        brief = {'entity': '2026 국세청 세금포인트',
                 'primary_keyword': '2026 세금포인트',
                 'official_urls': [source(text)['url']]}
        plan = {'title': '2026 세금포인트 안내',
                'lead': {'text': '개인의 5년 소멸기한은 ’25년에 부여하는 포인트부터 적용합니다.'},
                'sections': [], 'faq': []}
        reasons = critical_fact_reasons(brief, [source(text)], plan)
        self.assertNotIn('tax_points_2026_authoritative_version_missing', reasons)
        self.assertNotIn('tax_points_2026_expiry_cohort_missing', reasons)

    def test_missing_cohort_still_fails_closed(self):
        text = '세금포인트 소멸 기한 5년. 1년에 개인·법인 인당 1,000포인트 한도로 부여.'
        brief = {'entity': '2026 국세청 세금포인트',
                 'primary_keyword': '2026 세금포인트',
                 'official_urls': [source(text)['url']]}
        plan = {'title': '2026 세금포인트 안내',
                'lead': {'text': '개인의 5년 소멸기한이 적용됩니다.'},
                'sections': [], 'faq': []}
        reasons = critical_fact_reasons(brief, [source(text)], plan)
        self.assertIn('tax_points_2026_authoritative_version_missing', reasons)
        self.assertIn('tax_points_2026_expiry_cohort_missing', reasons)


if __name__ == '__main__':
    unittest.main()
