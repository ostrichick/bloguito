import copy
import hashlib
import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from agents.editorial import validate_bundle, topic_reasons, digest, policy, policy_fingerprint, render, supported_counts
from agents.editorial_writer import EditorialWriterAgent, article_from_bundle
from agents.temporal_validation import KST, extract_evidence
from agents.publisher import PublisherAgent

NOW = datetime(2026, 9, 14, 12, tzinfo=KST)


def sample():
    text = '서초구 가정용 선풍기는 배출수수료 면제 대상입니다. 아파트 단지 수집 거치대에 배출합니다.'
    brief = {'id':'test', 'category_key':'life-health', 'approved':True, 'entity':'서초구',
        'primary_keyword':'서초구 선풍기 버리는 법', 'question':'어디에 버리나?', 'angle':'1개 배출',
        'official_urls':['https://www.seocho.go.kr/guide'], 'required_title_terms':['서초구','선풍기'],
        'content_type':'evergreen', 'useful_until':None, 'evergreen_reason':'반복 배출 절차',
        'reviewed_at':'2026-09-14', 'review_until':'2026-10-01',
        'reader_questions':[{'id':'q1','question':'어디에 버리나?'}]}
    block = {'text':'서초구 가정용 선풍기는 배출수수료 면제 대상입니다.',
        'evidence':[{'source_id':'s0','quote':text}], 'answers':['q1']}
    bundle = {'brief':brief, 'sources':[{'id':'s0','url':brief['official_urls'][0], 'title':'배출 안내',
        'text':text, 'sha256':hashlib.sha256(text.encode()).hexdigest(), 'source_type':'official', 'fetched_at':NOW.isoformat()}],
        'plan':{'title':'서초구 선풍기 버리는 법', 'lead':block,
        'sections':[{'heading':'배출 방법','paragraphs':[{'text':'아파트 단지 수집 거치대에 배출합니다.', 'evidence':block['evidence'], 'answers':['q1']}]}], 'faq':[]},
        'temporal_source':{}}
    sign(bundle)
    return bundle


