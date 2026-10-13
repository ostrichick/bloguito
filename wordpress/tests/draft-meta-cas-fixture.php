<?php
/**
 * Pure-PHP fixture for the exact guarded NEW draft metadata transaction.
 *
 * Usage: php draft-meta-cas-fixture.php BASE64_OF_GUARDED_NEW_DRAFT_META_SCRIPT
 * This deliberately does not load WordPress or connect to MySQL. The fixture
 * replaces ONLY the php://stdin read with an in-memory JSON payload so each
 * case can exercise the original PHP mutation source in one CLI process.
 * Row locks / rollback here are modeled; MySQL isolation is NOT verified.
 */

$script = base64_decode($argv[1] ?? '', true);
if (!is_string($script) || strpos($script, 'file_get_contents("php://stdin")') === false) {
    fwrite(STDERR, "FAIL: missing exact guarded PHP script\n");
    exit(1);
}
$script = str_replace('file_get_contents("php://stdin")', '$GLOBALS["fixture_stdin"]', $script);
$fixture_meta = [];
$fixture_post = null;
$fixture_fail_key = null;
$fixture_missing = false;
$fixture_queries = [];
$fixture_writes = 0;
$fixture_transaction_meta = null;
$fixture_commit_unknown = false;

class FixtureWpdb {
    public $posts = 'wp_posts';
    public $postmeta = 'wp_postmeta';
    public function prepare($sql, ...$args) {
        return $sql;
    }
    public function get_var($sql) {
        global $fixture_missing, $fixture_queries;
        $fixture_queries[] = $sql;
        return $fixture_missing ? null : 901;
    }
    public function get_results($sql) {
        global $fixture_queries;
        $fixture_queries[] = $sql;
        return [];
    }
    public function query($sql) {
        global $fixture_queries, $fixture_transaction_meta, $fixture_meta, $fixture_commit_unknown;
        $fixture_queries[] = $sql;
        if ($sql === 'START TRANSACTION') {
            $fixture_transaction_meta = $fixture_meta;
        } elseif ($sql === 'ROLLBACK') {
            $fixture_meta = $fixture_transaction_meta;
        } elseif ($sql === 'COMMIT' && $fixture_commit_unknown) {
            return false;
        }
        return 1;
    }
}
$wpdb = new FixtureWpdb();

function wp_json_encode($v, $flags = 0) { return json_encode($v, $flags); }
function clean_post_cache($id) { }
function wp_cache_delete($id, $group) { }
function get_post($id) {
    global $fixture_post;
    return $id === 901 ? clone $fixture_post : null;
}
function metadata_exists($type, $id, $key) {
    global $fixture_meta;
    return array_key_exists($key, $fixture_meta);
}
function get_post_meta($id, $key, $single) {
    global $fixture_meta;
    return $fixture_meta[$key] ?? '';
}
function wp_slash($value) { return addslashes($value); }
function update_post_meta($id, $key, $value) {
    global $fixture_meta, $fixture_fail_key, $fixture_writes;
    ++$fixture_writes;
    if ($key === $fixture_fail_key) {
        return false;
    }
    // WordPress meta storage unslashes incoming values.
    $fixture_meta[$key] = stripslashes($value);
    return true;
}
function fixture_check($condition, $reason) {
    if (!$condition) {
        fwrite(STDERR, "FAIL: " . $reason . "\n");
        exit(1);
    }
}

