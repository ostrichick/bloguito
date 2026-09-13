"""Source-bound facts and a deliberately restricted publication format.

This checks exact evidence, not the truth of a source or arbitrary prose semantics.
"""
import hashlib
import html
import re
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from agents.temporal_validation import KST, LABELS
from agents.temporal_validation import extract_evidence

FIELDS = {**{label: kind for kind, expression in LABELS.items() for label in expression.split("|")},
          "장소": "venue", "공연장소": "venue", "행사장소": "venue",
          "티켓": "price", "관람료": "price", "입장료": "price", "지원금액": "benefit",
          "신청대상": "eligibility", "지원대상": "eligibility", "접종대상": "eligibility",
          "신청조건": "condition", "지원조건": "condition", "제외대상": "exclusion",
          "신청방법": "method", "접수처": "method", "문의": "contact"}
INTRO = "아래는 출처에서 확인한 핵심 정보입니다. 각 항목에 근거 링크를 함께 표시했습니다."


def _url(value):
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username


def snapshot(url: str, title: str, text: str, source_type: str) -> dict:
    return {"url": url, "title": title, "text": text, "source_type": source_type,
            "fetched_at": datetime.now(KST).isoformat(),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def build_manifest(sources: list[dict], category: str) -> dict:
    facts = []
    reasons = []
    labels = "|".join(sorted(FIELDS, key=len, reverse=True))
    pattern = re.compile(r"(?P<label>" + labels + r")\s*[:：]\s*(?P<value>.*?)(?=\n|[。]|[.!?]\s|(?:" + labels + r")\s*[:：]|$)")
    for index, source in enumerate(sources):
        if not _url(source.get("url", "")) or not source.get("text") or not source.get("title"):
            reasons.append("source_incomplete")
            continue
        if source.get("sha256") != hashlib.sha256(source["text"].encode("utf-8")).hexdigest():
            reasons.append("source_hash_mismatch")
            continue
        for match in pattern.finditer(source["text"]):
            value = match["value"].strip()
            if not value:
                continue
            facts.append({"id": f"s{index}f{len(facts)}", "kind": FIELDS[match["label"]],
                          "label": match["label"], "value": value, "source_url": source["url"],
                          "quote": match.group(0), "span": [match.start(), match.end()]})
    # Only identical fields collapse; conflicting facts are never silently overridden.
    values = {}
    for fact in facts:
        key = fact["kind"]
        values.setdefault(key, set()).add(fact["value"])
    if any(len(items) > 1 for kind, items in values.items() if kind in {"venue", "price", "benefit", "eligibility", "condition", "exclusion", "event", "application", "sale", "status"}):
        reasons.append("conflicting_core_facts")
    required = {"event", "venue", "price"} if category == "concert" else {"application", "eligibility", "method"}
    if not required.issubset(values):
        reasons.append("required_core_facts_missing")
    if not facts:
        reasons.append("no_structured_facts")
    return {"version": 1, "category": category, "sources": sources, "facts": facts,
            "status": "needs_review" if reasons else "verified", "reasons": list(dict.fromkeys(reasons))}


def render_content(manifest: dict) -> str:
    rows = "".join(f'<tr data-fact-id="{html.escape(f["id"], quote=True)}"><th>{html.escape(f["label"])}</th><td>{html.escape(f["value"])}</td><td><a href="{html.escape(f["source_url"], quote=True)}" target="_blank" rel="noopener noreferrer">출처</a></td></tr>' for f in manifest["facts"])
    return f'<p>{INTRO}</p><h2>확인된 핵심 정보</h2><table><thead><tr><th>항목</th><th>내용</th><th>근거</th></tr></thead><tbody>{rows}</tbody></table>'


def _signature(content: str):
    soup = BeautifulSoup(content, "html.parser")
    if soup.find(["script", "style", "iframe", "form", "img", "svg"]):
        raise ValueError("unsupported_markup")
    # Semantic tags, block order, text and links must all equal the fixed template.
    return [(tag.name, tag.get("data-fact-id"), tag.get("href"), tag.get_text(" ", strip=True)) for tag in soup.find_all(True)], soup.get_text(" ", strip=True)


def verify_article(article: dict, manifest: dict | None) -> dict:
    reasons = []
    if not isinstance(manifest, dict):
        return {"status": "needs_review", "reasons": ["fact_manifest_missing"]}
    rebuilt = build_manifest(manifest.get("sources", []), manifest.get("category", ""))
    if rebuilt != manifest or rebuilt["status"] != "verified":
        reasons.append("fact_manifest_invalid_or_incomplete")
    try:
        if article.get("title") != manifest["sources"][0]["title"]:
            reasons.append("title_not_source_bound")
        if _signature(article.get("content", "")) != _signature(render_content(rebuilt)):
            reasons.append("article_differs_from_verified_facts")
        if article.get("tags", []) != []:
            reasons.append("unverified_tags")
    except (ValueError, KeyError, IndexError, TypeError):
        reasons.append("invalid_article_or_manifest")
    return {"status": "verified" if not reasons else "needs_review", "reasons": reasons}


def verify_temporal_binding(source: dict, manifest: dict) -> bool:
    available = [field for entry in manifest.get("sources", [])
                 for field in extract_evidence(entry["text"], entry["url"])]
    return bool(available) and source.get("evidence") == available
