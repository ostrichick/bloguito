<?php
/**
 * Plugin Name: Bloguito Post Row Actions
 * Description: Add guarded publish/draft status actions to the Posts list and draft preview admin bar.
 * Version: 1.3.1
 */

if (!defined('ABSPATH')) {
    exit;
}

const BLOGUITO_PUBLISH_GATE_META_KEY = '_bloguito_publish_gate_v1';

/**
 * Last-resort database guard for core paths such as wp_publish_post() that
 * bypass wp_insert_post_data. Abort before a non-publish post can be written
 * as publish unless the exact post is inside our guarded transaction.
 */
add_filter('query', 'bloguito_guard_unguarded_publish_sql', PHP_INT_MIN);
function bloguito_guard_unguarded_publish_sql($query) {
    global $wpdb;

    if (!is_string($query) || !isset($wpdb) || !isset($wpdb->posts)) {
        return $query;
    }
    $table = preg_quote((string) $wpdb->posts, '/');
    if (!preg_match('/^\s*UPDATE\s+`?' . $table . '`?\s+SET\s+(.+?)\s+WHERE\s+(.+)$/is', $query, $parts)) {
        return $query;
    }
    if (!preg_match('/`?post_status`?\s*=\s*[\'\"]publish[\'\"]/i', $parts[1])) {
        return $query;
    }
    if (!preg_match('/`?ID`?\s*=\s*[\'\"]?(\d+)[\'\"]?/i', $parts[2], $id_match)) {
        wp_die('비가드 공개 상태 변경을 차단했습니다.', '발행 차단', ['response' => 409]);
    }
    $post_id = (int) $id_match[1];
    if ((int) ($GLOBALS['bloguito_guarded_publish_post_id'] ?? 0) === $post_id) {
        return $query;
    }
    $current_status = $wpdb->get_var($wpdb->prepare(
        "SELECT post_status FROM {$wpdb->posts} WHERE ID=%d",
        $post_id
    ));
    if ((string) $current_status !== 'publish') {
        wp_die('정규 발행 검증을 거치지 않은 공개 상태 변경을 차단했습니다.', '발행 차단', ['response' => 409]);
    }
    return $query;
}

/**
 * Verify the exact reviewed body/title and approved featured image currently
 * attached to a post. Missing or stale evidence always fails closed.
 *
 * @return true|WP_Error
 */
