<?php
/** Standalone contract test: php wordpress/tests/post-row-actions-test.php */
define('ABSPATH', __DIR__ . '/');

$registered_filters = [];
$registered_actions = [];
$test_caps = ['edit_post' => true, 'publish_posts' => true];
$test_post = (object) [
    'ID' => 837, 'post_type' => 'post', 'post_status' => 'draft',
    'post_title' => '검토된 글', 'post_content' => '<p>검토된 본문</p>',
];
$test_attachment = (object) ['ID' => 938, 'post_type' => 'attachment', 'post_status' => 'inherit'];
$test_thumbnail_id = 938;
$test_alt = '검토된 대표이미지';
$test_meta = [];
$test_image_file = tempnam(sys_get_temp_dir(), 'bloguito-cover-');
file_put_contents($test_image_file, 'approved-image-bytes');
$test_updated = null;
$test_is_admin = false;
$test_is_singular_post = true;
$test_is_preview = true;
$test_post_id = 837;

class TestWpdb {
    public $posts = 'wp_posts';
    public $postmeta = 'wp_postmeta';
    public $queries = [];
    public function prepare($query, ...$args) { return $query; }
    public function query($query) { $this->queries[] = $query; return 1; }
    public function get_var($query) { $this->queries[] = $query; return 1; }
    public function get_results($query) { $this->queries[] = $query; return []; }
    public function update($table, $data, $where, $formats = null, $where_formats = null) {
        global $test_post;
        $this->queries[] = 'UPDATE ' . $table;
        if (($where['ID'] ?? 0) === $test_post->ID && isset($data['post_status'])) {
            $test_post->post_status = $data['post_status'];
        }
        return 1;
    }
}
$wpdb = new TestWpdb();

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
function is_admin() {
    global $test_is_admin;
    return $test_is_admin;
}
function is_singular($post_type = '') {
    global $test_is_singular_post;
    return $post_type === 'post' && $test_is_singular_post;
}
function is_preview() {
    global $test_is_preview;
    return $test_is_preview;
}
function get_queried_object_id() {
    global $test_post_id;
    return $test_post_id;
}
function admin_url($path) { return 'https://example.test/wp-admin/' . $path; }
function add_query_arg($args, $url) { return $url . (strpos($url, '?') === false ? '?' : '&') . http_build_query($args); }
function wp_create_nonce($action) { return 'nonce-for-' . $action; }
function esc_url($value) { return $value; }
function esc_attr($value) { return htmlspecialchars($value, ENT_QUOTES, 'UTF-8'); }
function esc_html($value) { return htmlspecialchars($value, ENT_QUOTES, 'UTF-8'); }
function get_post($post_id) {
    global $test_post, $test_attachment;
    if ($test_post && $post_id === $test_post->ID) return clone $test_post;
    if ($test_attachment && $post_id === $test_attachment->ID) return clone $test_attachment;
    return null;
}
function get_post_meta($post_id, $key, $single = false) {
    global $test_post, $test_attachment, $test_meta, $test_alt;
    if ($post_id === $test_post->ID) return $test_meta[$key] ?? '';
    if ($post_id === $test_attachment->ID && $key === '_wp_attachment_image_alt') return $test_alt;
    return '';
}
function get_post_thumbnail_id($post_id) {
    global $test_post, $test_thumbnail_id;
    return $post_id === $test_post->ID ? $test_thumbnail_id : 0;
}
function wp_attachment_is_image($post_id) {
    global $test_attachment;
    return $post_id === $test_attachment->ID;
}
function get_attached_file($post_id) {
    global $test_attachment, $test_image_file;
    return $post_id === $test_attachment->ID ? $test_image_file : false;
}
function delete_post_meta($post_id, $key) {
    global $test_meta;
    unset($test_meta[$key]);
    return true;
}
function wp_unslash($value) { return is_string($value) ? stripslashes($value) : $value; }
function clean_post_cache($post_id) { return true; }
function wp_update_post($data, $wp_error = false) {
    global $test_updated, $test_post;
    $test_updated = $data;
    if (($data['ID'] ?? 0) !== $test_post->ID) {
        return $wp_error ? new WP_Error('bad_id', 'bad id') : 0;
    }
    $old_status = $test_post->post_status;
    $test_post->post_status = $data['post_status'];
    if (function_exists('bloguito_consume_publish_attestation')) {
        bloguito_consume_publish_attestation($test_post->post_status, $old_status, $test_post);
    }
    return $test_post->ID;
}
function is_wp_error($value) { return $value instanceof WP_Error; }
class TestAdminBar {
    public $nodes = [];
    public function add_node($node) { $this->nodes[$node['id']] = $node; }
}
function check($condition, $message) {
    if (!$condition) {
        fwrite(STDERR, 'FAIL: ' . $message . PHP_EOL);
        exit(1);
    }
}

