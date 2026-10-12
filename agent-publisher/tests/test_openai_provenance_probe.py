import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


SPEC = importlib.util.spec_from_file_location(
    'openai_provenance_probe', Path(__file__).resolve().parents[2]
    / 'scripts' / 'security' / 'openai_provenance_probe.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.content_provenance_checks = self

    def create(self, *, file):
        assert len(file[1].read()) > 0
        return self.result


class OpenAIProviderProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.image = Path(self.folder.name) / 'original.png'
        self.image.write_bytes(b'fixture-original-not-actually-a-png')
        self.verified = {'object': 'content_provenance_check', 'created_at': 1790000000,
                         'results': [{'type': 'c2pa', 'outcome': 'detected',
                                      'validation_state': 'trusted', 'issuer': 'OpenAI OpCo, LLC',
                                      'model': 'gpt-image'}]}

    def test_provider_signal_positive_still_only_a_signal(self):
        result = MODULE.probe_original(self.image, client=FakeClient(self.verified))
        self.assertEqual('provider_signal_detected', result['status'])
        self.assertTrue(result['trusted_openai_c2pa'])
        self.assertNotIn('host_signature', result)
        self.assertNotIn('task_id', result)

    def test_synthid_only_or_untrusted_claim_cannot_claim_strict_c2pa(self):
        for fake in ({'type': 'synthid', 'outcome': 'detected'},
                     {'type': 'c2pa', 'outcome': 'detected', 'validation_state': 'invalid',
                      'issuer': 'OpenAI OpCo, LLC', 'model': 'gpt-image'},
                     {'type': 'c2pa', 'outcome': 'detected', 'validation_state': 'trusted',
                      'issuer': 'Someone Else', 'model': 'gpt-image'}):
            with self.subTest(fake=fake):
                payload = dict(self.verified, results=[fake])
                self.assertEqual('held_provenance_unverifiable',
                                 MODULE.probe_original(self.image, client=FakeClient(payload))['status'])

    def test_provider_failure_is_not_host_proof(self):
        with self.assertRaisesRegex(ValueError, 'provider_provenance_response_invalid'):
            MODULE.probe_original(self.image, client=FakeClient({'results': []}))


if __name__ == '__main__':
    unittest.main()
