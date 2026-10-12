"""Review preparation and evidence for ChatGPT featured-image candidates.

Similarity is only a prompt for a reviewer. Neither a perceptual metric nor a
completed JSON receipt proves that a human/model actually viewed an image.
Only an observed, documented reviewer decision may accept visual quality.
This module never creates cover art or writes to WordPress.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from PIL import Image, ImageOps


SCHEMA_VERSION = 1
CHECKS = (
    "topic_scene", "editorial_quality", "candidate_diversity",
    "recent_cover_comparison", "text_accuracy", "mobile_readability",
)
REVIEW_RESULTS = frozenset({"PASS", "REJECT", "UNVERIFIED"})
REVIEW_ACTORS = frozenset({"user", "agent-delegated", "independent-reviewer"})
REVIEW_METHODS = frozenset({"human_visual", "direct_agent_visual", "vision_model"})
THUMBNAIL_SIZE = (240, 135)
# A quality decision is reusable only for 24 hours, even if policy/source SHA
# still matches. A new task may not inherit an earlier review. This is a local
# freshness policy, not authentication of the original observation.
VISUAL_REVIEW_TTL = timedelta(hours=24)
_ISO_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z")


def _aware_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or _ISO_TIMESTAMP.fullmatch(value) is None:
        raise ValueError("visual_review_timestamp_invalid_iso_timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("visual_review_timestamp_invalid_iso_timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("visual_review_timestamp_invalid_iso_timezone")
    return parsed.astimezone(timezone.utc)


def validate_visual_review_freshness(reviewed_at: str, *, task_created_at: str | None = None,
                                     now: datetime | None = None) -> None:
    """Require strict zone-aware ISO times, review <= now, and 24h task TTL."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("visual_review_timestamp_clock_timezone_missing")
    now = now.astimezone(timezone.utc)
    reviewed = _aware_timestamp(reviewed_at)
    if reviewed > now:
        raise ValueError("visual_review_timestamp_in_future")
    if now - reviewed > VISUAL_REVIEW_TTL:
        raise ValueError("visual_review_timestamp_expired")
    if task_created_at is not None:
        created = _aware_timestamp(task_created_at)
        if created > now or reviewed < created:
            raise ValueError("visual_review_timestamp_before_task_or_future_task")
        if (reviewed - created > VISUAL_REVIEW_TTL
                or now - created > VISUAL_REVIEW_TTL):
            raise ValueError("visual_review_timestamp_task_expired")


def validate_expected_candidate_count(expected_candidate_count: int | None) -> None:
    if expected_candidate_count is not None and (
            type(expected_candidate_count) is not int or not 1 <= expected_candidate_count <= 20):
        raise ValueError("visual_review_candidate_count_invalid")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy_binding() -> tuple[int, str]:
    path = Path(__file__).resolve().parents[1] / "editorial_policy.json"
    policy = json.loads(path.read_text(encoding="utf-8"))["featured_image_policy"]
    version = policy.get("version")
    if type(version) is not int or version < 1:
        raise ValueError("visual_review_generator_policy_invalid")
    return version, _sha(path)


def _fingerprint(path: Path) -> dict:
    """Measure coarse composition, intentionally excluding quality judgments."""
    with Image.open(path) as opened:
        opened.load()
        if opened.width < 1 or opened.height < 1:
            raise ValueError("visual_review_invalid_image_dimensions")
        fmt = opened.format
        w, h = opened.size
        # Only neutral grayscale blocks: ignore color/typography and detect
        # analogous background/text/card placement across different content.
        small = ImageOps.grayscale(opened).resize((60, 36), Image.Resampling.BILINEAR)
        pixels = small.load()
        cells = []
        for cy in range(6):
            for cx in range(10):
                block = [pixels[x, y] for y in range(cy * 6, cy * 6 + 6)
                         for x in range(cx * 6, cx * 6 + 6)]
                cells.append(round(sum(block) / (36 * 255), 5))
        # Difference hash highlights near pixel-identical or recolored art.
        dh = ImageOps.grayscale(opened).resize((17, 16), Image.Resampling.BILINEAR)
        row = list(dh.get_flattened_data())
        bits = tuple(row[y * 17 + x] > row[y * 17 + x + 1]
                     for y in range(16) for x in range(16))
    return {"sha256": _sha(path), "width": w, "height": h,
            "format": fmt, "layout": cells, "difference_hash": bits}


