<?php
/** Standalone regression test: php wordpress/tests/new-post-permalink-test.php */
define('ABSPATH', __DIR__ . '/');

$registered_filters = []; $registered_actions = []; $rewrite = null; $meta = []; $query_vars = []; $queried = null; $status = null; $no_cache = false;
$wp_query = new class { public $is_404 = false; public function set_404() { $this->is_404 = true; } };
class WP_Post { public $ID; public $post_type; public $post_name; public function __construct($id, $slug, $type='post') { $this->ID=$id; $this->post_name=$slug; $this->post_type=$type; } }
function add_filter($hook, $callback, $priority=10, $args=1) { global $registered_filters; $registered_filters[$hook]=[$callback,$priority,$args]; }
function add_action($hook, $callback, $priority=10, $args=1) { global $registered_actions; $registered_actions[$hook]=[$callback,$priority,$args]; }
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
check(isset($registered_actions['init']), 'rewrite hook registered');
check(isset($registered_actions['template_redirect']), 'request validation hook registered');
$legacy = new WP_Post(648, 'busan-october-festivals-2026');
$marked = new WP_Post(901, 'health-screening');
$meta[901][BLOGUITO_PERMALINK_META] = BLOGUITO_PERMALINK_SCHEME;
check(bloguito_new_post_permalink('https://lifeinfo24.org/busan-october-festivals-2026/', $legacy, false) === 'https://lifeinfo24.org/busan-october-festivals-2026/', 'legacy URL unchanged');
check(bloguito_new_post_permalink('legacy', $marked, false) === 'https://lifeinfo24.org/901/health-screening/', 'marked post uses ID/slug');
check(bloguito_new_post_permalink('legacy', $marked, true) === 'https://lifeinfo24.org/901/%postname%/', 'sample permalink placeholder preserved');
bloguito_register_id_slug_rewrite();
check($rewrite[0] === '^([1-9][0-9]*)/([a-z0-9]+(?:-[a-z0-9]+)*)/?$', 'rewrite accepts ID and lowercase slug');
check(strpos($rewrite[1], 'bloguito_id_slug=1') !== false && $rewrite[2] === 'top', 'rewrite marks custom route');
$vars = bloguito_id_slug_query_vars(['p']);
check(in_array('bloguito_id_slug', $vars, true) && in_array('bloguito_slug', $vars, true), 'custom query vars registered');
$queried = $marked; $query_vars = ['bloguito_id_slug'=>'1','bloguito_slug'=>'health-screening'];
bloguito_validate_id_slug_request();
check(!$wp_query->is_404 && $status === null, 'correct new URL resolves normally');
$queried = $legacy; $query_vars = ['bloguito_id_slug'=>'1','bloguito_slug'=>'busan-october-festivals-2026'];
bloguito_validate_id_slug_request();
check($wp_query->is_404 && $status === 404 && $no_cache, 'legacy post is not exposed through new route');
echo "OK new post permalink\n";
