<?php
/** Read-only WordPress integration check: wp eval-file this-file.php --allow-root */

if (!defined('ABSPATH')) {
    exit(1);
}

$columns = apply_filters('manage_post_posts_columns', ['title' => 'Title', 'date' => 'Date'], 'post');
if (array_keys($columns) !== ['title', 'bloguito_post_id', 'date']) {
    fwrite(STDERR, "Post ID column missing or out of order\n");
    exit(1);
}

$ids = get_posts(['post_type' => 'post', 'post_status' => 'any', 'numberposts' => 1, 'fields' => 'ids']);
$id = $ids ? (int) $ids[0] : 243;
ob_start();
do_action('manage_post_posts_custom_column', 'bloguito_post_id', $id);
$rendered = ob_get_clean();
if ($rendered !== (string) $id) {
    fwrite(STDERR, "Post ID renderer returned an unexpected value\n");
    exit(1);
}

if (!has_action('admin_bar_menu', 'bloguito_add_post_id_admin_bar')) {
    fwrite(STDERR, "Post ID admin bar hook is not registered\n");
    exit(1);
}

$published_ids = get_posts([
    'post_type' => 'post',
    'post_status' => 'publish',
    'numberposts' => 1,
    'fields' => 'ids',
]);
if ($published_ids && is_user_logged_in()) {
    $published_id = (int) $published_ids[0];
    $original_query = $GLOBALS['wp_query'];
    $GLOBALS['wp_query'] = new WP_Query(['p' => $published_id, 'post_type' => 'post']);
    if (!class_exists('WP_Admin_Bar')) {
        require_once ABSPATH . WPINC . '/class-wp-admin-bar.php';
    }
    $admin_bar = new WP_Admin_Bar();
    bloguito_add_post_id_admin_bar($admin_bar);
    $node = $admin_bar->get_node('bloguito-post-id');
    $GLOBALS['wp_query'] = $original_query;
    if (!$node || wp_strip_all_tags($node->title) !== '글 ID: ' . $published_id) {
        fwrite(STDERR, "Post ID admin bar item did not render for a published post\n");
        exit(1);
    }
}

echo "PASS: live WordPress post ID column and admin bar hooks\n";
