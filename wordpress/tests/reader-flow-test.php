<?php
/** php wordpress/tests/reader-flow-test.php */
define('ABSPATH', __DIR__ . '/');
$single = true;
$post = (object) ['post_content' => '<p>No reviewed next-reading block.</p>'];
function add_action($hook, $callback, $priority = 10) {}
function add_filter($hook, $callback) {}
function is_singular($type) { global $single; return $single; }
function get_post() { global $post; return $post; }
function check($ok, $message) {
    if (!$ok) { fwrite(STDERR, "FAIL: $message\n"); exit(1); }
}
require __DIR__ . '/../mu-plugins/bloguito-reader-flow.php';
check(bloguito_reader_flow_navigation(true), 'Theme navigation remains without reviewed links');
$post->post_content = '<div class="bloguito-interlink"><a href="/?p=235">Next task</a></div>';
check(!bloguito_reader_flow_navigation(true), 'Reviewed links replace chronological navigation');
$post->post_content = "<div class='other bloguito-interlink extra'>links</div>";
check(!bloguito_reader_flow_navigation(true), 'Multiple classes and either quote style work');
$post->post_content = '<p>bloguito-interlink</p>';
check(bloguito_reader_flow_navigation(true), 'Mentioning a class in text is not a link block');
$single = false;
check(bloguito_reader_flow_navigation(true), 'Archive navigation is preserved');
ob_start(); bloguito_reader_flow_styles(); $archive_css = ob_get_clean();
check($archive_css === '', 'Archive thumbnails do not receive single-post styles');
echo "PASS reader-flow scope and navigation\n";
