import copy
import unittest

from agents.validation_reuse import assess_validation_reuse
from test_editorial_system import sample


class ValidationReuseTests(unittest.TestCase):
    def test_exact_bundle_reuses_sources_policy_and_full_review(self):
        old = sample()
        result = assess_validation_reuse(old, copy.deepcopy(old))
        self.assertTrue(result["reuse_sources"])
        self.assertTrue(result["reuse_policy"])
        self.assertTrue(result["reuse_full_semantic_review"])
        self.assertFalse(result["delta_review_only"])

    def test_wording_change_with_same_sources_requests_delta_only(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["sections"][0]["heading"] = "더 짧은 표현"
        result = assess_validation_reuse(old, new)
        self.assertTrue(result["reuse_sources"])
        self.assertTrue(result["reuse_policy"])
        self.assertFalse(result["reuse_full_semantic_review"])
        self.assertTrue(result["delta_review_only"])


if __name__ == "__main__":
    unittest.main()
