<?php
/** Read-only WordPress integration check: wp eval-file this-file.php --allow-root */

if (!defined('ABSPATH')) {
    exit(1);
}

if (!has_filter('post_row_actions', 'bloguito_add_post_status_row_action')) {
    fwrite(STDERR, 'Post status row-action filter is not registered' . PHP_EOL);
    exit(1);
}
if (!has_action('admin_post_bloguito_set_post_status', 'bloguito_handle_post_status_action')) {
    fwrite(STDERR, 'Guarded post-status handler is not registered' . PHP_EOL);
    exit(1);
}
if (!has_action('admin_bar_menu', 'bloguito_add_preview_publish_admin_bar')) {
    fwrite(STDERR, 'Draft preview publish admin-bar hook is not registered' . PHP_EOL);
    exit(1);
}
if (!has_filter('wp_insert_post_data', 'bloguito_guard_publish_transition')) {
    fwrite(STDERR, 'Global publish transition gate is not registered' . PHP_EOL);
    exit(1);
}
if (!has_action('transition_post_status', 'bloguito_consume_publish_attestation')) {
    fwrite(STDERR, 'Publish attestation consumption hook is not registered' . PHP_EOL);
    exit(1);
}
if (!has_filter('query', 'bloguito_guard_unguarded_publish_sql')) {
    fwrite(STDERR, 'Direct publish SQL guard is not registered' . PHP_EOL);
    exit(1);
}

$new_publish = bloguito_guard_publish_transition([
    'post_type' => 'post',
    'post_status' => 'publish',
], [], [], false);
if (($new_publish['post_status'] ?? '') !== 'draft') {
    fwrite(STDERR, 'New direct publish creation is not forced to draft' . PHP_EOL);
    exit(1);
}
$new_future = bloguito_guard_publish_transition([
    'post_type' => 'post',
    'post_status' => 'future',
], [], [], false);
if (($new_future['post_status'] ?? '') !== 'draft') {
    fwrite(STDERR, 'New native future scheduling is not forced to draft' . PHP_EOL);
    exit(1);
}

$admins = get_users(['role' => 'administrator', 'number' => 1, 'fields' => 'ID']);
if (!$admins) {
    fwrite(STDERR, 'No administrator account is available for capability smoke test' . PHP_EOL);
    exit(1);
}
wp_set_current_user((int) $admins[0]);

$ids = get_posts([
    'post_type' => 'post',
    'post_status' => 'any',
    'numberposts' => 1,
    'fields' => 'ids',
]);
if (!$ids) {
    fwrite(STDERR, 'No post is available for row-action smoke test' . PHP_EOL);
    exit(1);
}

$post_id = (int) $ids[0];
$base = get_post($post_id);
$draft = clone $base;
$draft->post_status = 'draft';
$draft_actions = bloguito_add_post_status_row_action([], $draft);
$publishable = bloguito_validate_publishability($post_id) === true;
$has_publish_action = isset($draft_actions['bloguito-publish']);
if ($publishable !== $has_publish_action) {
    fwrite(STDERR, 'Draft publish row action does not match publish gate state' . PHP_EOL);
    exit(1);
}
if ($has_publish_action && strpos($draft_actions['bloguito-publish'], 'target=publish') === false) {
    fwrite(STDERR, 'Publishable draft row action has the wrong target' . PHP_EOL);
    exit(1);
}

$published = clone $base;
$published->post_status = 'publish';
$published_actions = bloguito_add_post_status_row_action([], $published);
if (!isset($published_actions['bloguito-to-draft']) || strpos($published_actions['bloguito-to-draft'], 'target=draft') === false) {
    fwrite(STDERR, 'Published-to-draft row action did not render as expected' . PHP_EOL);
    exit(1);
}

$preview_publish_url = bloguito_post_status_action_url($post_id, 'publish', 'permalink');
$query = [];
parse_str((string) wp_parse_url($preview_publish_url, PHP_URL_QUERY), $query);
if (($query['action'] ?? '') !== 'bloguito_set_post_status'
        || (int) ($query['post'] ?? 0) !== $post_id
        || ($query['target'] ?? '') !== 'publish'
        || ($query['bloguito_return'] ?? '') !== 'permalink'
        || !isset($query['_bloguito_nonce'])
        || !wp_verify_nonce(
            $query['_bloguito_nonce'],
            bloguito_post_status_nonce_action($post_id, 'publish')
        )) {
    fwrite(STDERR, 'Preview publish URL is missing guarded publish parameters' . PHP_EOL);
    exit(1);
}

echo 'PASS: live WordPress post row-action and preview publish hooks' . PHP_EOL;
