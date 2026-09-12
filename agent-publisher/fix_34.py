import subprocess

def fix_34():
    c34 = subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "get", "34", "--field=post_content", "--allow-root"], capture_output=True, text=True).stdout
    btn = '''
<div style="text-align: center; margin: 30px 0;">
  <a href="https://www.bokjiro.go.kr" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #2b6cb0; color: #ffffff; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1.15em; box-shadow: 0 4px 6px rgba(0,0,0,0.15);">👉 [복지로] 정부 지원금 온라인 신청 바로가기 (새창)</a>
</div>
'''
    new_c = c34 + btn
    new_c = new_c.replace("www.bokjiro.go.kr", '<a href="https://www.bokjiro.go.kr" target="_blank" rel="noopener noreferrer">www.bokjiro.go.kr(새창)</a>')
    with open("/tmp/p34.html", "w", encoding="utf-8") as f:
        f.write(new_c)
    subprocess.run("sudo docker cp /tmp/p34.html wordpress_app:/tmp/p34.html", shell=True)
    subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "update", "34", "/tmp/p34.html", "--allow-root"])
    print("Updated Post 34 successfully!")

if __name__ == "__main__":
    fix_34()
