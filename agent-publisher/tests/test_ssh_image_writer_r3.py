"""R3 offline forced-command/writer security contract (never touches SSH/WP)."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    path = ROOT / "scripts" / "security" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load("bloguito_ssh_write_gate")
writer = load("bloguito_wp_image_writer")
RID = "a" * 32
SHA = "b" * 64


def approved(now):
    issued = (now - timedelta(minutes=10)).isoformat()
    expires = (now + timedelta(hours=4)).isoformat()
    request = {
        "protocol": 1, "action": "featured-image-set", "request_id": RID,
        "task_id": "image_task_test001", "post_id": 930, "attachment_id": 931,
        "candidate_number": 1, "candidate_count": 1,
        "candidates": [{"candidate_number": 1, "sha256": SHA}],
        "source_sha256": SHA, "staged_sha256": SHA, "image_sha256": SHA,
        "alt_text": "설명", "release_sha256": SHA, "task_created_at":
            (now - timedelta(hours=1)).isoformat(),
        "generator_policy_sha256": SHA, "target": {"post_id": 930},
        "selection_mode": "agent-delegated", "review_actor": "independent_reviewer",
        "manifest_sha256": SHA, "review_receipt_sha256": SHA,
        "expected": {"post_status": "draft", "content_sha256": SHA,
                     "title_sha256": SHA, "slug_sha256": SHA, "excerpt_sha256": SHA,
                     "thumbnail_id": 11, "alt_sha256": SHA},
    }
    common = {"task_id": request["task_id"], "target": request["target"],
              "generator_policy_sha256": SHA}
    host = {**common, "candidates": request["candidates"],
            "issuer": "verified_chatgpt_host_event", "issued_at": issued,
            "expires_at": expires}
    review = {**common, "manifest_sha256": SHA, "review_receipt_sha256": SHA,
              "source_sha256": SHA, "staged_sha256": SHA,
              "selected_candidate": 1, "selection_mode": "agent-delegated",
              "review_actor": "independent_reviewer",
              "issuer": "independent_reviewer_authority", "issued_at": issued,
              "expires_at": expires}
    keys = (Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate())
    for kind, payload, key, field in (
        ("host_generation", host, keys[0], "origin"),
        ("review_selection", review, keys[1], "review"),
    ):
        message = b"bloguito-featured-image-trust-v1\n" + kind.encode() + b"\n" + writer._canonical(payload)
        request[field] = {"version": 1, "kind": kind, "payload": payload,
                          "signature": base64.b64encode(key.sign(message)).decode("ascii")}
    pub = [k.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
           for k in keys]
    return request, pub


class ForcedGateTest(unittest.TestCase):
    def test_exact_command_and_sudo_no_arguments(self):
        original = "wp-write featured-image-set " + RID
        self.assertEqual(["featured-image-set", RID], gate.parse_original(original))
        runner = Mock(return_value=subprocess.CompletedProcess([], 0))
        self.assertEqual(0, gate.dispatch(original, runner=runner))
        args, kw = runner.call_args
        self.assertEqual([gate.SUDO, "-n", gate.WRITER], args[0])
        self.assertEqual(["featured-image-set", RID], json.loads(kw["input"]))
        self.assertNotIn("shell", kw)

    def test_arbitrary_php_admin_shell_and_forwarding_rejected_before_sudo(self):
        runner = Mock()
        for cmd in ("", None, "wp-write eval phpinfo();", "wp eval 'id'",
                    "wp-write featured-image-set " + RID + "; id",
                    "wp-write featured-image-set " + RID + "\nwhoami",
                    "wp-write featured-image-set " + RID + " --user=admin",
                    "sudo docker exec wordpress_app wp media import /tmp/a.png",
                    "wp-write prepare-draft " + RID, "wp-write featured-image-set ../tmp/a",
                    "wp-write featured-image-set " + RID.upper(), "wp-write featured-image-set " + RID + "`id`",
                    "wp-write featured-image-set " + RID + "|sh"):
            with self.subTest(command=cmd):
                with self.assertRaises(ValueError):
                    gate.dispatch(cmd, runner=runner)
        runner.assert_not_called()


class RootWriterTests(unittest.TestCase):
    def test_json_request_schema_denies_php_admin_path_and_trailing_options(self):
        accepted = ("[\"featured-image-set\",\"" + RID + "\"]").encode()
        self.assertEqual(RID, writer.parse_request(accepted))
        for raw in (b"", b"{}", b'[]', b'null', b'"eval"', b'\xff',
                    b'["wp eval","phpinfo();"]',
                    b'["featured-image-set","../../etc/shadow"]',
                    b'["featured-image-set","' + RID.encode() + b'","--user=admin"]',
                    b'["featured-image-set","' + RID.encode() + b'" ,"wp-admin"]',
                    b'["featured-image-set","' + RID.encode() + b'","/tmp/evil.php"]',
                    b'["featured-image-set","' + RID.encode() + b'",null]',
                    b'["featured-image-set","' + RID.encode() + b'","' + RID.encode() + b'"]',
                    b'["featured-image-set","' + RID.encode() + b'", "a"]' + b" " * 513,
                    b'["featured-image-set","' + RID.encode() + b'","' + RID.encode() + b'","foo"]'):
            with self.subTest(raw=raw[:70]):
                with self.assertRaises(ValueError):
                    writer.parse_request(raw)

    def test_payload_requires_cas_digests_and_canonical_image_metadata(self):
        req, _ = approved(datetime.now(timezone.utc))
        self.assertIs(req, writer.validate_approval(req, RID))
        for key, bad in (("post_id", 0), ("post_id", True), ("attachment_id", "3"),
                         ("image_sha256", "not_hash"), ("release_sha256", "f" * 63),
                         ("selection_mode", "admin"), ("alt_text", "bad\x00alt"),
                         ("candidate_count", 5), ("source_sha256", "c" * 64),
                         ("task_id", "x"), ("target", {"post_id": 1})):
            changed = dict(req, **{key: bad})
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    writer.validate_approval(changed, RID)
        other = dict(req, expected=dict(req["expected"], post_status="publish;id"))
        with self.assertRaises(ValueError):
            writer.validate_approval(other, RID)

    def test_r1_r2_signed_envelopes_validated_against_distinct_root_anchors(self):
        now = datetime.now(timezone.utc)
        req, pubkeys = approved(now)
        def fake_trusted(path, size, **_kwargs):
            return pubkeys[0] if path == writer.HOST_PUBLIC_KEY else pubkeys[1]
        with patch.object(writer, "_trusted_file", side_effect=fake_trusted):
            writer.verify_approval_signatures(req, now=now)
            for field in ("origin", "review"):
                altered = dict(req)
                envelope = dict(req[field])
                envelope["payload"] = dict(envelope["payload"], issuer="forged_claim")
                altered[field] = envelope
                with self.subTest(field=field), self.assertRaises(ValueError):
                    writer.verify_approval_signatures(altered, now=now)
            old = dict(req)
            old["origin"] = dict(req["origin"], payload=dict(req["origin"]["payload"],
                                               issued_at=(now - timedelta(days=7)).isoformat()))
            with self.assertRaises(ValueError):
                writer.verify_approval_signatures(old, now=now)
        with patch.object(writer, "_trusted_file", return_value=pubkeys[0]):
            with self.assertRaisesRegex(ValueError, "independent_signers_required"):
                writer.verify_approval_signatures(req, now=now)

    def test_locked_runtime_hash_not_controllable_by_caller(self):
        runtime = b"<?php /* reviewed fixed release */"
        digest = hashlib.sha256(runtime).hexdigest()
        req = {"release_sha256": digest}
        def contents(path, _limit, **_kwargs):
            return (json.dumps({"protocol": 1, "runtime_sha256": digest}).encode()
                    if path == writer.RELEASE_LOCK else runtime)
        with patch.object(writer, "_trusted_file", side_effect=contents):
            self.assertEqual(digest, writer.locked_runtime_hash(req))
            with self.assertRaisesRegex(ValueError, "release_not_approved"):
                writer.locked_runtime_hash({"release_sha256": "c" * 64})

    def test_no_wordpress_mutation_before_preflight_and_single_claim(self):
        command = json.dumps(["featured-image-set", RID]).encode()
        req, _ = approved(datetime.now(timezone.utc))
        runner = Mock()
        with patch.object(writer, "load_approved_request", return_value=req), \
             patch.object(writer, "verify_approval_signatures", side_effect=ValueError("untrusted")):
            with self.assertRaisesRegex(ValueError, "untrusted"):
                writer.dispatch(command, runner=runner)
        runner.assert_not_called()

        expected_hash = req["release_sha256"]
        fixed_sha = (expected_hash + "  " + writer.CONTAINER_RUNTIME + "\n").encode()
        good = json.dumps({"status": "verified", "post_id": 930,
                           "attachment_id": 931, "image_sha256": SHA}).encode()
        runner = Mock(side_effect=[subprocess.CompletedProcess([], 0, stdout=fixed_sha),
                                   subprocess.CompletedProcess([], 0, stdout=good)])
        with patch.object(writer, "load_approved_request", return_value=req), \
             patch.object(writer, "verify_approval_signatures"), \
             patch.object(writer, "locked_runtime_hash", return_value=expected_hash), \
             patch.object(writer, "_claim_once") as claim:
            self.assertEqual("verified", json.loads(writer.dispatch(command, runner=runner))["status"])
        claim.assert_called_once_with(RID)
        self.assertEqual(2, runner.call_count)
        for call in runner.call_args_list:
            argv = call.args[0]
            self.assertEqual([writer.DOCKER, "exec", "--user", "www-data", "wordpress_app"], argv[:5])
            self.assertNotIn("--allow-root", argv)
            self.assertNotIn("--user=admin", argv)
            self.assertNotIn("eval", argv)
            self.assertNotIn("sh", argv)
        self.assertEqual("eval-file", runner.call_args_list[1].args[0][-3])
        self.assertEqual(writer.CONTAINER_RUNTIME, runner.call_args_list[1].args[0][-2])
        self.assertEqual("--user=" + writer.WP_USER, runner.call_args_list[1].args[0][-1])

    def test_claim_failure_denies_mutation_and_root_main_denies_nonroot(self):
        command = json.dumps(["featured-image-set", RID]).encode()
        req, _ = approved(datetime.now(timezone.utc))
        first = subprocess.CompletedProcess([], 0,
            stdout=(SHA + "  " + writer.CONTAINER_RUNTIME + "\n").encode())
        runner = Mock(return_value=first)
        with patch.object(writer, "load_approved_request", return_value=req), \
             patch.object(writer, "verify_approval_signatures"), \
             patch.object(writer, "locked_runtime_hash", return_value=SHA), \
             patch.object(writer, "_claim_once", side_effect=FileExistsError("replay")):
            with self.assertRaises(FileExistsError):
                writer.dispatch(command, runner=runner)
        self.assertEqual(1, runner.call_count)
        with patch.object(writer.os, "geteuid", return_value=1001, create=True):
            self.assertEqual(126, writer.main())


if __name__ == "__main__":
    unittest.main()
