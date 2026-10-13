<?php
/**
 * Fixed, SHA-pinned WordPress CLI runtime for an already imported cover.
 *
 * Invoke ONLY through the root-owned bloguito_wp_image_writer.py. That writer
 * authenticates origin/review signatures, reads a root-owned request, checks
 * this runtime's SHA on the host AND in the container, then permanently claims
 * the request ID before running `wp eval-file` as the dedicated nonadmin user.
 *
 * This file only changes two WordPress metadata values: _thumbnail_id and
 * _wp_attachment_image_alt. It cannot import media, edit a post, or publish.
 * The whole transaction is one attempt; any ambiguous failure requires a
 * read-only reconciliation, never an automatic repeat of the claimed ID.
 */

if (!defined('ABSPATH') || !class_exists('WP_CLI', false) || !isset($GLOBALS['wpdb'])) {
    fwrite(STDERR, "image_writer_requires_bootstrapped_wp_cli\n");
    exit(1);
}

$bloguito_image_deny = static function (string $reason): void {
    echo wp_json_encode(['status' => 'denied', 'code' => $reason], JSON_UNESCAPED_SLASHES) . "\n";
    exit(1);
};

// The root writer sends canonical JSON with unique keys. Revalidate the exact
// allowlisted shape in WordPress, since this is a separate execution boundary.
$bloguito_image_raw = stream_get_contents(STDIN, 8193);
if (!is_string($bloguito_image_raw) || strlen($bloguito_image_raw) < 2 || strlen($bloguito_image_raw) > 8192) {
    $bloguito_image_deny('invalid_request_size');
}
try {
    $bloguito_image_req = json_decode($bloguito_image_raw, true, 32, JSON_THROW_ON_ERROR);
} catch (Throwable $error) {
    $bloguito_image_deny('invalid_request_json');
}

$bloguito_image_exact_keys = static function ($value, array $required): bool {
    if (!is_array($value)) {
        return false;
    }
    $actual = array_keys($value);
    sort($actual, SORT_STRING);
    sort($required, SORT_STRING);
    return $actual === $required;
};
$bloguito_image_sha = static function ($value): bool {
    return is_string($value) && preg_match('/^[0-9a-f]{64}$/D', $value) === 1;
};
$bloguito_image_id = static function ($value): bool {
    return is_int($value) && $value > 0 && $value <= 999999999;
};

