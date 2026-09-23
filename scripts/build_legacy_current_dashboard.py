"""Render a local review index from a current, complete public REST triage.

This is an inspection aid: it neither fetches private WordPress data nor
asserts that a candidate is approved, fact-checked or published. Unlike the
2026-09-22 approval dashboard, no historical deployment status is hardcoded.
"""

import argparse
import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
OLDER = ROOT / 'tmp' / 'legacy_audit_20260922'


def load_triage(path, now=None):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    now = now or datetime.now(KST)
    if (data.get('schema_version') != 2 or data.get('complete') is not True
            or data.get('site') != 'https://lifeinfo24.org'
            or data.get('expected_total') != len(data.get('posts', []))
            or data.get('audited_at', '')[:10] != now.astimezone(KST).date().isoformat()):
        raise ValueError('fresh_complete_public_triage_required')
    ids = [post['id'] for post in data['posts']]
    if len(ids) != len(set(ids)) or any(type(item) is not int for item in ids):
        raise ValueError('invalid_or_duplicate_public_post_id')
    if any(post.get('fact_review_status') != 'unverified'
           or post.get('visual_review_status') != 'unverified'
           or post.get('link_behavior_review_status') != 'unverified'
           for post in data['posts']):
        raise ValueError('audit_status_is_not_independent_review')
    return data


def candidate(post_id):
    """Find only known public-safe HTML previews; never link backup or JSON."""
    if post_id in {63, 81}:
        for version in ('v2', 'v1'):
            prepared = (ROOT / 'tmp' / 'legacy_audit_20260923' / 'prime'
                        / f'approval-{post_id}-reviewed-{version}')
            manifest = prepared / 'approval-manifest.json'
            preview = prepared / 'compare-preview.html'
            if (manifest.is_file() and not manifest.is_symlink()
                    and preview.is_file() and not preview.is_symlink()):
                details = json.loads(manifest.read_text(encoding='utf-8'))
                if (details.get('post_id') == post_id
                        and details.get('preflight_status') == 'ready'
                        and details.get('approval_status') == 'prepared_not_authorized'
                        and details.get('source_hashes_match_live') is True):
                    return preview
        refreshed = (ROOT / 'tmp' / 'legacy_audit_20260923' / 'worker-flu'
                     / f'post-{post_id}-compare-unreviewed.html')
        if refreshed.is_file() and not refreshed.is_symlink():
            return refreshed
    groups = {
        'full-civic': {63, 81, 119, 140, 304, 105, 113, 121},
        'full-finance': {125, 127, 139, 218, 219, 220, 243},
        'full-mixed': {70, 77, 85, 99, 103, 349},
        'full-seasonal': {144, 145, 163, 217, 225},
    }
    for group, ids in groups.items():
        if post_id not in ids:
            continue
        directory = OLDER / group / f'post-{post_id}'
        for relative in ('approval-prepared-v2/compare-preview.html',
                         'approval-20260922-reviewed-v2/compare-preview.html',
                         'approval-prepared/compare-preview.html',
                         'full-article-compare.html', 'compare-preview.html'):
            path = directory / relative
            if path.is_file() and not path.is_symlink():
                return path
    return None


def render(data, output):
    changes = data.get('changes', {})
    missing = changes.get('missing_from_public_snapshot_ids', [])
    if any(type(value) is not int for value in missing):
        raise ValueError('invalid_missing_post_ids')
    count = sum('legacy_layout' in p['flags'] for p in data['posts'])
    rows = []
    for post in sorted(data['posts'], key=lambda item: item['id']):
        post_id = post['id']
        url = post['url']
        # Only canonical public URLs from the auditor are accepted.
        if not isinstance(url, str) or not url.startswith('https://lifeinfo24.org/'):
            raise ValueError('non_public_post_url')
        old = 'legacy_layout' in post['flags']
        path = candidate(post_id) if old else None
        preview = '—'
        if path is not None:
            relative = os.path.relpath(path, output.parent).replace('\\', '/')
            address = '/'.join(quote(part) if part != '..' else '..' for part in relative.split('/'))
            preview = f'<a href="{html.escape(address, quote=True)}">기존 글 ↔ 개정 후보</a>'
        title = html.escape(post['title'])
        status = '구형 본문 · 검토 필요' if old else '최신형 본문 · 사실 검토 별도'
        flags = ', '.join(post['flags']) if post['flags'] else '자동 구조 이상 미탐지'
        rows.append('<tr><th scope="row">#{id}</th><td><a href="{url}">{title}</a></td>'
                    '<td>{status}</td><td>{length}</td><td>{flags}</td><td>{preview}</td></tr>'.format(
                        id=post_id, url=html.escape(url, quote=True), title=title,
                        status=html.escape(status), length=int(post['text_characters']),
                        flags=html.escape(flags), preview=preview))
    lost = ', '.join('#' + str(item) for item in missing) or '없음'
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Bloguito 현재 공개 글 진단</title><style>'
            'body{font:16px/1.7 system-ui,sans-serif;max-width:1500px;margin:auto;padding:24px;color:#182a30}'
            'table{border-collapse:collapse;width:100%}th,td{border:1px solid #cdd9df;padding:12px;text-align:left;vertical-align:top}'
            'th{background:#eef6f2}a{color:#09664e}.scroll{overflow-x:auto}'
            '.notice{padding:14px;border-left:5px solid #a66b00;background:#fff7e6}</style></head><body>'
            '<h1>Bloguito 기존 글 현대화 — 오늘의 공개 상태</h1>'
            f'<p>공개 REST 기준 {html.escape(data["audited_at"])} · 총 {len(rows)}편 · '
            f'구형 본문 {count}편.</p>'
            f'<p class="notice">기준선에서 공개 목록 제외: {html.escape(lost)}. 삭제나 임시글 전환 여부는 '
            '공개 REST만으로 알 수 없습니다. 구조 탐지만 수행했으며 사실·링크·모바일 화면 검토 및 '
            '개정안 승인 여부는 이 페이지가 보증하지 않습니다. 이전 9/22 승인 대시보드의 배포 상태는 최신 정보가 아닙니다.</p>'
            '<div class="scroll"><table><thead><tr><th>ID</th><th>현재 공개 글</th><th>본문 형식</th>'
            '<th>글자 수</th><th>진단 후보</th><th>로컬 개정 미리보기</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div></body></html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--triage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = load_triage(args.triage)
    target = args.output.resolve()
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError('refuse_symlink_output')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(data, target), encoding='utf-8')
    print('current_dashboard', target, 'public', len(data['posts']))


if __name__ == '__main__':
    main()
