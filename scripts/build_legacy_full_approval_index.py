"""Build a local, non-publishing status index for the remaining legacy articles.

Workers own individual status.json files. The index never loads or links their
private WordPress backups and cannot approve, deploy, or publish anything.
"""

from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp" / "legacy_audit_20260922"
OUT = TMP / "full-approval-index"
GROUPS = {
    "full-seasonal": (145, 144, 225, 217, 163),
    "full-finance": (219, 220, 218, 243, 139, 127, 125),
    "full-civic": (304, 81, 63, 140, 113, 119, 121, 105),
    "full-mixed": (349, 99, 70, 85, 77, 103),
}
STAGES = {"ready", "blocked", "draft"}


def safe_file(value: str | None, *, allow_private: bool = False) -> Path | None:
    """Accept only a local, existing file inside this task's ignored directory."""
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid_path_type")
    candidate = (ROOT / value).resolve()
    if TMP.resolve() not in candidate.parents or not candidate.is_file():
        raise ValueError("approval_path_missing_or_outside_private_workspace")
    if not allow_private and ("PRIVATE" in candidate.name or candidate.suffix == ".json"):
        raise ValueError("private_or_machine_data_must_not_be_linked")
    return candidate


def load_status(group: str, post_id: int) -> dict:
    folder = TMP / group / f"post-{post_id}"
    manifest = folder / "status.json"
    if not manifest.is_file():
        return {"post_id": post_id, "stage": "pending", "reason": "전체 원고 승인 상태 미보고"}
    record = json.loads(manifest.read_text(encoding="utf-8"))
    if record.get("post_id") != post_id or record.get("stage") not in STAGES:
        raise ValueError(f"invalid_status:{post_id}")
    report = dict(record)
    approval_dir = record.get("approval_dir")
    approval = (ROOT / approval_dir).resolve() if isinstance(approval_dir, str) else None
    if approval is not None and (TMP.resolve() not in approval.parents or not approval.is_dir()):
        raise ValueError(f"approval_dir_outside_workspace:{post_id}")
    actual = None
    if approval is not None:
        approval_manifest = approval / "approval-manifest.json"
        if approval_manifest.is_file():
            actual = json.loads(approval_manifest.read_text(encoding="utf-8"))
            if actual.get("post_id") != post_id:
                raise ValueError(f"approval_id_mismatch:{post_id}")
    # A worker's 'ready' label is insufficient on its own. Check the actual
    # approval preflight artifact and independent-review flag before display.
    if report["stage"] == "ready" and not (
        report.get("review_passed") is True
        and report.get("preflight_status") == "ready"
        and actual is not None
        and actual.get("preflight_status") == "ready"
        and actual.get("source_hashes_match_live") is True
    ):
        report["stage"] = "blocked"
        report["reason"] = "ready 주장과 실제 검토·출처·원본 사전검사 증거 불일치"
    report["approval_manifest_observed"] = actual is not None
    report["preview"] = None
    report["diff"] = None
    if approval is not None:
        for key, filename in (("preview", "compare-preview.html"), ("diff", "content-diff.txt")):
            item = approval / filename
            if item.is_file():
                report[key] = item.relative_to(ROOT).as_posix()
    return report


def build() -> list[dict]:
    seen = set()
    records = []
    for group, post_ids in GROUPS.items():
        for post_id in post_ids:
            if post_id in seen:
                raise ValueError(f"duplicate_post:{post_id}")
            seen.add(post_id)
            records.append(load_status(group, post_id))
    if len(records) != 26:
        raise AssertionError("expected_25_remaining_and_103")
    return records


def render(records: list[dict]) -> str:
    rows = []
    for item in records:
        links = []
        for key, caption in (("preview", "변경 전후 미리보기"), ("diff", "변경 비교")):
            target = safe_file(item.get(key))
            if target:
                # index.html is nested one level beneath TMP.
                link = "../" + target.relative_to(TMP).as_posix()
                links.append(f'<a href="{html.escape(link, quote=True)}">{caption}</a>')
        blockers = item.get("evidence_blockers", [])
        if not isinstance(blockers, list):
            raise ValueError("invalid_blocker_list")
        details = "; ".join(str(x) for x in blockers) or item.get("reason", "")
        rows.append("<tr><th>#{}</th><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            item["post_id"], html.escape(item["stage"]), " · ".join(links) or "미생성",
            html.escape(str(details)),
        ))
    return ("<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Bloguito 글별 승인 전 상태</title><style>body{font:16px/1.7 system-ui;"
            "max-width:1400px;margin:24px auto;padding:0 16px}table{border-collapse:collapse;"
            "width:100%}th,td{padding:12px;border:1px solid #cbd5e1;text-align:left;"
            "vertical-align:top}a{margin-right:12px;color:#076b56} .scroll{overflow-x:auto}"
            "</style></head><body><h1>Bloguito: 글별 승인 전 상태</h1>"
            "<p>남은 25편과 #103의 로컬 검토 자료입니다. 상태는 자동 승인이나 공개 적용을 뜻하지 않습니다."
            " 개인 정보가 들어 있는 원본 WordPress 백업은 링크하지 않습니다.</p>"
            "<div class=\"scroll\"><table><thead><tr><th>ID</th><th>기술 상태</th>"
            "<th>비공개 미리보기</th><th>미해결/주의</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div></body></html>")


def main() -> None:
    records = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(render(records), encoding="utf-8")
    # Only public-safe status metadata; no source excerpts, original post
    # content, authentication data, full WordPress inventory or backups.
    safe = [{key: row.get(key) for key in ("post_id", "stage", "reason", "evidence_blockers",
                                         "review_passed", "preflight_status", "preview", "diff")}
            for row in records]
    (OUT / "status-summary.json").write_text(
        json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tally = {stage: sum(row["stage"] == stage for row in records)
             for stage in ("ready", "blocked", "draft", "pending")}
    print("approval_index", OUT / "index.html", "counts", tally)


if __name__ == "__main__":
    main()