$bloguito_image_request_keys = [
    'protocol', 'action', 'request_id', 'task_id', 'post_id', 'attachment_id',
    'candidate_number', 'candidate_count', 'candidates', 'image_sha256',
    'source_sha256', 'staged_sha256', 'alt_text', 'expected', 'release_sha256',
    'origin', 'review', 'task_created_at', 'target', 'generator_policy_sha256',
    'manifest_sha256', 'review_receipt_sha256', 'selection_mode', 'review_actor',
];
$bloguito_image_expected_keys = [
    'post_status', 'content_sha256', 'title_sha256', 'slug_sha256',
    'excerpt_sha256', 'thumbnail_id', 'alt_sha256',
];
if (!$bloguito_image_exact_keys($bloguito_image_req, $bloguito_image_request_keys)) {
    $bloguito_image_deny('unsupported_request_fields');
}
$bloguito_image_exp = $bloguito_image_req['expected'];
if (!$bloguito_image_exact_keys($bloguito_image_exp, $bloguito_image_expected_keys)
    || $bloguito_image_req['protocol'] !== 1
    || $bloguito_image_req['action'] !== 'featured-image-set'
    || !is_string($bloguito_image_req['request_id'])
    || preg_match('/^[0-9a-f]{32}$/D', $bloguito_image_req['request_id']) !== 1
    || !is_string($bloguito_image_req['task_id'])
    || preg_match('/^[A-Za-z0-9_.-]{8,128}$/D', $bloguito_image_req['task_id']) !== 1
    || !$bloguito_image_id($bloguito_image_req['post_id'])
    || !$bloguito_image_id($bloguito_image_req['attachment_id'])
    || $bloguito_image_req['post_id'] === $bloguito_image_req['attachment_id']
    || !$bloguito_image_exact_keys($bloguito_image_req['target'], ['post_id'])
    || $bloguito_image_req['target']['post_id'] !== $bloguito_image_req['post_id']
    || !$bloguito_image_sha($bloguito_image_req['source_sha256'])
    || !$bloguito_image_sha($bloguito_image_req['staged_sha256'])
    || !$bloguito_image_sha($bloguito_image_req['image_sha256'])
    || !hash_equals($bloguito_image_req['staged_sha256'], $bloguito_image_req['image_sha256'])
    || !$bloguito_image_sha($bloguito_image_req['release_sha256'])
    || !$bloguito_image_sha($bloguito_image_req['generator_policy_sha256'])
    || !$bloguito_image_sha($bloguito_image_req['manifest_sha256'])
    || !$bloguito_image_sha($bloguito_image_req['review_receipt_sha256'])
    || !is_array($bloguito_image_req['origin'])
    || !is_array($bloguito_image_req['review'])
    || !in_array($bloguito_image_req['selection_mode'], ['user', 'agent-delegated'], true)
    || !is_string($bloguito_image_req['review_actor'])
    || strlen($bloguito_image_req['review_actor']) < 1
    || !is_string($bloguito_image_req['task_created_at'])
    || !is_int($bloguito_image_req['candidate_number'])
    || !is_int($bloguito_image_req['candidate_count'])
    || $bloguito_image_req['candidate_number'] < 1
    || $bloguito_image_req['candidate_count'] > 20
    || $bloguito_image_req['candidate_number'] > $bloguito_image_req['candidate_count']
    || !is_array($bloguito_image_req['candidates'])
    || count($bloguito_image_req['candidates']) !== $bloguito_image_req['candidate_count']
    || !is_string($bloguito_image_req['alt_text'])
    || $bloguito_image_req['alt_text'] === ''
    || strlen($bloguito_image_req['alt_text']) > 1600
    || preg_match('/[\x00-\x1f\x7f]/u', $bloguito_image_req['alt_text']) !== 0
    || !in_array($bloguito_image_exp['post_status'], ['draft', 'publish'], true)
    || !is_int($bloguito_image_exp['thumbnail_id'])
    || $bloguito_image_exp['thumbnail_id'] < 0
    || $bloguito_image_exp['thumbnail_id'] > 999999999) {
    $bloguito_image_deny('invalid_approved_request');
}
foreach (['content_sha256', 'title_sha256', 'slug_sha256', 'excerpt_sha256', 'alt_sha256'] as $bloguito_image_field) {
    if (!$bloguito_image_sha($bloguito_image_exp[$bloguito_image_field])) {
        $bloguito_image_deny('invalid_expected_digest');
    }
}
foreach ($bloguito_image_req['candidates'] as $bloguito_image_index => $bloguito_image_row) {
    if (!$bloguito_image_exact_keys($bloguito_image_row, ['candidate_number', 'sha256'])
        || $bloguito_image_row['candidate_number'] !== $bloguito_image_index + 1
        || !$bloguito_image_sha($bloguito_image_row['sha256'])) {
        $bloguito_image_deny('invalid_candidate_inventory');
    }
}
if (!hash_equals(
    $bloguito_image_req['candidates'][$bloguito_image_req['candidate_number'] - 1]['sha256'],
    $bloguito_image_req['source_sha256']
)) {
    $bloguito_image_deny('selected_candidate_mismatch');
}

// A named, independently provisioned user and a dedicated primitive capability
// are mandatory. An admin, superadmin, or generic editor is never sufficient.
$bloguito_image_user = wp_get_current_user();
if (!$bloguito_image_user instanceof WP_User
    || !$bloguito_image_user->exists()
    || $bloguito_image_user->user_login !== 'bloguito-image-writer'
    || is_super_admin($bloguito_image_user->ID)
    || current_user_can('manage_options')
    || current_user_can('edit_users')
    || current_user_can('install_plugins')
    || !current_user_can('bloguito_write_featured_image')
    || !current_user_can('upload_files')
    || !current_user_can('edit_post', $bloguito_image_req['post_id'])
    || !current_user_can('edit_post', $bloguito_image_req['attachment_id'])) {
    $bloguito_image_deny('image_writer_capability_denied');
}

