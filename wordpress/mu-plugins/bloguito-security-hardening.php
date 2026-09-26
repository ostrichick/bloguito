<?php
/**
 * Plugin Name: Bloguito Security Hardening
 * Description: Low-risk security defaults for public enumeration and legacy WordPress attack surfaces.
 * Version: 1.0.0
 */

if (!defined('ABSPATH')) {
    exit;
}

// XML-RPC is not used by Bloguito. Keep it disabled at the application layer
// even though the public endpoint is also blocked upstream.
add_filter('xmlrpc_enabled', '__return_false');

// Do not advertise the WordPress version in generator metadata or feeds.
remove_action('wp_head', 'wp_generator');
add_filter('the_generator', '__return_empty_string');

// Bloguito has a single administrative author and does not use public author
// discovery. Hide the REST users collection from unauthenticated visitors while
// leaving it available to logged-in administrators and the editor UI.
add_filter('rest_pre_dispatch', 'bloguito_block_public_rest_user_enumeration', 10, 3);
function bloguito_block_public_rest_user_enumeration($result, $server, $request) {
    if (is_user_logged_in()) {
        return $result;
    }

    $route = $request->get_route();
    if (preg_match('#^/wp/v2/users(?:/|$)#', $route)) {
        return new WP_Error(
            'rest_not_found',
            'Not found.',
            ['status' => 404]
        );
    }

    return $result;
}

// Do not publish a core user sitemap for the single administrator account.
add_filter('wp_sitemaps_add_provider', 'bloguito_disable_public_user_sitemap', 10, 2);
function bloguito_disable_public_user_sitemap($provider, $name) {
    if ($name === 'users') {
        return false;
    }
    return $provider;
}
