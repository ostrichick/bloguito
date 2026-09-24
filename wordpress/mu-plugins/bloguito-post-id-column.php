<?php
/**
 * Plugin Name: Bloguito Post ID Column
 * Description: Show the WordPress post ID and last modified time in the Posts list, plus the post ID in the front-end admin bar.
 * Version: 1.2.0
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
