import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ScriptHygieneTests(unittest.TestCase):
    def test_scripts_root_contains_only_declared_reusable_python_tools(self):
        manifest = json.loads((ROOT / "scripts" / "maintained_scripts.json").read_text(encoding="utf-8"))
        declared = set(manifest["scripts"])
        present = {path.name for path in (ROOT / "scripts").glob("*.py")}
        self.assertEqual(declared, present)

    def test_ephemeral_workspaces_are_gitignored(self):
        lines = {
            line.strip() for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        }
        self.assertTrue({"/scratch/", "/docs/tasks/", "/scripts/archive/"}.issubset(lines))


if __name__ == "__main__":
    unittest.main()