$content = '<p>본문 \"인용\" \\ 경로</p>';
$expected = [
    'post_status' => 'draft', 'post_title' => '초안 \"제목\"',
    'post_name' => '', 'post_excerpt' => '개요',
    'content_sha256' => hash('sha256', $content),
];
$meta = [
    '_bloguito_permalink_scheme' => 'post-id-v1',
    'rank_math_focus_keyword' => '키워드 \"인용\" \\',
    'rank_math_title' => '제목 \"quotes\" \\',
    'rank_math_description' => '{\"a\": \"\\\\value\", \"b\": \"한국어\"}',
];
$cases = [
    'fresh' => 'ok',
    'replay_exact' => 'already_applied',
    'meta_partial' => 'meta_conflict',
    'meta_conflict' => 'meta_conflict',
    'body_drift' => 'cas_mismatch',
    'status_drift' => 'cas_mismatch',
    'title_drift' => 'cas_mismatch',
    'slug_drift' => 'cas_mismatch',
    'excerpt_drift' => 'cas_mismatch',
    'missing' => 'missing',
    'second_write_fails' => 'update_failed',
    'commit_unknown' => 'commit_ambiguous',
    'invalid_payload' => 'invalid_payload',
];

foreach ($cases as $name => $want) {
    $fixture_post = (object) [
        'ID' => 901,
        'post_status' => $expected['post_status'],
        'post_title' => $expected['post_title'],
        'post_name' => $expected['post_name'],
        'post_excerpt' => $expected['post_excerpt'],
        'post_content' => $content,
    ];
    $fixture_meta = [];
    $fixture_fail_key = null;
    $fixture_missing = false;
    $fixture_writes = 0;
    $fixture_queries = [];
    $fixture_commit_unknown = false;
    $payload = ['protocol' => 1, 'post_id' => 901, 'expected' => $expected, 'meta' => $meta];

    switch ($name) {
        case 'replay_exact': $fixture_meta = $meta; break;
        case 'meta_partial': $fixture_meta = ['rank_math_title' => $meta['rank_math_title']]; break;
        case 'meta_conflict': $fixture_meta = ['rank_math_title' => 'external editor value']; break;
        case 'body_drift': $fixture_post->post_content .= ' changed'; break;
        case 'status_drift': $fixture_post->post_status = 'publish'; break;
        case 'title_drift': $fixture_post->post_title .= ' changed'; break;
        case 'slug_drift': $fixture_post->post_name = 'new-slug'; break;
        case 'excerpt_drift': $fixture_post->post_excerpt .= ' changed'; break;
        case 'missing': $fixture_missing = true; break;
        case 'second_write_fails': $fixture_fail_key = 'rank_math_focus_keyword'; break;
        case 'commit_unknown': $fixture_commit_unknown = true; break;
        case 'invalid_payload': $payload['meta']['unknown_key'] = 'forbidden'; break;
    }
    $initial = $fixture_meta;
    $GLOBALS['fixture_stdin'] = json_encode($payload, JSON_UNESCAPED_UNICODE);
    ob_start();
    eval($script);
    $response = json_decode(ob_get_clean(), true);
    fixture_check(is_array($response) && ($response['status'] ?? null) === $want,
        "$name: expected $want, got " . json_encode($response));
    if ($name === 'fresh' || $name === 'replay_exact') {
        fixture_check(($response['saved_meta'] ?? null) === $meta, "$name: exact slashed metadata roundtrip");
        fixture_check($fixture_meta === $meta, "$name: final metadata differs");
    }
    if ($name === 'second_write_fails') {
        fixture_check($fixture_meta === $initial, 'write failure rolled back first metadata key');
        fixture_check($fixture_writes === 2, 'failure must exercise partial-write rollback');
    }
    if (!in_array($name, ['fresh', 'commit_unknown', 'second_write_fails'], true)) {
        fixture_check($fixture_meta === $initial && $fixture_writes === 0,
            "$name: rejected update modified metadata");
    }
    if ($name !== 'invalid_payload') {
        fixture_check(in_array('START TRANSACTION', $fixture_queries, true),
            "$name: transaction missing");
        fixture_check(count(array_filter($fixture_queries,
            fn($q) => strpos($q, 'FOR UPDATE') !== false)) >= ($name === 'missing' ? 1 : 2),
            "$name: expected row locks missing");
    }
    echo "PASS: $name\n";
}
