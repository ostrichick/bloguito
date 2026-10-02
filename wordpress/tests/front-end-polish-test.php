<?php
/** Standalone regression test: php wordpress/tests/front-end-polish-test.php */
define('ABSPATH', __DIR__ . '/');

$registered_filters = [];
$registered_actions = [];
$published_timestamp = 100;
$modified_timestamp = 2000;

function add_filter($hook, $callback, $priority = 10, $accepted_args = 1) {
    global $registered_filters;
    $registered_filters[$hook] = [$callback, $priority, $accepted_args];
}
function add_action($hook, $callback, $priority = 10, $accepted_args = 1) {
    global $registered_actions;
    $registered_actions[$hook] = [$callback, $priority, $accepted_args];
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
function get_bloginfo($show = '') {
    return $show === 'name' ? '생활정보 24 | 정부 지원금, 절세, 복지 생활 백과' : '';
}
function wp_parse_url($url, $component = -1) { return parse_url($url, $component); }
function wp_strip_all_tags($value) { return strip_tags($value); }
function untrailingslashit($value) { return rtrim($value, '/\\'); }

require dirname(__DIR__) . '/mu-plugins/bloguito-front-end-polish.php';

check(isset($registered_filters['generate_post_date_output']), 'GeneratePress date filter registered');
check($registered_filters['generate_post_date_output'][2] === 2, 'Date filter accepts theme arguments');
check(isset($registered_filters['generate_show_tags']), 'GeneratePress tag-display filter registered');
check(isset($registered_filters['generate_site_title_output']), 'GeneratePress site-title filter registered');
check(isset($registered_filters['wp_nav_menu_objects']), 'Primary-menu filter registered');
check($registered_filters['wp_nav_menu_objects'][2] === 2, 'Menu filter accepts wp_nav_menu arguments');
check(isset($registered_actions['wp_head']), 'Header presentation styles registered');

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

$site_title = '<p class="main-title"><a href="https://lifeinfo24.org/" rel="home">생활정보 24 | 정부 지원금, 절세, 복지 생활 백과</a></p>';
$formatted_title = bloguito_format_site_title_output($site_title);
check(strpos($formatted_title, 'bloguito-site-title-brand') !== false, 'Header brand receives stable line wrapper');
check(strpos($formatted_title, 'bloguito-site-title-tagline') !== false, 'Header descriptor receives stable second line');
check(strpos($formatted_title, '생활정보 24') !== false, 'Header brand text is preserved');
check(strpos($formatted_title, '정부 지원금, 절세, 복지 생활 백과') !== false, 'Header descriptor text is preserved');

$menu_items = [
    (object) ['title' => '공연·콘서트 예매', 'url' => 'https://lifeinfo24.org/category/concert/'],
    (object) ['title' => '사이트 소개', 'url' => 'https://lifeinfo24.org/about/'],
    (object) ['title' => '정부 복지·지원금', 'url' => 'https://lifeinfo24.org/category/welfare/'],
];
$primary_args = (object) ['theme_location' => 'primary'];
$primary_menu = bloguito_remove_primary_about_menu_item($menu_items, $primary_args);
check(count($primary_menu) === 2, 'Duplicate About item is removed from primary menu');
check($primary_menu[0]->title === '공연·콘서트 예매' && $primary_menu[1]->title === '정부 복지·지원금', 'Other primary items keep order');
$footer_args = (object) ['theme_location' => 'footer'];
check(count(bloguito_remove_primary_about_menu_item($menu_items, $footer_args)) === 3, 'Other menu locations keep About item');

ob_start(); bloguito_header_polish_styles(); $header_css = ob_get_clean();
check(strpos($header_css, '.bloguito-site-title-tagline') !== false, 'Header CSS styles the descriptor line');

echo "PASS: front-end metadata and header presentation\n";
