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
    policy_fingerprint,
    render,
    validate_bundle,
)
from agents.editorial_writer import EditorialWriterAgent
from agents.temporal_validation import KST
from agents.workflow_metrics import increment, timed
from config import DRAFTS_INDEX_FILE
from agents.wordpress_mutation import backup_json, get_post, update_post, verify_cas, verify_saved_fields


FULL_REVIEW_REQUIRED = "FULL_REVIEW_REQUIRED"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
    if not _evidence_pairs(new_bundle).issubset(_evidence_pairs(old_bundle)):
        reasons.append("new_evidence_added")

    old_tokens = _fact_tokens(old_plan, old_bundle.get("sources", []))
    new_tokens = _fact_tokens(new_plan, new_bundle.get("sources", []))
    added_tokens = sorted((new_tokens - old_tokens).elements())
    if added_tokens:
        reasons.append("new_fact_tokens:" + ",".join(added_tokens[:12]))

    if _high_risk_claims(new_plan) - _high_risk_claims(old_plan):
        reasons.append("new_high_risk_claim")

    delta = changed_blocks(old_bundle, new_bundle)
    return {
        "status": "candidate" if not reasons else FULL_REVIEW_REQUIRED,
        "reasons": reasons,
        "changed_blocks": delta,
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

    old_report = validate_bundle(old_bundle, _synthetic_inventory(old_bundle, now), now=now)
    if old_report["status"] != "ready":
        return {
            "status": FULL_REVIEW_REQUIRED,
            "reasons": ["base_review_not_current", *old_report["reasons"]],
            "changed_blocks": classification["changed_blocks"],
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
        }
    return classification


def _review_delta(old_bundle, new_bundle, delta, edit_intent):
    if not delta["added"] and not delta["removed"]:
        return {
            "mode": "delta",
            "base_review_digest": old_bundle["review"]["digest"],
            "base_policy_digest": old_bundle["review"]["policy_digest"],
            "delta_digest": digest(delta),
            "checks": {
                "meaning_preserved": True,
                "evidence_still_supports": True,
                "conditions_preserved": True,
                "no_new_claims": True,
                "reader_task_preserved": True,
            },
            "issues": [],
            "edit_intent": edit_intent,
            "checked_at": datetime.now(KST).isoformat(),
        }
    return EditorialWriterAgent(writing_enabled=False).review_delta(
        old_bundle,
        new_bundle,
        delta,
        edit_intent,
    )


def fast_revise_reviewed_draft(post_id, bundle, expected_content_sha256, *, confirmed=False,
                               edit_intent=None):
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_fast_draft_revision_confirmation_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    if (not isinstance(edit_intent, str) or not 4 <= len(edit_intent.strip()) <= 1000
            or re.search(r'[<>\x00]', edit_intent)):
        raise ValueError("fast_edit_intent_required")
    edit_intent = edit_intent.strip()
    lock = ROOT / "data" / ".editorial-publish.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError("editorial_publication_busy: inspect the existing job")

    try:
        if not DRAFTS_INDEX_FILE.is_file():
            raise ValueError("reviewed_draft_index_missing")
        index_before = DRAFTS_INDEX_FILE.read_text(encoding="utf-8")
        records = json.loads(index_before)
        matches = [item for item in records if int(item.get("id", -1)) == post_id]
        if len(matches) != 1 or "editorial_bundle" not in matches[0].get("fact_manifest", {}):
            raise ValueError("reviewed_draft_manifest_required")
        item = matches[0]
        old_bundle = item["fact_manifest"]["editorial_bundle"]

        report = validate_fast_edit(old_bundle, bundle)
        if report["status"] != "candidate":
            raise ValueError(FULL_REVIEW_REQUIRED + ":" + json.dumps(report["reasons"], ensure_ascii=False))
        delta_review = _review_delta(old_bundle, bundle, report["changed_blocks"], edit_intent)
        if (delta_review.get("issues") != []
                or any(value is not True for value in delta_review.get("checks", {}).values())):
            raise ValueError(FULL_REVIEW_REQUIRED + ":delta_semantic_review_failed")

        base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
        post_fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
        live = get_post(base, post_id, fields=post_fields)
        expected_old = render(old_bundle["plan"], old_bundle["sources"])
        if (not verify_cas(live, status="draft", title=old_bundle["plan"]["title"],
                           content_sha=expected_content_sha256)
                or live.get("post_content", "").replace("\r\n", "\n")
                    != expected_old.replace("\r\n", "\n")
                or DRAFTS_INDEX_FILE.read_text(encoding="utf-8") != index_before):
            raise ValueError("draft_changed_before_fast_revision")

        old_excerpt = excerpt_from_lead(old_bundle["plan"]["lead"])
        if live.get("post_excerpt", "") != old_excerpt:
            raise ValueError("draft_excerpt_changed_since_review")

        desired = render(bundle["plan"], bundle["sources"])
        new_excerpt = excerpt_from_lead(bundle["plan"]["lead"])
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        post_backup = backup_json(ROOT, "fast-draft-revision", post_id, live)
        archive = ROOT / "data" / "editorial_runs"
        index_backup = archive / f"fast-draft-revision-index-{post_id}-{stamp}.json"
        index_backup.write_text(index_before, encoding="utf-8")
        os.chmod(index_backup, 0o600)

        update_post(base, post_id, {"post_content": desired, "post_excerpt": new_excerpt})
        saved = get_post(base, post_id, fields=post_fields)
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
        if DRAFTS_INDEX_FILE.read_text(encoding="utf-8") != index_before:
            raise ValueError(f"draft_index_changed: recover from {index_backup}")

        stored = copy.deepcopy(bundle)
        stored["review"] = old_bundle["review"]
        stored["fast_edit_review"] = delta_review
        item["fact_manifest"]["editorial_bundle"] = stored
        temporary = DRAFTS_INDEX_FILE.with_suffix(".fast-revision-tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(DRAFTS_INDEX_FILE)
        return post_id
    finally:
        lock.rmdir()
