"""R1/R2 adversarial cases: test-issued signatures are fixtures, never production authority."""

import base64
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agents.featured_image_trust import (_canonical, verify_image_upload_trust)


class IndependentFeaturedImageTrustTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.keys = self.root / 'keys'
        self.keys.mkdir()
        self.host_key = Ed25519PrivateKey.generate()
        self.review_key = Ed25519PrivateKey.generate()
        for name, key in [('host', self.host_key), ('review', self.review_key)]:
            (self.keys / f'{name}.pub.pem').write_bytes(key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.created = self.now - timedelta(hours=2)
        self.task = {'task_id': 'task-12345678', 'target': {'post_id': 922},
                     'candidate_count': 1, 'generator_policy_sha256': 'f' * 64}
        self.manifest = self.root / 'candidate-manifest.json'
        self.review = self.root / 'quality.json'
        self.source = 'a' * 64
        self.staged = 'b' * 64
        self.manifest.write_text(json.dumps({'candidates': [
            {'candidate_number': 1, 'sha256': self.source}]}), encoding='utf-8')
        self.review.write_text(json.dumps({'task_id': self.task['task_id'],
                                           'review_actor': 'independent-reviewer'}), encoding='utf-8')
        self.common = {'task_id': self.task['task_id'], 'target': self.task['target'],
                       'generator_policy_sha256': 'f' * 64}
        self.host = {**self.common,
                     'candidates': [{'candidate_number': 1, 'sha256': self.source}],
                     'issuer': 'verified_chatgpt_host_event',
                     'issued_at': (self.now - timedelta(minutes=45)).isoformat(),
                     'expires_at': (self.now + timedelta(hours=1)).isoformat()}
        import hashlib
        self.approval = {
            **self.common, 'manifest_sha256': hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
            'review_receipt_sha256': hashlib.sha256(self.review.read_bytes()).hexdigest(),
            'source_sha256': self.source, 'staged_sha256': self.staged,
            'selected_candidate': 1, 'selection_mode': 'user',
            'review_actor': 'independent-reviewer',
            'issuer': 'independent_reviewer_authority',
            'issued_at': (self.now - timedelta(minutes=30)).isoformat(),
            'expires_at': (self.now + timedelta(hours=1)).isoformat(),
        }

    def sign(self, kind, payload, key=None):
        signer = key or (self.host_key if kind == 'host_generation' else self.review_key)
        proof = {'version': 1, 'kind': kind, 'payload': payload,
                 'signature': base64.b64encode(signer.sign(_canonical(kind, payload))).decode('ascii')}
        path = (self.manifest.with_name(self.manifest.name + '.host-proof.json')
                if kind == 'host_generation' else
                self.review.with_name(self.review.name + '.review-proof.json'))
        path.write_text(json.dumps(proof), encoding='utf-8')

    def verify(self, **changes):
        kwargs = dict(task=self.task, manifest_path=self.manifest, review_path=self.review,
                      source_sha256=self.source, staged_sha256=self.staged,
                      selected_candidate=1, selection_mode='user',
                      task_created_at=self.created.isoformat(), now=self.now,
                      trust_root=self.keys)
        kwargs.update(changes)
        return verify_image_upload_trust(**kwargs)

    def both_signed(self):
        self.sign('host_generation', self.host)
        self.sign('review_selection', self.approval)

    def test_missing_independent_issuer_is_held_before_import(self):
        with self.assertRaisesRegex(ValueError, 'held_provenance_unverifiable'):
            self.verify(trust_root=self.root / 'missing')

    @unittest.skipUnless(os.name == 'nt', 'Windows client cannot host POSIX-root trust anchors')
    def test_windows_client_cannot_appoint_its_own_production_trust_anchors(self):
        self.both_signed()
        with self.assertRaisesRegex(ValueError, 'protected_server_verifier_required'):
            self.verify(trust_root=None)

    def test_only_independently_signed_same_task_and_bytes_can_pass_fixture(self):
        self.both_signed()
        self.assertEqual('host_verified_and_review_authorized', self.verify()['status'])

    def test_caller_invented_imagegen_claim_and_review_json_without_proofs_fails(self):
        with self.assertRaisesRegex(ValueError, 'proof_missing_or_invalid'):
            self.verify()

    def test_host_proof_is_required_even_when_review_proof_is_signed(self):
        self.sign('review_selection', self.approval)
        with self.assertRaisesRegex(ValueError, 'proof_missing_or_invalid'):
            self.verify()

    def test_review_selection_requires_separate_issuer(self):
        self.sign('host_generation', self.host)
        self.sign('review_selection', self.approval, key=self.host_key)
        with self.assertRaisesRegex(ValueError, 'signature_or_issuer_unverifiable'):
            self.verify()

    def test_other_post_task_or_policy_replay_blocked(self):
        self.both_signed()
        for task in ({**self.task, 'target': {'post_id': 923}},
                     {**self.task, 'task_id': 'task-98765432'},
                     {**self.task, 'generator_policy_sha256': '0' * 64}):
            with self.subTest(task=task), self.assertRaises(ValueError):
                self.verify(task=task)

    def test_changed_manifest_or_review_or_staged_image_fails(self):
        self.both_signed()
        self.review.write_text(json.dumps({'task_id': self.task['task_id'],
                                           'review_actor': 'user'}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'not_authenticated'):
            self.verify()
        self.review.write_text(json.dumps({'task_id': self.task['task_id'],
                                           'review_actor': 'independent-reviewer'}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'not_authenticated'):
            self.verify(staged_sha256='c' * 64)
        self.manifest.write_text(json.dumps({'candidates': [
            {'candidate_number': 1, 'sha256': 'c' * 64}]}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'selected_source_mismatch'):
            self.verify()

    def test_expired_or_future_or_predates_task_proofs_are_rejected(self):
        self.both_signed()
        with self.assertRaisesRegex(ValueError, 'proof_expired_or_wrong_task_time'):
            self.verify(now=self.now + timedelta(days=2))
        with self.assertRaisesRegex(ValueError, 'proof_expired_or_wrong_task_time'):
            self.verify(task_created_at=(self.now - timedelta(minutes=5)).isoformat())
        with self.assertRaisesRegex(ValueError, 'proof_expired_or_wrong_task_time'):
            self.verify(now=self.now - timedelta(hours=1))

    def test_spoofed_signature_and_duplicate_public_keys_rejected(self):
        self.sign('host_generation', self.host, key=self.review_key)
        self.sign('review_selection', self.approval)
        with self.assertRaisesRegex(ValueError, 'signature_or_issuer_unverifiable'):
            self.verify()
        (self.keys / 'host.pub.pem').write_bytes((self.keys / 'review.pub.pem').read_bytes())
        with self.assertRaisesRegex(ValueError, 'independent_trust_issuers_unavailable'):
            self.verify()

    def test_selection_mode_and_review_actor_must_match_issuer_event(self):
        self.both_signed()
        with self.assertRaisesRegex(ValueError, 'not_authenticated'):
            self.verify(selection_mode='agent-delegated')
        self.review.write_text(json.dumps({'task_id': self.task['task_id'],
                                           'review_actor': 'agent-delegated'}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'not_authenticated'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
