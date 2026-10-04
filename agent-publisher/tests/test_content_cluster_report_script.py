import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "content_cluster_report_script",
    ROOT / "scripts" / "build_content_cluster_report.py",
)
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


class ContentClusterReportScriptTests(unittest.TestCase):
    def test_default_inventory_falls_back_to_complete_catalog_snapshot(self):
        rows = [{
            "ID": 10,
            "post_title": "테스트",
            "post_status": "publish",
            "content_urls": ["https://lifeinfo24.org/?p=20"],
        }]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            missing = root / "wordpress_inventory.json"
            catalog = root / "catalog_inventory.json"
            catalog.write_text(json.dumps(rows), encoding="utf-8")
            with patch.object(REPORT, "INVENTORY", missing):
                payload = REPORT.load_report_inventory(None, catalog)
        self.assertEqual(rows, payload["posts"])
        self.assertEqual(2, payload["schema_version"])

    def test_catalog_fallback_without_url_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            missing = root / "wordpress_inventory.json"
            catalog = root / "catalog_inventory.json"
            catalog.write_text(json.dumps([{
                "ID": 10,
                "post_title": "테스트",
                "post_status": "publish",
            }]), encoding="utf-8")
            with patch.object(REPORT, "INVENTORY", missing):
                with self.assertRaisesRegex(
                        REPORT.ContentClusterError,
                        "catalog_inventory_missing_content_urls"):
                    REPORT.load_report_inventory(None, catalog)

    def test_explicit_inventory_never_silently_uses_catalog_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            explicit = root / "explicit.json"
            catalog = root / "catalog_inventory.json"
            catalog.write_text(json.dumps([{
                "ID": 10,
                "post_title": "테스트",
                "post_status": "publish",
                "content_urls": [],
            }]), encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                REPORT.load_report_inventory(explicit, catalog)


if __name__ == "__main__":
    unittest.main()
