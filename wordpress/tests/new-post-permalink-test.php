<?php
/** Standalone regression test: php wordpress/tests/new-post-permalink-test.php */
define('ABSPATH', __DIR__ . '/');

$registered_filters = []; $registered_actions = []; $removed_actions = []; $rewrite = null; $meta = []; $query_vars = []; $queried = null; $status = null; $no_cache = false;
$wp_query = new class { public $is_404 = false; public function set_404() { $this->is_404 = true; } };
class WP_Post {
    public $ID; public $post_type; public $post_name; public $post_status;
    public function __construct($id, $slug, $type='post', $status='publish') {
        $this->ID=$id; $this->post_name=$slug; $this->post_type=$type; $this->post_status=$status;
    }
}
function add_filter($hook, $callback, $priority=10, $args=1) { global $registered_filters; $registered_filters[$hook]=[$callback,$priority,$args]; }
function add_action($hook, $callback, $priority=10, $args=1) { global $registered_actions; $registered_actions[$hook . ':' . $priority]=[$callback,$priority,$args]; }
function remove_action($hook, $callback, $priority=10) { global $removed_actions; $removed_actions[]=[$hook,$callback,$priority]; return true; }
function get_post_meta($id, $key, $single) { global $meta; return $meta[$id][$key] ?? ''; }
function home_url($path) { return 'https://lifeinfo24.org/' . ltrim($path, '/'); }
function user_trailingslashit($path) { return rtrim($path, '/') . '/'; }
function add_rewrite_rule($regex, $query, $position) { global $rewrite; $rewrite=[$regex,$query,$position]; }
function get_query_var($key) { global $query_vars; return $query_vars[$key] ?? ''; }
function get_queried_object() { global $queried; return $queried; }
function status_header($code) { global $status; $status=$code; }
function nocache_headers() { global $no_cache; $no_cache=true; }
function get_permalink($post) { return 'https://lifeinfo24.org/' . $post->post_name . '/'; }
function wp_safe_redirect($url, $code, $by) { throw new RuntimeException('redirect:' . $url . ':' . $code . ':' . $by); }
function check($ok, $message) { if (!$ok) { fwrite(STDERR, 'FAIL: ' . $message . PHP_EOL); exit(1); } }

require dirname(__DIR__) . '/mu-plugins/bloguito-new-post-permalinks.php';
check(isset($registered_filters['post_link']), 'post_link filter registered');
check(isset($registered_filters['query_vars']), 'query vars filter registered');
check(isset($registered_actions['init:10']), 'rewrite hook registered');
check(isset($registered_actions['template_redirect:0']), 'malformed route guard registered');
check(isset($registered_actions['template_redirect:1']), 'request handler registered');

$legacy = new WP_Post(648, 'busan-october-festivals-2026');
$new = new WP_Post(901, 'wordpress-internal-slug');
$draft = new WP_Post(902, 'draft-internal-slug', 'post', 'draft');
$page = new WP_Post(903, 'sample-page', 'page', 'publish');
$meta[901][BLOGUITO_PERMALINK_META] = BLOGUITO_PERMALINK_SCHEME;
$meta[902][BLOGUITO_PERMALINK_META] = BLOGUITO_PERMALINK_SCHEME;

check(bloguito_post_id_permalink('https://lifeinfo24.org/busan-october-festivals-2026/', $legacy, false) === 'https://lifeinfo24.org/busan-october-festivals-2026/', 'legacy canonical URL unchanged');
check(bloguito_post_id_permalink('legacy', $new, false) === 'https://lifeinfo24.org/p/901/', 'new post uses /p/ID/');
check(bloguito_post_id_permalink('legacy', $new, true) === 'https://lifeinfo24.org/p/901/', 'new post sample link is ID-only');

bloguito_register_post_id_rewrite();
check($rewrite[0] === '^p/([1-9][0-9]*)/?$', 'rewrite accepts variable-length positive post ID');
check(strpos($rewrite[1], 'bloguito_post_id_route=1') !== false && $rewrite[2] === 'top', 'rewrite marks custom route');
$vars = bloguito_post_id_query_vars(['p']);
check(in_array('bloguito_post_id_route', $vars, true), 'custom query var registered');

$queried = $new; $query_vars = ['bloguito_post_id_route'=>'1'];
bloguito_handle_post_id_request();
check(!$wp_query->is_404 && $status === null, 'published new post resolves /p/ID/ normally');

$queried = $legacy; $query_vars = ['bloguito_post_id_route'=>'1'];
try {
    bloguito_handle_post_id_request();
    check(false, 'legacy route must redirect');
} catch (RuntimeException $e) {
    check($e->getMessage() === 'redirect:https://lifeinfo24.org/busan-october-festivals-2026/:301:Bloguito', 'legacy /p/ID/ redirects once to existing canonical');
}

$wp_query->is_404=false; $status=null; $no_cache=false;
$queried = $draft; $query_vars = ['bloguito_post_id_route'=>'1'];
bloguito_handle_post_id_request();
check($wp_query->is_404 && $status === 404 && $no_cache, 'draft /p/ID/ is not publicly exposed');

$wp_query->is_404=false; $status=null; $no_cache=false;
$queried = $page; $query_vars = ['bloguito_post_id_route'=>'1'];
bloguito_handle_post_id_request();
check($wp_query->is_404 && $status === 404, 'page ID is not exposed through post route');

$wp_query->is_404=false; $status=null; $no_cache=false;
$queried = null; $query_vars = ['bloguito_post_id_route'=>'1'];
bloguito_handle_post_id_request();
check($wp_query->is_404 && $status === 404, 'missing post ID is 404');

$wp_query->is_404=false; $status=null; $no_cache=false; $removed_actions=[];
$_SERVER['REQUEST_URI'] = '/p/0610/';
bloguito_reject_malformed_post_id_path();
check($wp_query->is_404 && $status === 404, 'leading-zero post ID is forced to 404');
check(count($removed_actions) === 1 && $removed_actions[0][1] === 'redirect_canonical', 'malformed route disables canonical guessing');

$wp_query->is_404=false; $status=null; $no_cache=false; $removed_actions=[];
$_SERVER['REQUEST_URI'] = '/p/610/';
bloguito_reject_malformed_post_id_path();
check(!$wp_query->is_404 && $status === null && count($removed_actions) === 0, 'valid post ID path is not blocked');

echo "OK post ID permalink\n";
