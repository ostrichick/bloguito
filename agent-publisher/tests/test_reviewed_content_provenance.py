import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agents import editorial
from agents.editorial import digest, recognized_reviewed_content_hashes
from tests.test_editorial_system import sample, sign


def content_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ReviewedContentProvenanceTests(unittest.TestCase):
    def registry(self, bundle: dict, live_sha: str) -> dict:
        return {
            "schema_version": 1,
            "entries": [{
                "post_id": 844,
                "review_digest": bundle["review"]["digest"],
                "bundle_digest": digest(bundle),
                "reviewed_content_sha256": live_sha,
                "live_content_sha256": live_sha,
                "kind": "completed-full-review",
                "variant": "completed-full-review-test",
                "evidence_sha256": "b" * 64,
            }],
        }

    def test_exact_review_digest_accepts_completed_full_review_output(self):
        bundle = sample()
        sign(bundle)
        saved_sha = content_sha("exact saved full-review output")
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder) / "reviewed-content.json"
            registry.write_text(
                json.dumps(self.registry(bundle, saved_sha)), encoding="utf-8")
            with patch.object(editorial, "REVIEWED_CONTENT_PROVENANCE_FILE", registry):
                hashes = recognized_reviewed_content_hashes(bundle, post_id=844)
        self.assertEqual(saved_sha, hashes["completed-full-review-test"])

    def test_bundle_change_cannot_inherit_previous_reviewed_content_provenance(self):
        bundle = sample()
        sign(bundle)
        saved_sha = content_sha("exact saved full-review output")
        registry_payload = self.registry(bundle, saved_sha)
        changed = copy.deepcopy(bundle)
        changed["plan"]["title"] = "다른 제목"
        sign(changed)
        self.assertNotEqual(bundle["review"]["digest"], changed["review"]["digest"])
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder) / "reviewed-content.json"
            registry.write_text(json.dumps(registry_payload), encoding="utf-8")
            with patch.object(editorial, "REVIEWED_CONTENT_PROVENANCE_FILE", registry):
                hashes = recognized_reviewed_content_hashes(changed, post_id=844)
        self.assertNotIn("completed-full-review-test", hashes)

    def test_unbound_or_invalid_review_never_inherits_registry_entry(self):
        bundle = sample()
        sign(bundle)
        saved_sha = content_sha("exact saved full-review output")
        registry_payload = self.registry(bundle, saved_sha)
        bundle["plan"]["title"] = "review digest가 더는 묶이지 않은 제목"
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder) / "reviewed-content.json"
            registry.write_text(json.dumps(registry_payload), encoding="utf-8")
            with patch.object(editorial, "REVIEWED_CONTENT_PROVENANCE_FILE", registry):
                with self.assertRaisesRegex(
                        ValueError, "reviewed_content_review_not_bound"):
                    recognized_reviewed_content_hashes(bundle, post_id=844)

    def test_completed_full_review_entry_requires_same_reviewed_and_live_sha(self):
        bundle = sample()
        sign(bundle)
        payload = self.registry(bundle, "a" * 64)
        payload["entries"][0]["reviewed_content_sha256"] = "c" * 64
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder) / "reviewed-content.json"
            registry.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(editorial, "REVIEWED_CONTENT_PROVENANCE_FILE", registry):
                with self.assertRaisesRegex(
                        ValueError, "invalid_reviewed_content_provenance_registry"):
                    recognized_reviewed_content_hashes(bundle, post_id=844)

    def test_exact_image_substitution_lineage_can_bind_reviewed_bundle_to_live_sha(self):
        bundle = sample()
        sign(bundle)
        payload = {
            "schema_version": 1,
            "entries": [{
                "post_id": 844,
                "review_digest": bundle["review"]["digest"],
                "bundle_digest": digest(bundle),
                "reviewed_content_sha256": "a" * 64,
                "live_content_sha256": "c" * 64,
                "kind": "post-review-image-url-substitution",
                "variant": "post-review-images-test",
                "evidence_sha256": "b" * 64,
                "before_snapshot_sha256": "1" * 64,
                "mutation_payload_sha256": "d" * 64,
                "mutation_script_sha256": "e" * 64,
                "replacements": [{
                    "old_url": "https://lifeinfo24.org/wp-content/uploads/old.jpg",
                    "new_url": "https://lifeinfo24.org/wp-content/uploads/new.jpg",
                    "asset_sha256": "2" * 64,
                    "receipt_sha256": "f" * 64,
                }],
                "transformation_digest": "",
            }],
        }
        transformation = {
            "reviewed_content_sha256": "a" * 64,
            "live_content_sha256": "c" * 64,
            "before_snapshot_sha256": "1" * 64,
            "mutation_payload_sha256": "d" * 64,
            "mutation_script_sha256": "e" * 64,
            "replacements": payload["entries"][0]["replacements"],
        }
        payload["entries"][0]["transformation_digest"] = digest(transformation)
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder) / "reviewed-content.json"
            registry.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(editorial, "REVIEWED_CONTENT_PROVENANCE_FILE", registry):
                hashes = recognized_reviewed_content_hashes(bundle, post_id=844)
        self.assertEqual("c" * 64, hashes["post-review-images-test"])

    def test_transaction_live_sha_never_becomes_a_renderer_hash(self):
        bundle = sample()
        sign(bundle)
        transaction_sha = "c" * 64
        renderer_hashes = editorial.recognized_renderer_hashes(
            bundle["plan"], bundle["sources"],
            bundle.get("brief", {}).get("category_key"), post_id=844)
        self.assertNotIn(transaction_sha, renderer_hashes.values())


