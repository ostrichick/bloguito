import subprocess
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_calc_script import clean_script

# 1. Fetch current post 609 content directly from WordPress
print("[1] Fetching current post 609 content from WordPress...")
fetch_cmd = ["ssh", "bloguito", "sudo docker exec wordpress_app wp post get 609 --field=post_content --allow-root"]
res = subprocess.run(fetch_cmd, capture_output=True, text=False, check=True)
current_content = res.stdout.decode("utf-8", errors="replace").lstrip("\ufeff")

# 2. Verify script pattern in current content
if "<script>" not in current_content or "</script>" not in current_content:
    print("ERROR: <script> block not found in current post content")
    sys.exit(1)

# Replace the script block with clean_script
pattern = r'<script[\s\S]*?</script>'
updated_content = re.sub(pattern, lambda m: clean_script, current_content)

print("[2] Replacing script block with wpautop-safe clean_script...")

# Write updated content to a temporary file locally
tmp_file = Path("post_609_updated.html")
tmp_file.write_text(updated_content, encoding="utf-8")

# 3. Transfer and update post 609 on WordPress
print("[3] Updating WordPress post 609 content via WP-CLI...")
# Transfer file to remote container tmp
copy_cmd = ["scp", "post_609_updated.html", "bloguito:/tmp/post_609_updated.html"]
subprocess.run(copy_cmd, check=True)

# Copy into docker container and run wp post update
docker_prep = ["ssh", "bloguito", "sudo docker cp /tmp/post_609_updated.html wordpress_app:/tmp/post_609_updated.html"]
subprocess.run(docker_prep, check=True)

update_cmd = [
    "ssh", "bloguito",
    "sudo docker exec wordpress_app wp post update 609 /tmp/post_609_updated.html --allow-root"
]
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

res = subprocess.run(update_cmd, capture_output=True, text=False, check=True)
print("WP Update Output:", res.stdout.decode("utf-8", errors="replace").lstrip("\ufeff").strip())

# Clean up remote tmp
subprocess.run(["ssh", "bloguito", "sudo docker exec wordpress_app rm -f /tmp/post_609_updated.html ; rm -f /tmp/post_609_updated.html"], check=True)

# 4. Verify post 609 status, thumbnail, and rendered output
print("[4] Verifying post 609 status, thumbnail, and rendered script on WordPress...")
verify_php = """
$p = get_post(609);
$thumb = get_post_thumbnail_id(609);
$content = $p->post_content;
$rendered = apply_filters('the_content', $content);

preg_match('/<script[\\s\\S]*?<\\/script>/', $rendered, $m);
$script_has_p = (isset($m[0]) && (strpos($m[0], '<p>') !== false || strpos($m[0], '</p>') !== false)) ? 'YES' : 'NO';

echo json_encode([
    'id' => $p->ID,
    'status' => $p->post_status,
    'thumbnail_id' => $thumb,
    'has_thumbnail' => has_post_thumbnail(609),
    'script_found' => isset($m[0]),
    'script_has_p' => $script_has_p,
]);
"""

verify_cmd = [
    "ssh", "bloguito",
    "sudo docker exec -i wordpress_app php"
]
proc = subprocess.run(
    verify_cmd,
    input=f"<?php require '/var/www/html/wp-load.php';\n{verify_php}".encode("utf-8"),
    capture_output=True,
    text=False,
    check=True,
)

import json
info = json.loads(proc.stdout.decode("utf-8-sig", errors="replace"))
print("Verification Result:")
print(json.dumps(info, indent=2, ensure_ascii=False))

assert info["status"] == "draft", "Post 609 must remain draft!"
assert info["has_thumbnail"] is True, "Post 609 must have thumbnail!"
assert info["thumbnail_id"] != 0, "Thumbnail ID must not be 0!"
assert info["script_found"] is True, "Script must be found in rendered output!"
assert info["script_has_p"] == "NO", "Rendered script MUST NOT contain any <p> or </p> tags!"

print("\n🎉 ALL CHECKS PASSED: Post 609 calculator script is completely fixed and working without wpautop corruption!")
