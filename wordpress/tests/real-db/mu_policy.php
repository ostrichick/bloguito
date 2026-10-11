<?php
/** Real WordPress bootstrap, isolated test post + a 1px synthetic attachment. */
if (!defined('WP_CLI') || !WP_CLI) {
    throw new RuntimeException('This integration fixture only runs in WP-CLI');
}
require_once '/bloguito/wordpress/mu-plugins/bloguito-post-row-actions.php';

$post_id = (int) ($args[0] ?? 0);
$post = get_post($post_id);
if (!$post || $post->post_status !== 'draft') {
    throw new RuntimeException('Expected isolated draft');
}
$dir = wp_upload_dir();
if (!wp_mkdir_p($dir['basedir'])) {
    throw new RuntimeException('Cannot create ephemeral fixture directory');
}
$fixture = $dir['basedir'] . '/bloguito-ci-fixture-' . $post_id . '.png';
// Fixed, tiny test bitmap, used solely inside ephemeral CI WordPress storage.
$bytes = base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==');
if (file_put_contents($fixture, $bytes) !== strlen($bytes)) {
    throw new RuntimeException('Fixture write failed');
}
$attachment_id = wp_insert_attachment([
    'post_mime_type' => 'image/png',
    'post_title' => 'Bloguito CI isolated fixture',
    'post_status' => 'inherit',
], $fixture, $post_id, true);
if (is_wp_error($attachment_id)) {
    throw new RuntimeException('Fixture attachment failed: ' . $attachment_id->get_error_message());
}
$alt = 'CI only image';
update_post_meta($attachment_id, '_wp_attachment_image_alt', $alt);
update_post_meta($post_id, '_thumbnail_id', $attachment_id);
$gate = [
    'version' => 1,
    'post_id' => $post_id,
    'content_sha256' => hash('sha256', $post->post_content),
    'review_digest' => str_repeat('a', 64),
    'title_sha256' => hash('sha256', $post->post_title),
    'thumbnail_id' => $attachment_id,
    'image_sha256' => hash_file('sha256', $fixture),
    'alt_text_sha256' => hash('sha256', $alt),
    'approval_kind' => 'manual_user_selected',
    'approval_evidence_sha256' => str_repeat('b', 64),
    'expires_at_gmt' => '2099-01-01T00:00:00Z',
    'requires_live_state' => false,
];
$assert = static function ($valid, $label) {
    if (!$valid) {
        throw new RuntimeException('MU policy integration failed: ' . $label);
    }
    echo 'PASS: ' . $label . PHP_EOL;
};
$validate = static function ($candidate) use ($post_id) {
    update_post_meta($post_id, BLOGUITO_PUBLISH_GATE_META_KEY, wp_slash(wp_json_encode($candidate)));
    return bloguito_validate_publishability($post_id, null, null, true);
};
$assert($validate($gate) === true, 'manual user approval');
$gate['approval_kind'] = 'manual_agent_delegated';
$assert($validate($gate) === true, 'delegated approval with valid binding');
$gate['content_sha256'] = hash('sha256', 'wrong content');
$error = $validate($gate);
$assert(is_wp_error($error) && $error->get_error_code() === 'bloguito_publish_gate_content_changed',
    'delegated approval does not override content CAS');
$gate['content_sha256'] = hash('sha256', $post->post_content);
$gate['approval_evidence_sha256'] = 'malformed';
$assert(is_wp_error($validate($gate)), 'delegated approval evidence format');
$gate['approval_evidence_sha256'] = str_repeat('b', 64);
$gate['approval_kind'] = 'agent-delegated';
$assert(is_wp_error($validate($gate)), 'unnormalized selection kind refused');
$assert(get_post_status($post_id) === 'draft', 'policy checks never publish');
echo 'PASS: real WordPress MU policy checks' . PHP_EOL;