def _pair_signal(left: dict, right: dict, *, scope: str,
                 left_label: str, right_label: str) -> dict:
    similarity = 1 - sum(abs(a - b) for a, b in zip(left["layout"], right["layout"])) / len(left["layout"])
    hash_similarity = sum(a == b for a, b in zip(left["difference_hash"], right["difference_hash"])) / 256
    identical = left["sha256"] == right["sha256"]
    # A coarse layout often flags unrelated but analogous templates. No hard
    # 'reject' follows from these thresholds; reviewers compare originals.
    flagged = identical or similarity >= 0.88 or hash_similarity >= 0.91
    signal_id = hashlib.sha256((scope + ":" + left["sha256"] + ":" + right["sha256"]).encode()).hexdigest()[:20]
    return {"signal_id": signal_id, "scope": scope,
            "left": left_label, "right": right_label,
            "left_sha256": left["sha256"], "right_sha256": right["sha256"],
            "layout_similarity": round(similarity, 4),
            "difference_hash_similarity": round(hash_similarity, 4),
            "identical_bytes": identical, "requires_visual_comparison": flagged}


def analyze_candidate_diversity(candidate_paths: list[Path | str],
                                recent_paths: list[Path | str] = ()) -> dict:
    """Return evidence-bound repetition hints; never return aesthetic approval."""
    if not candidate_paths:
        raise ValueError("visual_review_candidates_required")
    fingerprints = [_fingerprint(Path(p).resolve(strict=True)) for p in candidate_paths]
    recent = [_fingerprint(Path(p).resolve(strict=True)) for p in recent_paths]
    pairs = []
    for i, left in enumerate(fingerprints):
        for j in range(i + 1, len(fingerprints)):
            pairs.append(_pair_signal(left, fingerprints[j], scope="within_set",
                                      left_label=str(i + 1), right_label=str(j + 1)))
        for j, other in enumerate(recent):
            pairs.append(_pair_signal(left, other, scope="recent_cover",
                                      left_label=str(i + 1), right_label=str(j + 1)))
    return {
        "method": "coarse_grayscale_layout_v1+difference_hash_v1",
        "not_a_quality_verdict": True,
        "recent_comparison": "available" if recent else "unavailable",
        "recent_cover_count": len(recent),
        "candidates": [{k: v for k, v in f.items()
                        if k in {"sha256", "format", "width", "height"}}
                       for f in fingerprints],
        "pair_signals": pairs,
        "review_required": [p["signal_id"] for p in pairs if p["requires_visual_comparison"]],
    }


