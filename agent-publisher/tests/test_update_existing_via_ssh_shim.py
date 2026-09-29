import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "update_existing_via_ssh.py"


def load_module():
    spec = importlib.util.spec_from_file_location("update_existing_via_ssh_shim", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UpdateExistingViaSshShimTests(unittest.TestCase):
    def test_legacy_arguments_forward_to_unified_adapter(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / "bundle.json"
            bundle.write_text("{}", encoding="utf-8")
            args = module.parse_args([
                str(bundle), "--post-id", "243", "--expected-content-sha256", "a" * 64,
                "--ssh-host", "bloguito", "--confirm-update", "--confirm-title-change",
            ])
        command = module.build_forwarded_command(args)
        self.assertIn("editorial_cli_via_ssh.py", command[1])
        self.assertEqual("update-existing", command[command.index("--") + 1])
        self.assertIn("--confirm-update", command)
        self.assertIn("--confirm-title-change", command)
        self.assertEqual("bloguito", command[command.index("--ssh-host") + 1])

    def test_main_returns_unified_adapter_exit_code(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / "bundle.json"
            bundle.write_text("{}", encoding="utf-8")
            with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 7)) as run:
                code = module.main([
                    str(bundle), "--post-id", "243", "--expected-content-sha256", "a" * 64,
                    "--confirm-update",
                ])
        self.assertEqual(7, code)
        self.assertEqual("update-existing", run.call_args.args[0][run.call_args.args[0].index("--") + 1])


if __name__ == "__main__":
    unittest.main()
