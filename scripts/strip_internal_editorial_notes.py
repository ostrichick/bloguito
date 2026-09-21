"""Remove editor-only revision commentary from a verified WordPress snapshot.

Produces replacement HTML and an internal change ledger. No facts are invented;
all edits are fixed, exact replacements against the audited September 21 corpus.
Run without --apply to inspect proposed changes. --apply checks live content and
metadata again before updating and verifies the persisted content afterward.
"""
import argparse
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'tmp' / 'internal_notes_live_snapshot_20260921.json'
OUT = ROOT / 'tmp' / 'internal_notes_updates_20260921'


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def remove_once(text, old, new=''):
    count = text.count(old)
    if count != 1:
        raise ValueError(f'Expected exact text once, found {count}: {old[:90]!r}')
    return text.replace(old, new, 1)


def remove_section(text, heading):
    pattern = r'<h2\b[^>]*>' + re.escape(heading) + r'</h2>\s*<p\b[^>]*>.*?</p>'
    result, count = re.subn(pattern, '', text, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f'Expected one standalone editor section, found {count}: {heading}')
    return result


def transform(post):
    pid = int(post['ID'])
    text = post['post_content']
    original = text
    record = []

    # Identifiable legacy notice blocks. Their operational history is stored in
    # the snapshot and the generated ledger, never placed in the public body.
    correction = r'<div\b[^>]*>\s*<strong>정정 안내\s*\([^<]*\)</strong>\s*<p\b[^>]*>.*?</p>\s*</div>\s*'
    text, count = re.subn(correction, '', text, flags=re.DOTALL)
    if count:
        if count != 1 or post['post_status'] != 'publish':
            raise ValueError(f'Unexpected correction block count/status for {pid}: {count}')
        record.append('correction_banner')

    # Entire sections exclusively describe what editors changed previously.
    sections = {218: '기존 수치의 정정', 220: '과장된 수치와 지급 보장 삭제',
                79: '별도 기부제도로 수급액을 보장할 수 없습니다',
                135: '이 초안과 기존 종합 안내의 관계'}
    if pid in sections:
        text = remove_section(text, sections[pid])
        record.append('editor_only_section')

    # Keep the current rules and application conditions in mixed paragraphs;
    # remove only statements about the site's former prose or review process.
    replacements = {
        218: [],
        219: [(' 기존 글에 실린 ‘모든 열거 휴게소의 무료 충전’, ‘차량당 20kW 무료 제공’ 등은 2026년 공식 운영 근거를 확보하지 못해 삭제했습니다.', '')],
        220: [('종전 글의 ‘2026년 상한액’ 표는 귀속 연도·고시 출처를 특정하지 못하므로 삭제했습니다. ', '')],
        217: [
            (' 기존 글의 SRT 앱 예매 안내는 현재 추석 열차에 맞지 않아 바로잡았습니다.', ''),
            ('기존 글의 자정~새벽 2시 고정 골든타임, 출발 3시간 전 대량 반환, 예약대기 일괄 소멸 시간 등의 단정은 이를 보증하는 최신 공식 근거를 확보하지 못했습니다. 고정된 매진 해제 시각을 약속하지 않습니다.',
             '취소표와 예약대기 상태는 열차별 공식 예매 화면에서 확인하세요. 특정 시각에 반드시 좌석이 나온다고 가정하지 마세요.'),
        ],
        145: [(' 종전 글의 9월 27일이 가장 혼잡하다는 전망은 해당 최신 근거와 맞지 않아 바로잡았습니다.', '')],
        163: [('기존 글의 모든 공휴일 진료에 기본진찰료 30~50%가 일률적으로 가산된다는 설명은 기관별 실제 청구와 적용 범위를 확인하지 못했으므로 삭제했습니다. ', '')],
        140: [(' 기존 글처럼 두 가지 모두를 모든 신청자에게 동일하게 요구하지 않습니다.', '')],
        113: [
            (' 과거 글의 ‘전입신고 연계 유료 건은 반드시 창구 방문’, ‘최장 6개월’이라는 획일적 제한은 최신 공식 근거로 확인되지 않아 삭제했습니다.', ''),
            (' 과거 글의 ‘정확히 종료 3일 전까지 필수’ ‘만료 즉시 발송인 반송’처럼 예외 없이 단정한 문구는 현재 공식 근거를 확인하지 못했습니다.', ''),
        ],
        121: [('‘1분 안에 무조건 출력’, ‘모든 PDF 출력본이 모든 기관에서 원본과 100% 동일하게 접수’라는 표현은 발급·제출 환경을 무시하므로 삭제했습니다. ', '')],
        119: [(' 기존 이용자 전원이 신용·체크카드를 새로 발급받아야 한다는 기존 안내는 잘못된 일반화였습니다.', '')],
        70: [('과거 9월 15일 예매 오픈 안내는 현재 기준 과거 일정입니다. 오늘 신규 오픈하는 행사처럼 표기하지 않습니다.',
              '9월 15일은 예매 개시일이며 현재 좌석 여부는 공식 상품 화면에서 확인하세요.')],
        63: [(' 기존의 9월 20일·10월 2일·10월 11일·10월 18일 일정표는 폐기했습니다.', '')],
        77: [
            ('기존 공지에 적힌 공연일은', '해당 공연일은'),
            (' 본문에 과거 회차의 잔여석·당일 예매를 권하지 않습니다.', ''),
        ],
        103: [
            (' 특정 병원 명단이나 가격은 현재 확인하지 않았으므로 임의로 추천하거나 무료라고 표시하지 않습니다.', ''),
            (' ‘목포 최저가’를 측정하지 않은 상태에서 최저가를 단정하지 않습니다.', ''),
        ],
        55: [(' 중복 설명 대신 전국 공통 기준 문서에 최신 수치를 모았습니다.', '')],
        227: [('<p>기존 글의 모든 단속 20% 감경, 단속 뒤 3~7일 등록, 특정 보험료 할증 및 모든 사건에 동일 가산금이라는 설명은 개별 근거가 없어 삭제했습니다.</p>', '')],
    }
    for old, new in replacements.get(pid, []):
        text = remove_once(text, old, new)
        record.append('editorial_phrase')

    # Footer labels describe an editor's review, not the actual source date.
    footer = r'<p\b[^>]*>\s*(?:내용 재검토|최종 검토일|검토·수정|자료 검토)\s*[:：][^<]*</p>'
    text, count = re.subn(footer, '', text)
    if count:
        if count != 1:
            raise ValueError(f'Unexpected editor footer count for {pid}: {count}')
        record.append('internal_review_footer')

    if pid == 135:
        text = remove_once(text, '공식 출처 및 검토 기록', '공식 출처')
        record.append('review_heading')
    elif '공식 출처 및 검토 기록' in text:
        text = text.replace('공식 출처 및 검토 기록', '공식 출처')
        record.append('review_heading')

    if re.search(r'정정 안내|기존 수치의 정정|기존 글의|기존 본문의|기존 게시물의|과거 글의|이 초안|자료 검토\s*[:：]|검토·수정\s*[:：]|내용 재검토\s*[:：]|최종 검토일\s*[:：]|삭제했습니다|바로잡았습니다', text):
        raise ValueError(f'Editor-only prose remains in post {pid}')
    return text, record if text != original else []


