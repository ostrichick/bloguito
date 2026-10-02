<?php
/** Standalone contract test: php wordpress/tests/post-row-actions-test.php */
define('ABSPATH', __DIR__ . '/');

$registered_filters = [];
$registered_actions = [];
$test_caps = ['edit_post' => true, 'publish_posts' => true];
$test_post = (object) ['ID' => 837, 'post_type' => 'post', 'post_status' => 'draft'];
$test_updated = null;

class WP_Error {
    private $code;
    private $message;
    public function __construct($code, $message) { $this->code = $code; $this->message = $message; }
    public function get_error_code() { return $this->code; }
    public function get_error_message() { return $this->message; }
}

function add_filter($hook, $callback, $priority = 10, $accepted_args = 1) {
    global $registered_filters;
    $registered_filters[$hook] = [$callback, $priority, $accepted_args];
}
function add_action($hook, $callback, $priority = 10, $accepted_args = 1) {
    global $registered_actions;
    $registered_actions[$hook] = [$callback, $priority, $accepted_args];
}
function current_user_can($capability, ...$args) {
    global $test_caps;
    return $test_caps[$capability] ?? false;
}
function admin_url($path) { return 'https://example.test/wp-admin/' . $path; }
function add_query_arg($args, $url) { return $url . (strpos($url, '?') === false ? '?' : '&') . http_build_query($args); }
function wp_nonce_url($url, $action, $name) { return add_query_arg([$name => 'nonce-for-' . $action], $url); }
function esc_url($value) { return $value; }
function esc_attr($value) { return htmlspecialchars($value, ENT_QUOTES, 'UTF-8'); }
function esc_html($value) { return htmlspecialchars($value, ENT_QUOTES, 'UTF-8'); }
function get_post($post_id) {
    global $test_post;
    return $test_post && $post_id === $test_post->ID ? clone $test_post : null;
}
function wp_update_post($data, $wp_error = false) {
    global $test_updated, $test_post;
    $test_updated = $data;
    if (($data['ID'] ?? 0) !== $test_post->ID) {
        return $wp_error ? new WP_Error('bad_id', 'bad id') : 0;
    }
    $test_post->post_status = $data['post_status'];
    return $test_post->ID;
}
function is_wp_error($value) { return $value instanceof WP_Error; }
function check($condition, $message) {
    if (!$condition) {
        fwrite(STDERR, 'FAIL: ' . $message . PHP_EOL);
        exit(1);
    }
}

require dirname(__DIR__) . '/mu-plugins/bloguito-post-row-actions.php';

check(isset($registered_filters['post_row_actions']), 'Row action filter registered');
check($registered_filters['post_row_actions'][2] === 2, 'Row action filter receives post object');
check(isset($registered_actions['admin_post_bloguito_set_post_status']), 'Guarded admin-post handler registered');
check(isset($registered_actions['admin_notices']), 'Success notice hook registered');

$base_actions = [
    'edit' => '<a>Edit</a>',
    'inline hide-if-no-js' => '<button>Quick Edit</button>',
    'trash' => '<a>Trash</a>',
    'view' => '<a>Preview</a>',
];
$actions = bloguito_add_post_status_row_action($base_actions, $test_post);
check(isset($actions['bloguito-publish']), 'Draft gets publish action');
check(strpos($actions['bloguito-publish'], '>발행</a>') !== false, 'Draft action label is publish');
check(strpos($actions['bloguito-publish'], 'target=publish') !== false, 'Draft action targets publish');
check(strpos($actions['bloguito-publish'], '_bloguito_nonce=nonce-for-bloguito-post-status-837-publish') !== false, 'Publish action is nonce protected');
check(!isset($actions['bloguito-to-draft']), 'Draft does not get to-draft action');
$keys = array_keys($actions);
check(array_search('bloguito-publish', $keys, true) + 1 === array_search('trash', $keys, true), 'Publish action is inserted immediately before trash');

$test_post->post_status = 'publish';
$actions = bloguito_add_post_status_row_action($base_actions, $test_post);
check(isset($actions['bloguito-to-draft']), 'Published post gets draft action');
check(strpos($actions['bloguito-to-draft'], '>임시글로 전환</a>') !== false, 'Published action clearly names draft transition');
check(strpos($actions['bloguito-to-draft'], 'target=draft') !== false, 'Published action targets draft');
check(!isset($actions['bloguito-publish']), 'Published post does not get publish action');
$keys = array_keys($actions);
check(array_search('bloguito-to-draft', $keys, true) + 1 === array_search('trash', $keys, true), 'To-draft action is inserted immediately before trash');

$test_post->post_status = 'pending';
check(bloguito_add_post_status_row_action(['edit' => 'keep'], $test_post) === ['edit' => 'keep'], 'Other statuses are unchanged');
$page = (object) ['ID' => 837, 'post_type' => 'page', 'post_status' => 'draft'];
check(bloguito_add_post_status_row_action(['edit' => 'keep'], $page) === ['edit' => 'keep'], 'Pages are unchanged');

$test_post->post_status = 'draft';
$test_caps['publish_posts'] = false;
check(bloguito_add_post_status_row_action(['edit' => 'keep'], $test_post) === ['edit' => 'keep'], 'Users without publish permission see no status action');
$test_post->post_status = 'publish';
$actions = bloguito_add_post_status_row_action([], $test_post);
check(isset($actions['bloguito-to-draft']), 'Users who can edit a published post can return it to draft without publish permission');
$test_caps['publish_posts'] = true;
$test_post->post_status = 'draft';
$test_caps['edit_post'] = false;
check(bloguito_add_post_status_row_action(['edit' => 'keep'], $test_post) === ['edit' => 'keep'], 'Users without edit permission see no status action');
$test_caps['edit_post'] = true;

$test_updated = null;
$result = bloguito_change_post_status(837, 'publish');
check($result === 837, 'Draft can transition to publish');
check($test_updated === ['ID' => 837, 'post_status' => 'publish'], 'Only ID and post_status are sent to wp_update_post');

$test_updated = null;
$result = bloguito_change_post_status(837, 'publish');
check(is_wp_error($result) && $result->get_error_code() === 'bloguito_status_conflict', 'Stale publish transition fails closed');
check($test_updated === null, 'Stale transition does not update WordPress');

$result = bloguito_change_post_status(837, 'draft');
check($result === 837 && $test_post->post_status === 'draft', 'Published post can return to draft');
$result = bloguito_change_post_status(837, 'pending');
check(is_wp_error($result) && $result->get_error_code() === 'bloguito_invalid_status', 'Unsupported target statuses fail closed');

$test_post->post_type = 'page';
$result = bloguito_change_post_status(837, 'publish');
check(is_wp_error($result) && $result->get_error_code() === 'bloguito_invalid_post', 'Non-post types cannot transition');

echo 'PASS: post row action tests' . PHP_EOL;
