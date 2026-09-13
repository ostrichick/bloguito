import subprocess
import re

c35 = subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "get", "35", "--field=post_content", "--allow-root"], capture_output=True, text=True).stdout

# 깨끗하게 정제
clean_btn = '<div style="text-align: center; margin: 30px 0;"><a href="https://www.gm.go.kr" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #319795; color: #ffffff; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1.15em; box-shadow: 0 4px 6px rgba(0,0,0,0.15);">👉 [광명시청] 공식 접수 및 공고 확인 바로가기 (새창)</a></div>'

# 중첩 태그 및 중복 버튼 정리
c35 = re.sub(r'<div style="text-align: center; margin: 3[05]px 0;">.*?</div>', '', c35, flags=re.DOTALL)
c35 = c35.replace("광명시 1인 가구 지원센터: 공식 홈페이지 참조", '광명시 1인 가구 지원센터: <a href="https://www.gm.go.kr" target="_blank" rel="noopener noreferrer">광명시청 공식 홈페이지 (www.gm.go.kr)</a>')

# 깔끔하게 2번 끝과 맨 끝에 단일 버튼 삽입
c35 = c35.replace("<h2>3. ", clean_btn + "\n<h2>3. ")
c35 = c35.strip() + "\n" + clean_btn

with open("/tmp/clean_35.html", "w", encoding="utf-8") as f:
    f.write(c35)

subprocess.run("sudo docker cp /tmp/clean_35.html wordpress_app:/tmp/clean_35.html", shell=True)
subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "update", "35", "/tmp/clean_35.html", "--allow-root"])
print("Post 35 cleaned perfectly!")
