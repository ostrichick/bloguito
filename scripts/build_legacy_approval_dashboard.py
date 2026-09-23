"""Build a local, non-deployable index of pre-approval Bloguito HTML previews.

Only links to non-private previews/diffs. No WordPress requests, scheduling,
publishing or login; all files are left inside the Git-ignored tmp workspace.
"""

import html
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / 'tmp' / 'legacy_audit_20260922'
OUTPUT = TMP / 'approval-dashboard' / 'index.html'

PRIORITY = {
    55: ('priority-prime/approval-55-ready',
         '독립 검토·전체 사전검사 통과. 개별 글 승인·적용 직전 재검사 대기.'),
    79: ('priority-prime/approval-79-ready',
         '독립 검토·전체 사전검사 통과. 계산기 인증 후 화면은 검증하지 않음.'),
    101: ('content-worker1/approval-101-20260922-r2',
          '독립 검토·전체 사전검사 통과. 잘못된 출처 라벨 교정·부부 20% 감액·지역별 재산공제 보강, 글별 승인 대기.'),
    103: ('priority-prime/approval-103-ready-v2',
          '자동·독립 검토 통과. 목포 자체사업 65세 경계의 두 공식 안내 충돌은 수동 보류.'),
}
LONGTAIL = (70, 77, 81, 85, 99, 105, 113, 119, 121, 125,
            127, 139, 140, 218, 219, 220, 243, 304, 349, 63)


def link(path, label):
    target = TMP / path
    if not target.is_file():
        return f'<span class="missing">미생성: {html.escape(label)}</span>'
    # index.html is one directory beneath TMP; all links stay local.
    address = '../' + '/'.join(quote(part) for part in Path(path).parts)
    return f'<a href="{html.escape(address, quote=True)}">{html.escape(label)}</a>'


def page():
    first = [
        ('#137 — 독립 검토 완료, 글별 승인 대기',
         link('pilot137/approval-20260922-1/compare-preview.html',
              '기존 저장 본문과 검토 원고 좌우 비교'),
         link('pilot137/approval-20260922-1/content-diff.txt',
              '원문 대비 변경 텍스트'),
         '전체 상태 인벤토리·원본 저장 SHA·원본 비공개 백업·공식 출처 해시 일치. 운영 반영 없음.'),
        ('#85 — 표 접근성·목차 출력용 변경안, 별도 운영 배포 승인 대기',
         link('layout-worker2/post85-original-full-preview.html', '현재 레이아웃'),
         link('layout-worker2/post85-runtime-mu-preview.html',
              '실제 PHP 목차·표 출력 후보'),
         '표 2개의 데이터는 보존. DB 본문을 변경하지 않는 전용 MU 파일은 서버에 설치하지 않음.'),
        ('#137 — 초록색 요약 상자 CSS 변경 전후(운영 미적용)',
         link('layout-worker2/post137-legacy-spacing-before-preview.html', '변경 전'),
         link('layout-worker2/post137-legacy-spacing-after-preview.html', '변경 후'),
         'CSS 소유자·적용 대상에 대한 별도 배포 승인 필요.'),
    ]
    rows = ''.join(
        '<tr><th>' + html.escape(title) + '</th><td>' + old + '</td><td>' + new
        + '</td><td>' + html.escape(note) + '</td></tr>'
        for title, old, new, note in first)
    for post_id, (folder, status) in PRIORITY.items():
        rows += ('<tr><th>#' + str(post_id) + ' — 승인 전 검토 패키지</th><td>'
                 + link(f'{folder}/content-diff.txt', '실제 저장 원본 대비 변경 텍스트')
                 + '</td><td>'
                 + link(f'{folder}/compare-preview.html',
                        '원본 WP 저장 글 vs 독립 검토 원고') + '</td><td>'
                 + html.escape(status + ' 공식 출처·원문 해시·검토 유효성은 승인 직전 재조회. 미게시.')
                 + '</td></tr>')
    for post_id in LONGTAIL:
        rows += ('<tr><th>#' + str(post_id) + ' — 부분 보강안, 글별 검토 전</th><td>'
                 + link(f'content-worker4/post-{post_id}-source.md', '기존 문단·출처 기록')
                 + '</td><td>'
                 + link(f'content-worker4/previews/post-{post_id}-compare.html',
                        '전체 글 대비 교체 후보 비교')
                 + '</td><td>원문 대비 후보 문단. 독립 심사·글별 승인 전 반영 금지.</td></tr>')
    explanation = ('<p><strong>운영 사이트 변경 0건.</strong> 이 페이지는 Git 제외 로컬 '
                   '승인 검토용 색인으로 자동 발행·배포·승인 기능이 없습니다. '
                   '링크는 준비 파일이 있을 때만 표시하며 개인 정보가 포함된 원본 '
                   'WordPress 백업으로 연결하지 않습니다.</p>')
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Bloguito 기존 글 현대화 승인 전 검토</title><style>'
            'body{font:16px/1.6 system-ui,sans-serif;max-width:1600px;margin:2rem auto;padding:0 1rem;'
            'color:#172a31;background:#f5f8fa}h1{font-size:clamp(1.5rem,3vw,2.2rem)}'
            'table{border-collapse:collapse;background:white;width:100%;min-width:900px}'
            'th,td{padding:.85rem;text-align:left;vertical-align:top;border:1px solid #d6e0e5}'
            'th{background:#e9f6f1;min-width:240px}a{color:#075e50;display:inline-block;margin:.2rem .5rem .2rem 0}'
            '.wrap{max-width:100%;overflow-x:auto}p{max-width:95ch}'
            '.warn{border-left:5px solid #ca9d29;padding:.8rem 1rem;background:#fffbe9}'
            '.missing{color:#872725}</style></head><body>'
            '<h1>Bloguito — 승인 전 변경안 통합 미리보기</h1>' + explanation +
            '<p class="warn">실제 운영 WordPress 갱신·MU 설치·정기 스케줄은 모두 별도 승인 전. '
            '정적 미리보기는 운영 테마·모바일 실제 배포 검사와 동일하지 않습니다.</p>'
            '<div class="wrap"><table><thead><tr><th>대상</th><th>변경 전/차이</th>'
            '<th>검토 후보</th><th>현재 상태</th></tr></thead><tbody>' + rows +
            '</tbody></table></div>'
            '<p>시한성 높은 #145·#144·#225·#217·#163의 공식 근거와 교체 원고는 '
            '<code>docs/legacy-remaining-content-approval-2026-09-22.md</code>, '
            '20편의 근거와 상태는 <code>docs/legacy-longtail-content-approval-2026-09-22.md</code>에 '
            '있습니다. 이 두 문서는 정식 전체 승인 원고를 뜻하지 않습니다.</p>'
            '</body></html>')


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.is_symlink():
        raise ValueError('refuse_to_overwrite_symlink')
    OUTPUT.write_text(page(), encoding='utf-8')
    print('LOCAL_APPROVAL_DASHBOARD:', OUTPUT)


if __name__ == '__main__':
    main()
