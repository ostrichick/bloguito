<?php
/**
 * Plugin Name: Bloguito Post ID Permalinks
 * Description: New posts use /p/ID/ while legacy public posts keep their existing canonical URLs and expose /p/ID/ as a 301 compatibility route.
 * Version: 2.0.2
 */

if (!defined('ABSPATH')) {
    exit;
}

define('BLOGUITO_PERMALINK_META', '_bloguito_permalink_scheme');
define('BLOGUITO_PERMALINK_SCHEME', 'post-id-v1');

function bloguito_uses_post_id_permalink($post) {
    return $post instanceof WP_Post
        && $post->post_type === 'post'
        && get_post_meta($post->ID, BLOGUITO_PERMALINK_META, true) === BLOGUITO_PERMALINK_SCHEME;
}

add_filter('post_link', 'bloguito_post_id_permalink', 10, 3);
function bloguito_post_id_permalink($permalink, $post, $leavename) {
    if (!bloguito_uses_post_id_permalink($post)) {
        return $permalink;
    }
    return home_url(user_trailingslashit('p/' . $post->ID));
}

add_action('init', 'bloguito_register_post_id_rewrite');
function bloguito_register_post_id_rewrite() {
    add_rewrite_rule(
        '^p/([1-9][0-9]*)/?$',
        'index.php?p=$matches[1]&bloguito_post_id_route=1',
        'top'
    );
}

add_filter('query_vars', 'bloguito_post_id_query_vars');
function bloguito_post_id_query_vars($vars) {
    $vars[] = 'bloguito_post_id_route';
    return $vars;
}

function bloguito_mark_404() {
    global $wp_query;
    if ($wp_query) {
        $wp_query->set_404();
    }
    status_header(404);
    nocache_headers();
}

function bloguito_can_preview_post_id_route($post) {
    return bloguito_uses_post_id_permalink($post)
        && is_preview()
        && current_user_can('edit_post', $post->ID);
}

add_action('template_redirect', 'bloguito_reject_malformed_post_id_path', 0);
function bloguito_reject_malformed_post_id_path() {
    $uri = isset($_SERVER['REQUEST_URI']) ? (string) $_SERVER['REQUEST_URI'] : '';
    $path = parse_url($uri, PHP_URL_PATH);
    if (!is_string($path) || strpos($path, '/p/') !== 0) {
        return;
    }
    if (preg_match('#^/p/[1-9][0-9]*/?$#', $path)) {
        return;
    }

    remove_action('template_redirect', 'redirect_canonical');
    bloguito_mark_404();
}

add_action('template_redirect', 'bloguito_handle_post_id_request', 1);
function bloguito_handle_post_id_request() {
    if ((string) get_query_var('bloguito_post_id_route') !== '1') {
        return;
    }

    $post = get_queried_object();
    if (!($post instanceof WP_Post) || $post->post_type !== 'post') {
        bloguito_mark_404();
        return;
    }

    // Keep non-public posts private, while preserving WordPress's authenticated
    // preview flow for editors of new-policy posts.
    if ($post->post_status !== 'publish') {
        if (bloguito_can_preview_post_id_route($post)) {
            return;
        }
        bloguito_mark_404();
        return;
    }

    // New-policy posts own /p/ID/ as their canonical URL.
    if (bloguito_uses_post_id_permalink($post)) {
        return;
    }

    // Legacy public posts keep their original canonical URL. /p/ID/ is only a
    // stable compatibility address and never renders a duplicate 200 page.
    wp_safe_redirect(get_permalink($post), 301, 'Bloguito');
    exit;
}
