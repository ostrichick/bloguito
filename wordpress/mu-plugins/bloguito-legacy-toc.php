<?php
/**
 * Plugin Name: Bloguito Legacy Article TOC
 * Description: Adds a compact table of contents to eligible existing articles at render time.
 * Version: 1.0.0
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * These were the 25 published articles without a native TOC on 2026-09-22.
 * Keeping an allowlist prevents changes to new articles or unrelated post types.
 */
function bloguito_legacy_toc_allowed_ids() {
    return array(55, 63, 70, 77, 79, 81, 85, 99, 101, 103, 105, 113, 119,
        121, 125, 127, 137, 139, 140, 144, 145, 163, 217, 219, 220);
}

/**
 * Pure renderer: no post metadata or saved post_content is ever updated.
 * Original headings and their IDs are preserved except for missing IDs in #85.
 */
function bloguito_legacy_toc_build($content, $post_id) {
    if (!in_array((int) $post_id, bloguito_legacy_toc_allowed_ids(), true)
        || strpos($content, 'bloguito-article') !== false
        || preg_match('~(?:bloguito-toc|bloguito-legacy-toc|lwptoc|ez-toc-container|\[lwptoc\])~i', $content)) {
        return $content;
    }

    $plain = trim(preg_replace('/\s+/u', ' ', wp_strip_all_tags($content)));
    // Unicode code points, independent of optional mbstring and Korean UTF-8 byte length.
    if (preg_match_all('/./us', $plain) < 700) {
        return $content;
    }

    if (!preg_match_all('~<h2\b([^>]*)>(.*?)</h2\s*>~is', $content, $headings,
        PREG_SET_ORDER | PREG_OFFSET_CAPTURE)) {
        return $content;
    }

    // #85's first h2 sits inside its opening summary card, not the article outline.
    // Fail closed when this known structural landmark has changed during an edit.
    if ((int) $post_id === 85) {
        if (count($headings) !== 6
            || trim(wp_strip_all_tags($headings[0][2][0])) !== '먼저 기억할 세 가지') {
            return $content;
        }
        $headings = array_slice($headings, 1);
    }

    $items = array();
    $insertions = array();
    $seen = array();
    $first_offset = null;
    foreach ($headings as $position => $heading) {
        $markup = $heading[0][0];
        $attrs = $heading[1][0];
        $label = trim(html_entity_decode(wp_strip_all_tags($heading[2][0]), ENT_QUOTES | ENT_HTML5, 'UTF-8'));
        if ($label === '') {
            continue;
        }

        if (preg_match('~(?:^|\s)id\s*=\s*(["\'])(.*?)\1~is', $attrs, $id_match)) {
            $id = $id_match[2];
        } elseif ((int) $post_id === 85) {
            $id = 'bloguito-legacy-85-' . ($position + 1);
            // A manually added element with this ID would make an anchor ambiguous.
            if (preg_match('~\bid\s*=\s*["\']' . preg_quote($id, '~') . '["\']~i', $content)) {
                return $content;
            }
            $insertions[] = array($heading[0][1], strlen($markup),
                preg_replace('~^<h2\b~i', '<h2 id="' . esc_attr($id) . '"', $markup, 1));
        } else {
            // Other legacy posts already have audited body anchors. Never invent
            // anchors for unreviewed FAQ, source lists or future layouts.
            continue;
        }

        if (!preg_match('/\A[A-Za-z][A-Za-z0-9_-]*\z/D', $id) || isset($seen[$id])) {
            return $content;
        }
        $seen[$id] = true;
        if ($first_offset === null) {
            $first_offset = $heading[0][1];
        }
        $items[] = '<li style="margin:6px 0"><a href="#' . esc_attr($id)
            . '" style="color:#0d7d59;text-decoration:none;font-weight:500">'
            . esc_html($label) . '</a></li>';
    }

    if (count($items) < 3 || $first_offset === null) {
        return $content;
    }

    // Replace only #85 heading start tags in reverse offset order. All source
    // text, tables and existing anchors remain byte-for-byte intact otherwise.
    for ($i = count($insertions) - 1; $i >= 0; $i--) {
        $old_offset = $insertions[$i][0];
        $content = substr_replace($content, $insertions[$i][2], $old_offset,
            $insertions[$i][1]);
    }

    $nav = '<nav class="bloguito-legacy-toc" aria-label="본문 목차" '
        . 'style="padding:16px 20px;margin:20px 0 28px;background:#f8fafc;'
        . 'border:1px solid #e2e8f0;border-left:4px solid #0d7d59;border-radius:8px">'
        . '<div style="font-size:16px;font-weight:700;color:#1e293b;margin-bottom:8px">목차</div>'
        . '<ul style="margin:0;padding-left:22px;line-height:1.75;font-size:15px">'
        . implode('', $items) . '</ul></nav>';
    return substr_replace($content, $nav, $first_offset, 0);
}

function bloguito_legacy_toc_filter($content) {
    if (is_admin() || !is_singular('post') || !is_main_query() || !in_the_loop()
        || is_feed() || (defined('REST_REQUEST') && REST_REQUEST)) {
        return $content;
    }
    $post_id = get_the_ID();
    if ((int) $post_id !== (int) get_queried_object_id()
        || get_post_status($post_id) !== 'publish') {
        return $content;
    }
    return bloguito_legacy_toc_build($content, $post_id);
}
add_filter('the_content', 'bloguito_legacy_toc_filter', 99);
