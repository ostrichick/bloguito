<?php
/**
 * Plugin Name: Bloguito Clarity Content Insights
 * Description: Mark single-post articles for Microsoft Clarity Content Insights without editing the theme.
 * Version: 1.0.0
 */

if (!defined('ABSPATH')) {
    exit;
}

add_filter('generate_article_microdata', 'bloguito_clarity_article_region');

function bloguito_clarity_article_region($microdata) {
    if (!is_singular('post') || !is_string($microdata)) {
        return $microdata;
    }

    if (strpos($microdata, 'data-clarity-region=') !== false) {
        return $microdata;
    }

    return rtrim($microdata) . ' data-clarity-region="article"';
}
