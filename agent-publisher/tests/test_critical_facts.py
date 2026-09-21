"""Regression tests for known stale-source failures in Bloguito, with no network calls."""
import hashlib
import unittest
from datetime import date
from agents.critical_facts import critical_fact_reasons, published_content_risks
from agents.editorial import validate_bundle
from test_editorial_system import sample, NOW


class CriticalPolicyRegressionTests(unittest.TestCase):
    def pension_bundle(self, source, claim):
        b = sample()
        b['brief'].update(entity='기초연금',primary_keyword='2026 기초연금 수급 기준',required_title_terms=['2026','기초연금'],official_urls=['https://www.mohw.go.kr/2026-guide'])
        b['plan']['title']='2026 기초연금 수급 기준'
        b['sources'][0].update(url=b['brief']['official_urls'][0],text=source,sha256=hashlib.sha256(source.encode()).hexdigest())
        for item in (b['plan']['lead'],b['plan']['sections'][0]['paragraphs'][0]):
            item['text']=claim
            item['evidence']=[{'source_id':'s0','quote':source}]
        return b

    def test_stale_government_text_and_exact_quote_cannot_pass(self):
        source='2026년 기초연금 단독가구 213만 원이고 월 최대 343,510원입니다.'
        b=self.pension_bundle(source,source)
        report=validate_bundle(b,{'checked_on':NOW.date().isoformat(),'posts':[]},now=NOW,require_review=False)
        self.assertIn('pension_2026_authoritative_baseline_missing',report['reasons'])
        self.assertIn('pension_2026_stale_annual_figures',report['reasons'])
        self.assertNotIn('quote_not_in_source',report['reasons'])

    def test_current_2026_pension_source_is_accepted(self):
        source='2026년 기초연금 단독 247만 원, 부부 395만 2,000원, 기준연금액 349,700원, 근로소득 기본공제 116만 원.'
        b=self.pension_bundle(source,'2026년 기초연금 단독 247만 원, 부부 395만 2,000원, 기준연금액 349,700원입니다.')
        r=critical_fact_reasons(b['brief'],b['sources'],b['plan'])
        self.assertEqual(r,[])

    def test_2026_tax_old_cap_rejected_even_with_official_quote(self):
        b={'entity':'세금포인트','primary_keyword':'2026 세금포인트 한도'}
        src=[{'source_type':'official','url':'https://www.nts.go.kr/old','text':'2026년 세금포인트 연간 최대 50점, 5년의 유효기간.'}]
        plan={'title':'2026 세금포인트','lead':{'text':'연간 최대 50점입니다. 5년 뒤 소멸합니다.'},'sections':[], 'faq':[]}
        r=critical_fact_reasons(b,src,plan)
        self.assertIn('tax_points_2026_authoritative_version_missing',r)
        self.assertIn('tax_points_2026_stale_50_point_cap',r)
        self.assertIn('tax_points_2026_expiry_cohort_missing',r)

    def test_tax_current_cohort_details_accepted(self):
        b={'entity':'세금포인트','primary_keyword':'2026 세금포인트'}
        source='2026년 국세청: 2025년 부여분부터 개인 연간 1,000포인트 한도, 개인의 5년 소멸기한 적용.'
        s=[{'source_type':'official','url':'https://www.nts.go.kr/notice','text':source}]
        plan={'title':'2026 세금포인트','lead':{'text':source},'sections':[],'faq':[]}
        self.assertEqual(critical_fact_reasons(b,s,plan),[])

    def test_influenza_older_schedule_and_quad_vaccine_blocked(self):
        b={'entity':'독감','primary_keyword':'2026 독감 백신'}
        s=[{'source_type':'official','url':'https://www.kdca.go.kr/2026','text':'2026년 독감 9월 20일 시작, 4가 백신'}]
        plan={'title':'2026 독감 안내','lead':{'text':'4가 백신, 9월 20일부터 접종'},'sections':[],'faq':[]}
        r=critical_fact_reasons(b,s,plan)
        self.assertEqual(len(r),3)

    def test_influenza_latest_2026_version_accepted(self):
        b={'entity':'독감','primary_keyword':'2026 독감 백신'}
        s=[{'source_type':'official','url':'https://www.kdca.go.kr/latest','text':'2026년 9월 16일 조정. 3가 백신. 9월 21일 어린이, 10월 6일 75세 이상.'}]
        plan={'title':'2026 독감 안내','lead':{'text':'3가 백신, 어린이는 9월 21일부터'},'sections':[],'faq':[]}
        self.assertEqual(critical_fact_reasons(b,s,plan),[])

    def test_correction_note_is_not_mistaken_for_active_old_claim(self):
        markup = '<div><strong>정정 안내 (2026년 9월 20일)</strong><p>연간 최대 50점 안내를 수정했습니다.</p></div><p>2025년 부여분부터 연간 1,000포인트입니다.</p>'
        self.assertEqual(published_content_risks('2026 세금포인트',markup),['internal_editorial_note_exposed'])
        flu = '<div><strong>정정 안내 (2026년 9월 20일)</strong>4가 백신 오류</div><p>3가 백신. 기존의 9월 20일부터 일정은 폐기했습니다.</p>'
        self.assertEqual(published_content_risks('2026 독감',flu),['internal_editorial_note_exposed'])

    def test_insurance_marketing_guarantee_rejected(self):
        b={'entity':'숨은 보험금','primary_keyword':'2026 숨은 보험금'}
        src=[{'source_type':'official','url':'https://www.fsc.go.kr/2021','text':'2021년 금융위원회: 별도 확인이 필요 없을 경우 3영업일 지급.'}]
        plan={'title':'2026 숨은 보험금','lead':{'text':'매년 12조 원 이상, 1,000만 원 이하 즉시 입금.'},'sections':[],'faq':[]}
        self.assertIn('insurance_2026_unverified_guarantee_or_amount',critical_fact_reasons(b,src,plan))

    def test_health_refund_unverified_2026_amount_rejected(self):
        b={'entity':'본인부담상한제','primary_keyword':'2026 본인부담상한제'}
        src=[{'source_type':'official','url':'https://www.nhis.or.kr/2024','text':'2024년 1분위 87만 원.'}]
        plan={'title':'2026 본인부담상한제','lead':{'text':'2026년 1분위 본인부담 상한액 약 87만 원, 평균 약 130만 원.'},'sections':[],'faq':[]}
        reasons=critical_fact_reasons(b,src,plan)
        self.assertIn('health_refund_2026_unverified_year_or_amount',reasons)
        self.assertIn('health_refund_2026_service_year_source_missing',reasons)

    def test_ev_free_claim_needs_2026_event_and_kwh_units(self):
        b={'entity':'전기차','primary_keyword':'2026 고속도로 전기차 충전'}
        src=[{'source_type':'official','url':'https://www.roadplus.co.kr/guide','text':'2024년 추석 휴게소 충전소 현황'}]
        plan={'title':'2026 전기차 충전','lead':{'text':'휴게소 무료 급속충전 1회 20kW 주행분 제공'},'sections':[],'faq':[]}
        reasons=critical_fact_reasons(b,src,plan)
        self.assertIn('ev_2026_free_charging_event_unverified',reasons)
        self.assertIn('ev_charging_energy_unit_kwh_required',reasons)

    def test_legacy_publication_scanner(self):
        self.assertIn('pension_known_stale_2026',published_content_risks('2026 기초연금','2026년 213만 원'))
        self.assertIn('outdated_today_event',published_content_risks('오늘 마지막 공연','오늘(2026년 9월 13일)',today=date(2026,9,20)))
        self.assertEqual(published_content_risks('2026 기초연금','2026년 247만 원'),[])

if __name__=='__main__': unittest.main()
