<?php
/**
 * Plugin Name: Bloguito Legacy Callout Spacing
 * Description: Keep the original green answer boxes vertically balanced.
 * Version: 1.0.0
 */

if (!defined('ABSPATH')) {
    exit;
}

add_action('wp_head', 'bloguito_output_legacy_callout_spacing', 20);
function bloguito_output_legacy_callout_spacing() {
    if (!is_singular('post')) {
        return;
    }
    ?>
    <style id="bloguito-legacy-callout-spacing">
        /* WordPress wpautop leaves an orphan </p> after legacy inline headings.
           HTML parsing turns it into an empty paragraph inside the card. */
        .entry-content div[style*="border-left"][style*="#11775a"] > p:empty {
            display: none;
        }

        /* GeneratePress otherwise adds 1.5em below the final paragraph. */
        .entry-content div[style*="border-left"][style*="#11775a"] > p {
            margin-top: 8px;
            margin-bottom: 0;
        }
    </style>
    <?php
}
