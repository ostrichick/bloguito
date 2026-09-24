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
$test_screen = (object) ['base' => 'edit', 'post_type' => 'post'];
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
    global $test_modified_time, $test_post_id;
    if ($format !== 'Y/m/d H:i' || $gmt !== false || $post_id !== $test_post_id || $translate !== true) {
        return false;
    }
    return $test_modified_time;
}
function get_current_screen() {
    global $test_screen;
    return $test_screen;
}
function esc_html($value) {
    return htmlspecialchars($value, ENT_QUOTES, 'UTF-8');
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
check(isset($registered_actions['admin_head-edit.php']), 'Post list width hook registered');
check(isset($registered_actions['admin_bar_menu']), 'Admin bar hook registered');
check(count($registered_filters) === 2 && count($registered_actions) === 3, 'Only expected screen hooks registered');
check($registered_actions['manage_post_posts_custom_column'][2] === 2, 'Renderer receives post ID');
check($registered_actions['admin_bar_menu'][1] === 81, 'Admin bar item follows core Edit Post item');

$columns = $registered_filters['manage_post_posts_columns'](['cb' => '선택', 'title' => '제목', 'date' => '날짜']);
check(array_keys($columns) === ['cb', 'title', 'bloguito_post_id', 'date', 'bloguito_last_modified'], 'ID follows title and modified follows date');
check($columns['bloguito_post_id'] === '글 ID', 'Korean column heading');
check($columns['bloguito_last_modified'] === '마지막 수정', 'Korean modified column heading');
check(array_keys($registered_filters['manage_post_posts_columns'](['date' => '날짜'])) === ['date', 'bloguito_last_modified', 'bloguito_post_id'], 'Missing title fallback');
check(array_keys($registered_filters['manage_post_posts_columns'](['title' => '제목'])) === ['title', 'bloguito_post_id', 'bloguito_last_modified'], 'Missing date fallback');

$sortable = $registered_filters['manage_edit-post_sortable_columns'](['title' => 'title']);
check($sortable['bloguito_last_modified'] === 'modified', 'Modified column sorts by WordPress modified field');

ob_start();
bloguito_adjust_post_list_column_widths();
$output = ob_get_clean();
check(strpos($output, '.column-title { width: 26%; }') !== false, 'Post title gets wider desktop column');
check(strpos($output, '.column-bloguito_post_id { width: 4%; }') !== false, 'Post ID stays compact');
check(strpos($output, '.column-wp-statistics-post-hits { width: 5%; }') !== false, 'Statistics hits stays compact');
$test_screen = (object) ['base' => 'edit', 'post_type' => 'page'];
ob_start();
bloguito_adjust_post_list_column_widths();
check(ob_get_clean() === '', 'Pages list does not get post-only widths');
$test_screen = (object) ['base' => 'edit', 'post_type' => 'post'];

ob_start();
bloguito_render_post_id_column('bloguito_post_id', 243);
$output = ob_get_clean();
check($output === '243', 'Exact post ID rendered');
ob_start();
bloguito_render_post_id_column('bloguito_last_modified', 243);
$output = ob_get_clean();
check($output === '2026/09/24 13:20', 'Exact local modified time rendered');
ob_start();
bloguito_render_post_id_column('date', 243);
check(ob_get_clean() === '', 'Unrelated column not modified');

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
