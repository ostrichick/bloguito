<?php
/** Standalone hook regression test: php wordpress/tests/post-id-column-test.php */
define('ABSPATH', __DIR__ . '/');

$registered_filters = [];
$registered_actions = [];
$test_is_admin = false;
$test_is_singular_post = true;
$test_post_id = 243;
$test_can_edit_post = true;
$test_modified_time = '2026/09/24 13:20';
$test_modified_timestamp = 1790236800;
$test_current_timestamp = 1790326800;
$test_screen = (object) ['base' => 'edit', 'post_type' => 'post'];
$test_tags = [
    (object) ['name' => '가나다', 'slug' => 'ga-na-da'],
    (object) ['name' => '라마바', 'slug' => 'ra-ma-ba'],
    (object) ['name' => '사아자', 'slug' => 'sa-a-ja'],
    (object) ['name' => '차카타', 'slug' => 'cha-ka-ta'],
];
function add_filter($hook, $callback) {
    global $registered_filters;
    $registered_filters[$hook] = $callback;
}
function add_action($hook, $callback, $priority = 10, $args = 1) {
    global $registered_actions;
    $registered_actions[$hook] = [$callback, $priority, $args];
}
function check($condition, $message) {
    if (!$condition) {
        fwrite(STDERR, "FAIL: $message\n");
        exit(1);
    }
}
function is_admin() {
    global $test_is_admin;
    return $test_is_admin;
}
function is_singular($post_type = '') {
    global $test_is_singular_post;
    return $post_type === 'post' && $test_is_singular_post;
}
function get_queried_object_id() {
    global $test_post_id;
    return $test_post_id;
}
function current_user_can($capability, ...$args) {
    global $test_can_edit_post, $test_post_id;
    return $capability === 'edit_post' && ($args[0] ?? null) === $test_post_id && $test_can_edit_post;
}
function get_post_modified_time($format, $gmt, $post_id, $translate) {
    global $test_modified_time, $test_modified_timestamp, $test_post_id;
    if ($gmt !== false || $post_id !== $test_post_id || $translate !== true) {
        return false;
    }
    if ($format === 'Y/m/d H:i') {
        return $test_modified_time;
    }
    if ($format === 'U') {
        return $test_modified_timestamp;
    }
    return false;
}
function esc_html($value) {
    return htmlspecialchars($value, ENT_QUOTES, 'UTF-8');
}
function esc_attr($value) {
    return htmlspecialchars($value, ENT_QUOTES, 'UTF-8');
}
function esc_url($value) {
    return $value;
}
function current_time($type) {
    global $test_current_timestamp;
    return $type === 'timestamp' ? $test_current_timestamp : false;
}
function human_time_diff($from, $to) {
    return (($to - $from) / 3600) . '시간';
}
function wp_get_post_terms($post_id, $taxonomy, $args) {
    global $test_post_id, $test_tags;
    if ($post_id !== $test_post_id || $taxonomy !== 'post_tag' || ($args['orderby'] ?? null) !== 'name') {
        return [];
    }
    return $test_tags;
}
function is_wp_error($value) {
    return false;
}
function admin_url($path) {
    return 'https://example.test/wp-admin/' . $path;
}
function add_query_arg($args, $url) {
    return $url . '?' . http_build_query($args);
}
function get_current_screen() {
    global $test_screen;
    return $test_screen;
}
class TestAdminBar {
    public $nodes = [];
    public function add_node($node) {
        $this->nodes[$node['id']] = $node;
    }
}

require dirname(__DIR__) . '/mu-plugins/bloguito-post-id-column.php';
check(isset($registered_filters['manage_post_posts_columns']), 'Post column filter registered');
check(isset($registered_filters['manage_edit-post_sortable_columns']), 'Sortable column filter registered');
check(isset($registered_actions['manage_post_posts_custom_column']), 'Post column renderer registered');
check(isset($registered_actions['admin_head-edit.php']), 'Post list CSS hook registered');
check(isset($registered_actions['admin_bar_menu']), 'Admin bar hook registered');
check(count($registered_filters) === 2 && count($registered_actions) === 3, 'Only expected screen hooks registered');
check($registered_actions['manage_post_posts_custom_column'][2] === 2, 'Renderer receives post ID');
check($registered_actions['admin_bar_menu'][1] === 81, 'Admin bar item follows core Edit Post item');

