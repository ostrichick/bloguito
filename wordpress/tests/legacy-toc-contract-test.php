<?php
/** Standalone regression harness: php wordpress/tests/legacy-toc-contract-test.php.
 * For stdin-only server validation, replace the PLUGIN_SOURCE marker with the
 * plugin's text (without its opening PHP tag) and define the embedded flag.
 */
define('ABSPATH', __DIR__);
function add_filter($name, $callback, $priority) {
    $GLOBALS['toc_registered_hook'] = array($name, $callback, $priority);
}
function wp_strip_all_tags($html) {
    return strip_tags($html);
}
function esc_html($value) {
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function esc_attr($value) {
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function is_admin() { return false; }
function is_singular($type) { return $type === 'post'; }
function is_main_query() { return true; }
function in_the_loop() { return true; }
function is_feed() { return false; }
function get_the_ID() { return $GLOBALS['test_post_id']; }
function get_queried_object_id() { return $GLOBALS['test_post_id']; }
function get_post_status($post_id) { return $GLOBALS['test_post_status']; }

if (defined('BLOGUITO_TOC_EMBEDDED')) {
    /* PLUGIN_SOURCE */
} else {
    require dirname(__DIR__) . '/mu-plugins/bloguito-legacy-toc.php';
}

function toc_assert($ok, $message) {
    if (!$ok) {
        throw new RuntimeException($message);
    }
    $GLOBALS['toc_test_count']++;
}

function toc_fixture($count, $with_ids = true, $lead = null) {
    $lead = $lead ?? str_repeat('복지 대상 및 신청 경로 안내. ', 54);
    $html = '<article class="bloguito-verified"><div>요약 ' . $lead . '</div>';
    for ($i = 1; $i <= $count; $i++) {
        $id = $with_ids ? ' id="guide-' . $i . '"' : '';
        $html .= '<h2' . $id . '>항목 ' . $i . '</h2><p>' . $lead . '</p>';
    }
    return $html . '</article>';
}

$GLOBALS['toc_test_count'] = 0;
$GLOBALS['test_post_id'] = 137;
$GLOBALS['test_post_status'] = 'publish';
toc_assert($GLOBALS['toc_registered_hook'] === array('the_content', 'bloguito_legacy_toc_filter', 99),
    'late content hook must be registered');

$legacy = toc_fixture(4);
$rendered = bloguito_legacy_toc_build($legacy, 137);
toc_assert(substr_count($rendered, 'class="bloguito-legacy-toc"') === 1,
    'eligible legacy article receives exactly one navigation');
toc_assert(substr_count($rendered, 'href="#guide-') === 4,
    'all audited section anchors are linked');
toc_assert(strpos($rendered, '<nav ') > strpos($rendered, '요약'),
    'navigation follows summary');
toc_assert(substr_count($rendered, 'id="guide-') === 4,
    'existing heading anchors remain unchanged');
toc_assert(bloguito_legacy_toc_build($rendered, 137) === $rendered,
    'second render cannot duplicate the navigation');
toc_assert(bloguito_legacy_toc_filter($legacy) === $rendered,
    'published single-post filter invokes pure builder');
toc_assert(bloguito_legacy_toc_build($legacy, 225) === $legacy,
    'new structured post is outside the whitelist');
toc_assert(bloguito_legacy_toc_build(str_replace('bloguito-verified', 'bloguito-article', $legacy), 137)
    === str_replace('bloguito-verified', 'bloguito-article', $legacy),
    'native article rendering is excluded');
toc_assert(bloguito_legacy_toc_build(str_replace('<article', '<nav class="lwptoc"></nav><article', $legacy), 137)
    === str_replace('<article', '<nav class="lwptoc"></nav><article', $legacy),
    'plugin TOC causes a safe no-op');
toc_assert(bloguito_legacy_toc_build(toc_fixture(2), 137) === toc_fixture(2),
    'articles with fewer than three anchored sections do not get a TOC');
toc_assert(bloguito_legacy_toc_build(toc_fixture(4, true, '짧음'), 137)
    === toc_fixture(4, true, '짧음'), 'short articles do not get a TOC');

$escaped = str_replace('항목 1', '조건 &amp; &lt;예외&gt;', $legacy);
$escaped_output = bloguito_legacy_toc_build($escaped, 137);
toc_assert(strpos($escaped_output, '조건 &amp; &lt;예외&gt;</a>') !== false,
    'heading entities are decoded once and escaped in navigation');
toc_assert(strpos($escaped_output, '조건 & <예외></a>') === false,
    'navigation cannot introduce raw heading markup');

$duplicate = str_replace('id="guide-2"', 'id="guide-1"', $legacy);
toc_assert(bloguito_legacy_toc_build($duplicate, 137) === $duplicate,
    'ambiguous heading anchors prevent TOC output');

$intro = '<div class="intro"><h2>먼저 기억할 세 가지</h2><p>'
    . str_repeat('맞춤형 복지 안내 및 신청. ', 55) . '</p></div>';
$post85 = $intro . '<div class="rest">';
for ($i = 1; $i <= 5; $i++) {
    $post85 .= '<h2>서비스별 선택 ' . $i . '</h2><p>'
        . str_repeat('신청 조건과 이용 방법. ', 20) . '</p>';
}
$post85 .= '<table><tr><th>원본</th><td>유지</td></tr></table></div>';
$after85 = bloguito_legacy_toc_build($post85, 85);
toc_assert(substr_count($after85, 'class="bloguito-legacy-toc"') === 1,
    '#85 gets a TOC');
toc_assert(strpos($after85, '</div>') < strpos($after85, '<nav ')
    && strpos($after85, '<nav ') < strpos($after85, '<h2 id="bloguito-legacy-85-'),
    '#85 TOC appears after the summary and before the first section');
toc_assert(substr_count($after85, 'id="bloguito-legacy-85-') === 5,
    '#85 receives exactly five visible heading anchors');
toc_assert(substr_count($after85, 'href="#bloguito-legacy-85-') === 5,
    '#85 TOC points to its five body sections');
toc_assert(strpos($after85, '<table><tr><th>원본</th><td>유지</td></tr></table>') !== false,
    '#85 original table is byte-for-byte preserved by TOC');
toc_assert(bloguito_legacy_toc_build($after85, 85) === $after85,
    '#85 repeated rendering is idempotent');

$changed85 = str_replace('먼저 기억할 세 가지', '다른 도입부', $post85);
toc_assert(bloguito_legacy_toc_build($changed85, 85) === $changed85,
    '#85 structural changes fail closed');
$GLOBALS['test_post_status'] = 'draft';
toc_assert(bloguito_legacy_toc_filter($legacy) === $legacy,
    'draft preview is not altered');

/* LIVE_SMOKE_BLOCK */

echo 'PASS: ' . $GLOBALS['toc_test_count'] . " legacy TOC contract checks\n";
