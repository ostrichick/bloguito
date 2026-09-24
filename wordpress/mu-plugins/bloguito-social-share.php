<?php
/**
 * Plugin Name: Bloguito Social Share & URL Copy
 * Description: Zero-bloat, high-performance 1-click URL copy and multi-messenger social sharing component for single posts.
 * Version: 1.0.0
 * Author: Bloguito Editorial Team
 */

if (!defined('ABSPATH')) {
    exit;
}

add_filter('the_content', 'bloguito_inject_social_share');

function bloguito_inject_social_share($content) {
    // Only inject on single post view in the main query loop
    if (!is_singular('post') || !in_the_loop() || !is_main_query()) {
        return $content;
    }

    $post_url   = esc_url(get_permalink());
    $post_title = esc_attr(get_the_title());
    $encoded_url = urlencode(get_permalink());
    $encoded_title = urlencode(get_the_title());

    // 1. Top Mini Share Bar
    $top_bar = '
    <div class="bloguito-top-share" style="display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin: 10px 0 22px 0; font-size: 13px;">
        <span style="color: #64748b; font-weight: 500; font-size: 12px;">공유하기</span>
        <button type="button" class="btn-copy-url" data-url="' . $post_url . '" style="background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; transition: all 0.2s;">
            🔗 링크 복사
        </button>
        <button type="button" class="btn-native-share" data-title="' . $post_title . '" data-url="' . $post_url . '" style="background: #fee500; color: #191919; border: 1px solid #e5ce00; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; transition: all 0.2s;">
            💬 카톡, 공유
        </button>
    </div>';

    // 2. Bottom Rich Share Card
    $bottom_card = '
    <div class="bloguito-bottom-share" style="margin: 45px 0 25px 0; padding: 24px 20px; background-color: #f8fafc; border: 1.5px solid #e2e8f0; border-radius: 14px; text-align: center; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);">
        <div style="font-size: 16px; font-weight: 800; color: #0f172a; margin-bottom: 6px;">
            📢 유익한 정보였다면 가족, 지인분들과 함께 나눠보세요!
        </div>
        <p style="font-size: 13.5px; color: #64748b; margin: 0 0 18px 0;">
            원클릭으로 링크를 복사하거나 카카오톡 및 SNS로 손쉽게 전달할 수 있습니다.
        </p>

        <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 10px;">
            <!-- URL 복사 -->
            <button type="button" class="btn-copy-url" data-url="' . $post_url . '" style="background-color: #1e293b; color: #ffffff; border: none; border-radius: 8px; padding: 10px 18px; font-size: 14px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 5px rgba(30, 41, 59, 0.15); transition: all 0.2s;">
                🔗 링크 복사
            </button>

            <!-- 카카오톡 / 메신저 (Web Share) -->
            <button type="button" class="btn-native-share" data-title="' . $post_title . '" data-url="' . $post_url . '" style="background-color: #fee500; color: #191919; border: 1px solid #e5ce00; border-radius: 8px; padding: 10px 18px; font-size: 14px; font-weight: 800; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 5px rgba(254, 229, 0, 0.3); transition: all 0.2s;">
                💬 카카오톡, 메신저
            </button>

            <!-- 네이버 블로그/카페 -->
            <a href="https://share.naver.com/web/shareView?url=' . $encoded_url . '&title=' . $encoded_title . '" target="_blank" rel="noopener noreferrer" style="background-color: #03c75a; color: #ffffff; border-radius: 8px; padding: 10px 16px; font-size: 14px; font-weight: 700; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 5px rgba(3, 199, 90, 0.2); transition: all 0.2s;">
                🟢 네이버
            </a>

            <!-- 밴드 -->
            <a href="https://band.us/plugin/share?body=' . $encoded_title . '%0A' . $encoded_url . '&route=lifeinfo24.org" target="_blank" rel="noopener noreferrer" style="background-color: #00d344; color: #ffffff; border-radius: 8px; padding: 10px 16px; font-size: 14px; font-weight: 700; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 5px rgba(0, 211, 68, 0.2); transition: all 0.2s;">
                밴드(BAND)
            </a>

            <!-- 페이스북 -->
            <a href="https://www.facebook.com/sharer/sharer.php?u=' . $encoded_url . '" target="_blank" rel="noopener noreferrer" style="background-color: #1877f2; color: #ffffff; border-radius: 8px; padding: 10px 16px; font-size: 14px; font-weight: 700; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 5px rgba(24, 119, 242, 0.2); transition: all 0.2s;">
                페이스북
            </a>
        </div>
    </div>';

    // 3. Lightweight Client-Side Script
    $script = '
    <script>
    (function() {
        if (window.__bloguitoShareInit) return;
        window.__bloguitoShareInit = true;

        document.addEventListener("click", function(e) {
            var copyBtn = e.target.closest(".btn-copy-url");
            if (copyBtn) {
                var url = copyBtn.getAttribute("data-url") || window.location.href;
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(url).then(function() {
                        showCopySuccess(copyBtn);
                    }).catch(function() {
                        fallbackCopy(url, copyBtn);
                    });
                } else {
                    fallbackCopy(url, copyBtn);
                }
                return;
            }

            var shareBtn = e.target.closest(".btn-native-share");
            if (shareBtn) {
                var title = shareBtn.getAttribute("data-title") || document.title;
                var sUrl = shareBtn.getAttribute("data-url") || window.location.href;
                if (navigator.share) {
                    navigator.share({
                        title: title,
                        text: title,
                        url: sUrl
                    }).catch(function(err) {
                        if (err.name !== "AbortError") {
                            console.log("Share failed:", err);
                        }
                    });
                } else {
                    var kakaoUrl = "https://story.kakao.com/share?url=" + encodeURIComponent(sUrl);
                    window.open(kakaoUrl, "_blank", "width=600,height=500,location=no,status=no,scrollbars=yes");
                }
                return;
            }
        });

        function showCopySuccess(btn) {
            var originalHtml = btn.innerHTML;
            var originalBg = btn.style.backgroundColor;
            var originalColor = btn.style.color;

            btn.innerHTML = "✅ 복사 완료!";
            btn.style.backgroundColor = "#147d64";
            btn.style.color = "#ffffff";

            setTimeout(function() {
                btn.innerHTML = originalHtml;
                btn.style.backgroundColor = originalBg;
                btn.style.color = originalColor;
            }, 2500);
        }

        function fallbackCopy(url, btn) {
            var input = document.createElement("textarea");
            input.value = url;
            input.style.position = "fixed";
            input.style.opacity = "0";
            document.body.appendChild(input);
            input.select();
            try {
                document.execCommand("copy");
                showCopySuccess(btn);
            } catch (err) {
                prompt("아래 URL을 복사하세요:", url);
            }
            document.body.removeChild(input);
        }
    })();
    </script>';

    return $top_bar . $content . $bottom_card . $script;
}
