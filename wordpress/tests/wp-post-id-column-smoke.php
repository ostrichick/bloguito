<?php
/** Read-only WordPress integration check: wp eval-file this-file.php --allow-root */

if (!defined('ABSPATH')) {
    exit(1);
}

$columns = apply_filters('manage_post_posts_columns', [
    'title' => 'Title',
    'author' => 'Author',
    'categories' => 'Categories',
    'tags' => 'Tags',
    'date' => 'Date',
], 'post');
if (array_keys($columns) !== ['title', 'bloguito_post_id', 'categories', 'bloguito_tags', 'date', 'bloguito_last_modified']) {
    fwrite(STDERR, "Post list columns are missing or out of order\n");
    exit(1);
}
if (isset($columns['author']) || isset($columns['tags'])) {
    fwrite(STDERR, "Native author/tags columns were not replaced as expected\n");
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

ob_start();
do_action('manage_post_posts_custom_column', 'bloguito_last_modified', $id);
$modified = ob_get_clean();
if (strpos($modified, 'bloguito-modified-relative') === false || strpos($modified, 'bloguito-modified-exact') === false) {
    fwrite(STDERR, "Modified renderer did not include relative and exact times\n");
    exit(1);
}

$tagged_ids = get_posts([
    'post_type' => 'post',
    'post_status' => 'any',
    'numberposts' => 100,
    'fields' => 'ids',
]);
$compact_tags_checked = false;
foreach ($tagged_ids as $tagged_id) {
    $terms = wp_get_post_terms($tagged_id, 'post_tag');
    if (!is_wp_error($terms) && count($terms) >= 3) {
        ob_start();
        do_action('manage_post_posts_custom_column', 'bloguito_tags', $tagged_id);
        $tags = ob_get_clean();
        if (substr_count($tags, '<a ') !== 2 || strpos($tags, 'bloguito-tag-more') === false) {
            fwrite(STDERR, "Compact tag renderer did not show exactly two tags plus a remainder badge\n");
            exit(1);
        }
        $compact_tags_checked = true;
        break;
    }
}
if (!$compact_tags_checked) {
    fwrite(STDERR, "No post with at least three tags was available for the compact-tag smoke test\n");
    exit(1);
}

if (!has_action('admin_head-edit.php', 'bloguito_adjust_post_list_column_widths')) {
    fwrite(STDERR, "Post list CSS hook is not registered\n");
    exit(1);
}
set_current_screen('edit-post');
ob_start();
bloguito_adjust_post_list_column_widths();
$css = ob_get_clean();
if (strpos($css, '.column-title { width: 38%; }') === false || strpos($css, 'tr.status-draft') === false || strpos($css, 'tr.status-pending') === false || strpos($css, 'tr.status-future') === false || strpos($css, '.column-author') !== false) {
    fwrite(STDERR, "Live post-list CSS did not include the expected title/draft/author rules\n");
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

echo "PASS: live WordPress post list and admin bar hooks\n";