function bloguito_validate_publishability(
    $post_id,
    $content_override = null,
    $title_override = null,
    $allow_live_state = false
) {
    $post_id = (int) $post_id;
    $post = $post_id > 0 ? get_post($post_id) : null;
    if (!$post || $post->post_type !== 'post') {
        return new WP_Error('bloguito_publish_gate_invalid_post', '발행할 글을 찾을 수 없습니다.');
    }

    $raw = (string) get_post_meta($post_id, BLOGUITO_PUBLISH_GATE_META_KEY, true);
    $gate = json_decode($raw, true);
    $required = [
        'version', 'post_id', 'content_sha256', 'review_digest', 'title_sha256',
        'thumbnail_id', 'image_sha256', 'alt_text_sha256', 'approval_kind',
        'approval_evidence_sha256', 'expires_at_gmt', 'requires_live_state',
    ];
    if (!is_array($gate)) {
        return new WP_Error('bloguito_publish_gate_missing', '대표이미지와 최종 검토 승인이 완료되지 않았습니다.');
    }
    $keys = array_keys($gate);
    sort($keys);
    $expected_keys = $required;
    sort($expected_keys);
    if ($keys !== $expected_keys || ($gate['version'] ?? null) !== 1
            || (int) ($gate['post_id'] ?? 0) !== $post_id) {
        return new WP_Error('bloguito_publish_gate_invalid', '발행 승인 정보가 올바르지 않습니다.');
    }

    $sha_keys = [
        'content_sha256', 'review_digest', 'title_sha256', 'image_sha256',
        'alt_text_sha256', 'approval_evidence_sha256',
    ];
    foreach ($sha_keys as $key) {
        if (!is_string($gate[$key]) || !preg_match('/^[0-9a-f]{64}$/D', $gate[$key])) {
            return new WP_Error('bloguito_publish_gate_invalid', '발행 승인 정보가 올바르지 않습니다.');
        }
    }
    if (!in_array($gate['approval_kind'], ['manual_user_selected', 'automated_visual_review'], true)) {
        return new WP_Error('bloguito_publish_gate_image_unapproved', '대표이미지 선택 또는 품질 검수가 완료되지 않았습니다.');
    }
    if (!is_bool($gate['requires_live_state'])) {
        return new WP_Error('bloguito_publish_gate_invalid', '발행 승인 정보가 올바르지 않습니다.');
    }
    if ($gate['requires_live_state'] && !$allow_live_state) {
        return new WP_Error(
            'bloguito_publish_gate_live_state_requires_canonical_preflight',
            '현재 상태 재확인이 필요한 글은 정규 promote-draft 검증으로만 발행할 수 있습니다.'
        );
    }
    $expires = is_string($gate['expires_at_gmt']) ? strtotime($gate['expires_at_gmt']) : false;
    if ($expires === false || $expires <= time()) {
        return new WP_Error('bloguito_publish_gate_expired', '최종 검토 유효 시간이 지나 다시 검토해야 합니다.');
    }

    $content = $content_override === null ? (string) $post->post_content : (string) $content_override;
    $title = $title_override === null ? (string) $post->post_title : (string) $title_override;
    if (!hash_equals($gate['content_sha256'], hash('sha256', $content))) {
        return new WP_Error('bloguito_publish_gate_content_changed', '대표이미지 승인 뒤 본문이 변경되어 다시 검토해야 합니다.');
    }
    if (!hash_equals($gate['title_sha256'], hash('sha256', $title))) {
        return new WP_Error('bloguito_publish_gate_title_changed', '대표이미지 승인 뒤 제목이 변경되어 다시 검토해야 합니다.');
    }

    $thumbnail_id = (int) get_post_thumbnail_id($post_id);
    if ($thumbnail_id <= 0 || $thumbnail_id !== (int) $gate['thumbnail_id']) {
        return new WP_Error('bloguito_publish_gate_image_changed', '승인된 대표이미지가 현재 글과 일치하지 않습니다.');
    }
    $attachment = get_post($thumbnail_id);
    if (!$attachment || $attachment->post_type !== 'attachment' || !wp_attachment_is_image($thumbnail_id)) {
        return new WP_Error('bloguito_publish_gate_image_invalid', '대표이미지 첨부파일을 검증할 수 없습니다.');
    }
    $alt = (string) get_post_meta($thumbnail_id, '_wp_attachment_image_alt', true);
    if ($alt === '' || !hash_equals($gate['alt_text_sha256'], hash('sha256', $alt))) {
        return new WP_Error('bloguito_publish_gate_alt_changed', '대표이미지 대체텍스트가 승인 상태와 일치하지 않습니다.');
    }
    $file = get_attached_file($thumbnail_id);
    if (!is_string($file) || $file === '' || !is_file($file)) {
        return new WP_Error('bloguito_publish_gate_file_missing', '대표이미지 원본 파일을 확인할 수 없습니다.');
    }
    $file_sha = hash_file('sha256', $file);
    if (!is_string($file_sha) || !hash_equals($gate['image_sha256'], $file_sha)) {
        return new WP_Error('bloguito_publish_gate_file_changed', '승인된 대표이미지 파일이 변경되었습니다.');
    }
    return true;
}

add_filter('post_row_actions', 'bloguito_add_post_status_row_action', 10, 2);
function bloguito_add_post_status_row_action($actions, $post) {
    if (!is_object($post) || ($post->post_type ?? '') !== 'post') {
        return $actions;
    }

    $post_id = (int) ($post->ID ?? 0);
    if ($post_id <= 0) {
        return $actions;
    }

    if ($post->post_status === 'draft') {
        $target_status = 'publish';
        $label = '발행';
        $action_key = 'bloguito-publish';
    } elseif ($post->post_status === 'publish') {
        $target_status = 'draft';
        $label = '임시글로 전환';
        $action_key = 'bloguito-to-draft';
    } else {
        return $actions;
    }

    if (!bloguito_can_change_post_status($post_id, $target_status)) {
        return $actions;
    }

    $url = bloguito_post_status_action_url($post_id, $target_status);

    $action_html = sprintf(
        '<a href="%1$s" aria-label="%2$s">%3$s</a>',
        esc_url($url),
        esc_attr(sprintf('글 #%1$d을(를) %2$s', $post_id, $label)),
        esc_html($label)
    );

    $ordered_actions = [];
    $inserted = false;
    foreach ($actions as $key => $html) {
        if (!$inserted && $key === 'trash') {
            $ordered_actions[$action_key] = $action_html;
            $inserted = true;
        }
        $ordered_actions[$key] = $html;
    }
    if (!$inserted) {
        $ordered_actions[$action_key] = $action_html;
    }

    return $ordered_actions;
}

