<?php
define('ABSPATH', __DIR__ . '/');
$front = true;
function add_action($hook, $callback, $priority = 10) {}
function is_front_page() { global $front; return $front; }
function is_home() { return false; }
function check($ok, $message) { if (!$ok) { fwrite(STDERR, "FAIL: $message\n"); exit(1); } }
require __DIR__ . '/../mu-plugins/bloguito-webmaster-verification.php';
ob_start(); bloguito_webmaster_verification_tags(); $html = ob_get_clean();
check(strpos($html, 'msvalidate.01') !== false, 'Bing verification tag missing on front page');
$front = false;
ob_start(); bloguito_webmaster_verification_tags(); $html = ob_get_clean();
check($html === '', 'Verification tag should stay off non-home pages');
echo "PASS webmaster verification scope\n";