$columns = $registered_filters['manage_post_posts_columns']([
    'cb' => '선택',
    'title' => '제목',
    'author' => '작성자',
    'categories' => '카테고리',
    'tags' => '태그',
    'date' => '날짜',
]);
check(array_keys($columns) === ['cb', 'title', 'bloguito_post_id', 'categories', 'bloguito_tags', 'date', 'bloguito_last_modified'], 'Author removed, tags compacted, ID and modified positioned');
check(!isset($columns['author']) && !isset($columns['tags']), 'Native author and tag columns removed');
check($columns['bloguito_post_id'] === '글 ID', 'Korean column heading');
check($columns['bloguito_tags'] === '태그', 'Compact tags keep Korean heading');
check($columns['bloguito_last_modified'] === '마지막 수정', 'Korean modified column heading');
check(array_keys($registered_filters['manage_post_posts_columns'](['date' => '날짜'])) === ['date', 'bloguito_last_modified', 'bloguito_post_id'], 'Missing title fallback');
check(array_keys($registered_filters['manage_post_posts_columns'](['title' => '제목'])) === ['title', 'bloguito_post_id', 'bloguito_last_modified'], 'Missing date fallback');

$sortable = $registered_filters['manage_edit-post_sortable_columns'](['title' => 'title']);
check($sortable['bloguito_last_modified'] === 'modified', 'Modified column sorts by WordPress modified field');

ob_start();
bloguito_render_post_id_column('bloguito_post_id', 243);
$output = ob_get_clean();
check($output === '243', 'Exact post ID rendered');
ob_start();
bloguito_render_post_id_column('bloguito_last_modified', 243);
$output = ob_get_clean();
check(strpos($output, '25시간 전') !== false, 'Relative modified age rendered');
check(strpos($output, '2026/09/24 13:20') !== false, 'Exact local modified time rendered');
ob_start();
bloguito_render_post_id_column('bloguito_tags', 243);
$output = ob_get_clean();
check(strpos($output, '>가나다</a>, <a') !== false, 'First two tags remain visible and linked');
check(strpos($output, '>라마바</a>') !== false, 'Second tag remains visible');
check(strpos($output, '+2') !== false, 'Remaining tag count rendered');
check(strpos($output, '사아자, 차카타') !== false, 'Full tag list remains in tooltip');
ob_start();
bloguito_render_post_id_column('date', 243);
check(ob_get_clean() === '', 'Unrelated column not modified');

ob_start();
bloguito_adjust_post_list_column_widths();
$output = ob_get_clean();
check(strpos($output, '.column-title { width: 38%; }') !== false, 'Title column widened');
check(strpos($output, 'tr.status-draft') !== false, 'Draft row styling rendered');
check(strpos($output, 'tr.status-pending') !== false, 'Pending row styling rendered');
check(strpos($output, 'tr.status-future') !== false, 'Scheduled row styling rendered');
check(strpos($output, '.column-author') === false, 'Author width rule removed');
$test_screen = (object) ['base' => 'edit', 'post_type' => 'page'];
ob_start();
bloguito_adjust_post_list_column_widths();
check(ob_get_clean() === '', 'List CSS limited to built-in Posts screen');
$test_screen = (object) ['base' => 'edit', 'post_type' => 'post'];

$admin_bar = new TestAdminBar();
bloguito_add_post_id_admin_bar($admin_bar);
check(isset($admin_bar->nodes['bloguito-post-id']), 'Current post ID added to admin bar');
check($admin_bar->nodes['bloguito-post-id']['title'] === '글 ID: 243', 'Admin bar shows exact post ID');
check(!isset($admin_bar->nodes['bloguito-post-id']['href']), 'Post ID is display-only');

$test_can_edit_post = false;
$admin_bar = new TestAdminBar();
bloguito_add_post_id_admin_bar($admin_bar);
check($admin_bar->nodes === [], 'Users without edit permission do not see the post ID');
$test_can_edit_post = true;
$test_is_singular_post = false;
$admin_bar = new TestAdminBar();
bloguito_add_post_id_admin_bar($admin_bar);
check($admin_bar->nodes === [], 'Non-post front-end screens do not show the post ID');
$test_is_singular_post = true;
$test_is_admin = true;
$admin_bar = new TestAdminBar();
bloguito_add_post_id_admin_bar($admin_bar);
check($admin_bar->nodes === [], 'WordPress admin screens do not show the front-end post ID item');
echo "PASS: post ID column tests\n";
