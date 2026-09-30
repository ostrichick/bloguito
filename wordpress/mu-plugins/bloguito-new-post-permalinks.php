<?php
/**
 * Plugin Name: Bloguito New Post Permalinks
 * Description: Keeps legacy post URLs unchanged while explicitly marked new posts use /post-id/short-slug/.
 * Version: 1.0.0
 */

if (!defined('ABSPATH')) {
    exit;
}

define('BLOGUITO_PERMALINK_META', '_bloguito_permalink_scheme');
define('BLOGUITO_PERMALINK_SCHEME', 'id-slug-v1');

function bloguito_uses_id_slug_permalink($post) {
    return $post instanceof WP_Post
        && $post->post_type === 'post'
        && get_post_meta($post->ID, BLOGUITO_PERMALINK_META, true) === BLOGUITO_PERMALINK_SCHEME;
}

add_filter('post_link', 'bloguito_new_post_permalink', 10, 3);
function bloguito_new_post_permalink($permalink, $post, $leavename) {
    if (!bloguito_uses_id_slug_permalink($post) || $post->post_name === '') {
        return $permalink;
    }
    $slug = $leavename ? '%postname%' : $post->post_name;
    return home_url(user_trailingslashit($post->ID . '/' . $slug));
}

add_action('init', 'bloguito_register_id_slug_rewrite');
function bloguito_register_id_slug_rewrite() {
    add_rewrite_rule(
        '^([1-9][0-9]*)/([a-z0-9]+(?:-[a-z0-9]+)*)/?$',
        'index.php?p=$matches[1]&bloguito_id_slug=1&bloguito_slug=$matches[2]',
        'top'
    );
}

add_filter('query_vars', 'bloguito_id_slug_query_vars');
function bloguito_id_slug_query_vars($vars) {
    $vars[] = 'bloguito_id_slug';
    $vars[] = 'bloguito_slug';
    return $vars;
}

add_action('template_redirect', 'bloguito_validate_id_slug_request', 1);
function bloguito_validate_id_slug_request() {
    if ((string) get_query_var('bloguito_id_slug') !== '1') {
        return;
    }
    $post = get_queried_object();
    if (!bloguito_uses_id_slug_permalink($post)) {
        global $wp_query;
        $wp_query->set_404();
        status_header(404);
        nocache_headers();
        return;
    }
    if ((string) get_query_var('bloguito_slug') !== (string) $post->post_name) {
        wp_safe_redirect(get_permalink($post), 301, 'Bloguito');
        exit;
    }
}
