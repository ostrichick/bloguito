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
if (!isset($draft_actions['bloguito-publish']) || strpos($draft_actions['bloguito-publish'], 'target=publish') === false) {
    fwrite(STDERR, 'Draft publish row action did not render as expected' . PHP_EOL);
    exit(1);
}

$published = clone $base;
$published->post_status = 'publish';
$published_actions = bloguito_add_post_status_row_action([], $published);
if (!isset($published_actions['bloguito-to-draft']) || strpos($published_actions['bloguito-to-draft'], 'target=draft') === false) {
    fwrite(STDERR, 'Published-to-draft row action did not render as expected' . PHP_EOL);
    exit(1);
}

echo 'PASS: live WordPress post row-action hooks' . PHP_EOL;
