import subprocess

def add_buttons():
    # 1. Post 33 (비바브라보 트로트 콘서트)
    c33_res = subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "get", "33", "--field=post_content", "--allow-root"], capture_output=True, text=True)
    c33 = c33_res.stdout.strip()
    btn33 = '''
<div style="text-align: center; margin: 30px 0;">
  <a href="https://tickets.interpark.com" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #e53e3e; color: #ffffff; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1.15em; box-shadow: 0 4px 6px rgba(0,0,0,0.15);">👉 [인터파크] 티켓 예매처 바로가기 (새창)</a>
</div>
'''
    if "인터파크" in c33 and "target=\"_blank\"" not in c33:
        # STEP 1 또는 글 중간에 버튼 삽입
        new_c33 = c33.replace("<h2>2. ", btn33 + "<h2>2. ")
        new_c33 = new_c33.replace("인터파크 티켓", '<a href="https://tickets.interpark.com" target="_blank" rel="noopener noreferrer">인터파크 티켓(새창)</a>')
        with open("/tmp/p33.html", "w", encoding="utf-8") as f:
            f.write(new_c33)
        subprocess.run("sudo docker cp /tmp/p33.html wordpress_app:/tmp/p33.html", shell=True)
        subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "update", "33", "/tmp/p33.html", "--allow-root"])
        print("Updated Post 33 with button!")

    # 2. Post 34 (고유가 피해지원금 2차 지급)
    c34_res = subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "get", "34", "--field=post_content", "--allow-root"], capture_output=True, text=True)
    c34 = c34_res.stdout.strip()
    btn34 = '''
<div style="text-align: center; margin: 30px 0;">
  <a href="https://www.bokjiro.go.kr" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #2b6cb0; color: #ffffff; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1.15em; box-shadow: 0 4px 6px rgba(0,0,0,0.15);">👉 [복지로] 정부 지원금 온라인 신청 바로가기 (새창)</a>
</div>
'''
    if "target=\"_blank\"" not in c34:
        new_c34 = c34.replace("<h2>3. ", btn34 + "<h2>3. ")
        new_c34 = new_c34.replace("www.bokjiro.go.kr", '<a href="https://www.bokjiro.go.kr" target="_blank" rel="noopener noreferrer">www.bokjiro.go.kr(새창)</a>')
        new_c34 = new_c34.replace("www.gov.kr", '<a href="https://www.gov.kr" target="_blank" rel="noopener noreferrer">www.gov.kr(새창)</a>')
        with open("/tmp/p34.html", "w", encoding="utf-8") as f:
            f.write(new_c34)
        subprocess.run("sudo docker cp /tmp/p34.html wordpress_app:/tmp/p34.html", shell=True)
        subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "update", "34", "/tmp/p34.html", "--allow-root"])
        print("Updated Post 34 with button!")

    # 3. Post 35 (광명시 1인가구 러닝크루)
    c35_res = subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "get", "35", "--field=post_content", "--allow-root"], capture_output=True, text=True)
    c35 = c35_res.stdout.strip()
    btn35 = '''
<div style="text-align: center; margin: 30px 0;">
  <a href="https://www.gm.go.kr" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #319795; color: #ffffff; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1.15em; box-shadow: 0 4px 6px rgba(0,0,0,0.15);">👉 [광명시청] 공식 접수 및 공고 확인 바로가기 (새창)</a>
</div>
'''
    if "target=\"_blank\"" not in c35:
        new_c35 = c35.replace("<h2>3. ", btn35 + "<h2>3. ")
        new_c35 = new_c35.replace("광명시청", '<a href="https://www.gm.go.kr" target="_blank" rel="noopener noreferrer">광명시청 공식 홈페이지(새창)</a>')
        with open("/tmp/p35.html", "w", encoding="utf-8") as f:
            f.write(new_c35)
        subprocess.run("sudo docker cp /tmp/p35.html wordpress_app:/tmp/p35.html", shell=True)
        subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "update", "35", "/tmp/p35.html", "--allow-root"])
        print("Updated Post 35 with button!")

if __name__ == "__main__":
    add_buttons()
