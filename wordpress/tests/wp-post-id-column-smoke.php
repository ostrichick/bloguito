<?php
/** Read-only WordPress integration check: wp eval-file this-file.php --allow-root */

if (!defined('ABSPATH')) {
    exit(1);
}

$columns = apply_filters('manage_post_posts_columns', ['title' => 'Title', 'date' => 'Date'], 'post');
if (array_keys($columns) !== ['title', 'bloguito_post_id', 'date']) {
    fwrite(STDERR, "Post ID column missing or out of order\n");
    exit(1);
}

$ids = get_posts(['post_type' => 'post', 'post_status' => 'any', 'numberposts' => 1, 'fields' => 'ids']);
$id = $ids ? (int) $ids[0] : 243;
ob_start();
do_action('manage_post_posts_custom_column', 'bloguito_post_id', $id);
$rendered = ob_get_clean();
if ($rendered !== (string) $id) {
    fwrite(STDERR, "Post ID renderer returned an unexpected value\n");
    exit(1);
}

echo "PASS: live WordPress post column hook and ID rendering\n";
