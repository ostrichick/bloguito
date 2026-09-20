<?php
/**
 * Plugin Name: Bloguito Post ID Column
 * Description: Show the WordPress post ID in the administrator's Posts list.
 * Version: 1.0.0
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
    }
    if (!isset($result['bloguito_post_id'])) {
        $result['bloguito_post_id'] = '글 ID';
    }
    return $result;
}

add_action('manage_post_posts_custom_column', 'bloguito_render_post_id_column', 10, 2);
function bloguito_render_post_id_column($column, $post_id) {
    if ($column === 'bloguito_post_id') {
        echo (int) $post_id;
    }
}
