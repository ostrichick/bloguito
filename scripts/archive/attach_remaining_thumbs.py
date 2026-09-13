from agents.designer import DesignerAgent
from agents.publisher import PublisherAgent
from config import CATEGORIES

designer = DesignerAgent()
publisher = PublisherAgent()

tasks = [tasks[1]] #
    {
        "id": 34,
        "title": "고유가 피해지원금 2차 지급 정부 지원금 신청 자격 금액 신청방법 총정리",
        "category": "정부 복지/지원금",
        "keyword": "정부 지원금 신청 자격",
    },
    {
        "id": 35,
        "title": "광명시 1인가구 지원 런천미터 러닝크루 신청 방법 기간 대상 중장년 건강 관리 꿀팁 총정리",
        "category": "생활/건강 정보",
        "keyword": "중장년 건강 관리 꿀팁",
    },
]

for t in tasks:
    img_path = designer.generate_image(t["title"], t["category"], t["keyword"])
    if img_path:
        import subprocess
        container_img = f"/tmp/feat_{t['id']}.jpg"
        subprocess.run(f"sudo docker cp {img_path} wordpress_app:{container_img}", shell=True)
        subprocess.run([
            "sudo", "docker", "exec", "wordpress_app",
            "wp", "media", "import", container_img,
            f"--post_id={t['id']}",
            "--featured_image",
            "--allow-root"
        ])
        print(f"Thumbnail attached to Post #{t['id']}")
