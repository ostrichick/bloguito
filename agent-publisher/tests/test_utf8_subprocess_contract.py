import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Utf8SubprocessContractTests(unittest.TestCase):
    def test_production_text_subprocesses_declare_encoding(self):
        failures = []
        roots = [ROOT / "agent-publisher", ROOT / "scripts"]
        for source_root in roots:
            for path in source_root.rglob("*.py"):
                relative = path.relative_to(ROOT).as_posix()
                if any(part in {".venv", "venv", "__pycache__"} for part in path.relative_to(ROOT).parts):
                    continue
                if ("/tests/" in f"/{relative}/" or "/archive/" in f"/{relative}/"
                        or "/data/" in f"/{relative}/"):
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                        continue
                    if node.func.attr != "run" or not isinstance(node.func.value, ast.Name):
                        continue
                    if node.func.value.id != "subprocess":
                        continue
                    keywords = {item.arg: item.value for item in node.keywords if item.arg}
                    text = keywords.get("text")
                    if not isinstance(text, ast.Constant) or text.value is not True:
                        continue
                    if "encoding" not in keywords:
                        failures.append(f"{relative}:{node.lineno}")
        self.assertEqual([], failures, "text=True subprocess.run must declare encoding: " + ", ".join(failures))


if __name__ == "__main__":
    unittest.main()
