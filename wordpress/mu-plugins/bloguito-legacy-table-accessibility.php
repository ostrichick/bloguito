<?php
/**
 * Plugin Name: Bloguito Legacy #85 Table Accessibility
 * Description: Render-only accessible tables for the two verified legacy tables in public post #85.
 * Version: 1.0.0
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Both fingerprints must match the same captured version of #85, in order.
 * WordPress's saved HTML and the_content's wpautop output differ in whitespace.
 * A change to either table disables the whole operation; no content is saved.
 */
function bloguito_legacy_table85_fingerprints() {
    return array(
        array(
            '146468626b5bfdc3bdae081855cbb008494c7e44117848ae08c147f79e5ee0e9',
            '3dc660a032b59af2246a6788a449f1fd47b281be147163edaa9ed3ba2f308179',
        ),
        array(
            '3c92963213015e846630e6d0ed6abd502c9f7c785553983f9ede9225a2027ce5',
            '05611f42784ec0028656b3f252f3adc5438ecdd456bb43ad5ec712351fe11228',
        ),
    );
}

/**
 * The five accepted strings are: verified saved and REST-rendered HTML,
 * those strings after the separately reviewed TOC at 99, and the exact
 * production the_content at 99 captured before this filter. Any other
 * content version disables the whole table patch.
 */
function bloguito_legacy_table85_content_fingerprints() {
    return array(
        '499afcf30df2cfbfdca7041e80bc139c90e1a8da5d5348837b77ee2b8e2cf065',
        '9791443dbf4c5c9f43236c034bb4e321f8dc14cc69fed44b7710d7b98cbe644a',
        'e0ad7f771dddda46b20d1888ef928c7c9e64855e7a3814b63372e18eed5b277f',
        '0b5ae88f3a60e5a7958806f7e1861e8c8525ddbe94d47ba33d9f390118e375f3',
        // Exact live WordPress the_content after the legacy TOC, observed on 2026-09-22.
        '2024150df5e6258353c99376ea4b307a0206933b44ae891c9388a5ce324da9c9',
    );
}

/** Only structural tags are added; all original table cell text remains intact. */
function bloguito_legacy_table85_decorate($original, $caption, $expected_rows) {
    if (strpos($original, '<table>') !== 0 || strpos($original, '<caption') !== false
        || strpos($original, 'scope=') !== false) {
        return null;
    }

    $table = str_replace(
        '<th>',
        '<th scope="col" style="padding:10px;border-bottom:2px solid #cbd5e1;text-align:left">',
        $original,
        $columns
    );
    if ($columns !== 3) {
        return null;
    }

    $table = preg_replace_callback(
        '~<tr>\s*<td>(.*?)</td>~s',
        function ($match) {
            return '<tr><th scope="row" style="padding:10px;border-bottom:1px solid #e2e8f0;'
                . 'text-align:left;font-weight:700">' . $match[1] . '</th>';
        },
        $table,
        -1,
        $rows
    );
    if ($table === null || $rows !== $expected_rows) {
        return null;
    }
    $table = str_replace(
        '<td>',
        '<td style="padding:10px;border-bottom:1px solid #e2e8f0;vertical-align:top">',
        $table
    );
    $table = substr_replace(
        $table,
        '<table style="border-collapse:collapse;width:100%;min-width:580px;font-size:15px;'
            . 'line-height:1.6;overflow-wrap:anywhere;word-break:keep-all">'
            . '<caption style="text-align:left;font-weight:700;margin-bottom:8px">'
            . esc_html($caption) . '</caption>',
        0,
        strlen('<table>')
    );

    return '<p class="bloguito-table-hint" style="font-size:13px;color:#475569;margin:0 0 6px">'
        . '작은 화면에서는 표를 좌우로 밀어 확인할 수 있습니다.</p>'
        . '<div class="bloguito-info-table" role="region" aria-label="' . esc_attr($caption)
        . '" tabindex="0" style="overflow-x:auto;margin:8px 0 24px;max-width:100%">'
        . $table . '</div>';
}

/** Pure function: output-only, independent of the TOC and callout plugins. */
function bloguito_legacy_table85_build($content, $post_id) {
    if ((int) $post_id !== 85 || !is_string($content)
        || !in_array(hash('sha256', $content), bloguito_legacy_table85_content_fingerprints(), true)
        || strpos($content, 'bloguito-article') !== false
        || strpos($content, 'bloguito-info-table') !== false
        || strpos($content, 'bloguito-table-hint') !== false
        || strpos($content, '먼저 기억할 세 가지') === false
        || preg_match_all('~<h2\b~i', $content) !== 6) {
        return $content;
    }
    if (preg_match_all('~<table\b[^>]*>.*?</table\s*>~is', $content, $tables) !== 2) {
        return $content;
    }
    $observed = array(hash('sha256', $tables[0][0]), hash('sha256', $tables[0][1]));
    $matching = false;
    foreach (bloguito_legacy_table85_fingerprints() as $expected) {
        if ($observed === $expected) {
            $matching = true;
            break;
        }
    }
    if (!$matching || substr_count($content, $tables[0][0]) !== 1
        || substr_count($content, $tables[0][1]) !== 1) {
        return $content;
    }

    $labels = array('복지멤버십과 보조금24의 역할 및 활용 방법', '혜택 신청 전 확인 항목');
    $replacements = array();
    foreach ($tables[0] as $index => $table) {
        $replacement = bloguito_legacy_table85_decorate($table, $labels[$index], $index === 0 ? 2 : 5);
        if ($replacement === null) {
            return $content;
        }
        $replacements[] = $replacement;
    }

    // Construct both replacements before touching the output, and fail closed.
    $rendered = str_replace($tables[0], $replacements, $content, $count);
    return $count === 2 ? $rendered : $content;
}

function bloguito_legacy_table85_filter($content) {
    if (is_admin() || !is_singular('post') || !is_main_query() || !in_the_loop()
        || is_feed() || (defined('REST_REQUEST') && REST_REQUEST)) {
        return $content;
    }
    $post_id = get_the_ID();
    if ((int) $post_id !== 85 || (int) get_queried_object_id() !== 85
        || get_post_status($post_id) !== 'publish') {
        return $content;
    }
    return bloguito_legacy_table85_build($content, $post_id);
}

// Apply after the legacy TOC (priority 99); neither plugin modifies saved HTML.
add_filter('the_content', 'bloguito_legacy_table85_filter', 100);
