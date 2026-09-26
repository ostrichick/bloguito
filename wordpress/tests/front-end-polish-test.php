<?php
/** Standalone regression test: php wordpress/tests/front-end-polish-test.php */
define('ABSPATH', __DIR__ . '/');

$registered_filters = [];
$published_timestamp = 100;
$modified_timestamp = 2000;

function add_filter($hook, $callback, $priority = 10, $accepted_args = 1) {
    global $registered_filters;
    $registered_filters[$hook] = [$callback, $priority, $accepted_args];
}
function check($condition, $message) {
    if (!$condition) {
        fwrite(STDERR, "FAIL: $message\n");
        exit(1);
    }
}
function get_the_time($format = '') {
    global $published_timestamp;
    return $format === 'U' ? $published_timestamp : '오전 9:00';
}
function get_the_modified_time($format = '') {
    global $modified_timestamp;
    return $format === 'U' ? $modified_timestamp : '오전 10:00';
}
function get_the_modified_date($format = '') {
    return $format === 'c' ? '2026-09-25T10:00:00+09:00' : '2026년 9월 25일';
}
function get_the_date($format = '') {
    return $format === 'c' ? '2026-09-24T09:00:00+09:00' : '2026년 9월 24일';
}
function generate_get_schema_type() { return 'microdata'; }
function esc_attr($value) { return htmlspecialchars($value, ENT_QUOTES, 'UTF-8'); }
function esc_html($value) { return htmlspecialchars($value, ENT_QUOTES, 'UTF-8'); }

require dirname(__DIR__) . '/mu-plugins/bloguito-front-end-polish.php';

check(isset($registered_filters['generate_post_date_output']), 'GeneratePress date filter registered');
check($registered_filters['generate_post_date_output'][2] === 2, 'Date filter accepts theme arguments');
check(isset($registered_filters['generate_show_tags']), 'GeneratePress tag-display filter registered');

$theme_time = '<time class="updated">old updated</time><time class="entry-date published">old published</time>';
$theme_output = '<span class="posted-on">prefix ' . $theme_time . '</span> ';
$modified = bloguito_render_single_visible_post_date($theme_output, $theme_time);
check(strpos($modified, '업데이트') !== false, 'Modified posts show an update label');
check(strpos($modified, 'dateModified') !== false, 'Modified posts preserve dateModified schema');
check(strpos($modified, '2026년 9월 25일') !== false, 'Modified date is visible');
check(strpos($modified, '2026년 9월 24일') === false, 'Published date is not duplicated on modified posts');
check(strpos($modified, 'prefix ') !== false, 'GeneratePress wrapper content is preserved');

$modified_timestamp = 100;
$published = bloguito_render_single_visible_post_date($theme_output, $theme_time);
check(strpos($published, '발행') !== false, 'Unmodified posts show a publication label');
check(strpos($published, 'datePublished') !== false, 'Published posts preserve datePublished schema');
check(strpos($published, '2026년 9월 24일') !== false, 'Publication date is visible');

$modified_timestamp = 1900;
$near_publish = bloguito_render_single_visible_post_date($theme_output, $theme_time);
check(strpos($near_publish, '발행') !== false, 'Near-simultaneous metadata writes stay publication-labelled');

echo "PASS: front-end date and tag presentation\n";
