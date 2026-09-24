<?php
/**
 * Plugin Name: Bloguito Post ID Column
 * Description: Improve the Posts list with post ID, modified time, compact tags, readable widths and clear draft states, plus the post ID in the front-end admin bar.
 * Version: 1.4.1
 */

if (!defined('ABSPATH')) {
    exit;
}

// Only the built-in Posts list; do not change Pages or custom post types.
add_filter('manage_post_posts_columns', 'bloguito_add_post_id_column');
function bloguito_add_post_id_column($columns) {
    $result = [];
    foreach ($columns as $key => $label) {
        if ($key === 'author') {
            continue;
        }

        if ($key === 'tags') {
            $result['bloguito_tags'] = '태그';
            continue;
        }

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

    if ($column === 'bloguito_tags') {
        bloguito_render_compact_tags($post_id);
        return;
    }

    if ($column === 'bloguito_last_modified') {
        $modified = get_post_modified_time('Y/m/d H:i', false, $post_id, true);
        $modified_timestamp = get_post_modified_time('U', false, $post_id, true);
        if ($modified !== false && $modified_timestamp !== false) {
            $relative = human_time_diff((int) $modified_timestamp, (int) current_time('timestamp')) . ' 전';
            echo '<strong class="bloguito-modified-relative">' . esc_html($relative) . '</strong>';
            echo '<br><span class="bloguito-modified-exact">' . esc_html($modified) . '</span>';
        }
    }
}

function bloguito_render_compact_tags($post_id) {
    $terms = wp_get_post_terms($post_id, 'post_tag', [
        'orderby' => 'name',
        'order' => 'ASC',
    ]);

    if (is_wp_error($terms) || !$terms) {
        echo '—';
        return;
    }

    $visible_terms = array_slice($terms, 0, 2);
    $remaining = max(0, count($terms) - count($visible_terms));
    $all_names = implode(', ', array_map(static function ($term) {
        return $term->name;
    }, $terms));

    echo '<span class="bloguito-compact-tags" title="' . esc_attr($all_names) . '">';
    foreach ($visible_terms as $index => $term) {
        if ($index > 0) {
            echo ', ';
        }
        $url = add_query_arg([
            'post_type' => 'post',
            'tag' => $term->slug,
        ], admin_url('edit.php'));
        echo '<a href="' . esc_url($url) . '">' . esc_html($term->name) . '</a>';
    }
    if ($remaining > 0) {
        echo ' <span class="bloguito-tag-more">+' . (int) $remaining . '</span>';
    }
    echo '</span>';
}

add_filter('manage_edit-post_sortable_columns', 'bloguito_make_last_modified_sortable');
function bloguito_make_last_modified_sortable($columns) {
    $columns['bloguito_last_modified'] = 'modified';
    return $columns;
}

// Keep the title readable and make non-published work easy to spot at a glance.
// WordPress keeps its normal responsive list layout below desktop widths.
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
        .post-type-post .wp-list-table.posts .column-title { width: 30%; }
        .post-type-post .wp-list-table.posts .column-bloguito_post_id { width: 4%; }
        .post-type-post .wp-list-table.posts .column-categories { width: 9%; }
        .post-type-post .wp-list-table.posts .column-bloguito_tags { width: 9%; }
        .post-type-post .wp-list-table.posts .column-comments { width: 3%; }
        .post-type-post .wp-list-table.posts .column-date { width: 9%; }
        .post-type-post .wp-list-table.posts .column-bloguito_last_modified { width: 10%; }
        .post-type-post .wp-list-table.posts .column-wp-statistics-post-hits { width: 4%; }
        .post-type-post .wp-list-table.posts .column-rank_math_seo_details { width: 18%; }
    }

    .post-type-post .wp-list-table.posts .column-bloguito_tags {
        line-height: 1.45;
    }
    .post-type-post .wp-list-table.posts .column-rank_math_seo_details {
        line-height: 1.45;
        word-break: normal;
        overflow-wrap: anywhere;
    }
    .post-type-post .bloguito-tag-more {
        display: inline-block;
        margin-left: 2px;
        padding: 0 5px;
        border: 1px solid #c3c4c7;
        border-radius: 10px;
        background: #f6f7f7;
        color: #50575e;
        font-size: 11px;
        font-weight: 600;
        white-space: nowrap;
    }
    .post-type-post .bloguito-modified-relative {
        font-weight: 600;
    }
    .post-type-post .bloguito-modified-exact {
        color: #646970;
        font-size: 11px;
        white-space: nowrap;
    }

    .post-type-post .wp-list-table.posts tr.status-draft > th,
    .post-type-post .wp-list-table.posts tr.status-draft > td {
        background: #fff9e8;
    }
    .post-type-post .wp-list-table.posts tr.status-pending > th,
    .post-type-post .wp-list-table.posts tr.status-pending > td {
        background: #faf5ff;
    }
    .post-type-post .wp-list-table.posts tr.status-future > th,
    .post-type-post .wp-list-table.posts tr.status-future > td {
        background: #f0f7ff;
    }
    .post-type-post .wp-list-table.posts tr.status-draft .column-title strong,
    .post-type-post .wp-list-table.posts tr.status-pending .column-title strong,
    .post-type-post .wp-list-table.posts tr.status-future .column-title strong {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-start;
        gap: 5px;
        font-size: 0;
    }
    .post-type-post .wp-list-table.posts tr.status-draft .column-title strong > .row-title,
    .post-type-post .wp-list-table.posts tr.status-pending .column-title strong > .row-title,
    .post-type-post .wp-list-table.posts tr.status-future .column-title strong > .row-title {
        order: 2;
        font-size: 13px;
        line-height: 1.45;
    }
    .post-type-post .wp-list-table.posts tr.status-draft .column-title strong > .post-state,
    .post-type-post .wp-list-table.posts tr.status-pending .column-title strong > .post-state,
    .post-type-post .wp-list-table.posts tr.status-future .column-title strong > .post-state {
        order: 1;
        display: inline-block;
        padding: 1px 7px 2px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 700;
        line-height: 1.45;
        white-space: nowrap;
    }
    .post-type-post .wp-list-table.posts tr.status-draft .column-title strong > .post-state {
        border: 1px solid #dba617;
        background: #fef3c7;
        color: #7a4b00;
    }
    .post-type-post .wp-list-table.posts tr.status-pending .column-title strong > .post-state {
        border: 1px solid #a78bfa;
        background: #ede9fe;
        color: #5b21b6;
    }
    .post-type-post .wp-list-table.posts tr.status-future .column-title strong > .post-state {
        border: 1px solid #72aee6;
        background: #e7f3ff;
        color: #135e96;
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
