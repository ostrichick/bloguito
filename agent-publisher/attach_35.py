import subprocess
from agents.designer import DesignerAgent

d = DesignerAgent()
img_path = d.generate_image("광명시 1인가구 지원 런천미터 러닝크루", "생활/건강 정보", "중장년 건강 관리 꿀팁")
if img_path:
    subprocess.run(f"sudo docker cp {img_path} wordpress_app:/tmp/feat_35.jpg", shell=True)
    subprocess.run([
        "sudo", "docker", "exec", "wordpress_app",
        "wp", "media", "import", "/tmp/feat_35.jpg",
        "--post_id=35",
        "--featured_image",
        "--allow-root"
    ])
    print("Post 35 thumbnail attached!")