def sign(bundle):
    body = {k:bundle[k] for k in ('brief','sources','plan','temporal_source')}
    bundle['review']={'digest':digest(body),'policy_digest':policy_fingerprint(), 'checked_at':NOW.isoformat(),
        'checks':{k:True for k in policy()['review_checks']}, 'issues':[]}


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.b = sample()
        self.inventory={'checked_on':'2026-09-14','posts':[]}

    def check(self, review=True):
        return validate_bundle(self.b,self.inventory,NOW,require_review=review)

    def test_summary_numbering_and_escaping(self):
        self.b['plan']['sections'].append({'heading':'2. 조건 <안내>', 'paragraphs':[self.b['plan']['lead']]})
        content = render(self.b['plan'], self.b['sources'])
        self.assertIn('>핵심 답변</div>', content)
        self.assertNotIn('3초 요약', content)
        self.assertIn('>배출 방법</h2>', content)
        self.assertNotIn('STEP 1</span>배출 방법', content)
        self.assertIn('>조건 &lt;안내&gt;</h2>', content)
        self.assertNotIn('STEP 2</span>조건', content)
        self.assertIn(self.b['plan']['lead']['text'], content)
        self.assertIn('https://www.seocho.go.kr/guide', content)
        # 네이티브 경량 목차(TOC) 및 점프 링크 앵커 검증
        self.assertIn('class="bloguito-toc"', content)
        self.assertIn('href="#step-1"', content)
        self.assertIn('id="step-1"', content)
        self.assertIn('href="#step-2"', content)
        self.assertIn('id="step-2"', content)
        self.assertIn('id="sources"', content)

    def test_render_toc_with_faq(self):
        self.b['plan']['faq'].append({'question_id':'q1','question':'FAQ 질문','answer':self.b['plan']['lead']})
        content = render(self.b['plan'], self.b['sources'])
        self.assertIn('href="#faq"', content)
        self.assertIn('id="faq"', content)

    def test_reader_middle_dot_is_rejected_but_source_snapshot_can_preserve_it(self):
        self.b['plan']['title'] = '서초구 선풍기 배출·수거 방법'
        self.assertIn('reader_middle_dot_disallowed', self.check(review=False)['reasons'])

        self.b = sample()
        self.b['sources'][0]['text'] += ' 공식 원문은 배출·수거라고 표기한다.'
        self.b['sources'][0]['sha256'] = hashlib.sha256(self.b['sources'][0]['text'].encode()).hexdigest()
        self.b['sources'][0]['title'] = '배출·수거 안내'
        self.b['sources'][0]['citation_label'] = '배출, 수거 안내'
        self.assertNotIn('reader_middle_dot_disallowed', self.check(review=False)['reasons'])

    def test_render_includes_interlinks_and_excludes_self(self):
        import tempfile
        from pathlib import Path
        posts_data = [
            {'title': '서초구 선풍기 배출 상세 안내', 'url': 'https://lifeinfo24.org/p1', 'category_name': '생활/건강', 'status': 'publish'},
            {'title': '기초연금 안내', 'url': 'https://lifeinfo24.org/p3', 'category_name': '정부 복지/지원금', 'status': 'publish'},
            {'title': '서초구 선풍기 오래된 글', 'url': 'http://161.33.0.234/p4', 'category_name': '생활/건강', 'status': 'publish'},
            {'title': self.b['plan']['title'], 'url': 'https://lifeinfo24.org/p2', 'category_name': '생활/건강', 'status': 'publish'},
        ]
        with tempfile.TemporaryDirectory() as folder:
            data_folder = Path(folder) / 'data'
            data_folder.mkdir()
            posts_file = data_folder / 'published_posts.json'
            posts_file.write_text(json.dumps(posts_data), encoding='utf-8')
            with patch('agents.editorial.ROOT', Path(folder)):
                content = render(self.b['plan'], self.b['sources'])
                self.assertIn('bloguito-interlink', content)
                self.assertIn('서초구 선풍기 배출 상세 안내', content)
                self.assertNotIn('기초연금 안내', content)
                self.assertNotIn('http://161.33.0.234', content)
                self.assertNotIn('https://lifeinfo24.org/p2', content)

    def test_reformat_refuses_user_edits_before_any_write(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            index = Path(folder) / 'drafts.json'
            index.write_text(json.dumps([{'id':112,'fact_manifest':{'editorial_bundle':self.b}}]), encoding='utf-8')
            inv = {'posts':[{'ID':112,'post_status':'draft','post_title':self.b['plan']['title'],'post_content':'user edited body'}]}
            with patch('agents.editorial.ROOT',Path(folder)), patch('agents.publisher.DRAFTS_INDEX_FILE',index), patch('sync_wordpress_inventory.sync_inventory'), patch('agents.editorial_writer.load_inventory',return_value=inv), patch('agents.publisher.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError,'user_edits_detected'):
                    PublisherAgent().reformat_draft(112)
                run.assert_not_called()

    def test_reformat_rejects_tampered_legacy_source_marker(self):
        """A user-edited legacy body is not trusted merely for containing source-links."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            index = Path(folder) / 'drafts.json'
            index.write_text(json.dumps([{'id': 112, 'fact_manifest': {'editorial_bundle': self.b}}]), encoding='utf-8')
            tampered = '<p>Manually edited article text</p><p class="source-links">source</p>'
            inv = {'posts': [{'ID': 112, 'post_status': 'draft',
                              'post_title': self.b['plan']['title'], 'post_content': tampered}]}
            with patch('agents.editorial.ROOT', Path(folder)), \
                 patch('agents.publisher.DRAFTS_INDEX_FILE', index), \
                 patch('sync_wordpress_inventory.sync_inventory'), \
                 patch('agents.editorial_writer.load_inventory', return_value=inv), \
                 patch('agents.publisher.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError, 'user_edits_detected'):
                    PublisherAgent().reformat_draft(112)
                run.assert_not_called()

    def test_valid_source_bound_narrative(self):
        self.assertEqual(self.check()['status'],'ready')
        self.assertIn('아파트 단지',render(self.b['plan'],self.b['sources']))

    def test_deadline_two_days_and_boundary(self):
        b=self.b['brief']; b.update(content_type='dated',useful_until='2026-09-15')
        self.assertIn('insufficient_useful_lifetime',topic_reasons(b,NOW.date()))
        b['useful_until']='2026-10-14'
        self.assertNotIn('insufficient_useful_lifetime',topic_reasons(b,NOW.date()))

    def test_missing_lifetime_is_not_evergreen(self):
        del self.b['brief']['content_type']
        self.assertIn('content_type_missing',self.check()['reasons'])

    def test_welfare_cannot_claim_evergreen(self):
        self.b['brief']['category_key']='welfare'
        self.assertIn('dated_category_cannot_bypass_time_check',self.check()['reasons'])

    def test_duplicate_draft_and_public_same_entity(self):
        for status in ['draft','publish','private','future','pending']:
            self.inventory['posts']=[{'post_status':status,'post_title':'서초구 선풍기 버리는 방법'}]
            self.assertIn('duplicate_topic',self.check()['reasons'])

    def test_source_url_duplicate_with_other_title(self):
        self.inventory['posts']=[{'post_status':'publish','post_title':'다른 제목','post_content':self.b['sources'][0]['url']}]
        self.assertIn('duplicate_topic',self.check()['reasons'])

    def test_stale_inventory_and_sources(self):
        self.inventory['checked_on']='2026-09-13'
        self.b['sources'][0]['fetched_at']=(NOW-timedelta(hours=25)).isoformat()
        self.assertTrue({'fresh_inventory_required','source_stale'}.issubset(self.check()['reasons']))

    def test_forged_quote(self):
        self.b['plan']['lead']['evidence'][0]['quote']='누구나 온라인으로 무료 수거됩니다.'
        self.assertIn('quote_not_in_source',self.check()['reasons'])

    def test_source_hash_mutation(self):
        self.b['sources'][0]['text']+=' 추가 조건'
        self.assertIn('source_hash_mismatch',self.check()['reasons'])

    def test_unconfirmed_number(self):
        self.b['plan']['lead']['text']+=' 50,000원을 지급합니다.'
        self.assertIn('number_without_evidence',self.check()['reasons'])

    def test_item_count_inference_does_not_allow_money_or_outside_range(self):
        self.assertEqual(supported_counts('선풍기 1개', '소형가전 5개 미만', {'1'}), {'1'})
        self.assertEqual(supported_counts('1만원 지급', '소형가전 5개 미만', {'1'}), set())
        self.assertEqual(supported_counts('5개', '소형가전 5개 미만', {'5'}), set())
        self.assertEqual(supported_counts('1개이며 1만원', '소형가전 5개 미만', {'1'}), set())

    def test_reader_deflection_and_blanket_disclaimer(self):
        for bad in ['공식 안내를 확인하세요.', '지급을 보장하지 않습니다.', '오늘은 신청기간 안에 해당합니다.']:
            self.b['plan']['lead']['text']=bad
            self.assertIn('reader_deflection_or_disclaimer',self.check()['reasons'])

    def test_unanswered_question(self):
        self.b['brief']['reader_questions'].append({'id':'q2','question':'비용은 얼마인가?'})
        self.assertIn('reader_question_not_answered',self.check()['reasons'])

    def test_missing_faq_answer(self):
        self.b['plan']['faq']=[{'question_id':'q2','question':'비용은?', 'answer':self.b['plan']['lead']}]
        self.assertIn('faq_answer_missing',self.check()['reasons'])

    def test_mutation_after_review(self):
        self.b['plan']['lead']['text']='서초구 가정용 선풍기는 배출수수료 면제 대상이 아닙니다.'
        self.assertIn('review_not_bound_to_current_content',self.check()['reasons'])

    def test_semantic_review_rejects_negation_even_with_valid_quote(self):
        self.b['plan']['lead']['text']='서초구 가정용 선풍기는 배출수수료 면제 대상이 아닙니다.'
        sign(self.b)
        self.b['review']['checks']['source_support']=False
        self.b['review']['issues']=['원문과 부정 표현이 반대']
        self.assertIn('semantic_review_failed',self.check()['reasons'])

    def test_policy_change_invalidates_review(self):
        changed={**policy(),'min_remaining_days':45}
        with patch('agents.editorial.policy',return_value=changed):
            self.assertIn('review_not_bound_to_current_content',self.check()['reasons'])

    def test_html_and_links_cannot_be_injected(self):
        self.b['plan']['lead']['text']='<script>bad()</script>'
        self.assertIn('raw_markup_or_url_in_prose',self.check()['reasons'])
        self.assertNotIn('<script>',render(self.b['plan'],self.b['sources']))

    def test_expired_review_and_malformed_payload(self):
        self.b['review']['checked_at']=(NOW-timedelta(days=2)).isoformat()
        self.assertIn('review_stale',self.check()['reasons'])
        self.assertEqual(validate_bundle({},self.inventory,NOW)['status'],'needs_review')

    def test_publisher_rechecks_before_write(self):
        article=article_from_bundle(self.b)
        with patch('sync_wordpress_inventory.sync_inventory'), patch('agents.editorial_writer.load_inventory',return_value=self.inventory), patch('agents.publisher.subprocess.run') as run:
            self.b['review']['checks']['source_support']=False
            with self.assertRaises(ValueError):
                PublisherAgent().publish(article)
            run.assert_not_called()

    def test_writer_revises_within_budget_and_holds(self):
        writer=EditorialWriterAgent(client=Mock())
        with patch.object(writer,'_call',return_value=self.b['plan']) as call, patch('agents.editorial_writer.validate_bundle',return_value={'status':'needs_review','reasons':['question_missing']}):
            with self.assertRaises(ValueError):
                writer.prepare(self.b['brief'],self.b['sources'],self.inventory)
            self.assertEqual(call.call_count,policy()['max_revisions']+1)

    def test_writer_reviews_separately(self):
        writer=EditorialWriterAgent(client=Mock())
        with patch.object(writer,'_call',return_value=self.b['plan']), patch.object(writer,'review',return_value=self.b['review']) as review, patch('agents.editorial_writer.validate_bundle',return_value={'status':'ready','reasons':[]}):
            bundle=writer.prepare(self.b['brief'],self.b['sources'],self.inventory)
            review.assert_called_once()
            self.assertIn('review',bundle)

    def test_review_only_agent_cannot_generate_plan(self):
        writer=EditorialWriterAgent(client=Mock(), writing_enabled=False)
        with self.assertRaisesRegex(ValueError, 'editorial_writer_disabled_for_manual_flow'):
            writer.prepare(self.b['brief'],self.b['sources'],self.inventory)
        writer.client.models.generate_content.assert_not_called()

    def test_manual_author_model_is_preserved_in_article_metadata(self):
        self.b['authoring']={'mode':'interactive_chatgpt','model':'GPT-5.6 Sol'}
        self.b['used_model']='GPT-5.6 Sol'
        article=article_from_bundle(self.b)
        self.assertEqual(article['used_model'],'GPT-5.6 Sol')
        self.assertEqual(article['editorial_bundle']['authoring']['mode'],'interactive_chatgpt')

    def test_old_publication_entry_cannot_bypass_gate(self):
        with patch('agents.publisher.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError,'editorial_bundle_required'):
                PublisherAgent().publish({'title':'과거 원고'})
            run.assert_not_called()

    def test_publisher_forces_draft_and_rereads_saved_content(self):
        article=article_from_bundle(self.b)
        commands=[]
        def fake(cmd, **kwargs):
            commands.append(cmd)
            if 'create' in cmd:
                return Mock(stdout='999')
            if '--fields=post_status,post_content' in cmd:
                return Mock(stdout=json.dumps({'post_status':'draft','post_content':article['content']}))
            return Mock(stdout='')
        with patch('sync_wordpress_inventory.sync_inventory') as sync, patch('agents.editorial_writer.load_inventory',return_value=self.inventory), patch('agents.publisher.subprocess.run',side_effect=fake), patch('agents.editorial.datetime') as clock, patch.object(PublisherAgent,'_record_post') as record, patch('agents.publisher.POST_STATUS','publish'):
            clock.now.return_value=NOW
            clock.fromisoformat=datetime.fromisoformat
            self.assertEqual(PublisherAgent().publish(article),999)
            self.assertEqual(sync.call_count,2)
            self.assertTrue(any('--post_status=draft' in c for c in commands))
            self.assertFalse(any('--post_status=publish' in c for c in commands))
            self.assertEqual(record.call_args.kwargs['status'],'draft')
            self.assertTrue(any('rank_math_focus_keyword' in c for c in commands))
            self.assertTrue(any('rank_math_description' in c for c in commands))

    def test_evergreen_does_not_require_news_rss(self):
        from agents.radar import RadarAgent
        with patch('agents.radar.load_briefs',return_value=[self.b['brief']]), patch('agents.radar.feedparser.parse') as rss:
            radar=object.__new__(RadarAgent);radar.history=set()
            items=radar.search_news('life-health')
            self.assertTrue(items[0]['editorial_direct'])
            rss.assert_not_called()

    def test_actual_source_deadline_overrides_optimistic_brief(self):
        self.b['brief'].update(content_type='dated', useful_until='2026-12-31', category_key='welfare')
        text='신청기간: 2026.09.01 ~ 2026.09.15\n'+self.b['sources'][0]['text']
        self.b['sources'][0].update(text=text,sha256=hashlib.sha256(text.encode()).hexdigest())
        self.b['temporal_source']={'evidence':extract_evidence(text,self.b['sources'][0]['url'])}
        self.assertIn('source_deadline_too_close',self.check()['reasons'])

    def test_model_transient_failure_is_bounded(self):
        from agents.editorial_writer import Plan
        class Busy(Exception):
            code=503
        writer=EditorialWriterAgent(client=Mock())
        writer.client.models.generate_content.side_effect=Busy('busy')
        with patch('agents.editorial_writer.time.sleep'):
            with self.assertRaises(Busy):
                writer._call('test',{},Plan,'writer')
        self.assertEqual(writer.client.models.generate_content.call_count,3)

    def test_model_auth_error_does_not_retry(self):
        from agents.editorial_writer import Plan
        class NoAuth(Exception):
            code=401
        writer=EditorialWriterAgent(client=Mock())
        writer.client.models.generate_content.side_effect=NoAuth('no auth')
        with self.assertRaises(NoAuth):
            writer._call('test',{},Plan,'writer')
        self.assertEqual(writer.client.models.generate_content.call_count,1)


if __name__=='__main__':
    unittest.main()
