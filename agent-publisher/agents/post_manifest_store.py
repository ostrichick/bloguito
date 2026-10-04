"""Per-post reviewed manifest storage with legacy index compatibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 1
SCHEMA_DIR = "post_manifests"
SCHEMA_FILE = "schema.json"


@contextmanager
def editorial_lock(root: Path | str) -> Iterator[Path]:
    """Hold the single editorial mutation lock and fail closed on stale locks."""
    lock = acquire_editorial_lock(root)
    try:
        yield lock
    finally:
        release_editorial_lock(lock)


def acquire_editorial_lock(root: Path | str) -> Path:
    """Acquire the shared editorial mutation lock without hiding stale locks."""
    lock = Path(root) / "data" / ".editorial-publish.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ValueError("editorial_publication_busy: inspect the existing job") from exc
    return lock


def release_editorial_lock(lock: Path | str) -> None:
    Path(lock).rmdir()


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_write_bytes(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    try:
        os.chmod(temporary, mode)
    except OSError:
        pass
    temporary.replace(path)
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def atomic_write_json(path: Path | str, payload: Any, *, mode: int = 0o600) -> None:
    _atomic_write_bytes(Path(path), _json_bytes(payload), mode=mode)


def schema_path(index_path: Path | str) -> Path:
    return Path(index_path).parent / SCHEMA_DIR / SCHEMA_FILE


def _manifest_path(index_path: Path, post_id: int, digest: str) -> Path:
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("invalid_post_manifest_digest")
    return index_path.parent / SCHEMA_DIR / f"post-{int(post_id)}-{digest[:20]}.json"


def storage_enabled(index_path: Path | str) -> bool:
    marker = schema_path(index_path)
    if not marker.is_file():
        return False
    payload = json.loads(marker.read_text(encoding="utf-8"))
    if payload != {"version": SCHEMA_VERSION}:
        raise ValueError("invalid_post_manifest_schema")
    return True


def activate_storage(data_dir: Path | str) -> Path:
    data_dir = Path(data_dir)
    marker = data_dir / SCHEMA_DIR / SCHEMA_FILE
    if marker.exists():
        if json.loads(marker.read_text(encoding="utf-8")) != {"version": SCHEMA_VERSION}:
            raise ValueError("invalid_post_manifest_schema")
        return marker
    atomic_write_json(marker, {"version": SCHEMA_VERSION})
    return marker


def _load_index(index_path: Path) -> tuple[str, list[dict]]:
    raw = index_path.read_text(encoding="utf-8")
    rows = json.loads(raw)
    if not isinstance(rows, list):
        raise ValueError("invalid_editorial_index")
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, dict) or not str(row.get("id", "")).isdigit():
            raise ValueError("invalid_editorial_index")
        post_id = int(row["id"])
        if post_id in seen:
            raise ValueError("duplicate_editorial_index_id")
        seen.add(post_id)
    return raw, rows


def _record_digest(record: dict) -> str:
    return hashlib.sha256(_json_bytes(record)).hexdigest()


def _compact_row(record: dict, digest: str) -> dict:
    compact = {key: value for key, value in record.items() if key != "fact_manifest"}
    compact["manifest_sha256"] = digest
    return compact


def _load_manifest(index_path: Path, row: dict) -> tuple[dict, bytes]:
    expected = row.get("manifest_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("invalid_post_manifest_digest")
    path = _manifest_path(index_path, int(row["id"]), expected)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("post_manifest_digest_mismatch")
    record = json.loads(raw.decode("utf-8"))
    if not isinstance(record, dict) or int(record.get("id", -1)) != int(row["id"]):
        raise ValueError("invalid_post_manifest")
    for key, value in row.items():
        if key == "manifest_sha256":
            continue
        if record.get(key) != value:
            raise ValueError("post_manifest_index_mismatch")
    if not isinstance(record.get("fact_manifest"), dict):
        raise ValueError("reviewed_editorial_manifest_required")
    return record, raw


def _target_token(row: dict, manifest_raw: bytes | None) -> str:
    payload = {
        "row": row,
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest() if manifest_raw is not None else None,
    }
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class StateSnapshot:
    index_path: Path
    post_id: int
    record: dict
    row: dict
    mode: str
    index_raw: str
    target_token: str


def load_record(index_path: Path | str, post_id: int) -> StateSnapshot | None:
    index = Path(index_path)
    raw, rows = _load_index(index)
    matches = [row for row in rows if int(row.get("id", -1)) == int(post_id)]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("duplicate_editorial_index_id")
    row = matches[0]
    if "manifest_sha256" not in row:
        record = dict(row)
        token = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return StateSnapshot(index, int(post_id), record, dict(row), "inline", raw, token)
    if not storage_enabled(index):
        raise ValueError("post_manifest_schema_required")
    record, manifest_raw = _load_manifest(index, row)
    return StateSnapshot(
        index, int(post_id), record, dict(row), "per-post", raw,
        _target_token(row, manifest_raw),
    )


def load_records(index_path: Path | str) -> list[dict]:
    index = Path(index_path)
    _raw, rows = _load_index(index)
    result = []
    enabled = storage_enabled(index)
    for row in rows:
        if "manifest_sha256" not in row:
            result.append(dict(row))
        else:
            if not enabled:
                raise ValueError("post_manifest_schema_required")
            record, _manifest_raw = _load_manifest(index, row)
            result.append(record)
    return result


def assert_unchanged(snapshot: StateSnapshot) -> None:
    if snapshot.mode == "inline":
        current = snapshot.index_path.read_text(encoding="utf-8")
        if hashlib.sha256(current.encode("utf-8")).hexdigest() != snapshot.target_token:
            raise ValueError("editorial_index_changed")
        return
    current = load_record(snapshot.index_path, snapshot.post_id)
    if current is None or current.target_token != snapshot.target_token:
        raise ValueError("editorial_manifest_changed")


def _write_manifest(index_path: Path, record: dict) -> str:
    raw = _json_bytes(record)
    digest = hashlib.sha256(raw).hexdigest()
    path = _manifest_path(index_path, int(record["id"]), digest)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("post_manifest_collision")
    else:
        _atomic_write_bytes(path, raw)
    return digest


def _replace_row(rows: list[dict], post_id: int, new_row: dict) -> list[dict]:
    result = []
    replaced = False
    for row in rows:
        if int(row.get("id", -1)) == int(post_id):
            if replaced:
                raise ValueError("duplicate_editorial_index_id")
            result.append(new_row)
            replaced = True
        else:
            result.append(row)
    if not replaced:
        raise ValueError("reviewed_post_manifest_required")
    return result


def replace_record(snapshot: StateSnapshot, record: dict) -> None:
    if int(record.get("id", -1)) != snapshot.post_id or not isinstance(record.get("fact_manifest"), dict):
        raise ValueError("invalid_editorial_record")
    assert_unchanged(snapshot)
    if not storage_enabled(snapshot.index_path):
        rows = json.loads(snapshot.index_raw)
        atomic_write_json(snapshot.index_path, _replace_row(rows, snapshot.post_id, record))
        return
    # Manifest first, then index pointer. A crash before the index swap leaves the
    # old inline/compact row authoritative; the sidecar is safe to overwrite later.
    digest = _write_manifest(snapshot.index_path, record)
    _raw, latest_rows = _load_index(snapshot.index_path)
    if snapshot.mode == "per-post":
        current = load_record(snapshot.index_path, snapshot.post_id)
        if current is None or current.target_token != snapshot.target_token:
            raise ValueError("editorial_manifest_changed")
    else:
        current_row = next(row for row in latest_rows if int(row.get("id", -1)) == snapshot.post_id)
        if current_row != snapshot.row:
            raise ValueError("editorial_index_changed")
    atomic_write_json(snapshot.index_path, _replace_row(
        latest_rows, snapshot.post_id, _compact_row(record, digest)))


def upsert_record(index_path: Path | str, record: dict) -> None:
    index = Path(index_path)
    if not isinstance(record, dict) or not str(record.get("id", "")).isdigit():
        raise ValueError("invalid_editorial_record")
    post_id = int(record["id"])
    raw, rows = _load_index(index) if index.exists() else ("[]", [])
    reviewed = isinstance(record.get("fact_manifest"), dict)
    if not storage_enabled(index) or not reviewed:
        rows = [row for row in rows if int(row.get("id", -1)) != post_id]
        rows.append(record)
        atomic_write_json(index, rows)
        return
    digest = _write_manifest(index, record)
    rows = [row for row in rows if int(row.get("id", -1)) != post_id]
    rows.append(_compact_row(record, digest))
    atomic_write_json(index, rows)


def remove_record(index_path: Path | str, post_id: int) -> bool:
    index = Path(index_path)
    if not index.exists():
        return False
    raw, rows = _load_index(index)
    remaining = [row for row in rows if int(row.get("id", -1)) != int(post_id)]
    if len(remaining) == len(rows):
        return False
    atomic_write_json(index, remaining)
    return True


def move_record(snapshot: StateSnapshot, target_index: Path | str, record: dict) -> None:
    """Move one unchanged reviewed record between indexes with exact-byte rollback.

    The source snapshot is the CAS token.  A crash may leave an unreferenced
    manifest sidecar, but the two authoritative index files are restored exactly
    on any failure.
    """
    target = Path(target_index)
    if target.resolve() == snapshot.index_path.resolve():
        raise ValueError("editorial_index_move_requires_distinct_target")
    if int(record.get("id", -1)) != snapshot.post_id:
        raise ValueError("invalid_editorial_record")
    assert_unchanged(snapshot)
    source_raw = snapshot.index_path.read_bytes()
    target_raw = target.read_bytes() if target.exists() else None
    try:
        upsert_record(target, record)
        # Recheck under the caller's editorial lock after the target write.  The
        # target write must never silently authorize deletion of a changed source.
        assert_unchanged(snapshot)
        if not remove_record(snapshot.index_path, snapshot.post_id):
            raise ValueError("editorial_index_move_source_missing")
    except Exception:
        _atomic_write_bytes(snapshot.index_path, source_raw)
        if target_raw is None:
            target.unlink(missing_ok=True)
        else:
            _atomic_write_bytes(target, target_raw)
        raise


def migrate_index(index_path: Path | str) -> int:
    index = Path(index_path)
    if not storage_enabled(index):
        raise ValueError("post_manifest_schema_required")
    raw, rows = _load_index(index)
    converted = 0
    compact = []
    for row in rows:
        if isinstance(row.get("fact_manifest"), dict):
            digest = _write_manifest(index, row)
            compact.append(_compact_row(row, digest))
            converted += 1
        elif "manifest_sha256" not in row:
            compact.append(row)
        else:
            _load_manifest(index, row)
            compact.append(row)
    if converted:
        atomic_write_json(index, compact)
    return converted


def snapshot_backup_payload(snapshot: StateSnapshot) -> dict:
    return {
        "version": 1,
        "post_id": snapshot.post_id,
        "mode": snapshot.mode,
        "target_token": snapshot.target_token,
        "record": snapshot.record,
    }


def migrate_data_dir(data_dir: Path | str) -> dict[str, int]:
    """Enable per-post storage and compact the two canonical editorial indexes."""
    data = Path(data_dir)
    indexes = [data / "draft_posts.json", data / "published_posts.json"]
    # Validate every existing legacy index before creating the schema marker.
    for index in indexes:
        if index.is_file():
            _load_index(index)
    activate_storage(data)
    result = {}
    for index in indexes:
        result[index.name] = migrate_index(index) if index.is_file() else 0
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Compact Bloguito editorial state into per-post manifests.")
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(migrate_data_dir(args.data_dir), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
