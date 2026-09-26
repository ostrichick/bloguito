"""Classify a WordPress post_tag inventory without mutating WordPress.

The Bloguito editorial workflow is intentionally closed to *new* tags. This
utility inventories the legacy taxonomy and produces a conservative governance
report. It never deletes, renames, merges, or reassigns a term.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


KEEP = "유지"
MERGE = "통합 후보"
STOP = "신규 사용 중단"
DELETE = "삭제 후보"


def normalized_name(name: str) -> str:
    """Normalize only superficial spacing/punctuation for exact duplicate checks."""
    return re.sub(r"[\s\-_·,./]+", "", str(name)).casefold()


def is_dated_name(name: str) -> bool:
    """Treat explicit calendar-year tags as dated rather than reusable taxonomy."""
    return bool(re.search(r"(?:^|\D)20\d{2}(?:\D|$)", str(name)))


def classify(tags: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for tag in tags:
        groups.setdefault(normalized_name(tag["name"]), []).append(tag)

    merge_target_by_id: dict[int, dict] = {}
    for items in groups.values():
        if len(items) < 2:
            continue
        ordered = sorted(
            items,
            key=lambda item: (
                -int(item["count"]),
                len(str(item["name"])),
                int(item["term_id"]),
            ),
        )
        canonical = ordered[0]
        for duplicate in ordered[1:]:
            merge_target_by_id[int(duplicate["term_id"])] = canonical

    rows: list[dict] = []
    for tag in sorted(tags, key=lambda item: int(item["term_id"])):
        term_id = int(tag["term_id"])
        count = int(tag["count"])
        name = str(tag["name"])
        merge_target = merge_target_by_id.get(term_id)

        if count == 0:
            classification = DELETE
            reason = "현재 연결 글 0개, 삭제는 실행하지 않고 후보로만 보존"
            merge_into = ""
        elif merge_target is not None:
            classification = MERGE
            merge_into = str(merge_target["name"])
            reason = "공백/구두점만 다른 동일 표기 후보, 자동 통합은 실행하지 않음"
        elif count >= 2 and not is_dated_name(name):
            classification = KEEP
            merge_into = ""
            reason = "현재 2개 이상 글에서 재사용되고 연도 한정 표기가 아님"
        else:
            classification = STOP
            merge_into = ""
            if is_dated_name(name):
                reason = "연도 한정 태그, 기존 연결은 보존하되 신규 사용 중단"
            else:
                reason = "현재 1개 글에서만 사용, 기존 연결은 보존하되 신규 사용 중단"

        rows.append(
            {
                "term_id": term_id,
                "name": name,
                "slug": str(tag["slug"]),
                "count": count,
                "classification": classification,
                "merge_into": merge_into,
                "reason": reason,
            }
        )
    return rows


def summary(rows: list[dict]) -> dict[str, int]:
    result = {KEEP: 0, MERGE: 0, STOP: 0, DELETE: 0}
    for row in rows:
        result[row["classification"]] += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify Bloguito legacy post tags without mutation")
    parser.add_argument("inventory", type=Path, help="wp term list post_tag JSON output")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--csv-out", type=Path)
    args = parser.parse_args()

    with args.inventory.open(encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise ValueError("tag inventory must be a JSON list")

    rows = classify(raw)
    report = {"total": len(rows), "summary": summary(rows), "tags": rows}

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        with args.csv_out.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["term_id", "name"])
            writer.writeheader()
            writer.writerows(rows)

    print(json.dumps({"total": len(rows), "summary": summary(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
