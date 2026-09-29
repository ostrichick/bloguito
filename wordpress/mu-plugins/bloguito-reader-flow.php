<?php
/**
 * Plugin Name: Bloguito Reader Flow
 * Description: Keep the first answer close to the title and prioritize reviewed next-reading links.
 * Version: 1.1.1
 */

if (!defined('ABSPATH')) {
    exit;
}

add_action('wp_head', 'bloguito_reader_flow_styles', 25);
function bloguito_reader_flow_styles() {
    if (!is_singular('post')) {
        return;
    }
    ?>
    <style id="bloguito-reader-flow">
        /* Preserve the whole cover, including text; do not crop it. Archive
           thumbnails keep their existing layout. */
        .single-post .inside-article .post-image,
        .single-post .inside-article .featured-image {
            margin-top: 0;
            margin-bottom: 16px;
        }
        .single-post .inside-article .post-image img,
        .single-post .inside-article .featured-image img {
            width: auto;
            height: auto;
            max-width: 100%;
            max-height: 200px;
            object-fit: contain;
        }
        .single-post .entry-title {
            font-size: clamp(26px, 3vw, 34px);
            line-height: 1.4;
            overflow-wrap: anywhere;
        }
        .single-post .entry-content {
            margin-top: 16px;
        }
        .single-post .bloguito-top-share {
            margin: 0 0 12px !important;
        }
        @media (min-width: 1025px) {
            .single-post .inside-article .post-image img,
            .single-post .inside-article .featured-image img {
                max-height: 420px;
            }
        }
        @media (max-width: 768px) {
            .single-post .inside-article {
                padding: 20px;
            }
            .single-post .inside-article .post-image img,
            .single-post .inside-article .featured-image img {
                display: block;
                width: 100%;
                max-width: 100%;
                height: auto;
                max-height: none;
            }
            .single-post .entry-title {
                font-size: 26px;
            }
        }
    </style>
    <?php
}

// A reviewed related-reading block is more useful than chronological links
// to unrelated posts. Keep the theme fallback on posts without that block.
add_filter('generate_show_post_navigation', 'bloguito_reader_flow_navigation');
function bloguito_reader_flow_navigation($show) {
    if (!is_singular('post')) {
        return $show;
    }
    $post = get_post();
    if ($post && preg_match('/class=["\'][^"\']*\bbloguito-interlink\b/', $post->post_content)) {
        return false;
    }
    return $show;
}
