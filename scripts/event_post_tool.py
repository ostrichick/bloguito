#!/usr/bin/env python3
"""Reusable event-post validation, image normalization and local visual QA.

This replaces per-post scratch scripts for the deterministic parts of monthly
event roundup work.  It deliberately does not guess image rights or factual
claims: the operator supplies reviewed provenance in the image manifest and the
editorial bundle remains the source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent-publisher"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from agents.editorial import render, validate_bundle
from agents.event_post_standard import validate_event_post_standard
from agents.validation_router import build_event_candidate_validation_plan
from agents.validation_runner import run_validation_plan, selected_test_files


TARGET_SIZE = (1200, 675)
IMAGE_RIGHTS = {"generated_original", "site_owned", "open_license", "permission_granted"}


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("json_object_required")
    return payload


def validate_event_candidate(
    bundle: dict,
    *,
    run_tests: bool = False,
    target_status: str = "draft",
    post_id: int | None = None,
    expected_content_sha256: str | None = None,
) -> dict:
    """Run deterministic bundle checks and one targeted event regression plan."""
    editorial = validate_bundle(
        bundle,
        {"checked_on": "", "posts": []},
        scopes={"content", "source"},
    )
    event_reasons = validate_event_post_standard(bundle)
    plan = build_event_candidate_validation_plan(
        bundle,
        target_status=target_status,
        post_id=post_id,
        expected_content_sha256=expected_content_sha256,
    )
    selected = selected_test_files(plan)
    validation = run_validation_plan(plan) if run_tests else None
    tests_ok = validation is None or validation.get("status") == "passed"
    return {
        "status": "ready" if editorial.get("status") == "ready" and not event_reasons and tests_ok else "blocked",
        "editorial": editorial,
        "event_standard_reasons": event_reasons,
        "validation_plan": plan,
        "selected_test_files": selected,
        "validation": validation,
    }


def _safe_image_name(value: str, index: int) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", (value or "").strip()).strip("-").lower()
    return value or f"event-{index:02d}"


def prepare_event_images(manifest_path: Path, output_dir: Path) -> dict:
    """Normalize reviewed local candidates to stable 1200x675 WebP assets."""
    manifest = _load_json(manifest_path)
    items = manifest.get("images")
    if manifest.get("version") != 1 or not isinstance(items, list) or not items:
        raise ValueError("event_image_manifest_invalid")
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    previews = []
    seen_names = set()
    resampling = getattr(Image, "Resampling", Image).LANCZOS

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError("event_image_manifest_item_invalid")
        required = ("name", "event_name", "source_url", "source_year", "rights", "depiction")
        if any(not item.get(key) for key in required):
            raise ValueError("event_image_manifest_provenance_required")
        has_local = bool(item.get("input"))
        has_remote = bool(item.get("download_url"))
        if has_local == has_remote:
            raise ValueError("event_image_input_or_download_url_required")
        if not str(item["source_url"]).startswith("https://"):
            raise ValueError("event_image_source_https_required")
        if has_remote and not str(item["download_url"]).startswith("https://"):
            raise ValueError("event_image_download_https_required")
        try:
            source_year = int(item["source_year"])
        except (TypeError, ValueError) as exc:
            raise ValueError("event_image_source_year_invalid") from exc
        if not 2000 <= source_year <= 2100:
            raise ValueError("event_image_source_year_invalid")
        rights = str(item["rights"]).strip()
        rights_url = str(item.get("rights_url") or "").strip() or None
        if rights not in IMAGE_RIGHTS:
            raise ValueError("event_image_rights_invalid")
        if rights in {"open_license", "permission_granted"} and (
                rights_url is None or not rights_url.startswith("https://")):
            raise ValueError("event_image_rights_url_required")

        name = _safe_image_name(str(item["name"]), index)
        if name in seen_names:
            raise ValueError("event_image_name_duplicate")
        seen_names.add(name)
        destination = output_dir / f"{name}.webp"
        try:
            if has_local:
                source = Path(str(item["input"]))
                if not source.is_absolute():
                    source = (manifest_path.parent / source).resolve()
                if not source.is_file():
                    raise ValueError("event_image_input_missing:" + str(source))
                image_context = Image.open(source)
            else:
                request = urllib.request.Request(
                    str(item["download_url"]),
                    headers={"User-Agent": "Mozilla/5.0 BloguitoEditorial/1.0"},
                )
                with urllib.request.urlopen(request, timeout=20) as response:
                    image_context = Image.open(io.BytesIO(response.read()))
            with image_context as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                normalized = ImageOps.fit(image, TARGET_SIZE, method=resampling, centering=(0.5, 0.5))
                normalized.save(destination, "WEBP", quality=88, method=6)
        except Exception as exc:
            raise ValueError("event_image_decode_failed:" + name) from exc
        sha = hashlib.sha256(destination.read_bytes()).hexdigest()
        results.append({
            "name": name,
            "event_name": str(item["event_name"]).strip(),
            "path": str(destination),
            "width": TARGET_SIZE[0],
            "height": TARGET_SIZE[1],
            "sha256": sha,
            "source_url": str(item["source_url"]).strip(),
            "source_year": source_year,
            "rights": rights,
            "rights_url": rights_url,
            "license_label": str(item.get("license_label") or "").strip() or None,
            "depiction": str(item["depiction"]).strip(),
            "download_url": str(item.get("download_url") or "").strip() or None,
        })
        with Image.open(destination) as preview:
            previews.append(preview.convert("RGB").copy())

    thumb_size = (600, 338)
    cols = 2
    rows = (len(previews) + cols - 1) // cols
    sheet = Image.new("RGB", (thumb_size[0] * cols, thumb_size[1] * rows), "white")
    for index, preview in enumerate(previews):
        thumb = ImageOps.fit(preview, thumb_size, method=resampling)
        x = (index % cols) * thumb_size[0]
        y = (index // cols) * thumb_size[1]
        sheet.paste(thumb, (x, y))
    contact = output_dir / "contact-sheet.jpg"
    sheet.save(contact, "JPEG", quality=88)
    report = {"version": 1, "images": results, "contact_sheet": str(contact)}
    (output_dir / "images.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def qa_event_bundle(bundle: dict, html_out: Path | None = None) -> dict:
    """Produce stable structural QA plus an optional browser-ready local HTML file."""
    body = render(bundle["plan"], bundle["sources"])
    sections = [
        section for section in (bundle.get("plan", {}).get("sections") or [])
        if isinstance(section, dict) and section.get("event_name")
    ]
    expected = len(sections)
    expected_addresses = sum(
        1 for section in sections
        if isinstance(section.get("location"), dict)
        and str(section["location"].get("address") or "").strip()
        and str(section["location"].get("address") or "").strip().casefold()
        != str(section["location"].get("venue") or "").strip().casefold()
    )
    checks = {
        "event_standard": not validate_event_post_standard(bundle),
        "mobile_overview": 'class="bloguito-overview-mobile"' in body,
        "desktop_overview": "bloguito-overview-desktop" in body,
        "event_image_count": body.count('class="bloguito-event-image"') == expected,
        "location_card_count": body.count('class="festival-location-card"') == expected,
        "location_heading_count": body.count("📍 행사장 위치:") == expected,
        "address_line_count": body.count("<strong>주소</strong>:") == expected_addresses,
    }
    if html_out is not None:
        html_out.parent.mkdir(parents=True, exist_ok=True)
        html_out.write_text(
            "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Event post QA</title><style>body{margin:0;background:#fff}"
            ".qa-shell{max-width:820px;margin:0 auto;padding:24px 16px;box-sizing:border-box}"
            "img{max-width:100%;height:auto}</style></head><body><main class=\"qa-shell\">"
            + body + "</main></body></html>",
            encoding="utf-8",
        )
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "detailed_event_sections": expected,
        "rendered_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "html": str(html_out) if html_out is not None else None,
    }


def _find_browser() -> Path | None:
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for command in ("msedge", "chrome", "chromium"):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))
    return next((path for path in candidates if str(path) and path.is_file()), None)


def capture_qa_screenshots(html_path: Path, output_dir: Path) -> dict:
    """Capture exactly one desktop and one mobile local render with a headless browser."""
    browser = _find_browser()
    if browser is None:
        raise ValueError("qa_browser_not_found")
    output_dir.mkdir(parents=True, exist_ok=True)
    uri = html_path.resolve().as_uri()
    outputs = {}
    for name, width, height in (("desktop", 1440, 1000), ("mobile", 500, 950)):
        target = (output_dir / f"{name}.png").resolve()
        command = [
            str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            f"--window-size={width},{height}", f"--screenshot={target}", uri,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
            raise ValueError("qa_screenshot_failed:" + name)
        outputs[name] = str(target)
    return outputs


def _write_output(payload: dict, output: Path | None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)

    validate = sub.add_parser("validate", help="validate one complete event-post candidate")
    validate.add_argument("bundle", type=Path)
    validate.add_argument("--run-tests", action="store_true")
    validate.add_argument("--target-status", choices=["draft", "publish"], default="draft")
    validate.add_argument("--post-id", type=int)
    validate.add_argument("--expected-content-sha256")
    validate.add_argument("--output", type=Path)

    images = sub.add_parser("images", help="normalize reviewed local event images from one manifest")
    images.add_argument("manifest", type=Path)
    images.add_argument("--output-dir", type=Path, required=True)
    images.add_argument("--output", type=Path)

    qa = sub.add_parser("qa", help="run structural QA and optionally capture two screenshots")
    qa.add_argument("bundle", type=Path)
    qa.add_argument("--html-out", type=Path, required=True)
    qa.add_argument("--screenshot-dir", type=Path)
    qa.add_argument("--output", type=Path)

    args = parser.parse_args(argv)
    if args.action == "validate":
        payload = validate_event_candidate(
            _load_json(args.bundle),
            run_tests=args.run_tests,
            target_status=args.target_status,
            post_id=args.post_id,
            expected_content_sha256=args.expected_content_sha256,
        )
        _write_output(payload, args.output)
        return 0 if payload["status"] == "ready" else 1
    if args.action == "images":
        payload = prepare_event_images(args.manifest, args.output_dir)
        _write_output(payload, args.output)
        return 0

    payload = qa_event_bundle(_load_json(args.bundle), args.html_out)
    if args.screenshot_dir and payload["status"] == "passed":
        payload["screenshots"] = capture_qa_screenshots(args.html_out, args.screenshot_dir)
    _write_output(payload, args.output)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
