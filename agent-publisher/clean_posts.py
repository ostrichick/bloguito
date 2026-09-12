import subprocess
import re

def clean_and_fix_posts():
    # 1. Post 34 복구
    res34 = subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "get", "34", "--field=post_content", "--allow-root"], capture_output=True, text=True)
    c34 = res34.stdout.strip()

    # 깨진 태그 정리: 중복 a 태그 싹 제거 후 정상 구조로 교체
    c34_clean = re.sub(r'<a href="https://<a href="[^"]+"[^>]*>[^<]+</a>" target="_blank"[^>]*>👉 \[복지로\][^<]+</a>', '', c34)
    c34_clean = re.sub(r'www\.bokjiro\.go\.kr\(새창\)" target="_blank" rel="noopener">복지로 공식 홈페이지 \(www\.bokjiro\.go\.kr\(새창\)\)', '<a href="https://www.bokjiro.go.kr" target="_blank" rel="noopener noreferrer">복지로 공식 홈페이지 (www.bokjiro.go.kr)</a>', c34_clean)
    c34_clean = re.sub(r'<a href="https://www\.bokjiro\.go\.kr"[^>]*>www\.bokjiro\.go\.kr\(새창\)</a>', '<a href="https://www.bokjiro.go.kr" target="_blank" rel="noopener noreferrer">www.bokjiro.go.kr</a>', c34_clean)
    c34_clean = re.sub(r'<a href="https://www\.gov\.kr"[^>]*>www\.gov\.kr\(새창\)</a>', '<a href="https://www.gov.kr" target="_blank" rel="noopener noreferrer">www.gov.kr</a>', c34_clean)
    
    # 깔끔한 단일 버튼 추가
    btn34 = '''
<div style="text-align: center; margin: 35px 0;">
  <a href="https://www.bokjiro.go.kr" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #2b6cb0; color: #ffffff; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1.15em; box-shadow: 0 4px 6px rgba(0,0,0,0.15);">👉 [복지로] 정부 지원금 온라인 신청 바로가기 (새창)</a>
</div>
'''
    if "👉 [복지로] 정부 지원금 온라인 신청 바로가기" not in c34_clean:
        c34_clean = c34_clean.strip() + btn34

    with open("/tmp/clean_34.html", "w", encoding="utf-8") as f:
        f.write(c34_clean)
    subprocess.run("sudo docker cp /tmp/clean_34.html wordpress_app:/tmp/clean_34.html", shell=True)
    subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "update", "34", "/tmp/clean_34.html", "--allow-root"])
    print("Post 34 successfully cleaned and fixed!")

    # 2. Post 35 복구 (공식 홈페이지 참조 -> 실제 링크 및 버튼 삽입)
    res35 = subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "get", "35", "--field=post_content", "--allow-root"], capture_output=True, text=True)
    c35 = res35.stdout.strip()

    c35_clean = c35.replace(
        "광명시 1인 가구 지원센터: 공식 홈페이지 참조",
        '광명시 1인 가구 지원센터: <a href="https://www.gm.go.kr" target="_blank" rel="noopener noreferrer">광명시청 공식 홈페이지 (www.gm.go.kr)</a>'
    )
    
    btn35 = '''
<div style="text-align: center; margin: 35px 0;">
  <a href="https://www.gm.go.kr" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #319795; color: #ffffff; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1.15em; box-shadow: 0 4px 6px rgba(0,0,0,0.15);">👉 [광명시청] 공식 접수 및 공고 확인 바로가기 (새창)</a>
</div>
'''
    if "👉 [광명시청] 공식 접수 및 공고 확인 바로가기" not in c35_clean:
        c35_clean = c35_clean.strip() + btn35

    with open("/tmp/clean_35.html", "w", encoding="utf-8") as f:
        f.write(c35_clean)
    subprocess.run("sudo docker cp /tmp/clean_35.html wordpress_app:/tmp/clean_35.html", shell=True)
    subprocess.run(["sudo", "docker", "exec", "wordpress_app", "wp", "post", "update", "35", "/tmp/clean_35.html", "--allow-root"])
    print("Post 35 successfully cleaned and fixed!")

if __name__ == "__main__":
    clean_and_fix_posts()
