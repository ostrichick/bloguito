import io
import os
import unittest
from unittest.mock import patch

from agents.runtime_stdio import configure_utf8_stdio


class _FakeStream(io.StringIO):
    def __init__(self):
        super().__init__()
        self.calls = []

    def reconfigure(self, **kwargs):
        self.calls.append(kwargs)


class RuntimeStdioTests(unittest.TestCase):
    def test_configure_utf8_stdio_sets_safe_utf8_streams_and_child_defaults(self):
        stdout = _FakeStream()
        stderr = _FakeStream()
        with patch("agents.runtime_stdio.sys.stdout", stdout), \
             patch("agents.runtime_stdio.sys.stderr", stderr), \
             patch.dict(os.environ, {}, clear=True):
            configure_utf8_stdio()
            self.assertEqual(os.environ["PYTHONIOENCODING"], "utf-8")
            self.assertEqual(os.environ["PYTHONUTF8"], "1")
        self.assertEqual(stdout.calls, [{"encoding": "utf-8", "errors": "replace"}])
        self.assertEqual(stderr.calls, [{"encoding": "utf-8", "errors": "replace"}])

    def test_korean_and_symbols_are_not_part_of_control_flow(self):
        stream = _FakeStream()
        with patch("agents.runtime_stdio.sys.stdout", stream), \
             patch("agents.runtime_stdio.sys.stderr", stream):
            configure_utf8_stdio()
            print("⚠️ 자동차검사 · → ①", file=stream)
        self.assertIn("자동차검사", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
