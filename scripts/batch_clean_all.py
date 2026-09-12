import os
import subprocess
from PIL import Image

UPLOADS_DIR = "/var/lib/docker/volumes/wordpress_wp_data/_data/wp-content/uploads/2026/09"
ORIGINALS = ["thumb.jpg", "feat_41.jpg", "feat_34.jpg", "feat_35.jpg"]

def clean_watermark(file_path):
    print(f"Cleaning {file_path}...")
    im = Image.open(file_path)
    w, h = im.size
    # Crop bottom 36px to eliminate pollinations.ai watermark
    cropped = im.crop((0, 0, w, h - 36))
    final_im = cropped.resize((1200, 675), Image.Resampling.LANCZOS)
    final_im.save(file_path, "JPEG", quality=95)
    print(f"-> Successfully cropped and resized to {final_im.size}")

def update_post_35():
    print("Fixing Post 35 Section 7...")
    res = subprocess.run(
        ["docker", "exec", "wordpress_app", "wp", "post", "get", "35", "--field=post_content", "--allow-root"],
        capture_output=True,
        text=True,
        check=True
    )
    content = res.stdout
    old_text = "<li><strong>광명시 1인 가구 지원센터:</strong> 공식 홈페이지 참조</li>"
    new_text = "<li><strong>광명시 1인 가구 지원센터:</strong> <a href=\"https://gm1center.or.kr\" target=\"_blank\" rel=\"noopener noreferrer\">공식 홈페이지 바로가기 (새창)</a> (문의: ☎ 02-897-2179)</li>"
    
    if old_text in content:
        content = content.replace(old_text, new_text)
        # Write to temp file inside container or stdin
        p = subprocess.Popen(
            ["docker", "exec", "-i", "wordpress_app", "wp", "post", "update", "35", "-", "--allow-root"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = p.communicate(input=content)
        print("Updated post 35:", stdout, stderr)
    else:
        print("old_text not found in post 35, already cleaned.")

def main():
    # 1. Clean images
    for fname in ORIGINALS:
        path = os.path.join(UPLOADS_DIR, fname)
        if os.path.exists(path):
            clean_watermark(path)
        else:
            print(f"File not found: {path}")

    # 2. Regenerate WordPress thumbnails
    print("Regenerating WordPress thumbnails...")
    subprocess.run(
        ["docker", "exec", "wordpress_app", "wp", "media", "regenerate", "--yes", "--allow-root"],
        check=True
    )
    print("Media regeneration complete!")

    # 3. Fix Post 35
    update_post_35()

if __name__ == "__main__":
    main()