$bloguito_image_post_id = $bloguito_image_req['post_id'];
$bloguito_image_attachment_id = $bloguito_image_req['attachment_id'];
global $wpdb;
$bloguito_image_engines = $wpdb->get_results($wpdb->prepare(
    'SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES ' .
    'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s,%s)',
    $wpdb->posts, $wpdb->postmeta
), ARRAY_A);
if (!is_array($bloguito_image_engines) || count($bloguito_image_engines) !== 2
    || $wpdb->last_error !== ''
    || count(array_filter($bloguito_image_engines, static function ($row) use ($wpdb) {
        return in_array($row['TABLE_NAME'] ?? null, [$wpdb->posts, $wpdb->postmeta], true)
            && ($row['ENGINE'] ?? null) === 'InnoDB';
    })) !== 2) {
    // An implicit-autocommit table would make CAS/ALT writes non-atomic.
    $bloguito_image_deny('transactional_innodb_required');
}
$bloguito_image_transaction_started = false;
// Metadata transactions are only atomic on transactional tables. Fail closed
// if an older WordPress schema still uses MyISAM (or table visibility fails).
$bloguito_image_engines = $wpdb->get_results($wpdb->prepare(
    'SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() '
    . 'AND TABLE_NAME IN (%s, %s)', $wpdb->posts, $wpdb->postmeta
), ARRAY_A);
if (!is_array($bloguito_image_engines) || count($bloguito_image_engines) !== 2
    || $wpdb->last_error !== '') {
    $bloguito_image_deny('database_transaction_safety_unverified');
}
foreach ($bloguito_image_engines as $bloguito_image_engine) {
    if (!in_array($bloguito_image_engine['TABLE_NAME'], [$wpdb->posts, $wpdb->postmeta], true)
        || strtoupper((string) $bloguito_image_engine['ENGINE']) !== 'INNODB') {
        $bloguito_image_deny('database_transaction_safety_unverified');
    }
}
$bloguito_image_verify_meta = static function () use ($wpdb, $bloguito_image_post_id, $bloguito_image_attachment_id) {
    $sql = $wpdb->prepare(
        "SELECT meta_id, post_id, meta_key, meta_value FROM {$wpdb->postmeta} " .
        "WHERE (post_id=%d AND meta_key=%s) OR (post_id=%d AND meta_key=%s) " .
        'ORDER BY meta_id FOR UPDATE',
        $bloguito_image_post_id, '_thumbnail_id',
        $bloguito_image_attachment_id, '_wp_attachment_image_alt'
    );
    $rows = $wpdb->get_results($sql, ARRAY_A);
    if (!is_array($rows) || count($rows) > 2 || $wpdb->last_error !== '') {
        throw new RuntimeException('meta_snapshot_failed');
    }
    $result = ['thumbnail' => null, 'alt' => null];
    foreach ($rows as $row) {
        $slot = (int) $row['post_id'] === $bloguito_image_post_id && $row['meta_key'] === '_thumbnail_id'
            ? 'thumbnail' : 'alt';
        if ($result[$slot] !== null) {
            throw new RuntimeException('duplicate_post_meta_denied');
        }
        $result[$slot] = ['meta_id' => (int) $row['meta_id'], 'value' => (string) $row['meta_value']];
    }
    return $result;
};