function bloguito_post_status_action_url($post_id, $target_status, $return_mode = 'referer') {
    $args = [
        'action' => 'bloguito_set_post_status',
        'post' => (int) $post_id,
        'target' => (string) $target_status,
        '_bloguito_nonce' => wp_create_nonce(
            bloguito_post_status_nonce_action($post_id, $target_status)
        ),
    ];
    if ($return_mode === 'permalink') {
        $args['bloguito_return'] = 'permalink';
    }

    return add_query_arg($args, admin_url('admin-post.php'));
}

add_action('admin_bar_menu', 'bloguito_add_preview_publish_admin_bar', 82);
function bloguito_add_preview_publish_admin_bar($wp_admin_bar) {
    if (is_admin() || !is_singular('post') || !is_preview()) {
        return;
    }

    $post_id = (int) get_queried_object_id();
    $post = $post_id > 0 ? get_post($post_id) : null;
    if (!$post || $post->post_type !== 'post' || $post->post_status !== 'draft') {
        return;
    }
    if (!bloguito_can_change_post_status($post_id, 'publish')) {
        return;
    }

    $wp_admin_bar->add_node([
        'id' => 'bloguito-preview-publish',
        'title' => '발행',
        'href' => bloguito_post_status_action_url($post_id, 'publish', 'permalink'),
        'meta' => [
            'title' => sprintf('글 #%d을 바로 발행', $post_id),
            'class' => 'bloguito-preview-publish',
        ],
    ]);
}

function bloguito_post_status_nonce_action($post_id, $target_status) {
    return 'bloguito-post-status-' . (int) $post_id . '-' . $target_status;
}

function bloguito_can_change_post_status($post_id, $target_status) {
    $post_id = (int) $post_id;
    $target_status = (string) $target_status;

    if ($post_id <= 0 || !current_user_can('edit_post', $post_id)) {
        return false;
    }
    if ($target_status === 'publish') {
        return current_user_can('publish_posts')
            && bloguito_validate_publishability($post_id) === true;
    }
    return $target_status === 'draft';
}

/**
 * Change only the post status after confirming the exact expected transition.
 *
 * @return int|WP_Error Updated post ID or an error.
 */
function bloguito_change_post_status($post_id, $target_status) {
    $post_id = (int) $post_id;
    $target_status = (string) $target_status;
    $post = get_post($post_id);

    if (!$post || $post->post_type !== 'post') {
        return new WP_Error('bloguito_invalid_post', '글을 찾을 수 없습니다.');
    }

    $expected_current = [
        'publish' => 'draft',
        'draft' => 'publish',
    ];
    if (!isset($expected_current[$target_status])) {
        return new WP_Error('bloguito_invalid_status', '허용되지 않은 글 상태입니다.');
    }
    if ($post->post_status !== $expected_current[$target_status]) {
        return new WP_Error('bloguito_status_conflict', '글 상태가 이미 변경되었습니다. 목록을 새로고침한 뒤 다시 시도하세요.');
    }
    if ($target_status === 'publish') {
        return bloguito_atomic_publish_post($post_id);
    }

    $result = wp_update_post([
        'ID' => $post_id,
        'post_status' => $target_status,
    ], true);
    if (is_wp_error($result)) {
        return $result;
    }
    $saved = get_post($post_id);
    if (!$saved || $saved->post_status !== $target_status) {
        return new WP_Error('bloguito_publish_gate_blocked', '발행 검증에서 상태 변경이 차단되었습니다.');
    }
    return $result;
}

