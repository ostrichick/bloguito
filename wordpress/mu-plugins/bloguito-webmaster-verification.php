<?php
/**
 * Plugin Name: Bloguito Webmaster Verification
 * Description: Persistent webmaster ownership verification tags.
 * Version: 1.0.0
 */
if (!defined('ABSPATH')) { exit; }

add_action('wp_head', 'bloguito_webmaster_verification_tags', 1);
function bloguito_webmaster_verification_tags() {
    if (!is_front_page() && !is_home()) {
        return;
    }
    echo '<meta name="msvalidate.01" content="821BAD262336BD5F65939DAA9684BFEE" />' . "\n";
}
