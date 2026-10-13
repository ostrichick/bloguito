"""Exercise the real fixed PHP setter only in a verified synthetic R4 fixture.

No origin/review authority is issued here. Direct PHP calls exercise its DB and
capability boundary, not the root writer, SSH/sudo installation or new import.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import secrets
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts/ops'))
import image_r4_pc_fixture as fixture


def run(folder: Path) -> dict:
    fixture._check_local_docker()
    state = fixture.verified_fixture(folder)
    evidence = json.loads((folder / 'r4-smoke-evidence.json').read_text())
    if (evidence.get('status') != 'SYNTHETIC_E2E_PASS_R4_ACCEPTANCE_NO_GO'
            or evidence.get('project') != state['project']):
        raise ValueError('successful_synthetic_r4_fixture_required')
    result_path = folder / 'r3-setter-evidence.json'
    if result_path.exists():
        raise ValueError('r3_setter_already_attempted')
    result = {'status': 'NO-GO', 'scope': 'synthetic_fixed_php_only', 'checks': [],
              'r1_r2_issuance_tested': False, 'root_writer_tested': False,
              'ssh_sudo_tested': False, 'new_media_import_tested': False}
    fixture._write_exclusive(result_path, json.dumps(result).encode())
    runtime = ROOT / 'scripts/security/featured_image_set.php'
    mount = str(runtime) + ':/r3-setter.php:ro'
    post = evidence['post_id']
    attachments = evidence['attachment_ids']
    def wp(*args, **kw):
        return fixture._cli(folder, *args, **kw).stdout.strip()
    def observe():
        return json.loads(wp('eval', 'echo wp_json_encode(['
            '"post"=>get_post('+str(post)+',ARRAY_A),'
            '"thumbnail"=>(int)get_post_meta('+str(post)+',"_thumbnail_id",true),'
            '"alts"=>array_map(function($id){return (string)get_post_meta($id,"_wp_attachment_image_alt",true);},'
            +json.dumps(attachments)+'),'
            '"attachment_count"=>count(get_posts(["post_type"=>"attachment","post_parent"=>'
            +str(post)+',"post_status"=>"inherit","numberposts"=>-1]))]);'))
    def request(attachment):
        live = observe(); p = live['post']; sha = state['files'][f'synthetic-{attachments.index(attachment)+1}.png']
        return {'protocol': 1, 'action': 'featured-image-set', 'request_id': uuid.uuid4().hex,
            'task_id': 'synthetic_r3_test', 'post_id': post, 'attachment_id': attachment,
            'candidate_number': 1, 'candidate_count': 1,
            'candidates': [{'candidate_number': 1, 'sha256': sha}],
            'image_sha256': sha, 'source_sha256': sha, 'staged_sha256': sha,
            'alt_text': 'Synthetic R3 transactional ALT',
            'release_sha256': hashlib.sha256(runtime.read_bytes()).hexdigest(),
            'origin': {}, 'review': {}, 'task_created_at': '2026-10-13T00:00:00Z',
            'target': {'post_id': post}, 'generator_policy_sha256': 'a'*64,
            'manifest_sha256': 'a'*64, 'review_receipt_sha256': 'a'*64,
            'selection_mode': 'agent-delegated', 'review_actor': 'SYNTHETIC_NOT_AUTHORITY',
            'expected': {'post_status': p['post_status'], 'thumbnail_id': live['thumbnail'],
                'content_sha256': hashlib.sha256(p['post_content'].encode()).hexdigest(),
                'title_sha256': hashlib.sha256(p['post_title'].encode()).hexdigest(),
                'slug_sha256': hashlib.sha256(p['post_name'].encode()).hexdigest(),
                'excerpt_sha256': hashlib.sha256(p['post_excerpt'].encode()).hexdigest(),
                'alt_sha256': hashlib.sha256(live['alts'][attachments.index(attachment)].encode()).hexdigest()}}
    def call(req, user='bloguito-image-writer', wrapper=None):
        args = ['run', '--rm', '-T', '--volume', mount]
        if wrapper:
            args += ['--volume', str(wrapper)+':/r3-fault.php:ro']
        args += ['cli', 'eval-file', '/r3-fault.php' if wrapper else '/r3-setter.php', '--user='+user]
        completed = fixture._docker(folder, *args, stdin=json.dumps(req), allow_failure=True)
        parsed = json.loads(completed.stdout.strip())
        assert (completed.returncode == 0) == (parsed.get('status') == 'verified')
        return parsed
    def record(name):
        result['checks'].append(name); print('PASS '+name, flush=True)
    def deny(name, req, **kw):
        before = observe()
        assert call(req, **kw)['status'] == 'denied'
        assert observe() == before
        record(name)
    try:
        lint = fixture._docker(folder, 'run', '--rm', '-T', '--volume', mount,
            '--entrypoint', 'php', 'cli', '-l', '/r3-setter.php')
        assert 'No syntax errors' in lint.stdout
        record('actual_php_lint')
        wp('role', 'create', 'bloguito_image_writer', 'Synthetic Image Writer')
        wp('cap', 'add', 'bloguito_image_writer', 'read', 'edit_posts', 'edit_others_posts',
           'edit_published_posts', 'upload_files', 'bloguito_write_featured_image')
        wp('user', 'create', 'bloguito-image-writer', 'r3-writer@example.invalid',
           '--role=bloguito_image_writer', '--prompt=user_pass', '--porcelain',
           stdin=secrets.token_hex(32)+'\n')
        baseline = observe()
        deny('administrator_denied_without_mutation', request(attachments[0]), user='r4_fixture_admin')
        wp('cap', 'remove', 'bloguito_image_writer', 'bloguito_write_featured_image')
        deny('missing_custom_capability_denied', request(attachments[0]))
        wp('cap', 'add', 'bloguito_image_writer', 'bloguito_write_featured_image')
        bad = request(attachments[0]); bad['expected']['content_sha256'] = '0'*64
        deny('stale_body_denied', bad)
        bad = request(attachments[0]); bad['expected']['thumbnail_id'] = 999999
        deny('stale_thumbnail_denied', bad)
        bad = request(attachments[0]); bad['expected']['alt_sha256'] = '0'*64
        deny('stale_alt_denied', bad)
        bad = request(attachments[0]); bad['image_sha256'] = bad['staged_sha256'] = '0'*64
        deny('attachment_bytes_mismatch_denied', bad)
        good = request(attachments[0]); assert call(good)['status'] == 'verified'
        after = observe()
        assert after['thumbnail'] == attachments[0] and after['alts'][0] == good['alt_text']
        assert after['post'] == baseline['post'] and after['attachment_count'] == 3
        record('nonadmin_real_metadata_write_and_readback')
        denied_replay = call(good)
        assert denied_replay['status'] == 'denied' and observe() == after
        record('stale_baseline_replay_denied')
        pending = [request(a) for a in attachments[1:]]
        barrier = threading.Barrier(2)
        def compete(req):
            barrier.wait(); return call(req)['status']
        with ThreadPoolExecutor(2) as pool:
            statuses = list(pool.map(compete, pending))
        assert sorted(statuses) == ['denied', 'verified']
        assert observe()['post'] == baseline['post'] and observe()['attachment_count'] == 3
        record('two_real_php_connections_exactly_one_cas_winner')
        # Fail the second metadata write after ALT is changed inside the transaction.
        wrapper = folder / 'r3-rollback-fault.php'
        wrapper.write_text('<?php add_filter("query",function($q){'
            'if((stripos($q,"INSERT")!==false||stripos($q,"UPDATE")!==false)'
            '&&strpos($q,"_thumbnail_id")!==false){return "INVALID SYNTHETIC SQL";}return $q;});'
            'require "/r3-setter.php";', encoding='utf-8')
        rollback = request(attachments[0]); rollback['alt_text'] = 'Must roll back this ALT'
        deny('real_second_write_failure_rolls_back_alt_and_thumbnail', rollback, wrapper=wrapper)
        result['status'] = 'SYNTHETIC_PHP_SETTER_PASS_R3_ACCEPTANCE_NO_GO'
        result['final'] = observe()
    finally:
        result_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--confirm-local-isolated', action='store_true')
    args = parser.parse_args()
    if not args.confirm_local_isolated:
        parser.error('confirm_local_isolated_required')
    print(json.dumps(run(args.fixture), indent=2))
