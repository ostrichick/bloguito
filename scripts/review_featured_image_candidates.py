"""Prepare, record and verify real visual observations of sealed candidates.

Prepare writes an UNVERIFIED checklist and small display-only previews. A
reviewer must open the full originals and previews, then fill every observation
and pair-comparison decision. Finalize cannot infer an aesthetic PASS.

Examples:
  python scripts/review_featured_image_candidates.py prepare --manifest PATH --output review-template.json --preview-dir review-previews
  python scripts/review_featured_image_candidates.py finalize --template review-template.json --staged PATH --selected-candidate 1 --selection-mode user --task-id post123-image --review-actor user --review-method human_visual --selection-reason "I inspected the subject and compared all candidates" --output visual-review.json
  python scripts/review_featured_image_candidates.py verify --receipt visual-review.json --manifest PATH --staged PATH
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent-publisher"))
from agents.featured_image_quality_review import (  # noqa: E402
    finalize_visual_review, prepare_review_template, save_mobile_previews,
    verify_visual_review_evidence,
)


def _write_unique(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    prepare = commands.add_parser("prepare", help="Create unreviewed evidence checklist")
    prepare.add_argument("--manifest", required=True, type=Path)
    prepare.add_argument("--recent", type=Path, action="append", default=[], help="Repeat for recent cover originals")
    prepare.add_argument("--preview-dir", type=Path, help="Display-only 240x135 PNGs; never upload")
    prepare.add_argument("--output", type=Path, required=True)

    finalize = commands.add_parser("finalize", help="Validate filled human/model observations")
    finalize.add_argument("--template", type=Path, required=True)
    finalize.add_argument("--staged", type=Path, required=True)
    finalize.add_argument("--selected-candidate", type=int, required=True)
    finalize.add_argument("--selection-mode", choices=["user", "agent-delegated"], required=True)
    finalize.add_argument("--task-id", required=True)
    finalize.add_argument("--review-actor", choices=["user", "agent-delegated", "independent-reviewer"], required=True)
    finalize.add_argument("--review-method", choices=["human_visual", "direct_agent_visual", "vision_model"], required=True)
    finalize.add_argument("--model-result-ref")
    finalize.add_argument("--selection-reason", required=True)
    finalize.add_argument("--output", type=Path, required=True)

    verify = commands.add_parser("verify", help="Recheck receipt against current source/stage")
    verify.add_argument("--receipt", required=True, type=Path)
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--staged", required=True, type=Path)
    args = parser.parse_args()

    if args.action == "prepare":
        template = prepare_review_template(args.manifest, args.recent)
        if args.preview_dir:
            save_mobile_previews(template, args.preview_dir)
        _write_unique(args.output, template)
        print(json.dumps({"status": "quality_review_pending",
                          "candidates": len(template["candidate_observations"]),
                          "repetition_signals": len(template["candidate_analysis"]["review_required"]),
                          "template": str(args.output.resolve())}, ensure_ascii=False))
        return 0
    if args.action == "finalize":
        template = json.loads(args.template.read_text(encoding="utf-8"))
        receipt = finalize_visual_review(
            template, staged_path=args.staged,
            selected_candidate=args.selected_candidate,
            selection_mode=args.selection_mode, task_id=args.task_id,
            review_actor=args.review_actor, review_method=args.review_method,
            selection_reason=args.selection_reason,
            model_result_ref=args.model_result_ref)
        _write_unique(args.output, receipt)
        print(json.dumps({"status": receipt["review_result"], "issues": receipt["issues"],
                          "receipt": str(args.output.resolve())}, ensure_ascii=False))
        return 0 if receipt["review_result"] == "pass" else 2
    if args.action == "verify":
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        result = verify_visual_review_evidence(
            receipt, manifest_path=args.manifest, staged_path=args.staged)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "pass" else 2
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "quality_review_failed", "reason": str(error)},
                         ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
