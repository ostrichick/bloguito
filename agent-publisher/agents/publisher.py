import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from config import POST_STATUS, POSTS_INDEX_FILE, SITE_URL


class PublisherAgent:
    """작성된 원고와 썸네일 이미지를 워드프레스 컨테이너에 안전하게 등록하고 내부 링크 색인을 갱신하는 발행 에이전트"""

    def __init__(self, container_name: str = "wordpress_app"):
        self.container_name = container_name

    def _record_published_post(self, post_id: int, title: str, category_id: int, category_name: str):
        """성공적으로 발행된 포스트 정보를 로컬 색인 파일에 기록하여 차후 타 포스트의 내부 링크(Interlinking) 추천에 활용"""
        posts = []
        if POSTS_INDEX_FILE.exists():
            try:
                with open(POSTS_INDEX_FILE, "r", encoding="utf-8") as f:
                    posts = json.load(f)
            except Exception:
                posts = []

        # 워드프레스 고유주소(URL) 조회
        url_cmd = [
            "sudo", "docker", "exec", self.container_name,
            "wp", "post", "get", str(post_id),
            "--field=url",
            "--allow-root"
        ]
        res = subprocess.run(url_cmd, capture_output=True, text=True)
        post_url = res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else f"{SITE_URL}/?p={post_id}"

        # 중복 제거 후 추가
        posts = [p for p in posts if p.get("id") != post_id]
        posts.append({
            "id": post_id,
            "title": title,
            "url": post_url,
            "category_id": category_id,
            "category_name": category_name,
            "published_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

        POSTS_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(POSTS_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)
        print(f"[PublisherAgent] 📚 내부 링크 색인(Interlinking Index) 업데이트 완료 ({len(posts)}개 글 등록)")

    def publish(self, article: dict, image_path: Path = None) -> int:
        title = article["title"]
        content = article["content"]
        cat_id = article["category_id"]
        cat_name = article.get("category_name", "")
        tags_str = ",".join(article.get("tags", []))
        status = POST_STATUS  # 'draft' or 'publish'

        print(f"[PublisherAgent] 🚀 워드프레스 포스트 등록: '{title}' (상태: {status})")

        # 1. HTML 본문 임시 파일 저장 및 컨테이너 복사
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".html") as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            container_file = f"/tmp/post_content_{temp_path.stem}.html"
            cp_cmd = f"sudo docker cp {temp_path} {self.container_name}:{container_file}"
            subprocess.run(cp_cmd, shell=True, check=True, stdout=subprocess.DEVNULL)

            # 2. WP-CLI 명령으로 포스트 생성
            wp_cmd = [
                "sudo", "docker", "exec", self.container_name,
                "wp", "post", "create", container_file,
                f"--post_type=post",
                f"--post_status={status}",
                f"--post_title={title}",
                f"--post_category={cat_id}",
                f"--tags_input={tags_str}",
                "--allow-root",
                "--porcelain",
            ]

            res = subprocess.run(wp_cmd, capture_output=True, text=True, check=True)
            post_id = int(res.stdout.strip())

            # 3. 임시 파일 정리
            subprocess.run(f"sudo docker exec {self.container_name} rm -f {container_file}", shell=True, stdout=subprocess.DEVNULL)

            # 4. 특성 이미지(썸네일) 연결
            if image_path and image_path.exists():
                try:
                    container_img = f"/tmp/feat_{post_id}.jpg"
                    subprocess.run(f"sudo docker cp {image_path} {self.container_name}:{container_img}", shell=True, check=True, stdout=subprocess.DEVNULL)
                    img_cmd = [
                        "sudo", "docker", "exec", self.container_name,
                        "wp", "media", "import", container_img,
                        f"--post_id={post_id}",
                        "--featured_image",
                        "--allow-root",
                    ]
                    subprocess.run(img_cmd, capture_output=True, text=True, check=True)
                    subprocess.run(f"sudo docker exec {self.container_name} rm -f {container_img}", shell=True, stdout=subprocess.DEVNULL)
                    print(f"[PublisherAgent] 🖼️ 대표 썸네일(Featured Image) 등록 완료! (Post #{post_id})")
                except Exception as img_err:
                    print(f"[PublisherAgent] ⚠️ 썸네일 등록 중 오류: {img_err}")

            # 5. 내부 링크 색인 저장
            try:
                self._record_published_post(post_id, title, cat_id, cat_name)
            except Exception as rec_err:
                print(f"[PublisherAgent] ⚠️ 색인 저장 중 오류: {rec_err}")

            print(f"[PublisherAgent] 🎉 포스팅 완료! (Post ID: {post_id}, 상태: {status})")
            return post_id

        except Exception as e:
            print(f"[PublisherAgent] ❌ 발행 실패: {e}")
            raise e
        finally:
            if temp_path.exists():
                temp_path.unlink()