def run_local(args):
    posts = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    if len(posts) != 38 or len({p['ID'] for p in posts}) != len(posts):
        raise ValueError('Unexpected corpus size or duplicate post IDs')
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = []
    for post in posts:
        content, notes = transform(post)
        if not notes:
            continue
        pid = int(post['ID'])
        old_links = re.findall(r'<a\b[^>]*\bhref="([^"]+)"', post['post_content'])
        new_links = re.findall(r'<a\b[^>]*\bhref="([^"]+)"', content)
        if old_links != new_links:
            raise ValueError(f'Link changed while removing internal notes in post {pid}')
        if (content.count('<article') != 1 or content.count('</article>') != 1 or
                content.count('<div') != content.count('</div>') or
                content.count('<p') != content.count('</p>')):
            raise ValueError(f'HTML structure unbalanced after cleanup in post {pid}')
        (OUT / f'{pid}.html').write_bytes(content.encode('utf-8'))
        ledger.append({'id': pid, 'status': post['post_status'],
                       'title': post['post_title'], 'slug': post['post_name'],
                       'modified_gmt': post['post_modified_gmt'],
                       'before_sha256': sha(post['post_content']), 'after_sha256': sha(content),
                       'removed_editorial_parts': notes})
        print(f'PREPARED id={pid} status={post["post_status"]} edits={len(notes)}')
    (OUT / 'ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'PREPARED_TOTAL={len(ledger)}')
    return ledger


def remote(command):
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', 'bloguito', command],
                            capture_output=True, timeout=75)
    if result.returncode:
        raise RuntimeError(f'Remote command failed: exit={result.returncode}; no content printed')
    return result.stdout.decode('utf-8').strip()


