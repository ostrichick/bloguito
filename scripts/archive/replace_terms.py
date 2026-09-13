import subprocess

def clean_terms():
    res = subprocess.run(
        ["sudo", "docker", "exec", "wordpress_app", "wp", "post", "list", "--format=ids", "--allow-root"],
        capture_output=True,
        text=True,
    )
    ids = res.stdout.strip().split()

    for pid in ids:
        t_res = subprocess.run(
            ["sudo", "docker", "exec", "wordpress_app", "wp", "post", "get", pid, "--field=post_title", "--allow-root"],
            capture_output=True,
            text=True,
        )
        c_res = subprocess.run(
            ["sudo", "docker", "exec", "wordpress_app", "wp", "post", "get", pid, "--field=post_content", "--allow-root"],
            capture_output=True,
            text=True,
        )
        title = t_res.stdout.strip()
        content = c_res.stdout.strip()

        # 제목 정제
        new_title = (
            title.replace("선생님들의", "")
            .replace("선생님들", "")
            .replace("선생님의", "")
            .replace("선생님", "")
            .replace("독자 여러분", "여러분")
            .replace("독자", "")
            .replace("  ", " ")
        )
        # 본문 정제
        new_content = (
            content.replace("선생님 여러분", "여러분")
            .replace("독자 여러분", "여러분")
            .replace("선생님들께서", "여러분께서")
            .replace("선생님들", "여러분")
            .replace("선생님의", "여러분의")
            .replace("선생님께", "여러분께")
            .replace("선생님", "여러분")
            .replace("독자분들", "여러분")
            .replace("독자들", "여러분")
        )

        if new_title != title or new_content != content:
            temp_file = f"/tmp/post_{pid}.txt"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            subprocess.run(f"sudo docker cp {temp_file} wordpress_app:{temp_file}", shell=True)
            subprocess.run(
                ["sudo", "docker", "exec", "wordpress_app", "wp", "post", "update", pid, temp_file, f"--post_title={new_title}", "--allow-root"]
            )
            print(f"Cleaned Post #{pid}: {new_title}")

if __name__ == "__main__":
    clean_terms()
