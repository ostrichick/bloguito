"""Private, read-only Microsoft Clarity Data Export API snapshot collector.

Runs only after the project owner has installed a token in a private file.
The Clarity API returns rolling 24/48/72-hour windows, not calendar-day data.
Do not sum overlapping snapshots or interpret dashboard metrics as GA4 data.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo


ENDPOINT = "https://www.clarity.ms/export-data/api/v1/project-live-insights"
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = BASE_DIR / "data" / "clarity"
VIEWS = {"summary": None, "device": "Device", "url": "URL"}
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class ClarityError(Exception):
    """Safe diagnostic code; never include a token or raw HTTP response."""


class BlockRedirects(HTTPRedirectHandler):
    """Do not forward a bearer credential to a redirected destination."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def load_token(token_file):
    path = Path(token_file)
    if path.is_symlink() or not path.is_file():
        raise ClarityError("token_file_unavailable")
    details = path.stat()
    if os.name == "posix" and (stat.S_IMODE(details.st_mode) != 0o600):
        raise ClarityError("token_file_permissions_must_be_0600")
    if not 1 <= details.st_size <= 8192:
        raise ClarityError("token_file_invalid_size")
    try:
        token = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise ClarityError("token_file_unreadable") from None
    if not token or any(char.isspace() for char in token):
        raise ClarityError("token_file_invalid_format")
    return token


def request_export(token, days, dimension):
    params = {"numOfDays": str(days)}
    if dimension is not None:
        params["dimension1"] = dimension
    request = Request(
        ENDPOINT + "?" + urlencode(params),
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with build_opener(BlockRedirects()).open(request, timeout=30) as response:
            if response.status != 200 or response.geturl().split("?", 1)[0] != ENDPOINT:
                raise ClarityError("unexpected_response_or_redirect")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise ClarityError("clarity_http_" + str(exc.code)) from None
    except (URLError, TimeoutError, OSError):
        raise ClarityError("clarity_request_failed") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ClarityError("clarity_response_too_large")
    try:
        return json.loads(raw)
    except (UnicodeError, ValueError):
        raise ClarityError("clarity_response_invalid_json") from None


def validate_response(value):
    if not isinstance(value, list):
        raise ClarityError("clarity_response_not_a_metric_list")
    for metric in value:
        if (not isinstance(metric, dict)
                or not isinstance(metric.get("metricName"), str)
                or not isinstance(metric.get("information"), list)):
            raise ClarityError("clarity_metric_invalid")
        if len(metric["information"]) > 1000 or not all(
            isinstance(item, dict) for item in metric["information"]
        ):
            raise ClarityError("clarity_metric_rows_invalid")
    return value


def collect(token, days=1, *, views=("summary", "device", "url"),
            requester=request_export, now=None):
    if days not in (1, 2, 3):
        raise ClarityError("invalid_days")
    if not views or len(set(views)) != len(views) or any(view not in VIEWS for view in views):
        raise ClarityError("invalid_views")
    results = {}
    for view in views:
        results[view] = validate_response(requester(token, days, VIEWS[view]))
    timestamp = now or datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "source": "Microsoft Clarity Data Export API",
        "collected_at_utc": timestamp.astimezone(timezone.utc).isoformat(),
        "window": {"type": "rolling", "hours": 24 * days, "api_timezone": "UTC"},
        "views": results,
        "limitations": [
            "Rolling windows may overlap across snapshots; do not sum them blindly.",
            "Clarity metrics differ from GA4 sessions and WordPress visitors.",
            "API responses are limited to 1000 rows per request; no pagination.",
        ],
    }


def private_directory(path):
    path = Path(path)
    if path.is_symlink():
        raise ClarityError("output_directory_symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise ClarityError("output_directory_permissions_must_be_0700")
    return path


def snapshot_path(output_dir, *, now=None):
    timestamp = now or datetime.now(timezone.utc)
    kst_date = timestamp.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    return Path(output_dir) / ("clarity-" + kst_date + ".json")


def existing_snapshot_matches(target, days, views):
    if target.is_symlink():
        raise ClarityError("output_target_symlink")
    if not target.exists():
        return False
    try:
        existing = json.loads(target.read_text(encoding="utf-8"))
        if (existing.get("schema_version") != 1
                or existing.get("window", {}).get("hours") != 24 * days
                or set(existing.get("views", {})) != set(views)):
            raise ClarityError("snapshot_scope_conflict")
        for payload in existing["views"].values():
            validate_response(payload)
    except (OSError, UnicodeError, ValueError, AttributeError, TypeError, KeyError):
        raise ClarityError("snapshot_invalid_existing_file") from None
    return True


def save_snapshot(snapshot, output_dir, *, now=None):
    directory = private_directory(output_dir)
    target = snapshot_path(directory, now=now)
    if target.is_symlink():
        raise ClarityError("output_target_symlink")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=directory, prefix=".clarity-", suffix=".tmp",
            delete=False,
        ) as handle:
            tmp = Path(handle.name)
            os.chmod(tmp, 0o600)
            json.dump(snapshot, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp, target)  # Atomic create; never replace a completed day's snapshot.
        except FileExistsError:
            raise ClarityError("snapshot_already_exists") from None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return target


def main(argv=None, *, requester=request_export):
    parser = argparse.ArgumentParser(description="Private Microsoft Clarity rolling snapshot")
    parser.add_argument("--token-file", type=Path,
                        default=Path(os.environ["BLOGUITO_CLARITY_TOKEN_FILE"])
                        if os.getenv("BLOGUITO_CLARITY_TOKEN_FILE") else None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--days", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--view", action="append", choices=tuple(VIEWS))
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    views = tuple(args.view) if args.view else ("summary", "device", "url")
    try:
        directory = private_directory(args.output_dir)
        if existing_snapshot_matches(snapshot_path(directory, now=now), args.days, views):
            print("clarity_collection_skipped:snapshot_already_exists")
            return 0
        if args.token_file is None:
            raise ClarityError("token_file_not_configured")
        token = load_token(args.token_file)
        snapshot = collect(token, args.days, views=views, requester=requester, now=now)
        destination = save_snapshot(snapshot, directory, now=now)
    except (ClarityError, OSError) as exc:
        code = str(exc) if isinstance(exc, ClarityError) else "filesystem_failure"
        print("clarity_collection_failed:" + code, file=sys.stderr)
        return 1
    print("clarity_collection_ok file=" + destination.name + " views=" + str(len(views)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
