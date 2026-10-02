<?php
/**
 * Plugin Name: Bloguito Post Row Actions
 * Description: Add guarded publish/draft status actions to the Posts list and draft preview admin bar.
 * Version: 1.1.0
 */

if (!defined('ABSPATH')) {
    exit;
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
        return current_user_can('publish_posts');
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

    return wp_update_post([
        'ID' => $post_id,
        'post_status' => $target_status,
    ], true);
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
