<?php
/**
 * Plugin Name: Bloguito Front-end Polish
 * Description: Keep public metadata concise and polish the shared GeneratePress header.
 * Version: 1.1.0
 */

if (!defined('ABSPATH')) {
    exit;
}

// GeneratePress otherwise prints both the modified and published dates when a
// post changes. Show one clearly-labelled date: the modified date when it
// differs from publication, otherwise the publication date.
add_filter('generate_post_date_output', 'bloguito_render_single_visible_post_date', 10, 2);
function bloguito_render_single_visible_post_date($output, $time_string) {
    $published_timestamp = (int) get_the_time('U');
    $modified_timestamp = (int) get_the_modified_time('U');

    // Match GeneratePress 3.6.1's own updated-date threshold. Changes within
    // 30 minutes of publication are treated as the original publication.
    if ($modified_timestamp > ($published_timestamp + 1800)) {
        $label = '업데이트';
        $datetime = get_the_modified_date('c');
        $display = get_the_modified_date();
        $itemprop = 'dateModified';
        $class = 'entry-date updated-date';
    } else {
        $label = '발행';
        $datetime = get_the_date('c');
        $display = get_the_date();
        $itemprop = 'datePublished';
        $class = 'entry-date published';
    }

    $schema_attribute = (
        function_exists('generate_get_schema_type')
        && 'microdata' === generate_get_schema_type()
    ) ? ' itemprop="' . esc_attr($itemprop) . '"' : '';

    $time = sprintf(
        '<time class="%1$s" datetime="%2$s"%3$s><span class="bloguito-date-label">%4$s</span> %5$s</time>',
        esc_attr($class),
        esc_attr($datetime),
        $schema_attribute,
        esc_html($label),
        esc_html($display)
    );

    // Replace only the date fragment GeneratePress passes to this filter so
    // its wrapper, optional date link and inside-meta hook remain untouched.
    return str_replace($time_string, $time, $output);
}

// Legacy posts accumulated hundreds of mostly one-off tags. Tag archives are
// already noindex; keep categories visible and remove the tag cloud from the
// public post-card/footer UI without deleting any taxonomy data.
add_filter('generate_show_tags', '__return_false');

// Keep the long site name readable without changing the WordPress blogname
// used by metadata and SEO. GeneratePress exposes only the rendered header
// title through this filter, so the visual split stays presentation-only.
add_filter('generate_site_title_output', 'bloguito_format_site_title_output');
function bloguito_format_site_title_output($output) {
    $name = get_bloginfo('name');
    $parts = preg_split('/\s*\|\s*/u', $name, 2);
    if (count($parts) !== 2 || trim($parts[0]) === '' || trim($parts[1]) === '') {
        return $output;
    }

    $title_markup = sprintf(
        '<span class="bloguito-site-title-brand">%1$s <span class="bloguito-site-title-separator" aria-hidden="true">|</span></span><span class="bloguito-site-title-tagline">%2$s</span>',
        esc_html(trim($parts[0])),
        esc_html(trim($parts[1]))
    );

    return preg_replace(
        '/(<a\b[^>]*>).*?(<\/a>)/su',
        '$1' . $title_markup . '$2',
        $output,
        1
    );
}

// The About page remains in the footer. Remove only its duplicate entry from
// the GeneratePress primary menu, leaving other menus and the page itself intact.
add_filter('wp_nav_menu_objects', 'bloguito_remove_primary_about_menu_item', 10, 2);
function bloguito_remove_primary_about_menu_item($items, $args) {
    if (!isset($args->theme_location) || 'primary' !== $args->theme_location) {
        return $items;
    }

    return array_values(array_filter($items, function ($item) {
        if (!is_object($item)) {
            return true;
        }

        $path = isset($item->url) ? wp_parse_url($item->url, PHP_URL_PATH) : '';
        $title = isset($item->title) ? trim(wp_strip_all_tags($item->title)) : '';
        return '/about' !== untrailingslashit((string) $path) && '사이트 소개' !== $title;
    }));
}

add_action('wp_head', 'bloguito_header_polish_styles', 26);
function bloguito_header_polish_styles() {
    ?>
    <style id="bloguito-header-polish">
        .site-branding .main-title > a {
            display: inline-flex;
            flex-direction: column;
            align-items: flex-start;
            line-height: 1.15;
        }
        .bloguito-site-title-brand {
            white-space: nowrap;
        }
        .bloguito-site-title-tagline {
            display: block;
            margin-top: 4px;
            font-size: 0.64em;
            font-weight: 600;
            line-height: 1.35;
            white-space: normal;
        }
        @media (max-width: 768px) {
            .bloguito-site-title-tagline {
                font-size: 0.6em;
            }
        }
    </style>
    <?php
}
