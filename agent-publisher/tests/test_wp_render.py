import subprocess
import re
import sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_calc_script import clean_script

# Prepare php code to test apply_filters('the_content') on clean_script
php_code = f"""
$raw = <<<'EOD'
{clean_script}
EOD;
echo apply_filters('the_content', $raw);
"""

# Run via ssh and docker exec
cmd = [
    "ssh", "bloguito",
    "sudo docker exec -i wordpress_app php"
]

proc = subprocess.run(
    cmd,
    input=f"<?php require '/var/www/html/wp-load.php';\n{php_code}".encode("utf-8"),
    capture_output=True,
    text=False,
)

if proc.returncode != 0:
    print("SSH/PHP Error:", proc.stderr.decode("utf-8", errors="replace"))
    sys.exit(proc.returncode)

rendered = proc.stdout.decode("utf-8", errors="replace")

# Check if there are any <p> or </p> inside <script>
m = re.search(r'(<script[\s\S]*?</script>)', rendered)
if not m:
    print("ERROR: <script> tag not found in rendered output")
    sys.exit(1)

script_tag = m.group(1)
if "<p>" in script_tag or "</p>" in script_tag:
    print("FAILED: <p> or </p> still found inside <script> tag!")
    print(script_tag)
    sys.exit(1)

print("SUCCESS: 0 <p> or </p> tags inside <script>! wpautop preserved script perfectly!")
print("Rendered script snippet:")
print(script_tag[:200] + "...")
