<?php
/** php wordpress/tests/clarity-content-insights-test.php */
define('ABSPATH', __DIR__ . '/');
$single = true;

function add_filter($hook, $callback) {}
function is_singular($type) { global $single; return $single && $type === 'post'; }
function check($ok, $message) {
    if (!$ok) { fwrite(STDERR, "FAIL: $message\n"); exit(1); }
}

require __DIR__ . '/../mu-plugins/bloguito-clarity-content-insights.php';

$input = 'itemtype="https://schema.org/CreativeWork" itemscope';
$marked = bloguito_clarity_article_region($input);
check(strpos($marked, 'data-clarity-region="article"') !== false, 'Single post gets the Clarity article region');
check(substr_count($marked, 'data-clarity-region=') === 1, 'Clarity region is added once');
check(bloguito_clarity_article_region($marked) === $marked, 'Existing Clarity region is preserved without duplication');

$single = false;
check(bloguito_clarity_article_region($input) === $input, 'Archive article markup is unchanged');
check(bloguito_clarity_article_region(false) === false, 'Non-string GeneratePress microdata is preserved');

echo "PASS clarity content insights scope\n";