def _load_manifest(path: Path) -> tuple[dict, list[Path]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("candidates") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("visual_review_manifest_candidates_missing")
    numbers = [r.get("candidate_number") for r in rows if isinstance(r, dict)]
    # A selected-only manifest produced by the legitimate prior transport is
    # allowed, but it cannot claim that unavailable siblings were compared.
    if (len(numbers) != len(rows)
            or any(type(number) is not int or number < 1 for number in numbers)
            or (numbers != list(range(1, len(rows) + 1)) and len(numbers) != 1)):
        raise ValueError("visual_review_manifest_numbering_invalid")
    paths = []
    seen_bytes = set()
    seen_pixels = set()
    for row in rows:
        if (not isinstance(row.get("path"), str)
                or not isinstance(row.get("sha256"), str)):
            raise ValueError("visual_review_manifest_candidate_invalid")
        path = Path(row["path"]).resolve(strict=True)
        original_sha = _sha(path)
        if original_sha != row.get("sha256"):
            raise ValueError("visual_review_candidate_sha_mismatch")
        with Image.open(path) as image:
            if (image.format != row.get("format")
                    or image.width != row.get("width")
                    or image.height != row.get("height")
                    or path.stat().st_size != row.get("bytes")):
                raise ValueError("visual_review_candidate_format_size_mismatch")
            normalized = ImageOps.exif_transpose(image).convert("RGBA")
            pixels_digest = hashlib.sha256(
                f"{normalized.width}x{normalized.height}:RGBA:".encode("ascii")
                + normalized.tobytes()).hexdigest()
        if original_sha in seen_bytes or pixels_digest in seen_pixels:
            raise ValueError("visual_review_duplicate_candidate_content")
        seen_bytes.add(original_sha)
        seen_pixels.add(pixels_digest)
        paths.append(path)
    return data, paths


def validate_candidate_comparison(manifest: Mapping, comparison: object,
                                  *, expected_candidate_count: int | None = None,
                                  selected_candidate: int | None = None) -> None:
    """Compare the claimed review set to the actual SHA-sealed distinct files."""
    validate_expected_candidate_count(expected_candidate_count)
    rows = manifest.get("candidates")
    if not isinstance(rows, list) or not isinstance(comparison, list):
        raise ValueError("visual_review_comparison_invalid")
    if expected_candidate_count is not None:
        if len(rows) != expected_candidate_count or len(comparison) != expected_candidate_count:
            raise ValueError("visual_review_candidate_count_mismatch")
        if [row["candidate_number"] for row in rows] != list(range(1, expected_candidate_count + 1)):
            raise ValueError("visual_review_candidate_count_mismatch")
        if type(selected_candidate) is not int or not 1 <= selected_candidate <= expected_candidate_count:
            raise ValueError("visual_review_candidate_count_mismatch")
    expected = [{"candidate_number": row["candidate_number"], "source_sha256": row["sha256"]}
                for row in rows]
    if comparison != expected:
        raise ValueError("visual_review_comparison_manifest_mismatch")


def prepare_review_template(manifest_path: Path | str,
                            recent_paths: list[Path | str] = ()) -> dict:
    """Produce an *unreviewed* form. Nothing here is a PASS endorsement."""
    path = Path(manifest_path).resolve(strict=True)
    manifest, sources = _load_manifest(path)
    recent = [Path(p).resolve(strict=True) for p in recent_paths]
    analysis = analyze_candidate_diversity(sources, recent)
    policy_version, policy_sha256 = _policy_binding()
    observations = {}
    for row, candidate in zip(manifest["candidates"], analysis["candidates"]):
        observations[str(row["candidate_number"])] = {
            "source_sha256": candidate["sha256"],
            "observed_full_size": False,
            "full_size_observation": "",
            "observed_mobile_thumbnail": False,
            "mobile_observation": "",
            "checks": {name: {"result": "UNVERIFIED", "evidence": ""} for name in CHECKS},
        }
    return {"review_template_version": 1, "manifest_path": str(path),
            "manifest_sha256": _sha(path), "candidate_analysis": analysis,
            "generator_policy_version": policy_version,
            "generator_policy_sha256": policy_sha256,
            "recent_cover_paths": [str(p) for p in recent],
            "candidate_observations": observations,
            "comparison_decisions": {},
            "recent_comparison_note": "" if recent_paths else "Unavailable: no recent covers provided; request/review when available.",
            "review_scope": "actual_originals_and_240x135_mobile_thumbnails",
            "status": "quality_review_pending"}


def save_mobile_previews(template: Mapping, destination: Path | str) -> list[Path]:
    """Write review-only resized previews, never substitutes for originals."""
    source_path = Path(template["manifest_path"]).resolve(strict=True)
    if _sha(source_path) != template["manifest_sha256"]:
        raise ValueError("visual_review_manifest_changed")
    manifest, sources = _load_manifest(source_path)
    folder = Path(destination).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for row, src in zip(manifest["candidates"], sources):
        target = folder / f"candidate-{row['candidate_number']}-mobile-review.png"
        if target.exists():
            raise FileExistsError(str(target))
        with Image.open(src) as im:
            preview = ImageOps.contain(im.convert("RGB"), THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            mobile_canvas = Image.new("RGB", THUMBNAIL_SIZE, "white")
            mobile_canvas.paste(preview, ((THUMBNAIL_SIZE[0] - preview.width) // 2,
                                         (THUMBNAIL_SIZE[1] - preview.height) // 2))
            mobile_canvas.save(target, format="PNG")
        saved.append(target)
    return saved


def finalize_visual_review(template: Mapping, *, staged_path: Path | str,
                           selected_candidate: int, selection_mode: str,
                           task_id: str, review_actor: str, review_method: str,
                           selection_reason: str, reviewed_at: str | None = None,
                           model_result_ref: str | None = None,
                           expected_candidate_count: int | None = None,
                           task_created_at: str | None = None) -> dict:
    """Validate explicit per-image observations; issue P1-compatible receipt.

    A receipt is still reviewer-reported evidence, not independent proof of
    tool invocations. No boolean PASS is generated from similarity metrics.
    """
    if template.get("review_template_version") != 1:
        raise ValueError("visual_review_template_version_invalid")
    path = Path(template["manifest_path"]).resolve(strict=True)
    if _sha(path) != template.get("manifest_sha256"):
        raise ValueError("visual_review_manifest_changed")
    manifest, sources = _load_manifest(path)
    validate_expected_candidate_count(expected_candidate_count)
    if expected_candidate_count is not None and (
            len(manifest["candidates"]) != expected_candidate_count
            or [r["candidate_number"] for r in manifest["candidates"]]
               != list(range(1, expected_candidate_count + 1))):
        raise ValueError("visual_review_candidate_count_mismatch")
    version, policy_sha = _policy_binding()
    if (template.get("generator_policy_version") != version
            or template.get("generator_policy_sha256") != policy_sha):
        raise ValueError("visual_review_generator_policy_changed")
    analysis = template.get("candidate_analysis")
    recent_paths = template.get("recent_cover_paths")
    if (not isinstance(analysis, dict) or not isinstance(recent_paths, list)
            or len(recent_paths) != analysis.get("recent_cover_count")
            or analysis != analyze_candidate_diversity(sources, recent_paths)):
        raise ValueError("visual_review_similarity_evidence_invalid")
    if type(selected_candidate) is not int or selected_candidate not in [r["candidate_number"] for r in manifest["candidates"]]:
        raise ValueError("visual_review_selected_candidate_invalid")
    if expected_candidate_count is not None and selected_candidate > expected_candidate_count:
        raise ValueError("visual_review_candidate_count_mismatch")
    if selection_mode not in {"user", "agent-delegated"}:
        raise ValueError("visual_review_selection_mode_invalid")
    if (review_actor not in REVIEW_ACTORS or review_method not in REVIEW_METHODS
            or (selection_mode == "user" and review_actor == "agent-delegated")
            or (review_method == "vision_model" and not model_result_ref)):
        raise ValueError("visual_review_actor_or_method_invalid")
    if (not isinstance(task_id, str)
            or re.fullmatch(r"[a-zA-Z0-9_.-]{4,120}", task_id) is None
            or not isinstance(selection_reason, str)
            or len(selection_reason.strip()) < 12):
        raise ValueError("visual_review_task_or_selection_reason_missing")
    reviewed_at = reviewed_at or datetime.now(timezone.utc).isoformat()
    validate_visual_review_freshness(reviewed_at, task_created_at=task_created_at)
    observations = template.get("candidate_observations")
    if not isinstance(observations, dict) or set(observations) != {str(row["candidate_number"]) for row in manifest["candidates"]}:
        raise ValueError("visual_review_observations_missing")
    issues = []
    selected_checks = None
    for row in manifest["candidates"]:
        number = row["candidate_number"]
        record = observations[str(number)]
        if not isinstance(record, dict) or record.get("source_sha256") != row["sha256"]:
            raise ValueError("visual_review_observation_sha_mismatch")
        if (record.get("observed_full_size") is not True
                or record.get("observed_mobile_thumbnail") is not True
                or not isinstance(record.get("full_size_observation"), str)
                or len(record["full_size_observation"].strip()) < 12
                or not isinstance(record.get("mobile_observation"), str)
                or len(record["mobile_observation"].strip()) < 12):
            raise ValueError("visual_review_actual_views_not_documented")
        check_map = record.get("checks")
        if not isinstance(check_map, dict) or set(check_map) != set(CHECKS):
            raise ValueError("visual_review_six_checks_missing")
        for check, decision in check_map.items():
            if (not isinstance(decision, dict) or decision.get("result") not in REVIEW_RESULTS
                    or not isinstance(decision.get("evidence"), str)
                    or len(decision["evidence"].strip()) < 12):
                raise ValueError("visual_review_check_evidence_missing")
            if decision["result"] != "PASS" and number == selected_candidate:
                issues.append(f"candidate_{number}:{check}:{decision['result']}")
            elif decision["result"] == "UNVERIFIED":
                issues.append(f"candidate_{number}:{check}:UNVERIFIED")
        if number == selected_candidate:
            selected_checks = {check: decision["result"] == "PASS" for check, decision in check_map.items()}
    signals = analysis["pair_signals"]
    flagged = [s["signal_id"] for s in signals if s["requires_visual_comparison"]]
    decisions = template.get("comparison_decisions")
    if not isinstance(decisions, dict) or any(k not in flagged for k in decisions):
        raise ValueError("visual_review_comparison_decisions_invalid")
    for key in flagged:
        evidence = decisions.get(key)
        if (not isinstance(evidence, dict)
                or type(evidence.get("accepted_distinct")) is not bool
                or not isinstance(evidence.get("reason"), str)
                or len(evidence["reason"].strip()) < 15):
            raise ValueError("visual_review_flagged_pair_unreviewed")
        if evidence["accepted_distinct"] and any(
                s["signal_id"] == key and s["identical_bytes"] for s in signals):
            raise ValueError("visual_review_identical_candidate_not_distinct")
        if not evidence["accepted_distinct"] and any(
                s["signal_id"] == key and s["left"] == str(selected_candidate) for s in signals):
            issues.append("selected_candidate_repeats_existing_layout:" + key)
        if not evidence["accepted_distinct"] and any(
                s["signal_id"] == key and s["right"] == str(selected_candidate)
                and s["scope"] == "within_set" for s in signals):
            issues.append("selected_candidate_repeats_other_candidate:" + key)
    staged = Path(staged_path).resolve(strict=True)
    with Image.open(staged) as image:
        image.load()
        stage_info = {"format": image.format, "width": image.width, "height": image.height}
    if (stage_info["width"], stage_info["height"]) != (1200, 675):
        raise ValueError("visual_review_stage_dimensions_invalid")
    selected_source = next(p for r, p in zip(manifest["candidates"], sources)
                           if r["candidate_number"] == selected_candidate)
    # Match the existing canonical stage receipt, not merely a caller's SHA
    # string. The upload path still independently checks lineage and CAS.
    try:
        stage = json.loads(staged.with_suffix(staged.suffix + ".stage.json").read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ValueError("visual_review_stage_receipt_missing") from exc
    required_stage = {
        "source_path": str(selected_source),
        "source_sha256": _sha(selected_source),
        "output_path": str(staged),
        "output_sha256": _sha(staged),
        "candidate_manifest": str(path),
        "candidate_number": selected_candidate,
        "selection_mode": selection_mode,
        "sealed_source_sha256": _sha(selected_source),
    }
    if (not isinstance(stage, dict)
            or any(stage.get(key) != value for key, value in required_stage.items())
            or (stage.get("selection_actor") is not None and stage.get("selection_actor") != selection_mode)):
        raise ValueError("visual_review_stage_receipt_binding_invalid")
    status = "pass" if not issues else "reject" if any("REJECT" in i or "repeats" in i for i in issues) else "unverified"
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "generator_policy_version": version,
        "source_sha256": _sha(selected_source),
        "staged_sha256": _sha(staged),
        "source_image": {k: v for k, v in _fingerprint(selected_source).items() if k in {"sha256", "width", "height", "format"}},
        "staged_image": stage_info,
        "selected_candidate": selected_candidate,
        "selection_mode": selection_mode,
        "review_actor": review_actor,
        "review_method": review_method,
        "reviewed_at": reviewed_at,
        "review_result": status,
        "issues": issues,
        "checks": selected_checks,
        "comparison_set": [{"candidate_number": r["candidate_number"], "source_sha256": r["sha256"]}
                           for r in manifest["candidates"]],
        "selection_reason": selection_reason,
        "review_evidence": {"candidate_observations": observations,
                            "similarity_analysis": analysis,
                            "comparison_decisions": decisions,
                            "recent_cover_paths": recent_paths,
                            "manifest_sha256": _sha(path),
                            "generator_policy_sha256": policy_sha,
                            "recent_comparison_note": template.get("recent_comparison_note")},
    }
    if review_method == "vision_model":
        receipt["model_result_ref"] = model_result_ref
    return receipt


def verify_visual_review_evidence(receipt: Mapping, *, manifest_path: Path | str,
                                  staged_path: Path | str,
                                  expected_candidate_count: int | None = None,
                                  task_created_at: str | None = None) -> dict:
    """Revalidate source/stage/observations against independently read files.

    This detects stale files, changed receipts and unsupported PASS claims. It
    does *not* authenticate a reviewer's identity or external visual session.
    """
    if not isinstance(receipt, Mapping) or receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("visual_review_receipt_schema_invalid")
    validate_visual_review_freshness(receipt.get("reviewed_at"), task_created_at=task_created_at)
    validate_expected_candidate_count(expected_candidate_count)
    evidence = receipt.get("review_evidence")
    if not isinstance(evidence, dict):
        raise ValueError("visual_review_observation_evidence_missing")
    manifest, _ = _load_manifest(Path(manifest_path).resolve(strict=True))
    validate_candidate_comparison(
        manifest, receipt.get("comparison_set"),
        expected_candidate_count=expected_candidate_count,
        selected_candidate=receipt.get("selected_candidate"))
    template = prepare_review_template(manifest_path, evidence.get("recent_cover_paths", []))
    if (evidence.get("manifest_sha256") != template["manifest_sha256"]
            or evidence.get("generator_policy_sha256") != template["generator_policy_sha256"]
            or evidence.get("similarity_analysis") != template["candidate_analysis"]):
        raise ValueError("visual_review_receipt_evidence_binding_invalid")
    template["candidate_observations"] = evidence.get("candidate_observations")
    template["comparison_decisions"] = evidence.get("comparison_decisions")
    template["recent_comparison_note"] = evidence.get("recent_comparison_note")
    rebuilt = finalize_visual_review(
        template, staged_path=staged_path,
        selected_candidate=receipt.get("selected_candidate"),
        selection_mode=receipt.get("selection_mode"),
        task_id=receipt.get("task_id"),
        review_actor=receipt.get("review_actor"),
        review_method=receipt.get("review_method"),
        selection_reason=receipt.get("selection_reason"),
        reviewed_at=receipt.get("reviewed_at"),
        model_result_ref=receipt.get("model_result_ref"),
        expected_candidate_count=expected_candidate_count,
        task_created_at=task_created_at)
    if dict(receipt) != rebuilt:
        raise ValueError("visual_review_receipt_tampered_or_stale")
    return {"status": rebuilt["review_result"],
            "source_sha256": rebuilt["source_sha256"],
            "staged_sha256": rebuilt["staged_sha256"],
            "reviewed_candidate_count": len(rebuilt["comparison_set"])}
