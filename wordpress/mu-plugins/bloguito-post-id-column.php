<?php
/**
 * Plugin Name: Bloguito Post ID Column
 * Description: Improve the Posts list with post ID, modified time, readable column widths, and the current post ID in the front-end admin bar.
 * Version: 1.3.0
 */

if (!defined('ABSPATH')) {
    exit;
}

// Only the built-in Posts list; do not change Pages or custom post types.
add_filter('manage_post_posts_columns', 'bloguito_add_post_id_column');
function bloguito_add_post_id_column($columns) {
    $result = [];
    foreach ($columns as $key => $label) {
        $result[$key] = $label;
        if ($key === 'title') {
            $result['bloguito_post_id'] = '글 ID';
        }
        if ($key === 'date') {
            $result['bloguito_last_modified'] = '마지막 수정';
        }
    }
    if (!isset($result['bloguito_post_id'])) {
        $result['bloguito_post_id'] = '글 ID';
    }
    if (!isset($result['bloguito_last_modified'])) {
        $result['bloguito_last_modified'] = '마지막 수정';
    }
    return $result;
}

add_action('manage_post_posts_custom_column', 'bloguito_render_post_id_column', 10, 2);
function bloguito_render_post_id_column($column, $post_id) {
    if ($column === 'bloguito_post_id') {
        echo (int) $post_id;
        return;
    }

    if ($column === 'bloguito_last_modified') {
        $modified = get_post_modified_time('Y/m/d H:i', false, $post_id, true);
        if ($modified !== false) {
            echo esc_html($modified);
        }
    }
}

add_filter('manage_edit-post_sortable_columns', 'bloguito_make_last_modified_sortable');
function bloguito_make_last_modified_sortable($columns) {
    $columns['bloguito_last_modified'] = 'modified';
    return $columns;
}

// Keep the title readable after adding ID, modified-time and statistics columns.
// Let WordPress use its normal responsive list layout below desktop widths.
add_action('admin_head-edit.php', 'bloguito_adjust_post_list_column_widths');
function bloguito_adjust_post_list_column_widths() {
    $screen = get_current_screen();
    if (!$screen || $screen->base !== 'edit' || $screen->post_type !== 'post') {
        return;
    }
    ?>
    <style id="bloguito-post-list-column-widths">
    @media screen and (min-width: 1100px) {
        .post-type-post .wp-list-table.posts {
            table-layout: fixed;
        }
        .post-type-post .wp-list-table.posts .column-title { width: 26%; }
        .post-type-post .wp-list-table.posts .column-bloguito_post_id { width: 4%; }
        .post-type-post .wp-list-table.posts .column-author { width: 8%; }
        .post-type-post .wp-list-table.posts .column-categories { width: 10%; }
        .post-type-post .wp-list-table.posts .column-tags { width: 19%; }
        .post-type-post .wp-list-table.posts .column-comments { width: 3%; }
        .post-type-post .wp-list-table.posts .column-date { width: 11%; }
        .post-type-post .wp-list-table.posts .column-bloguito_last_modified { width: 11%; }
        .post-type-post .wp-list-table.posts .column-wp-statistics-post-hits { width: 5%; }
    }
    </style>
    <?php
}

// Show the current post ID beside the built-in Edit Post item in the front-end admin bar.
add_action('admin_bar_menu', 'bloguito_add_post_id_admin_bar', 81);
function bloguito_add_post_id_admin_bar($wp_admin_bar) {
    if (is_admin() || !is_singular('post')) {
        return;
    }

    $post_id = (int) get_queried_object_id();
    if ($post_id <= 0 || !current_user_can('edit_post', $post_id)) {
        return;
    }

    $wp_admin_bar->add_node([
        'id' => 'bloguito-post-id',
        'title' => '글 ID: ' . $post_id,
        'meta' => [
            'title' => '현재 글 ID: ' . $post_id,
        ],
    ]);
}
