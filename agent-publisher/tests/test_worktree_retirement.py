"""Safety acceptance for explicit end-of-task Git worktree retirement."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'ops' / 'retire_worktree.py'
spec = importlib.util.spec_from_file_location('retire_worktree', SCRIPT)
retire_worktree = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retire_worktree)


class WorktreeRetirementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.main = self.folder / 'main'
        self.main.mkdir()
        self.git('init', '-b', 'main', cwd=self.main)
        self.git('config', 'user.email', 'test@example.invalid', cwd=self.main)
        self.git('config', 'user.name', 'Worktree Tests', cwd=self.main)
        (self.main / '.gitignore').write_text('scratch/\ncache/\n', encoding='utf-8')
        (self.main / 'readme.md').write_text('baseline\n', encoding='utf-8')
        self.git('add', '.', cwd=self.main)
        self.git('commit', '-m', 'base', cwd=self.main)
        self.target = self.folder / 'feature'
        self.git('worktree', 'add', '-b', 'feature', str(self.target), cwd=self.main)
        self.root_patch = patch.object(retire_worktree, 'ROOT', self.main)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    @staticmethod
    def git(*args, cwd):
        return subprocess.run(['git', *args], cwd=cwd, capture_output=True,
                              encoding='utf-8', text=True, check=True)

    def test_archives_ignored_and_deletes_only_safe_completed_branch(self):
        cache = self.target / 'cache'
        cache.mkdir()
        (cache / 'audit.json').write_text('{"keep":true}\n', encoding='utf-8')
        report = retire_worktree.retire(self.target, apply=False)
        self.assertEqual(report['ignored_file_count'], 1)
        self.assertTrue(self.target.exists())
        done = retire_worktree.retire(self.target, apply=True)
        self.assertTrue(done['applied'])
        self.assertFalse(self.target.exists())
        self.assertEqual(
            (self.main / 'scratch/tasks/worktree-retirement/feature/ignored/cache/audit.json').read_text(encoding='utf-8'),
            '{"keep":true}\n',
        )
        self.assertTrue((self.main / 'scratch/tasks/worktree-retirement/feature/receipt.json').exists())
        self.assertNotIn('feature', self.git('branch', '--list', cwd=self.main).stdout)
        self.assertTrue(self.main.exists())

    def test_refuses_unmerged_or_dirty_worktree(self):
        (self.target / 'readme.md').write_text('dirty\n', encoding='utf-8')
        with self.assertRaisesRegex(retire_worktree.RetirementBlocked, 'changes'):
            retire_worktree.retire(self.target, apply=True)
        self.git('restore', 'readme.md', cwd=self.target)
        (self.target / 'independent.txt').write_text('unique\n', encoding='utf-8')
        self.git('add', 'independent.txt', cwd=self.target)
        self.git('commit', '-m', 'unfinished work', cwd=self.target)
        with self.assertRaisesRegex(retire_worktree.RetirementBlocked, 'not merged'):
            retire_worktree.retire(self.target, apply=True)
        self.assertTrue(self.target.exists())
        self.assertFalse((self.main / 'scratch/tasks/worktree-retirement/feature').exists())

    def test_refuses_main_worktree(self):
        with self.assertRaisesRegex(retire_worktree.RetirementBlocked, 'never main'):
            retire_worktree.retire(self.main, apply=True)


if __name__ == '__main__':
    unittest.main()