class ReviewedContentCatalogReconcileTests(unittest.TestCase):
    def test_status_reconcile_accepts_exact_completed_full_review_binding(self):
        import sync_post_catalog as catalog

        bundle = sample()
        bundle["plan"]["title"] = "검토 완료 저장본"
        sign(bundle)
        saved_sha = content_sha("historical full-review saved HTML")
        record = {
            "id": 844,
            "title": bundle["plan"]["title"],
            "url": "https://lifeinfo24.org/?p=844",
            "category_id": 275,
            "category_name": "건강/의료",
            "status": "draft",
            "expires_at": None,
            "fact_manifest": {"editorial_bundle": bundle},
            "published_at": "2026-10-03 10:00",
        }
        registry_payload = {
            "schema_version": 1,
            "entries": [{
                "post_id": 844,
                "review_digest": bundle["review"]["digest"],
                "bundle_digest": digest(bundle),
                "reviewed_content_sha256": saved_sha,
                "live_content_sha256": saved_sha,
                "kind": "completed-full-review",
                "variant": "completed-full-review-test",
                "evidence_sha256": "d" * 64,
            }],
        }
        live = [{
            "ID": 844,
            "post_title": bundle["plan"]["title"],
            "post_status": "publish",
            "permalink": "https://lifeinfo24.org/test/",
            "content_sha256": saved_sha,
        }]
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / "draft_posts.json").write_text(
                json.dumps([record], ensure_ascii=False), encoding="utf-8")
            (data / "published_posts.json").write_text("[]", encoding="utf-8")
            registry = data / "reviewed-content.json"
            registry.write_text(json.dumps(registry_payload), encoding="utf-8")
            with patch.object(editorial, "REVIEWED_CONTENT_PROVENANCE_FILE", registry):
                result = catalog.reconcile_reviewed_statuses(live, data)

        self.assertEqual([{
            "post_id": 844,
            "from_status": "draft",
            "to_status": "publish",
            "provenance_variant": "completed-full-review-test",
        }], result["moved"])

    def test_invalid_review_refuses_status_reconcile_even_when_renderer_is_exact(self):
        import sync_post_catalog as catalog
        from agents.editorial import render

        bundle = sample()
        bundle["plan"]["title"] = "검토 결합이 깨진 글"
        sign(bundle)
        content = render(bundle["plan"], bundle["sources"])
        bundle["review"]["digest"] = "0" * 64
        record = {
            "id": 844,
            "title": bundle["plan"]["title"],
            "url": "https://lifeinfo24.org/?p=844",
            "category_id": 275,
            "category_name": "건강/의료",
            "status": "draft",
            "expires_at": None,
            "fact_manifest": {"editorial_bundle": bundle},
            "published_at": "2026-10-03 10:00",
        }
        live = [{
            "ID": 844,
            "post_title": bundle["plan"]["title"],
            "post_status": "publish",
            "permalink": "https://lifeinfo24.org/test/",
            "content_sha256": content_sha(content),
        }]
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / "draft_posts.json").write_text(
                json.dumps([record], ensure_ascii=False), encoding="utf-8")
            (data / "published_posts.json").write_text("[]", encoding="utf-8")
            result = catalog.reconcile_reviewed_statuses(live, data)
        self.assertEqual([], result["moved"])
        self.assertEqual([{
            "post_id": 844,
            "reason": "reviewed_bundle_invalid",
        }], result["skipped"])


if __name__ == "__main__":
    unittest.main()
