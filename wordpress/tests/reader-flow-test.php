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
$single = true;
ob_start(); bloguito_reader_flow_styles(); $single_css = ob_get_clean();
check(strpos($single_css, '@media (min-width: 1025px)') !== false, 'Desktop image breakpoint is present');
check(strpos($single_css, 'max-height: 420px') !== false, 'Desktop featured images are large enough to read');
check(strpos($single_css, 'width: 100%') !== false, 'Mobile featured images use the full content width');
check(strpos($single_css, 'max-height: none') !== false, 'Mobile featured images are not height-capped');
check(strpos($single_css, 'max-height: 120px') === false, 'Old narrow mobile featured-image cap is removed');
echo "PASS reader-flow scope and navigation\n";
