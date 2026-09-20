import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch, Mock
from agents.publisher import PublisherAgent

class DraftCommandSafetyTests(unittest.TestCase):
    def test_live_drafts_list_read_only_without_index(self):
        payload=[{'ID':243,'post_title':'검토 대기','post_date':'2026-09-18 12:00:00','post_status':'draft'}]
        with patch('agents.publisher.DRAFTS_INDEX_FILE',Path('/nonexistent-draft-posts-index.json')), patch('agents.publisher.subprocess.run',return_value=Mock(stdout=json.dumps(payload))) as run:
            rows=PublisherAgent().list_drafts()
            self.assertEqual(rows[0]['ID'],243)
            self.assertEqual(rows[0]['category_name'],'미분류')
            args=run.call_args.args[0]
            self.assertIn('list',args)
            self.assertNotIn('update',args)
            self.assertNotIn('publish',args)

    def test_promote_requires_explicit_confirmation_before_io(self):
        with patch('agents.publisher.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError,'explicit_publication_confirmation_required'):
                PublisherAgent().promote_draft(243)
            run.assert_not_called()

    def test_untracked_draft_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            with patch('agents.editorial.ROOT',Path(root)),patch('agents.publisher.DRAFTS_INDEX_FILE',Path(root)/'missing.json'),patch('agents.publisher.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError,'tracked_editorial_draft_required'):
                    PublisherAgent().promote_draft(243,confirmed=True)
                run.assert_not_called()

    def test_user_modified_draft_never_published(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'drafts.json'
            bundle={'plan':{'title':'검토 대기'},'sources':[{'url':'https://example.org/official','sha256':'hash'}],
                    'brief':{'category_key':'life-health','official_urls':['https://example.org/official']}}
            path.write_text(json.dumps([{'id':243,'fact_manifest':{'editorial_bundle':bundle}}]),encoding='utf-8')
            inventory={'posts':[{'ID':243,'post_status':'draft','post_title':'검토 대기','post_content':'human changed body'}]}
            with (patch('agents.editorial.ROOT',Path(root)),patch('agents.publisher.DRAFTS_INDEX_FILE',path),
                 patch('agents.editorial.render',return_value='original reviewed body'),
                 patch('agents.editorial_writer.load_inventory',return_value=inventory),
                 patch('sync_wordpress_inventory.sync_inventory'),
                 patch('agents.publisher.subprocess.run') as run):
                with self.assertRaisesRegex(ValueError,'draft_changed_or_not_draft'):
                    PublisherAgent().promote_draft(243,confirmed=True)
                run.assert_not_called()

    def test_promotion_must_revalidate_current_official_sources(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'drafts.json'
            bundle={'plan':{'title':'검토 대기'},'sources':[{'url':'https://example.org/official','sha256':'old'}],
                    'brief':{'category_key':'life-health','official_urls':['https://example.org/official']}}
            path.write_text(json.dumps([{'id':243,'fact_manifest':{'editorial_bundle':bundle}}]),encoding='utf-8')
            inventory={'posts':[{'ID':243,'post_status':'draft','post_title':'검토 대기','post_content':'original reviewed body'}]}
            with (patch('agents.editorial.ROOT',Path(root)),patch('agents.publisher.DRAFTS_INDEX_FILE',path),
                 patch('agents.editorial.render',return_value='original reviewed body'),
                 patch('agents.editorial.validate_bundle',return_value={'status':'ready','reasons':[]}),
                 patch('agents.editorial_writer.fetch_sources',return_value=[{'url':'https://example.org/official','sha256':'new'}]),
                 patch('agents.editorial_writer.load_inventory',return_value=inventory),
                 patch('sync_wordpress_inventory.sync_inventory'),
                 patch('agents.publisher.subprocess.run') as run):
                with self.assertRaisesRegex(ValueError,'official_source_changed_since_review'):
                    PublisherAgent().promote_draft(243,confirmed=True)
                run.assert_not_called()

if __name__=='__main__': unittest.main()