/**
 * Publish one draft under the same row locks used by the canonical Python
 * mutation. This path is only for non-live-state posts whose attestation is
 * already current; high-volatility posts must use promote-draft.
 *
 * @return int|WP_Error
 */
function bloguito_atomic_publish_post($post_id) {
    global $wpdb;

    $post_id = (int) $post_id;
    if ($post_id <= 0 || !isset($wpdb)) {
        return new WP_Error('bloguito_publish_gate_unavailable', '발행 검증기를 사용할 수 없습니다.');
    }

    $wpdb->query('START TRANSACTION');
    $locked = $wpdb->get_var($wpdb->prepare(
        "SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",
        $post_id
    ));
    if (!$locked) {
        $wpdb->query('ROLLBACK');
        return new WP_Error('bloguito_invalid_post', '글을 찾을 수 없습니다.');
    }
    $wpdb->get_results($wpdb->prepare(
        "SELECT meta_id FROM {$wpdb->postmeta} WHERE post_id=%d AND meta_key IN (%s,%s) FOR UPDATE",
        $post_id,
        '_thumbnail_id',
        BLOGUITO_PUBLISH_GATE_META_KEY
    ));
    wp_cache_delete($post_id, 'post_meta');
    clean_post_cache($post_id);
    $post = get_post($post_id);
    if (!$post || $post->post_type !== 'post' || $post->post_status !== 'draft') {
        $wpdb->query('ROLLBACK');
        return new WP_Error('bloguito_status_conflict', '글 상태가 이미 변경되었습니다. 목록을 새로고침한 뒤 다시 시도하세요.');
    }

    $thumbnail_id = (int) get_post_thumbnail_id($post_id);
    if ($thumbnail_id > 0) {
        $wpdb->get_var($wpdb->prepare(
            "SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",
            $thumbnail_id
        ));
        $wpdb->get_results($wpdb->prepare(
            "SELECT meta_id FROM {$wpdb->postmeta} WHERE post_id=%d AND meta_key IN (%s,%s) FOR UPDATE",
            $thumbnail_id,
            '_wp_attachment_image_alt',
            '_wp_attached_file'
        ));
        wp_cache_delete($thumbnail_id, 'post_meta');
        clean_post_cache($thumbnail_id);
    }

    $gate = bloguito_validate_publishability($post_id);
    if (is_wp_error($gate)) {
        $wpdb->query('ROLLBACK');
        return $gate;
    }

    $GLOBALS['bloguito_guarded_publish_post_id'] = $post_id;
    $result = wp_update_post([
        'ID' => $post_id,
        'post_status' => 'publish',
    ], true);
    unset($GLOBALS['bloguito_guarded_publish_post_id']);
    if (is_wp_error($result)) {
        $wpdb->query('ROLLBACK');
        clean_post_cache($post_id);
        return $result;
    }

    clean_post_cache($post_id);
    $saved = get_post($post_id);
    if (!$saved || $saved->post_status !== 'publish') {
        $wpdb->query('ROLLBACK');
        clean_post_cache($post_id);
        return new WP_Error('bloguito_publish_gate_blocked', '발행 검증에서 상태 변경이 차단되었습니다.');
    }
    if ($wpdb->query('COMMIT') === false) {
        clean_post_cache($post_id);
        return new WP_Error('bloguito_publish_gate_commit_failed', '발행 트랜잭션을 완료하지 못했습니다.');
    }
    return $post_id;
}

/**
 * Cover every WordPress draft/pending/future/private -> publish route, including
 * native editor, REST, WP-CLI and custom row actions.
 */
add_filter('wp_insert_post_data', 'bloguito_guard_publish_transition', 99, 4);
function bloguito_guard_publish_transition($data, $postarr, $unsanitized_postarr = [], $update = false) {
    $post_id = isset($postarr['ID']) ? (int) $postarr['ID'] : 0;
    if (($data['post_type'] ?? '') !== 'post') {
        return $data;
    }
    if (!$update || $post_id <= 0) {
        if (in_array(($data['post_status'] ?? ''), ['publish', 'future'], true)) {
            $data['post_status'] = 'draft';
        }
        return $data;
    }
    if (($data['post_status'] ?? '') === 'future') {
        $data['post_status'] = 'draft';
        return $data;
    }
    if (($data['post_status'] ?? '') !== 'publish') {
        return $data;
    }
    $current = get_post($post_id);
    if (!$current || $current->post_type !== 'post' || $current->post_status === 'publish') {
        return $data;
    }
    if ((int) ($GLOBALS['bloguito_guarded_publish_post_id'] ?? 0) !== $post_id) {
        $data['post_status'] = $current->post_status;
    }
    return $data;
}

