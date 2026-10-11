"""Offline API-contract checks; never use a real Clarity token or endpoint."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from clarity_collector import (
    BlockRedirects, ClarityError, collect, existing_snapshot_matches, load_token, main,
    save_snapshot, snapshot_path,
    validate_response,
)


TIME = datetime(2026, 10, 11, 1, 0, tzinfo=timezone.utc)


class ClarityCollectorTests(unittest.TestCase):
    @staticmethod
    def fake_request(token, days, dimension):
        assert token == "fake.token.value"
        assert days == 1
        return [{"metricName": "Traffic", "information": [
            {"totalSessionCount": "6", **({dimension: "example"} if dimension else {})}
        ]}]

    def test_three_explicit_views_and_rolling_window(self):
        result = collect("fake.token.value", requester=self.fake_request, now=TIME)
        self.assertEqual(tuple(result["views"]), ("summary", "device", "url"))
        self.assertEqual(result["views"]["summary"][0]["metricName"], "Traffic")
        self.assertEqual(result["window"]["hours"], 24)
        self.assertEqual(snapshot_path(Path("/private"), now=TIME).name,
                         "clarity-2026-10-11.json")

    def test_invalid_parameters_or_unexpected_response_fail_closed(self):
        for data in (None, {}, [{"metricName": "Traffic"}],
                     [{"metricName": "Traffic", "information": [1]}]):
            with self.subTest(data=data), self.assertRaises(ClarityError):
                validate_response(data)
        with self.assertRaisesRegex(ClarityError, "invalid_days"):
            collect("dummy", 30, requester=self.fake_request)
        with self.assertRaisesRegex(ClarityError, "invalid_views"):
            collect("dummy", views=("summary", "summary"), requester=self.fake_request)

    def test_token_file_permissions_and_no_secret_in_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            token_path = Path(root) / "private-token"
            token_path.write_text("fake.token.value\n", encoding="utf-8")
            os.chmod(token_path, 0o600)
            self.assertEqual(load_token(token_path), "fake.token.value")
            snapshot = collect(load_token(token_path), requester=self.fake_request, now=TIME)
            out = Path(root) / "reports"
            target = save_snapshot(snapshot, out, now=TIME)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), snapshot)
            self.assertNotIn("fake.token.value", target.read_text(encoding="utf-8"))
            self.assertEqual(target.name, "clarity-2026-10-11.json")
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                os.chmod(token_path, 0o644)
                with self.assertRaisesRegex(ClarityError, "permissions"):
                    load_token(token_path)
            with self.assertRaisesRegex(ClarityError, "snapshot_already_exists"):
                save_snapshot(snapshot, out, now=TIME)
            self.assertTrue(existing_snapshot_matches(target, 1, ("summary", "device", "url")))
            with self.assertRaisesRegex(ClarityError, "snapshot_scope_conflict"):
                existing_snapshot_matches(target, 3, ("summary", "device", "url"))

    def test_redirect_handler_denies_any_destination(self):
        self.assertIsNone(BlockRedirects().redirect_request(None, None, 302, "redirect", {},
                                                             "https://untrusted.example/path"))

    def test_missing_token_and_no_api_call(self):
        with tempfile.TemporaryDirectory() as root:
            calls = []
            def request(*args):
                calls.append(args)
                raise AssertionError("Must not call Clarity")
            code = main(["--token-file", str(Path(root) / "missing"),
                         "--output-dir", str(Path(root) / "out")], requester=request)
            self.assertEqual(code, 1)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
