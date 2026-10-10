"""Offline security regression for the proposed read-only SSH identity.

No SSH connection, Docker engine, sudo or system mutation is used by tests.
"""

import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]


def load_file(name):
    path = ROOT / "scripts" / "security" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load_file("bloguito_ssh_gate")
reader = load_file("bloguito_wp_readonly")


class GateTests(unittest.TestCase):
    def test_permitted_original_commands(self):
        for original, expected in (
            ("wp-read health", ["health"]),
            ("wp-read inventory", ["inventory"]),
            ("wp-read post-get 119", ["post-get", "119"]),
            ("wp-read post-status 1", ["post-status", "1"]),
        ):
            with self.subTest(original=original):
                self.assertEqual(expected, gate.parse_original(original))

    def test_reject_shell_and_sensitive_operations(self):
        for original in (
            None, "", "wp-read", "wp-read post-get 0",
            "wp-read post-get -1", "wp-read post-get 9999999999",
            "wp-read post-get 1; id", "wp-read post-get 1\nwhoami",
            "wp-read post-get 1 && id", "wp-read post-get 1`id`",
            "wp-read post-get 1 --allow-root", "wp-read post-update 119",
            "wp-read eval", "sudo docker ps", "wp-read inventory ",
            "wp-read post-get 0001", "wp-read post-get 1\x00",
        ):
            with self.subTest(original=original):
                with self.assertRaises(ValueError):
                    gate.parse_original(original)

    def test_gate_calls_only_no_argument_sudo_target_with_validated_input(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0))
        self.assertEqual(0, gate.dispatch("wp-read post-get 123", runner=runner))
        args, kwargs = runner.call_args
        self.assertEqual([gate.SUDO, "-n", gate.READER], args[0])
        self.assertEqual(["post-get", "123"], json.loads(kwargs["input"]))
        self.assertTrue(kwargs["check"] is False)

    def test_gate_rejects_before_invoking_sudo(self):
        runner = Mock()
        with self.assertRaises(ValueError):
            gate.dispatch("wp-read post-get 9; sleep 1", runner=runner)
        runner.assert_not_called()


class RootReaderTests(unittest.TestCase):
    def test_fixed_wp_commands(self):
        cases = {
            '["health"]': ["core", "version", "--allow-root"],
            '["inventory"]': list(reader.INVENTORY),
            '["post-get","12"]': ["post", "get", "12", "--format=json", "--allow-root"],
            '["post-status","97"]': ["post", "get", "97", "--field=post_status", "--allow-root"],
        }
        for payload, expected in cases.items():
            with self.subTest(payload=payload):
                self.assertEqual(expected, reader.parse_request(payload.encode()))

    def test_root_reader_independently_rejects_untrusted_stdin(self):
        for payload in (
            b"", b"{}", b'"post-get"', b"[]", b"null", b'["eval","phpinfo();"]',
            b'["post-get","1;id"]', b'["post-get","0"]',
            b'["post-get",1]', b'["post-get","1","--field=post_status"]',
            b'["health","x"]', b'["inventory","--allow-root"]',
            b'["post-update","1"]', b'\xff', b'x' * 513,
        ):
            with self.subTest(payload=payload[:40]):
                with self.assertRaises(ValueError):
                    reader.parse_request(payload)

    def test_root_reader_never_passes_untrusted_docker_flags_or_shell(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0))
        reader.dispatch(b'["post-get","463"]', runner=runner)
        argv = runner.call_args.args[0]
        self.assertEqual([reader.DOCKER, "exec", "wordpress_app", "wp", "post", "get", "463", "--format=json", "--allow-root"], argv)
        self.assertIs(subprocess.DEVNULL, runner.call_args.kwargs["stdin"])
        self.assertEqual({"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, runner.call_args.kwargs["env"])

    def test_invalid_request_never_spawns_docker(self):
        runner = Mock()
        with self.assertRaises(ValueError):
            reader.dispatch(b'["post-get","1 && id"]', runner=runner)
        runner.assert_not_called()

    def test_root_reader_main_denies_non_root_or_extra_arguments(self):
        with patch.object(reader.os, "geteuid", return_value=1001, create=True):
            self.assertEqual(126, reader.main())
        with patch.object(reader.os, "geteuid", return_value=0, create=True), patch.object(reader.sys, "argv", ["reader", "--unexpected"]):
            self.assertEqual(126, reader.main())


if __name__ == "__main__":
    unittest.main()
