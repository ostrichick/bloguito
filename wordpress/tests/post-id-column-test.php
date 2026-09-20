<?php
/** Standalone hook regression test: php wordpress/tests/post-id-column-test.php */
define('ABSPATH', __DIR__ . '/');

$registered_filters = [];
$registered_actions = [];
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

require dirname(__DIR__) . '/mu-plugins/bloguito-post-id-column.php';
check(isset($registered_filters['manage_post_posts_columns']), 'Post column filter registered');
check(isset($registered_actions['manage_post_posts_custom_column']), 'Post column renderer registered');
check(count($registered_filters) === 1 && count($registered_actions) === 1, 'No unrelated screen hooks');
check($registered_actions['manage_post_posts_custom_column'][2] === 2, 'Renderer receives post ID');

$columns = $registered_filters['manage_post_posts_columns'](['cb' => '선택', 'title' => '제목', 'date' => '날짜']);
check(array_keys($columns) === ['cb', 'title', 'bloguito_post_id', 'date'], 'ID follows title');
check($columns['bloguito_post_id'] === '글 ID', 'Korean column heading');
check(array_keys($registered_filters['manage_post_posts_columns'](['date' => '날짜'])) === ['date', 'bloguito_post_id'], 'Missing title fallback');

ob_start();
bloguito_render_post_id_column('bloguito_post_id', 243);
$output = ob_get_clean();
check($output === '243', 'Exact post ID rendered');
ob_start();
bloguito_render_post_id_column('date', 243);
check(ob_get_clean() === '', 'Unrelated column not modified');
echo "PASS: post ID column tests\n";
