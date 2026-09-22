<?php
/**
 * Read-only standalone contract harness; inject both plugin sources and a
 * base64-encoded JSON fixture into the three markers before piping to PHP.
 * Does not connect to WordPress or update any post.
 */
define('ABSPATH', '/test');
function add_filter($hook, $function, $priority) {
    $GLOBALS['registered_filters'][] = array($hook, $function, $priority);
}
function wp_strip_all_tags($html) { return strip_tags($html); }
function esc_html($value) { return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function esc_attr($value) { return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function is_admin() { return $GLOBALS['ctx']['admin']; }
function is_singular($type) { return $GLOBALS['ctx']['singular'] && $type === 'post'; }
function is_main_query() { return $GLOBALS['ctx']['main']; }
function in_the_loop() { return $GLOBALS['ctx']['loop']; }
function is_feed() { return $GLOBALS['ctx']['feed']; }
function get_the_ID() { return $GLOBALS['ctx']['post']; }
function get_queried_object_id() { return $GLOBALS['ctx']['queried']; }
function get_post_status($id) { return $GLOBALS['ctx']['status']; }

/* TOC_PLUGIN_SOURCE */
/* TABLE_PLUGIN_SOURCE */

function table85_assert($ok, $description) {
    if (!$ok) {
        throw new RuntimeException($description);
    }
    $GLOBALS['checks']++;
}
function table85_marked($before, $after) {
    preg_match_all('~<table\b[^>]*>.*?</table\s*>~is', $before, $old);
    preg_match_all('~<p class="bloguito-table-hint".*?</p><div class="bloguito-info-table".*?</table></div>~s',
        $after, $new);
    table85_assert(count($old[0]) === 2 && count($new[0]) === 2, 'exactly two table-only wrappers');
    $masked_before = str_replace($old[0], '[TABLE]', $before);
    $masked_after = str_replace($new[0], '[TABLE]', $after);
    table85_assert($masked_before === $masked_after, 'all non-table content preserved byte-for-byte');
    foreach ($old[0] as $i => $markup) {
        $new_table = preg_replace('~\A.*?(<table\b.*</table>).*\z~s', '$1', $new[0][$i]);
        $new_table = preg_replace('~<caption\b[^>]*>.*?</caption>~s', '', $new_table);
        table85_assert(
            preg_replace('/\s+/u', '', strip_tags($markup))
                === preg_replace('/\s+/u', '', strip_tags($new_table)),
            'table ' . $i . ': every cell text remains identical'
        );
    }
}

$fixtures = json_decode(base64_decode('/* FIXTURE_BASE64 */'), true, 512, JSON_THROW_ON_ERROR);
$GLOBALS['checks'] = 0;
$GLOBALS['ctx'] = array(
    'admin' => false, 'singular' => true, 'main' => true, 'loop' => true,
    'feed' => false, 'post' => 85, 'queried' => 85, 'status' => 'publish',
);
table85_assert(in_array(array('the_content', 'bloguito_legacy_toc_filter', 99), $GLOBALS['registered_filters'], true),
    'existing TOC filter remains at priority 99');
table85_assert(in_array(array('the_content', 'bloguito_legacy_table85_filter', 100), $GLOBALS['registered_filters'], true),
    'table filter runs after TOC at priority 100');

$old_render = $fixtures['rendered'];
$old_saved = $fixtures['saved'];
$before_toc = bloguito_legacy_toc_build($old_render, 85);
$saved_toc = bloguito_legacy_toc_build($old_saved, 85);
foreach (array(
    'REST' => $old_render,
    'saved' => $old_saved,
    'REST+TOC' => $before_toc,
    'saved+TOC' => $saved_toc,
) as $name => $before) {
    $after = bloguito_legacy_table85_build($before, 85);
    table85_assert($after !== $before, $name . ': table transformation occurs');
    table85_assert(bloguito_legacy_table85_build($after, 85) === $after, $name . ': repeated call is idempotent');
    table85_assert(substr_count($after, 'class="bloguito-info-table"') === 2, $name . ': exactly two regions');
    table85_assert(substr_count($after, '<caption ') === 2, $name . ': exactly two captions');
    table85_assert(substr_count($after, 'scope="col"') === 6, $name . ': six column headers');
    table85_assert(substr_count($after, 'scope="row"') === 7, $name . ': seven row headers');
    table85_assert(substr_count($after, 'tabindex="0"') === 2, $name . ': keyboard regions');
    table85_marked($before, $after);
}

$tampered = str_replace('복지멤버십', '변경된 제도', $old_render);
table85_assert(bloguito_legacy_table85_build($tampered, 85) === $tampered, 'changed first table fails closed');
$tampered = str_replace('접수 방법', '새 접수 방법', $old_render);
table85_assert(bloguito_legacy_table85_build($tampered, 85) === $tampered, 'changed second table fails closed');
$tampered = str_replace('<table>', '<table class="changed">', $old_render);
table85_assert(bloguito_legacy_table85_build($tampered, 85) === $tampered, 'changed table start tag fails closed');
$tampered = str_replace('</table>', '</table><table></table>', $old_render);
table85_assert(bloguito_legacy_table85_build($tampered, 85) === $tampered, 'third table fails closed');
$tampered = str_replace('먼저 기억할 세 가지', '새 요약 제목', $old_render);
table85_assert(bloguito_legacy_table85_build($tampered, 85) === $tampered, 'changed summary landmark fails closed');
$tampered = str_replace('지원금 소식을', '지원금 뉴스를', $old_render);
table85_assert($tampered !== $old_render
    && bloguito_legacy_table85_build($tampered, 85) === $tampered,
    'a change outside both tables fails the whole-content guard');
$tampered = str_replace('지원금 소식을', '지원금 뉴스를', $before_toc);
table85_assert($tampered !== $before_toc
    && bloguito_legacy_table85_build($tampered, 85) === $tampered,
    'a change after TOC insertion also fails the whole-content guard');
$tampered = str_replace('<table>', '<table class="bloguito-info-table">', $old_render);
table85_assert(bloguito_legacy_table85_build($tampered, 85) === $tampered, 'existing table wrapper fails closed');
$tampered = str_replace('<div ', '<div class="bloguito-article" ', $old_render);
table85_assert(bloguito_legacy_table85_build($tampered, 85) === $tampered, 'new renderer fails closed');
$mixed = str_replace($fixtures['saved_tables'][0], $fixtures['rendered_tables'][0], $old_saved);
table85_assert(bloguito_legacy_table85_build($mixed, 85) === $mixed, 'mixed saved/REST fingerprints fail closed');
table85_assert(bloguito_legacy_table85_build($old_render, 137) === $old_render, 'other post ID excluded');

$changed = array();
foreach ($fixtures['posts'] as $post) {
    $before = $post['html'];
    $after = bloguito_legacy_table85_build($before, $post['id']);
    if ($post['id'] === 85) {
        table85_assert($after !== $before, 'census #85 changes');
        table85_marked($before, $after);
        $changed[] = 85;
    } else {
        table85_assert($before === $after, 'census other ' . $post['id'] . ' unchanged');
    }
}
table85_assert(count($fixtures['posts']) === 30 && $changed === array(85), 'exact 30-post scope');

foreach (array('admin', 'singular', 'main', 'loop', 'feed') as $flag) {
    $GLOBALS['ctx'][$flag] = ($flag === 'singular' || $flag === 'main' || $flag === 'loop') ? false : true;
    table85_assert(bloguito_legacy_table85_filter($old_render) === $old_render, $flag . ' context excluded');
    $GLOBALS['ctx'][$flag] = ($flag === 'singular' || $flag === 'main' || $flag === 'loop');
}
$GLOBALS['ctx']['status'] = 'draft';
table85_assert(bloguito_legacy_table85_filter($old_render) === $old_render, 'draft excluded');
$GLOBALS['ctx']['status'] = 'publish';
$GLOBALS['ctx']['queried'] = 137;
table85_assert(bloguito_legacy_table85_filter($old_render) === $old_render, 'queried ID mismatch excluded');
$GLOBALS['ctx']['queried'] = 85;
table85_assert(bloguito_legacy_table85_filter($old_render) !== $old_render, 'published main singular filter works');
define('REST_REQUEST', true);
table85_assert(bloguito_legacy_table85_filter($old_render) === $old_render, 'REST request excluded');

echo json_encode(array(
    'checks' => $GLOBALS['checks'],
    'posts' => count($fixtures['posts']),
    'changed' => $changed,
    'rendered_toc_sha256' => hash('sha256', $before_toc),
    'saved_toc_sha256' => hash('sha256', $saved_toc),
    'rendered_after_base64' => base64_encode(bloguito_legacy_table85_build($before_toc, 85)),
), JSON_UNESCAPED_UNICODE) . "\n";
