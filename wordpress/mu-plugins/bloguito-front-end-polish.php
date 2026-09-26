<?php
/**
 * Plugin Name: Bloguito Front-end Polish
 * Description: Keep public post metadata concise and reduce low-value tag clutter.
 * Version: 1.0.0
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
