<?php
/** Fixed backend for the authorized summary-label migration, invoked by WP-CLI. */
if (!defined('WP_CLI') || !WP_CLI) { exit(1); }
$payload = json_decode(file_get_contents('php://stdin'), true);
if (!is_array($payload) || !isset($payload['id'], $payload['before_sha256'], $payload['edits'], $payload['preserved'])) {
    WP_CLI::error('Invalid summary migration payload');
}
$id = (int) $payload['id'];
if ($id < 1 || !preg_match('/^[a-f0-9]{64}$/D', $payload['before_sha256'])) { WP_CLI::error('Invalid CAS'); }
global $wpdb;
$wpdb->query('START TRANSACTION');
$row = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->posts} WHERE ID = %d FOR UPDATE", $id), ARRAY_A);
if (!$row || $row['post_type'] !== 'post' || hash('sha256', $row['post_content']) !== $payload['before_sha256']) {
    $wpdb->query('ROLLBACK'); WP_CLI::error('Post changed since inventory');
}
$preserved = ['post_title', 'post_status', 'post_excerpt', 'post_name', 'post_date', 'post_date_gmt', 'post_author'];
foreach ($preserved as $field) {
    if (!array_key_exists($field, $payload['preserved']) || (string) $row[$field] !== (string) $payload['preserved'][$field]) {
        $wpdb->query('ROLLBACK'); WP_CLI::error('Preserved field changed: ' . $field);
    }
}
$content = $row['post_content'];
$edits = $payload['edits'];
usort($edits, function($a, $b) { return $b['start'] <=> $a['start']; });
$boundary = strlen($content);
foreach ($edits as $edit) {
    $start = $edit['start']; $end = $edit['end']; $old = $edit['old']; $new = $edit['new'];
    $label = in_array($old, ['핵심 답변', '핵심답변', '핵심 요약', '핵심요약', '빠른 요약', '핵심 정보', '먼저 답부터'], true) && $new === '한눈에 보기';
    $badge = $new === '' && preg_match('/^<span\b[^>]*>3초 요약<\/span>$/Du', $old);
    if (!is_int($start) || !is_int($end) || $start < 0 || $end <= $start || $end > $boundary ||
        substr($content, $start, $end - $start) !== $old || (!$label && !$badge)) {
        $wpdb->query('ROLLBACK'); WP_CLI::error('Invalid label-only edit');
    }
    $content = substr($content, 0, $start) . $new . substr($content, $end);
    $boundary = $start;
}
if (!$edits || hash('sha256', $content) !== $payload['after_sha256']) {
    $wpdb->query('ROLLBACK'); WP_CLI::error('Unexpected output hash');
}
// Backups must stay outside the public document root.
$backup_dir = '/tmp/bloguito-summary-backups';
if (!is_dir($backup_dir) && !mkdir($backup_dir, 0700, true)) {
    $wpdb->query('ROLLBACK'); WP_CLI::error('Backup directory failed');
}
$backup = $backup_dir . '/post-' . $id . '-' . $payload['before_sha256'] . '.json';
if (!file_exists($backup)) {
    $handle = fopen($backup, 'x');
    if (!$handle) { $wpdb->query('ROLLBACK'); WP_CLI::error('Backup failed'); }
    chmod($backup, 0600);
    $data = json_encode($row, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if (fwrite($handle, $data) !== strlen($data)) { fclose($handle); $wpdb->query('ROLLBACK'); WP_CLI::error('Incomplete backup'); }
    fclose($handle);
} else {
    $previous = json_decode(file_get_contents($backup), true);
    if (!is_array($previous) || hash('sha256', $previous['post_content']) !== $payload['before_sha256']) {
        $wpdb->query('ROLLBACK'); WP_CLI::error('Invalid existing backup');
    }
}
$result = wp_update_post(wp_slash(['ID' => $id, 'post_content' => $content, 'edit_date' => true]), true);
if (is_wp_error($result)) { $wpdb->query('ROLLBACK'); WP_CLI::error($result->get_error_message()); }
$saved = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->posts} WHERE ID = %d", $id), ARRAY_A);
if (!$saved || $saved['post_content'] !== $content) { $wpdb->query('ROLLBACK'); clean_post_cache($id); WP_CLI::error('Stored content differs'); }
foreach ($preserved as $field) {
    if ((string) $saved[$field] !== (string) $row[$field]) { $wpdb->query('ROLLBACK'); clean_post_cache($id); WP_CLI::error('Preserved field differs: ' . $field); }
}
$wpdb->query('COMMIT');
clean_post_cache($id);
echo json_encode(['id' => $id, 'after_sha256' => hash('sha256', $saved['post_content']), 'verified' => true], JSON_UNESCAPED_UNICODE) . "\n";
