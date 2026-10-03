"""Deterministic fingerprints for reusing unchanged editorial validation work."""

from __future__ import annotations

from copy import deepcopy

from agents.editorial import digest, policy_fingerprint


def _review_body(bundle: dict) -> dict:
    return {
        key: deepcopy(bundle[key])
        for key in ("brief", "sources", "plan", "temporal_source")
        if key in bundle
    }


def validation_fingerprint(bundle: dict | None) -> dict[str, str | None]:
    if not isinstance(bundle, dict):
        return {
            "content_digest": None,
            "source_digest": None,
            "policy_digest": None,
            "review_digest": None,
            "review_policy_digest": None,
            "review_checked_at": None,
        }
    review = bundle.get("review") if isinstance(bundle.get("review"), dict) else {}
    return {
        "content_digest": digest(_review_body(bundle)),
        "source_digest": digest(bundle.get("sources", [])),
        "policy_digest": policy_fingerprint(bundle),
        "review_digest": review.get("digest"),
        "review_policy_digest": review.get("policy_digest"),
        "review_checked_at": review.get("checked_at"),
    }


def assess_validation_reuse(old_bundle: dict | None, new_bundle: dict) -> dict:
    old = validation_fingerprint(old_bundle)
    new = validation_fingerprint(new_bundle)
    has_baseline = isinstance(old_bundle, dict)
    same_sources = has_baseline and old["source_digest"] == new["source_digest"]
    same_policy = has_baseline and old["policy_digest"] == new["policy_digest"]
    old_review_current_for_policy = old["review_policy_digest"] == old["policy_digest"]
    exact_review_body = old["content_digest"] == new["content_digest"]
    return {
        "fingerprint_before": old,
        "fingerprint_after": new,
        "reuse_sources": bool(same_sources),
        "reuse_policy": bool(same_policy),
        "reuse_full_semantic_review": bool(
            exact_review_body and same_policy and old_review_current_for_policy
            and old["review_digest"] == old["content_digest"]
        ),
        "delta_review_only": bool(same_sources and same_policy and not exact_review_body),
    }