add_action('transition_post_status', 'bloguito_consume_publish_attestation', 10, 3);
function bloguito_consume_publish_attestation($new_status, $old_status, $post) {
    if ($new_status === 'publish' && $old_status !== 'publish'
            && is_object($post) && ($post->post_type ?? '') === 'post') {
        $post_id = (int) $post->ID;
        if ((int) ($GLOBALS['bloguito_guarded_publish_post_id'] ?? 0) !== $post_id) {
            global $wpdb;
            $wpdb->update(
                $wpdb->posts,
                ['post_status' => 'draft'],
                ['ID' => $post_id],
                ['%s'],
                ['%d']
            );
            clean_post_cache($post_id);
            return;
        }
        delete_post_meta($post_id, BLOGUITO_PUBLISH_GATE_META_KEY);
    }
}

add_action('admin_post_bloguito_set_post_status', 'bloguito_handle_post_status_action');
function bloguito_handle_post_status_action() {
    $post_id = isset($_GET['post']) ? absint($_GET['post']) : 0;
    $target_status = isset($_GET['target']) ? sanitize_key(wp_unslash($_GET['target'])) : '';
    $return_mode = isset($_GET['bloguito_return'])
        ? sanitize_key(wp_unslash($_GET['bloguito_return']))
        : 'referer';

    if ($post_id <= 0
            || !in_array($target_status, ['publish', 'draft'], true)
            || !in_array($return_mode, ['referer', 'permalink'], true)
            || ($return_mode === 'permalink' && $target_status !== 'publish')) {
        wp_die('잘못된 글 상태 변경 요청입니다.', '잘못된 요청', ['response' => 400]);
    }

    check_admin_referer(
        bloguito_post_status_nonce_action($post_id, $target_status),
        '_bloguito_nonce'
    );

    if (!bloguito_can_change_post_status($post_id, $target_status)) {
        wp_die('이 글의 발행 상태를 변경할 권한이 없습니다.', '권한 없음', ['response' => 403]);
    }

    $result = bloguito_change_post_status($post_id, $target_status);
    if (is_wp_error($result)) {
        wp_die(esc_html($result->get_error_message()), '상태 변경 실패', ['response' => 409]);
    }

    if ($return_mode === 'permalink') {
        $redirect = get_permalink($post_id);
        if (!$redirect) {
            $redirect = admin_url('edit.php');
        }
    } else {
        $redirect = wp_get_referer();
        if (!$redirect) {
            $redirect = admin_url('edit.php');
        }
        $redirect = remove_query_arg([
            'bloguito_status_changed',
            'bloguito_post_id',
        ], $redirect);
        $redirect = add_query_arg([
            'bloguito_status_changed' => $target_status,
            'bloguito_post_id' => $post_id,
        ], $redirect);
    }

    wp_safe_redirect($redirect);
    exit;
}

add_action('admin_notices', 'bloguito_post_status_changed_notice');
function bloguito_post_status_changed_notice() {
    $status = isset($_GET['bloguito_status_changed'])
        ? sanitize_key(wp_unslash($_GET['bloguito_status_changed']))
        : '';
    $post_id = isset($_GET['bloguito_post_id']) ? absint($_GET['bloguito_post_id']) : 0;
    if ($post_id <= 0 || !in_array($status, ['publish', 'draft'], true)) {
        return;
    }

    $message = $status === 'publish'
        ? sprintf('글 #%d을 발행했습니다.', $post_id)
        : sprintf('글 #%d을 임시글로 전환했습니다.', $post_id);
    echo '<div class="notice notice-success is-dismissible"><p>' . esc_html($message) . '</p></div>';
}
