"""Scoped edits for already-reviewed WordPress drafts.

The fast path is intentionally narrow: it permits presentation/prose changes
that reuse the exact reviewed topic, sources and evidence. Any new factual
scope returns FULL_REVIEW_REQUIRED instead of silently widening the edit.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime

from agents.editorial import (
    ROOT,
    all_blocks,
    digest,
    excerpt_from_lead,
    fresh,
    policy,
    policy_fingerprint,
    render,
    validate_bundle,
)
from agents.editorial_draft_reviser import _matches_reviewed_draft_content
from agents.editorial_writer import EditorialWriterAgent
from agents.post_manifest_store import (
    acquire_editorial_lock,
    assert_unchanged,
    load_record,
    release_editorial_lock,
    replace_record,
    snapshot_backup_payload,
)
from agents.temporal_validation import KST
from agents.source_validation_cache import verify_explicit_live_sources
from agents.workflow_metrics import increment
from config import DRAFTS_INDEX_FILE
from agents.wordpress_mutation import (
    backup_json,
    get_post,
    guarded_update_post,
    verify_cas,
    verify_saved_fields,
)


FULL_REVIEW_REQUIRED = "FULL_REVIEW_REQUIRED"
FAST_CHAIN_MAX_LENGTH = 5
_BASELINE_MIGRATION_REASONS = {
    "event_standard_overview_schedule_layout_invalid",
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _review_body(bundle):
    return {
        key: bundle[key]
        for key in ("brief", "sources", "plan", "temporal_source")
        if key in bundle
    }


def _edit_intent_digest(edit_intent):
    return digest({"edit_intent": edit_intent.strip()})


def _delta_checks_pass(delta_review):
    return (
        isinstance(delta_review, dict)
        and delta_review.get("issues") == []
        and all(value is True for value in delta_review.get("checks", {}).values())
    )


def validate_fast_review_lineage(bundle, now=None):
    """Validate a full-review anchor plus zero or more bound Fast deltas.

    The full semantic review remains the trust anchor. Every Fast delta must bind
    the exact prior content digest to the exact resulting content digest. This
    permits consecutive wording/layout edits without pretending that the old full
    review directly reviewed the newest prose.
    """
    now = now or datetime.now(KST)
    review = bundle.get("review") if isinstance(bundle.get("review"), dict) else {}
    current_policy = policy_fingerprint(bundle)
    body_digest = digest(_review_body(bundle))
    reasons = []
    if review.get("policy_digest") != current_policy:
        reasons.append("review_policy_changed")
    if not fresh(review.get("checked_at"), now, policy()["review_max_age_hours"]):
        reasons.append("review_stale")
    required_checks = policy()["review_checks"]
    if (any(review.get("checks", {}).get(key) is not True for key in required_checks)
            or review.get("issues") != []):
        reasons.append("semantic_review_failed")
    if reasons:
        return {"status": FULL_REVIEW_REQUIRED, "reasons": reasons, "chain_length": 0}
    if review.get("digest") == body_digest:
        return {"status": "ready", "reasons": [], "chain_length": 0}

    chain = bundle.get("fast_edit_chain")
    if not isinstance(chain, list) or not chain:
        return {
            "status": FULL_REVIEW_REQUIRED,
            "reasons": ["review_not_bound_to_current_content"],
            "chain_length": 0,
        }
    if len(chain) > FAST_CHAIN_MAX_LENGTH:
        return {
            "status": FULL_REVIEW_REQUIRED,
            "reasons": ["fast_review_chain_limit"],
            "chain_length": len(chain),
        }

    expected_base = review.get("digest")
    for index, delta_review in enumerate(chain):
        if not _delta_checks_pass(delta_review):
            reasons.append(f"fast_delta_review_failed:{index}")
            break
        if delta_review.get("base_review_digest") != review.get("digest"):
            reasons.append(f"fast_delta_anchor_mismatch:{index}")
            break
        if delta_review.get("base_policy_digest") != current_policy:
            reasons.append(f"fast_delta_policy_mismatch:{index}")
            break
        if delta_review.get("base_content_digest") != expected_base:
            reasons.append(f"fast_delta_base_mismatch:{index}")
            break
        result_digest = delta_review.get("result_content_digest")
        if not isinstance(result_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", result_digest):
            reasons.append(f"fast_delta_result_missing:{index}")
            break
        if not fresh(delta_review.get("checked_at"), now, policy()["review_max_age_hours"]):
            reasons.append(f"fast_delta_review_stale:{index}")
            break
        expected_base = result_digest
    if not reasons and expected_base != body_digest:
        reasons.append("fast_review_chain_not_bound_to_current_content")
    return {
        "status": "ready" if not reasons else FULL_REVIEW_REQUIRED,
        "reasons": reasons,
        "chain_length": len(chain),
    }


def _evidence_pairs(bundle):
    return {
        (item.get("source_id"), item.get("quote"))
        for block in all_blocks(bundle.get("plan", {}))
        for item in block.get("evidence", [])
        if isinstance(item, dict)
    }


_NUMBER_FACT_TOKEN = re.compile(
    r"\d+(?:[.,]\d+)*(?:\s*(?:원|만원|명|개|회|분|시간|시|일|월|년|%))?"
)
_KOREAN_MONTH_DAY = re.compile(r"(?<!\d)(\d{1,2})월\s*(\d{1,2})일")
_COMPACT_MONTH_DAY = re.compile(
    r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:\([월화수목금토일]\))?"
)
_GEO_VENUE_CANDIDATE = re.compile(
    r"[가-힣A-Za-z0-9]+(?:특별시|광역시|특별자치시|특별자치도|도|시|군|구|동|읍|면|리|역|센터|회관|홀|아레나|돔|체육관)"
)
_COMMON_REGION_TOKENS = {
    '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
    '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
}


def _visible_text(plan):
    values = [plan.get("title", ""), (plan.get("lead") or {}).get("text", "")]
    for section in plan.get("sections", []):
        values.append(section.get("heading", ""))
        values.extend((p or {}).get("text", "") for p in section.get("paragraphs", []))
        table = section.get("table") or {}
        values.append(table.get("caption", ""))
        values.extend(table.get("headers", []))
        for row in table.get("rows", []):
            values.extend(row.get("cells", []))
    for faq in plan.get("faq", []):
        values.extend((faq.get("question", ""), (faq.get("answer") or {}).get("text", "")))
    return "\n".join(value for value in values if isinstance(value, str))


def _fact_tokens(plan, sources):
    visible = _visible_text(plan)
    result = Counter(
        match.group(0).replace(" ", "")
        for match in _NUMBER_FACT_TOKEN.finditer(visible)
    )
    source_text = "\n".join(
        source.get("text", "") for source in sources if isinstance(source, dict)
    )
    for match in _GEO_VENUE_CANDIDATE.finditer(visible):
        token = match.group(0)
        # Short Korean words such as "정리", "당시", "관리" can end in an
        # administrative suffix by accident. Treat such strings as factual
        # locations/venues only when the reviewed source snapshot contains the
        # exact token. Major region names are handled explicitly below.
        if token in source_text:
            result[token] += 1
    for token in _COMMON_REGION_TOKENS:
        count = visible.count(token)
        if count:
            result[token] += count
    return result


def _date_format_number_allowance(old_plan, new_plan):
    """Allow only digit fragments created by an equivalent date-format rewrite.

    Fast edits normally reject every newly visible number.  Converting an already
    reviewed Korean date such as ``10월 7일`` to the compact overview form
    ``10/7(수)`` changes the tokenizer from ``10월``/``7일`` to bare ``10``/``7``
    even though the date itself is unchanged.  Match exact month/day pairs and
    exempt only the bare numeric fragments belonging to those matched pairs.

    This deliberately does not exempt prices, times, years, counts, or a compact
    date whose month/day pair did not already appear in the reviewed copy.
    """
    old_dates = Counter(
        (str(int(month)), str(int(day)))
        for month, day in _KOREAN_MONTH_DAY.findall(_visible_text(old_plan))
    )
    new_dates = Counter(
        (str(int(month)), str(int(day)))
        for month, day in _COMPACT_MONTH_DAY.findall(_visible_text(new_plan))
    )
    allowed = Counter()
    for pair, count in new_dates.items():
        matched = min(count, old_dates.get(pair, 0))
        if not matched:
            continue
        month, day = pair
        allowed[month] += matched
        allowed[day] += matched
    return allowed


def _high_risk_claims(plan):
    text = _visible_text(plan)
    patterns = (
        r"(?:현재\s*)?(?:예매|판매|신청|접수)\s*(?:중|가능)",
        r"잔여\s*좌석|남은\s*좌석|매진|품절",
        r"(?:지원|수급|선정)\s*(?:대상|가능|확정)",
    )
    return {pattern for pattern in patterns if re.search(pattern, text)}


def _block_signature(block):
    return {
        "scope": block.get("scope", "content"),
        "text": block.get("text", ""),
        "evidence": block.get("evidence", []),
        "answers": block.get("answers", []),
        "calculations": block.get("calculations", []),
    }


def _dedupe_evidence(items):
    seen = set()
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = (item.get("source_id"), item.get("quote"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _structural_review_blocks(plan):
    """Represent reader-visible structure in the scoped delta review."""
    result = []
    for index, section in enumerate(plan.get("sections", [])):
        section_evidence = []
        for paragraph in section.get("paragraphs", []):
            section_evidence.extend(paragraph.get("evidence", []))
        table = section.get("table") or {}
        for row in table.get("rows", []):
            section_evidence.extend(row.get("evidence", []))
        section_evidence = _dedupe_evidence(section_evidence)
        result.append({
            "scope": f"section_heading:{index}",
            "text": section.get("heading", ""),
            "evidence": section_evidence,
            "answers": [],
            "calculations": [],
        })
        if table:
            result.append({
                "scope": f"table_structure:{index}",
                "text": " | ".join([table.get("caption", ""), *table.get("headers", [])]),
                "evidence": section_evidence,
                "answers": [],
                "calculations": [],
            })
    for index, faq in enumerate(plan.get("faq", [])):
        answer = faq.get("answer") or {}
        result.append({
            "scope": f"faq_question:{index}",
            "text": faq.get("question", ""),
            "evidence": _dedupe_evidence(answer.get("evidence", [])),
            "answers": answer.get("answers", []),
            "calculations": [],
        })
    return result


def _review_units(plan):
    content = []
    for item in all_blocks(plan):
        signature = _block_signature(item)
        signature["scope"] = "content"
        content.append(signature)
    return [*content, *_structural_review_blocks(plan)]


def changed_blocks(old_bundle, new_bundle):
    old = _review_units(old_bundle["plan"])
    new = _review_units(new_bundle["plan"])
    old_counts = Counter(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in old)
    new_counts = Counter(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in new)
    removed = [json.loads(item) for item, count in (old_counts - new_counts).items() for _ in range(count)]
    added = [json.loads(item) for item, count in (new_counts - old_counts).items() for _ in range(count)]
    return {"removed": removed, "added": added}


def classify_fast_edit(old_bundle, new_bundle):
    reasons = []
    if old_bundle.get("brief") != new_bundle.get("brief"):
        reasons.append("brief_changed")
    if old_bundle.get("temporal_source", {}) != new_bundle.get("temporal_source", {}):
        reasons.append("temporal_source_changed")
    if old_bundle.get("sources") != new_bundle.get("sources"):
        reasons.append("sources_or_actions_changed")
    old_plan = old_bundle.get("plan", {})
    new_plan = new_bundle.get("plan", {})
    if old_plan.get("title") != new_plan.get("title"):
        reasons.append("title_changed")
    if old_plan.get("related_posts", []) != new_plan.get("related_posts", []):
        reasons.append("related_posts_changed")
    if old_plan.get("official_navigation", []) != new_plan.get("official_navigation", []):
        reasons.append("official_navigation_changed")
    old_section_links = [section.get("official_links", []) for section in old_plan.get("sections", [])]
    new_section_links = [section.get("official_links", []) for section in new_plan.get("sections", [])]
    if old_section_links != new_section_links:
        # Reader navigation to an external destination is not a wording-only
        # delta. Force Standard so the URL/source binding is fully validated.
        reasons.append("section_official_links_changed")
    if not _evidence_pairs(new_bundle).issubset(_evidence_pairs(old_bundle)):
        reasons.append("new_evidence_added")

    old_tokens = _fact_tokens(old_plan, old_bundle.get("sources", []))
    new_tokens = _fact_tokens(new_plan, new_bundle.get("sources", []))
    added = new_tokens - old_tokens
    added -= _date_format_number_allowance(old_plan, new_plan)
    added_tokens = sorted(added.elements())
    if added_tokens:
        reasons.append("new_fact_tokens:" + ",".join(added_tokens[:12]))

    if _high_risk_claims(new_plan) - _high_risk_claims(old_plan):
        reasons.append("new_high_risk_claim")

    delta = changed_blocks(old_bundle, new_bundle)
    return {
        "status": "candidate" if not reasons else FULL_REVIEW_REQUIRED,
        "reasons": reasons,
        "changed_blocks": delta,
        "base_content_digest": digest(_review_body(old_bundle)),
        "result_content_digest": digest(_review_body(new_bundle)),
    }


def _synthetic_inventory(bundle, now=None):
    now = now or datetime.now(KST)
    rows = [
        {"ID": item["post_id"], "post_title": item["label"], "post_status": "publish", "post_content": ""}
        for item in bundle.get("plan", {}).get("related_posts", [])
        if isinstance(item, dict) and type(item.get("post_id")) is int
    ]
    return {"checked_on": now.date().isoformat(), "posts": rows}


def validate_fast_edit(old_bundle, new_bundle, now=None):
    classification = classify_fast_edit(old_bundle, new_bundle)
    if classification["status"] != "candidate":
        return classification

    old_report = validate_bundle(
        old_bundle,
        _synthetic_inventory(old_bundle, now),
        now=now,
        require_review=False,
    )
    old_reasons = set(old_report.get("reasons", []))
    baseline_layout_migration = bool(
        old_reasons
        and old_reasons <= _BASELINE_MIGRATION_REASONS
        and old_bundle.get("brief", {}).get("event_post_standard_version") is not None
        and new_bundle.get("brief", {}).get("event_post_standard_version") is not None
    )
    if old_report["status"] != "ready" and not baseline_layout_migration:
        return {
            "status": FULL_REVIEW_REQUIRED,
            "reasons": ["base_review_not_current", *old_report["reasons"]],
            "changed_blocks": classification["changed_blocks"],
            "base_content_digest": classification["base_content_digest"],
            "result_content_digest": classification["result_content_digest"],
        }
    lineage = validate_fast_review_lineage(old_bundle, now=now)
    if lineage["status"] != "ready":
        return {
            "status": FULL_REVIEW_REQUIRED,
            "reasons": ["base_review_not_current", *lineage["reasons"]],
            "changed_blocks": classification["changed_blocks"],
            "base_content_digest": classification["base_content_digest"],
            "result_content_digest": classification["result_content_digest"],
        }
    if lineage.get("chain_length", 0) >= FAST_CHAIN_MAX_LENGTH:
        return {
            "status": FULL_REVIEW_REQUIRED,
            "reasons": ["fast_review_chain_limit"],
            "changed_blocks": classification["changed_blocks"],
            "base_content_digest": classification["base_content_digest"],
            "result_content_digest": classification["result_content_digest"],
        }
    new_report = validate_bundle(
        new_bundle,
        _synthetic_inventory(new_bundle, now),
        now=now,
        require_review=False,
    )
    if new_report["status"] != "ready":
        return {
            "status": FULL_REVIEW_REQUIRED,
            "reasons": ["fast_deterministic_check_failed", *new_report["reasons"]],
            "changed_blocks": classification["changed_blocks"],
            "base_content_digest": classification["base_content_digest"],
            "result_content_digest": classification["result_content_digest"],
        }
    if baseline_layout_migration:
        classification = dict(classification)
        classification["baseline_migration"] = sorted(old_reasons)
    return classification


def _review_delta(old_bundle, new_bundle, delta, edit_intent):
    if not delta["added"] and not delta["removed"]:
        return {
            "mode": "delta",
            "base_review_digest": old_bundle["review"]["digest"],
            "base_policy_digest": old_bundle["review"]["policy_digest"],
            "delta_digest": digest(delta),
            "base_content_digest": digest(_review_body(old_bundle)),
            "result_content_digest": digest(_review_body(new_bundle)),
            "checks": {
                "meaning_preserved": True,
                "evidence_still_supports": True,
                "conditions_preserved": True,
                "no_new_claims": True,
                "reader_task_preserved": True,
            },
            "issues": [],
            "edit_intent_digest": _edit_intent_digest(edit_intent),
            "checked_at": datetime.now(KST).isoformat(),
        }
    return EditorialWriterAgent(writing_enabled=False).review_delta(
        old_bundle,
        new_bundle,
        delta,
        edit_intent,
    )


def validate_prepared_delta_review(old_bundle, report, delta_review, edit_intent):
    """Validate a previously completed delta review before reusing it.

    This enables interrupted Fast edits to resume without paying for the same
    semantic review again, while binding the cached result to the exact baseline,
    policy, delta and user edit intent.
    """
    if not isinstance(delta_review, dict):
        return False
    if report.get("status") != "candidate":
        return False
    if delta_review.get("base_review_digest") != old_bundle.get("review", {}).get("digest"):
        return False
    if delta_review.get("base_policy_digest") != old_bundle.get("review", {}).get("policy_digest"):
        return False
    if delta_review.get("delta_digest") != digest(report.get("changed_blocks", {})):
        return False
    if delta_review.get("base_content_digest") != report.get("base_content_digest"):
        return False
    if delta_review.get("result_content_digest") != report.get("result_content_digest"):
        return False
    if delta_review.get("edit_intent_digest") != _edit_intent_digest(edit_intent):
        return False
    return _delta_checks_pass(delta_review)


def prepare_fast_delta_review(old_bundle, new_bundle, report, edit_intent):
    """Run only the Fast-path changed-block semantic review and bind it."""
    if report.get("status") != "candidate":
        raise ValueError(FULL_REVIEW_REQUIRED + ":" + json.dumps(report.get("reasons", []), ensure_ascii=False))
    delta_review = _review_delta(old_bundle, new_bundle, report["changed_blocks"], edit_intent)
    if not validate_prepared_delta_review(old_bundle, report, delta_review, edit_intent):
        raise ValueError(FULL_REVIEW_REQUIRED + ":delta_semantic_review_failed")
    return delta_review


def build_fast_stored_bundle(old_bundle, new_bundle, delta_review):
    """Return the candidate plus the exact full-review/delta lineage to persist."""
    stored = copy.deepcopy(new_bundle)
    stored["review"] = old_bundle["review"]
    stored["fast_edit_review"] = copy.deepcopy(delta_review)
    prior_chain = old_bundle.get("fast_edit_chain", [])
    if not isinstance(prior_chain, list):
        raise ValueError(FULL_REVIEW_REQUIRED + ":invalid_fast_edit_chain")
    if len(prior_chain) >= FAST_CHAIN_MAX_LENGTH:
        raise ValueError(FULL_REVIEW_REQUIRED + ":fast_review_chain_limit")
    stored["fast_edit_chain"] = [*copy.deepcopy(prior_chain), copy.deepcopy(delta_review)]
    return stored


def fast_revise_reviewed_draft(post_id, bundle, expected_content_sha256, *, confirmed=False,
                               edit_intent=None, prepared_delta_review=None):
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_fast_draft_revision_confirmation_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    if (not isinstance(edit_intent, str) or not 4 <= len(edit_intent.strip()) <= 1000
            or re.search(r'[<>\x00]', edit_intent)):
        raise ValueError("fast_edit_intent_required")
    edit_intent = edit_intent.strip()
    lock = acquire_editorial_lock(ROOT)

    try:
        if not DRAFTS_INDEX_FILE.is_file():
            raise ValueError("reviewed_draft_index_missing")
        state_snapshot = load_record(DRAFTS_INDEX_FILE, post_id)
        if state_snapshot is None or "editorial_bundle" not in state_snapshot.record.get("fact_manifest", {}):
            raise ValueError("reviewed_draft_manifest_required")
        item = state_snapshot.record
        old_bundle = item["fact_manifest"]["editorial_bundle"]

        report = validate_fast_edit(old_bundle, bundle)
        if report["status"] != "candidate":
            raise ValueError(FULL_REVIEW_REQUIRED + ":" + json.dumps(report["reasons"], ensure_ascii=False))
        if prepared_delta_review is not None:
            if not validate_prepared_delta_review(
                    old_bundle, report, prepared_delta_review, edit_intent):
                raise ValueError(FULL_REVIEW_REQUIRED + ":prepared_delta_review_mismatch")
            delta_review = prepared_delta_review
        else:
            delta_review = prepare_fast_delta_review(old_bundle, bundle, report, edit_intent)

        verify_explicit_live_sources(bundle)

        base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
        post_fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
        live = get_post(base, post_id, fields=post_fields)
        if (not verify_cas(live, status="draft", title=old_bundle["plan"]["title"],
                           content_sha=expected_content_sha256)
                or not _matches_reviewed_draft_content(
                    old_bundle, live.get("post_content", ""), post_id=post_id)):
            raise ValueError("draft_changed_before_fast_revision")
        assert_unchanged(state_snapshot)

        old_excerpt = excerpt_from_lead(old_bundle["plan"]["lead"])
        if live.get("post_excerpt", "") != old_excerpt:
            raise ValueError("draft_excerpt_changed_since_review")

        desired = render(bundle["plan"], bundle["sources"])
        new_excerpt = excerpt_from_lead(bundle["plan"]["lead"])
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        post_backup = backup_json(ROOT, "fast-draft-revision", post_id, live)
        archive = ROOT / "data" / "editorial_runs"
        index_backup = archive / f"fast-draft-revision-index-{post_id}-{stamp}.json"
        index_backup.write_text(
            json.dumps(snapshot_backup_payload(state_snapshot), ensure_ascii=False, indent=2),
            encoding="utf-8")
        os.chmod(index_backup, 0o600)

        saved = guarded_update_post(
            base,
            post_id,
            expected={
                "post_status": "draft",
                "post_title": live.get("post_title", ""),
                "post_name": live.get("post_name", ""),
                "post_excerpt": live.get("post_excerpt", ""),
                "content_sha256": expected_content_sha256,
            },
            updates={"post_content": desired, "post_excerpt": new_excerpt},
        )
        if not verify_saved_fields(
                saved,
                expected={
                    "post_status": "draft",
                    "post_title": live.get("post_title"),
                    "post_content": desired,
                    "post_excerpt": new_excerpt,
                },
                preserved={"post_name": live.get("post_name")}):
            raise ValueError(f"fast_draft_revision_save_verification_failed: recover from {post_backup}")
        try:
            assert_unchanged(state_snapshot)
        except ValueError as exc:
            raise ValueError(f"draft_index_changed: recover from {index_backup}") from exc

        stored = build_fast_stored_bundle(old_bundle, bundle, delta_review)
        updated = dict(item)
        updated.setdefault("fact_manifest", dict(item.get("fact_manifest", {})))["editorial_bundle"] = stored
        replace_record(state_snapshot, updated)
        return post_id
    finally:
        release_editorial_lock(lock)
