import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.editorial import excerpt_from_lead, render
from agents.editorial_draft_reviser import (
    _before_generated_source_footer,
    revise_reviewed_draft,
)
from test_editorial_system import NOW, sample


class EditorialDraftReviserTests(unittest.TestCase):
    def test_full_reviewed_draft_revision_can_apply_explicit_reviewed_title_change(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["lead"]["text"] = "새로 독립 검토된 원고 문장입니다."
        new["plan"]["title"] = "새로 독립 검토된 제목"
        old_body = render(old["plan"], old["sources"])
        new_body = render(new["plan"], new["sources"])
        live = {
            "ID": 393,
            "post_title": old["plan"]["title"],
            "post_status": "draft",
            "post_name": "same-slug",
            "post_content": old_body,
            "post_excerpt": excerpt_from_lead(old["plan"]["lead"]),
        }

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / "data"
            data.mkdir()
            index = data / "draft_posts.json"
            index.write_text(json.dumps([{
                "id": 393,
                "fact_manifest": {"editorial_bundle": old},
            }]), encoding="utf-8")

            def run(args, **kwargs):
                if args[5:7] == ["post", "get"]:
                    return Mock(stdout=json.dumps(live))
                if args[5:7] == ["post", "update"]:
                    live["post_content"] = next(
                        arg.split("=", 1)[1] for arg in args if arg.startswith("--post_content=")
                    )
                    live["post_excerpt"] = next(
                        arg.split("=", 1)[1] for arg in args if arg.startswith("--post_excerpt=")
                    )
                    title_args = [arg for arg in args if arg.startswith("--post_title=")]
                    if title_args:
                        live["post_title"] = title_args[0].split("=", 1)[1]
                    return Mock(stdout="Success")
                raise AssertionError(args)

            inventory = {"checked_on": NOW.date().isoformat(), "posts": [live]}
            with patch("agents.editorial_draft_reviser.ROOT", root), \
                 patch("agents.editorial_draft_reviser.DRAFTS_INDEX_FILE", index), \
                 patch("agents.editorial_draft_reviser.sync_inventory"), \
                 patch("agents.editorial_draft_reviser.invalidate_inventory") as invalidate, \
                 patch("agents.editorial_draft_reviser.load_inventory", return_value=inventory), \
                 patch("agents.editorial_draft_reviser.validate_bundle", return_value={"status": "ready", "reasons": []}), \
                 patch("agents.editorial_draft_reviser.fetch_sources", return_value=new["sources"]), \
                 patch("agents.editorial_draft_reviser.save_report"), \
                 patch("agents.editorial_draft_reviser.subprocess.run", side_effect=run):
                result = revise_reviewed_draft(
                    393,
                    new,
                    hashlib.sha256(old_body.encode()).hexdigest(),
                    confirmed=True,
                    confirm_title_change=True,
                )

            self.assertEqual(result, 393)
            invalidate.assert_called_once_with()
            self.assertEqual(live["post_status"], "draft")
            self.assertEqual(live["post_name"], "same-slug")
            self.assertEqual(live["post_title"], new["plan"]["title"])
            self.assertEqual(live["post_content"], new_body)
            saved_index = json.loads(index.read_text(encoding="utf-8"))
            self.assertEqual(saved_index[0]["fact_manifest"]["editorial_bundle"], new)
            self.assertEqual(len(list((data / "editorial_runs").glob("draft-revision-393-*.json"))), 1)
            self.assertEqual(len(list((data / "editorial_runs").glob("draft-revision-index-393-*.json"))), 1)

    def test_revision_requires_confirmation(self):
        with self.assertRaisesRegex(ValueError, "specific_draft_revision_confirmation_required"):
            revise_reviewed_draft(393, {}, "0" * 64, confirmed=False)

    def test_source_footer_only_renderer_migration_is_accepted_by_comparison_helper(self):
        old = (
            '<div class="bloguito-article"><p>검토된 본문</p>'
            '<div style="margin-top:44px"><h2 id="sources">출처</h2>'
            '<ul class="source-list"><li>old</li></ul></div></div>'
        )
        new = (
            '<div class="bloguito-article"><p>검토된 본문</p>'
            '<div style="margin-top:44px"><h2 id="sources">출처</h2>'
            '<ul class="source-list"><li>new</li></ul></div></div>'
        )
        self.assertEqual(
            _before_generated_source_footer(old),
            _before_generated_source_footer(new),
        )

    def test_source_footer_migration_does_not_hide_prose_change(self):
        old = (
            '<div class="bloguito-article"><p>검토된 본문</p>'
            '<div><h2 id="sources">출처</h2><ul class="source-list"></ul></div></div>'
        )
        edited = (
            '<div class="bloguito-article"><p>사람이 바꾼 본문</p>'
            '<div><h2 id="sources">출처</h2><ul class="source-list"></ul></div></div>'
        )
        self.assertNotEqual(
            _before_generated_source_footer(old),
            _before_generated_source_footer(edited),
        )


if __name__ == "__main__":
    unittest.main()