$bloguito_image_apply_meta = static function (int $post_id, string $key, ?array $old, string $new) use ($wpdb): void {
    if ($old !== null && $old['value'] === $new) {
        return;
    }
    if ($old === null) {
        $ok = $wpdb->insert($wpdb->postmeta,
            ['post_id' => $post_id, 'meta_key' => $key, 'meta_value' => $new],
            ['%d', '%s', '%s']);
    } else {
        $ok = $wpdb->update($wpdb->postmeta, ['meta_value' => $new],
            ['meta_id' => $old['meta_id'], 'post_id' => $post_id, 'meta_key' => $key,
             'meta_value' => $old['value']],
            ['%s'], ['%d', '%d', '%s', '%s']);
    }
    if ($ok !== 1 || $wpdb->last_error !== '') {
        throw new RuntimeException('meta_update_failed');
    }
};

try {
    if ($wpdb->query('START TRANSACTION') === false) {
        throw new RuntimeException('transaction_unavailable');
    }
    $bloguito_image_transaction_started = true;
    $bloguito_image_post = $wpdb->get_row($wpdb->prepare(
        "SELECT ID, post_type, post_status, post_title, post_name, post_content, post_excerpt " .
        "FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE", $bloguito_image_post_id
    ), ARRAY_A);
    $bloguito_image_attachment = $wpdb->get_row($wpdb->prepare(
        "SELECT ID, post_type, post_parent, post_mime_type FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",
        $bloguito_image_attachment_id
    ), ARRAY_A);
    if (!is_array($bloguito_image_post) || !is_array($bloguito_image_attachment)
        || $wpdb->last_error !== '' || $bloguito_image_post['post_type'] !== 'post'
        || $bloguito_image_post['post_status'] !== $bloguito_image_exp['post_status']
        || $bloguito_image_attachment['post_type'] !== 'attachment'
        || (int) $bloguito_image_attachment['post_parent'] !== $bloguito_image_post_id
        || !in_array($bloguito_image_attachment['post_mime_type'],
                     ['image/jpeg', 'image/png', 'image/webp'], true)) {
        throw new RuntimeException('post_or_attachment_baseline_changed');
    }
    foreach ([
        'content_sha256' => 'post_content', 'title_sha256' => 'post_title',
        'slug_sha256' => 'post_name', 'excerpt_sha256' => 'post_excerpt',
    ] as $bloguito_image_digest => $bloguito_image_column) {
        if (!hash_equals($bloguito_image_exp[$bloguito_image_digest],
                         hash('sha256', (string) $bloguito_image_post[$bloguito_image_column]))) {
            throw new RuntimeException('post_cas_mismatch');
        }
    }
    $bloguito_image_old_meta = $bloguito_image_verify_meta();
    $bloguito_image_old_thumb = $bloguito_image_old_meta['thumbnail'] === null
        ? 0 : $bloguito_image_old_meta['thumbnail']['value'];
    $bloguito_image_current_thumb = $bloguito_image_old_thumb === 0 ? 0
        : (ctype_digit((string) $bloguito_image_old_thumb) ? (int) $bloguito_image_old_thumb : -1);
    $bloguito_image_old_alt = $bloguito_image_old_meta['alt'] === null
        ? '' : $bloguito_image_old_meta['alt']['value'];
    if ($bloguito_image_current_thumb !== $bloguito_image_exp['thumbnail_id']
        || !hash_equals($bloguito_image_exp['alt_sha256'], hash('sha256', $bloguito_image_old_alt))) {
        throw new RuntimeException('thumbnail_or_alt_cas_mismatch');
    }
    $bloguito_image_attached = get_attached_file($bloguito_image_attachment_id);
    $bloguito_image_upload_root = wp_get_upload_dir();
    $bloguito_image_root_path = is_array($bloguito_image_upload_root)
        && empty($bloguito_image_upload_root['error'])
        ? realpath((string) $bloguito_image_upload_root['basedir']) : false;
    $bloguito_image_real_file = is_string($bloguito_image_attached)
        ? realpath($bloguito_image_attached) : false;
    if ($bloguito_image_root_path === false || $bloguito_image_real_file === false
        || strpos($bloguito_image_real_file, $bloguito_image_root_path . DIRECTORY_SEPARATOR) !== 0
        || !is_file($bloguito_image_real_file) || !is_readable($bloguito_image_real_file)
        || !hash_equals($bloguito_image_req['image_sha256'],
                        (string) hash_file('sha256', $bloguito_image_real_file))) {
        throw new RuntimeException('attachment_file_sha_or_path_mismatch');
    }
    $bloguito_image_file_info = @getimagesize($bloguito_image_real_file);
    if (!is_array($bloguito_image_file_info)
        || ($bloguito_image_file_info['mime'] ?? '') !== $bloguito_image_attachment['post_mime_type']) {
        throw new RuntimeException('attachment_image_format_invalid');
    }

    // The SELECT ... FOR UPDATE locks the post, attachment and existing metadata
    // rows. Both metadata changes belong to the same InnoDB transaction.
    $bloguito_image_apply_meta($bloguito_image_attachment_id, '_wp_attachment_image_alt',
        $bloguito_image_old_meta['alt'], $bloguito_image_req['alt_text']);
    $bloguito_image_apply_meta($bloguito_image_post_id, '_thumbnail_id',
        $bloguito_image_old_meta['thumbnail'], (string) $bloguito_image_attachment_id);

    $bloguito_image_new_meta = $bloguito_image_verify_meta();
    $bloguito_image_after = $wpdb->get_row($wpdb->prepare(
        "SELECT ID, post_type, post_status, post_title, post_name, post_content, post_excerpt " .
        "FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE", $bloguito_image_post_id
    ), ARRAY_A);
    if ($bloguito_image_after !== $bloguito_image_post
        || $bloguito_image_new_meta['thumbnail'] === null
        || $bloguito_image_new_meta['thumbnail']['value'] !== (string) $bloguito_image_attachment_id
        || $bloguito_image_new_meta['alt'] === null
        || $bloguito_image_new_meta['alt']['value'] !== $bloguito_image_req['alt_text']
        || !hash_equals($bloguito_image_req['image_sha256'],
                        (string) hash_file('sha256', $bloguito_image_real_file))) {
        throw new RuntimeException('transaction_readback_mismatch');
    }
    if ($wpdb->query('COMMIT') === false) {
        throw new RuntimeException('transaction_commit_ambiguous');
    }
    $bloguito_image_transaction_started = false;
    wp_cache_delete($bloguito_image_post_id, 'post_meta');
    wp_cache_delete($bloguito_image_attachment_id, 'post_meta');
    clean_post_cache($bloguito_image_post_id);
    clean_post_cache($bloguito_image_attachment_id);
    $bloguito_image_postcommit = $bloguito_image_verify_meta();
    $bloguito_image_postcommit_row = $wpdb->get_row($wpdb->prepare(
        "SELECT ID, post_type, post_status, post_title, post_name, post_content, post_excerpt " .
        "FROM {$wpdb->posts} WHERE ID=%d", $bloguito_image_post_id
    ), ARRAY_A);
    if ($bloguito_image_postcommit['thumbnail'] === null
        || $bloguito_image_postcommit['thumbnail']['value'] !== (string) $bloguito_image_attachment_id
        || $bloguito_image_postcommit['alt'] === null
        || $bloguito_image_postcommit['alt']['value'] !== $bloguito_image_req['alt_text']
        || $bloguito_image_postcommit_row !== $bloguito_image_post
        || !hash_equals($bloguito_image_req['image_sha256'],
                        (string) hash_file('sha256', $bloguito_image_real_file))) {
        throw new RuntimeException('post_commit_readback_mismatch');
    }
} catch (Throwable $error) {
    if ($bloguito_image_transaction_started) {
        $wpdb->query('ROLLBACK');
        wp_cache_delete($bloguito_image_post_id, 'post_meta');
        wp_cache_delete($bloguito_image_attachment_id, 'post_meta');
    }
    $bloguito_image_deny('wordpress_transaction_or_readback_failed');
}

echo wp_json_encode([
    'status' => 'verified',
    'post_id' => $bloguito_image_post_id,
    'attachment_id' => $bloguito_image_attachment_id,
    'image_sha256' => $bloguito_image_req['image_sha256'],
], JSON_UNESCAPED_SLASHES) . "\n";
