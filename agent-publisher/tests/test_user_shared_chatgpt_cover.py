"""A URL selected by the user must be authenticated against the actual share HTML."""
import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.featured_image import (
    SHARED_CHATGPT_ORIGIN, verify_manual_image_upload_lineage,
    verify_user_shared_chatgpt_origin,
)
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from stage_featured_image import verify_candidate_manifest


class UserSharedImageTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.mid = "m_" + "a" * 32
        self.fid = "file_" + "b" * 32
        token = base64.b64encode(json.dumps({"id": self.mid + ":" + self.fid}).encode()).decode()
        self.url = "https://chatgpt.com/backend-api/estuary/public_content/enc/" + token
        self.share = "https://chatgpt.com/s/" + self.mid
        self.page = self.root / "page.html"
        self.page.write_text(f"<a href='{self.share}'><img src='{self.url}'></a>", encoding="utf-8")
        from PIL import Image
        self.source = self.root / "original.png"
        Image.new("RGB", (1672, 941)).save(self.source)
        raw = self.source.read_bytes()
        self.manifest = {
            "version": 2, "origin_claim": SHARED_CHATGPT_ORIGIN,
            "user_shared_image": {
                "share_url": self.share, "share_page_path": str(self.page.resolve()),
                "share_page_sha256": hashlib.sha256(self.page.read_bytes()).hexdigest(),
                "original_asset_url": self.url, "file_id": self.fid,
            },
            "candidates": [{
                "candidate_number": 1, "path": str(self.source.resolve()),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "format": "PNG", "width": 1672, "height": 941, "bytes": len(raw),
            }],
        }
        self.path = self.root / "manifest.json"
        self._save_manifest()

    def _save_manifest(self):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_valid_share_selected_by_user(self):
        self.assertEqual(self.fid, verify_user_shared_chatgpt_origin(self.manifest)["file_id"])
        bound = verify_candidate_manifest(
            self.source, self.path, selected_candidate=1, selection_mode="user")
        self.assertEqual(SHARED_CHATGPT_ORIGIN, bound["origin_claim"])

    def test_wrong_claims_or_broken_source_are_rejected(self):
        for key, value in (
            ("share_url", "https://evil.example/s/" + self.mid),
            ("original_asset_url", "https://evil.example/original.png"),
            ("file_id", "file_" + "c" * 32),
            ("share_page_sha256", "0" * 64),
        ):
            with self.subTest(key=key):
                manifest = json.loads(json.dumps(self.manifest))
                manifest["user_shared_image"][key] = value
                with self.assertRaises(ValueError):
                    verify_user_shared_chatgpt_origin(manifest)
        self.source.write_bytes(b"different")
        with self.assertRaises(ValueError):
            verify_candidate_manifest(
                self.source, self.path, selected_candidate=1, selection_mode="user")

    def test_cannot_claim_agent_selection(self):
        with self.assertRaisesRegex(ValueError, "user_selection"):
            verify_candidate_manifest(
                self.source, self.path, selected_candidate=1, selection_mode="agent-delegated")

    def test_staged_receipt_requires_same_origin_and_hashes(self):
        from PIL import Image
        output = self.root / "upload.webp"
        Image.new("RGB", (1200, 675)).save(output)
        source_sha = self.manifest["candidates"][0]["sha256"]
        staged_sha = hashlib.sha256(output.read_bytes()).hexdigest()
        stage = {
            "source_path": str(self.source.resolve()), "source_sha256": source_sha,
            "output_path": str(output.resolve()), "output_sha256": staged_sha,
            "candidate_manifest": str(self.path.resolve()), "candidate_number": 1,
            "selection_mode": "user", "selection_actor": "user",
            "sealed_source_sha256": source_sha,
            "origin_claim": SHARED_CHATGPT_ORIGIN,
        }
        receipt = output.with_suffix(output.suffix + ".stage.json")
        receipt.write_text(json.dumps(stage))
        self.assertEqual(source_sha, verify_manual_image_upload_lineage(
            output, self.path, 1, "user")["source_sha256"])
        without_actor = dict(stage)
        without_actor.pop("selection_actor")
        receipt.write_text(json.dumps(without_actor))
        with self.assertRaisesRegex(ValueError, "lineage_receipt_mismatch"):
            verify_manual_image_upload_lineage(output, self.path, 1, "user")
        stage["origin_claim"] = {"generator_tool": "image_gen.text2im",
                                 "save_tool": "cos_core.save_image"}
        receipt.write_text(json.dumps(stage))
        with self.assertRaisesRegex(ValueError, "lineage_receipt_mismatch"):
            verify_manual_image_upload_lineage(output, self.path, 1, "user")


if __name__ == "__main__":
    unittest.main()