require dirname(__DIR__) . '/mu-plugins/bloguito-post-row-actions.php';

function set_valid_publish_gate() {
    global $test_post, $test_attachment, $test_meta, $test_alt, $test_image_file, $test_thumbnail_id;
    $test_thumbnail_id = $test_attachment->ID;
    $test_meta[BLOGUITO_PUBLISH_GATE_META_KEY] = json_encode([
        'version' => 1,
        'post_id' => $test_post->ID,
        'content_sha256' => hash('sha256', $test_post->post_content),
        'review_digest' => str_repeat('1', 64),
        'title_sha256' => hash('sha256', $test_post->post_title),
        'thumbnail_id' => $test_attachment->ID,
        'image_sha256' => hash_file('sha256', $test_image_file),
        'alt_text_sha256' => hash('sha256', $test_alt),
        'approval_kind' => 'manual_user_selected',
        'approval_evidence_sha256' => str_repeat('2', 64),
        'expires_at_gmt' => '2099-01-01T00:00:00Z',
        'requires_live_state' => false,
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}
set_valid_publish_gate();

check(isset($registered_filters['post_row_actions']), 'Row action filter registered');
check($registered_filters['post_row_actions'][2] === 2, 'Row action filter receives post object');
check(isset($registered_actions['admin_post_bloguito_set_post_status']), 'Guarded admin-post handler registered');
check(isset($registered_actions['admin_notices']), 'Success notice hook registered');
check(isset($registered_actions['admin_bar_menu']), 'Preview publish admin-bar hook registered');
check($registered_actions['admin_bar_menu'][1] === 82, 'Preview publish button follows the post ID admin-bar item');
check(isset($registered_filters['wp_insert_post_data']), 'Global publish transition filter registered');
check($registered_filters['wp_insert_post_data'][2] === 4, 'Global publish transition filter receives full update context');
check(isset($registered_actions['transition_post_status']), 'Publish attestation consumption hook registered');

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

$test_meta[BLOGUITO_PUBLISH_GATE_META_KEY] = '';
$actions = bloguito_add_post_status_row_action(['edit' => 'keep'], $test_post);
check($actions === ['edit' => 'keep'], 'Draft without publish attestation has no publish action');
$blocked = bloguito_change_post_status(837, 'publish');
check(is_wp_error($blocked) && $blocked->get_error_code() === 'bloguito_publish_gate_missing', 'Draft without attestation cannot publish');
set_valid_publish_gate();

$test_alt = '변경된 ALT';
check(bloguito_add_post_status_row_action(['edit' => 'keep'], $test_post) === ['edit' => 'keep'], 'Changed ALT invalidates publish action');
$test_alt = '검토된 대표이미지';
set_valid_publish_gate();
$test_thumbnail_id = 999;
check(bloguito_add_post_status_row_action(['edit' => 'keep'], $test_post) === ['edit' => 'keep'], 'Changed thumbnail invalidates publish action');
set_valid_publish_gate();

$live_gate = json_decode($test_meta[BLOGUITO_PUBLISH_GATE_META_KEY], true);
$live_gate['requires_live_state'] = true;
$test_meta[BLOGUITO_PUBLISH_GATE_META_KEY] = json_encode($live_gate);
check(bloguito_add_post_status_row_action(['edit' => 'keep'], $test_post) === ['edit' => 'keep'], 'Live-state draft has no direct WordPress publish action');
$live_blocked = bloguito_change_post_status(837, 'publish');
check(is_wp_error($live_blocked) && $live_blocked->get_error_code() === 'bloguito_publish_gate_live_state_requires_canonical_preflight', 'Live-state draft requires canonical promote preflight');
set_valid_publish_gate();

$guarded = bloguito_guard_publish_transition([
    'post_type' => 'post', 'post_status' => 'publish',
    'post_content' => $test_post->post_content, 'post_title' => $test_post->post_title,
], ['ID' => 837], [], true);
check($guarded['post_status'] === 'draft', 'Native existing-post publish is forced back to draft without guarded transaction context');
$GLOBALS['bloguito_guarded_publish_post_id'] = 837;
$guarded = bloguito_guard_publish_transition([
    'post_type' => 'post', 'post_status' => 'publish',
], ['ID' => 837], [], true);
check($guarded['post_status'] === 'publish', 'Guarded transaction context may publish an existing post');
unset($GLOBALS['bloguito_guarded_publish_post_id']);

$created = bloguito_guard_publish_transition([
    'post_type' => 'post', 'post_status' => 'publish',
], [], [], false);
check($created['post_status'] === 'draft', 'New direct publish creation is forced to draft');
$scheduled = bloguito_guard_publish_transition([
    'post_type' => 'post', 'post_status' => 'future',
], ['ID' => 837], [], true);
check($scheduled['post_status'] === 'draft', 'Native future scheduling is forced to draft');

$test_post->post_status = 'publish';
set_valid_publish_gate();
bloguito_consume_publish_attestation('publish', 'draft', $test_post);
check($test_post->post_status === 'draft', 'Direct wp_publish_post-style transition is reverted to draft');
check(isset($test_meta[BLOGUITO_PUBLISH_GATE_META_KEY]), 'Rejected direct transition does not consume attestation');

$test_post->post_status = 'draft';
$admin_bar = new TestAdminBar();
bloguito_add_preview_publish_admin_bar($admin_bar);
check(isset($admin_bar->nodes['bloguito-preview-publish']), 'Draft preview gets publish admin-bar button');
check($admin_bar->nodes['bloguito-preview-publish']['title'] === '발행', 'Preview admin-bar button label is publish');
check(strpos($admin_bar->nodes['bloguito-preview-publish']['href'], 'target=publish') !== false, 'Preview button targets publish');
check(strpos($admin_bar->nodes['bloguito-preview-publish']['href'], 'bloguito_return=permalink') !== false, 'Preview publish returns to public permalink');
check(strpos($admin_bar->nodes['bloguito-preview-publish']['href'], '_bloguito_nonce=nonce-for-bloguito-post-status-837-publish') !== false, 'Preview publish button is nonce protected');

$test_post->post_status = 'publish';
$admin_bar = new TestAdminBar();
bloguito_add_preview_publish_admin_bar($admin_bar);
check($admin_bar->nodes === [], 'Published post preview does not show publish button');

$test_post->post_status = 'draft';
$test_is_preview = false;
$admin_bar = new TestAdminBar();
bloguito_add_preview_publish_admin_bar($admin_bar);
check($admin_bar->nodes === [], 'Normal front-end view does not show preview publish button');
$test_is_preview = true;

$test_caps['publish_posts'] = false;
$admin_bar = new TestAdminBar();
bloguito_add_preview_publish_admin_bar($admin_bar);
check($admin_bar->nodes === [], 'Users without publish permission see no preview publish button');
$test_caps['publish_posts'] = true;

$test_is_admin = true;
$admin_bar = new TestAdminBar();
bloguito_add_preview_publish_admin_bar($admin_bar);
check($admin_bar->nodes === [], 'WordPress admin screens do not show preview publish button');
$test_is_admin = false;

$test_is_singular_post = false;
$admin_bar = new TestAdminBar();
bloguito_add_preview_publish_admin_bar($admin_bar);
check($admin_bar->nodes === [], 'Non-post preview screens do not show preview publish button');
$test_is_singular_post = true;

$test_updated = null;
$result = bloguito_change_post_status(837, 'publish');
check($result === 837, 'Draft can transition to publish');
check($test_updated === ['ID' => 837, 'post_status' => 'publish'], 'Only ID and post_status are sent to wp_update_post');
check(!isset($test_meta[BLOGUITO_PUBLISH_GATE_META_KEY]), 'Successful publication consumes the attestation');

$test_updated = null;
$result = bloguito_change_post_status(837, 'publish');
check(is_wp_error($result) && $result->get_error_code() === 'bloguito_status_conflict', 'Stale publish transition fails closed');
check($test_updated === null, 'Stale transition does not update WordPress');

$result = bloguito_change_post_status(837, 'draft');
check($result === 837 && $test_post->post_status === 'draft', 'Published post can return to draft');
check(bloguito_add_post_status_row_action(['edit' => 'keep'], $test_post) === ['edit' => 'keep'], 'Returned draft requires fresh approval before republishing');
$result = bloguito_change_post_status(837, 'pending');
check(is_wp_error($result) && $result->get_error_code() === 'bloguito_invalid_status', 'Unsupported target statuses fail closed');

$test_post->post_type = 'page';
$result = bloguito_change_post_status(837, 'publish');
check(is_wp_error($result) && $result->get_error_code() === 'bloguito_invalid_post', 'Non-post types cannot transition');

@unlink($test_image_file);
echo 'PASS: post row action tests' . PHP_EOL;