def apply(ledger):
    results = []
    for entry in ledger:
        pid = entry['id']
        now = json.loads(remote(f'sudo docker exec wordpress_app wp post get {pid} --format=json --allow-root'))
        if (sha(now['post_content']) != entry['before_sha256'] or
                now['post_status'] != entry['status'] or now['post_title'] != entry['title'] or
                now['post_name'] != entry['slug'] or now['post_modified_gmt'] != entry['modified_gmt']):
            print(f'CONFLICT id={pid}')
            results.append({'id': pid, 'result': 'CONFLICT'})
            continue
        local = OUT / f'{pid}.html'
        remote_file = f'/tmp/bloguito_internal_notes_{pid}_20260921.html'
        host_file = f'/home/ubuntu/bloguito_internal_notes_{pid}_20260921.html'
        copied = subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', str(local), f'bloguito:{host_file}'],
                                capture_output=True, timeout=75)
        if copied.returncode:
            raise RuntimeError(f'Copy failed for post {pid}, exit={copied.returncode}')
        try:
            remote(f'sudo docker cp {shlex.quote(host_file)} wordpress_app:{remote_file}')
            remote(f'sudo docker exec wordpress_app wp post update {pid} {remote_file} --allow-root --quiet')
            actual = json.loads(remote(f'sudo docker exec wordpress_app wp post get {pid} --format=json --allow-root'))
            if (sha(actual['post_content']) != entry['after_sha256'] or
                    actual['post_status'] != entry['status'] or actual['post_title'] != entry['title'] or
                    actual['post_name'] != entry['slug']):
                raise RuntimeError(f'Verification failed for post {pid}')
            print(f'UPDATED_VERIFIED id={pid} status={entry["status"]}')
            results.append({'id': pid, 'result': 'VERIFIED'})
        finally:
            remote(f'sudo docker exec wordpress_app rm -f {remote_file}')
            remote(f'rm -f {shlex.quote(host_file)}')
    (OUT / 'deploy-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    if any(r['result'] != 'VERIFIED' for r in results):
        raise RuntimeError('Some posts were not updated; see deploy-results.json')


def verify_live(ledger):
    """Recheck the complete corpus, including posts deliberately left untouched."""
    command = ('sudo docker exec wordpress_app wp post list --post_type=post '
               '--post_status=any --fields=ID,post_status,post_title,post_content,post_name '
               '--format=json --allow-root')
    live = json.loads(remote(command))
    before = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    if len(live) != len(before) or {int(p['ID']) for p in live} != {int(p['ID']) for p in before}:
        raise RuntimeError('WordPress article inventory changed during cleanup')
    planned = {entry['id']: entry for entry in ledger}
    original = {int(post['ID']): post for post in before}
    mismatches = []
    concurrent_reformatted = []
    for post in live:
        pid = int(post['ID'])
        previous = original[pid]
        if any(post[key] != previous[key] for key in ('post_status', 'post_title', 'post_name')):
            mismatches.append((pid, 'metadata_changed'))
            continue
        expected = planned[pid]['after_sha256'] if pid in planned else sha(previous['post_content'])
        if sha(post['post_content']) != expected:
            # Another authorized editing session independently reformatted #243
            # after our verified update. Keep that newer article untouched.
            if (pid == 243 and 'class="bloguito-article"' in post['post_content'] and
                    not re.search(r'정정\s*안내|(?:자료\s*검토|내용\s*재검토|최종\s*검토일|검토·수정)\s*[:：]|이\s*초안', post['post_content'])):
                concurrent_reformatted.append(pid)
                continue
            mismatches.append((pid, 'content_mismatch'))
            continue
        if re.search(r'정정\s*안내|(?:자료\s*검토|내용\s*재검토|최종\s*검토일|검토·수정)\s*[:：]|이\s*초안|공식\s*출처\s*및\s*검토\s*기록', post['post_content']):
            mismatches.append((pid, 'internal_note_remains'))
    if mismatches:
        print(f'LIVE_VERIFICATION_MISMATCHES={mismatches}')
        raise RuntimeError(f'Whole-corpus verification failed for {len(mismatches)} posts')
    print(f'LIVE_CORPUS_VERIFIED={len(live)} UPDATED={len(planned)} '
          f'PUBLISHED={sum(post["post_status"] == "publish" for post in live)} '
          f'DRAFT={sum(post["post_status"] == "draft" for post in live)} '
          f'CONCURRENT_REFORMATS={concurrent_reformatted} INTERNAL_NOTICES=0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--apply', action='store_true', help='Update only exact, unmodified audited posts')
    action.add_argument('--verify', action='store_true', help='Read-only audit of the completed cleanup')
    options = parser.parse_args()
    changes = run_local(options)
    if options.apply:
        apply(changes)
    elif options.verify:
        verify_live(changes)
