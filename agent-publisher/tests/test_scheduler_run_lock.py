"""Cross-process fault injection for the scheduled-growth writer boundary.

No WordPress/network access: subprocesses replace the work function before
invoking the REAL main CLI entrypoint, exercising its OS lock and result path.
"""

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AGENT_ROOT.parent
DRIVER = textwrap.dedent("""
    import os, sys, time
    sys.path.insert(0, os.environ['BLOGUITO_AGENT_ROOT'])
    import main as pipeline
    def fake_run(*args, **kwargs):
        with open(os.environ['BLOGUITO_LOCK_TEST_MARKER'], 'a', encoding='ascii') as stream:
            stream.write('entered\\n')
            stream.flush()
        time.sleep(float(os.environ.get('BLOGUITO_LOCK_TEST_SLEEP', '1.1')))
        return {'growth_action': 'no_action', 'growth_reason': 'test',
                'growth_outcome': 'no_action', 'errors': 0, 'published': 0}
    pipeline.run_pipeline = fake_run
    raise SystemExit(pipeline.main(['--category', 'health']))
""")


def _pipeline_result(output):
    lines = [line[len('PIPELINE_RESULT '):] for line in output.splitlines()
             if line.startswith('PIPELINE_RESULT ')]
    if len(lines) != 1:
        raise AssertionError('expected exactly one PIPELINE_RESULT, saw: ' + output[:1000])
    return json.loads(lines[0])


class SchedulerRunLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.marker = self.base / 'entered.txt'
        self.lock = self.base / 'growth' / '.scheduler-run.lock'
        self.env = dict(os.environ,
                        BLOGUITO_AGENT_ROOT=str(AGENT_ROOT),
                        BLOGUITO_LOCK_TEST_MARKER=str(self.marker),
                        BLOGUITO_GROWTH_LOCK_PATH=str(self.lock),
                        PYTHONUTF8='1')
        self.processes = []
        self.addCleanup(self._stop_processes)

    def _stop_processes(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            # A wait() does not close pipes; explicit close avoids test-suite
            # ResourceWarnings when a subprocess already exited successfully.
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

    def _launch(self, *, sleep='1.1'):
        env = dict(self.env, BLOGUITO_LOCK_TEST_SLEEP=sleep)
        process = subprocess.Popen([sys.executable, '-u', '-c', DRIVER], env=env,
                                   cwd=REPO_ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding='utf-8')
        self.processes.append(process)
        return process

    def _await_entry(self):
        limit = time.monotonic() + 8
        while time.monotonic() < limit:
            if self.marker.exists() and self.marker.stat().st_size:
                return
            time.sleep(.02)
        self.fail('first process did not enter the guarded pipeline')

    def test_two_main_processes_only_one_runs_and_busy_is_not_no_action(self):
        first = self._launch()
        self._await_entry()
        second = self._launch()
        second_out, second_err = second.communicate(timeout=12)
        self.assertEqual(0, second.returncode, second_err)
        busy = _pipeline_result(second_out)
        self.assertEqual('already_running', busy['status'])
        self.assertEqual('already_running', busy['growth_outcome'])
        self.assertEqual('already_running', busy['growth_reason'])
        self.assertEqual(0, busy['errors'])
        self.assertIn('"state": "already_running"', second_out)
        first_out, first_err = first.communicate(timeout=12)
        self.assertEqual(0, first.returncode, first_err)
        self.assertEqual('completed', _pipeline_result(first_out)['status'])
        self.assertEqual('no_action', _pipeline_result(first_out)['growth_outcome'])
        self.assertEqual(['entered'], self.marker.read_text().splitlines())

    def test_force_kill_releases_kernel_lock_without_unlink(self):
        first = self._launch(sleep='30')
        self._await_entry()
        self.assertTrue(self.lock.exists())
        first.kill()  # SIGKILL on Linux / forced termination on Windows.
        first.communicate(timeout=8)
        second = self._launch(sleep='.02')
        output, stderr = second.communicate(timeout=12)
        self.assertEqual(0, second.returncode, stderr)
        self.assertEqual('completed', _pipeline_result(output)['status'])
        self.assertEqual(2, len(self.marker.read_text().splitlines()))
        self.assertTrue(self.lock.exists(), 'the lock inode must not be deleted')

    def test_standalone_growth_writers_cannot_mutate_while_scheduler_running(self):
        first = self._launch()
        self._await_entry()
        for script, reason in (
                ('record_growth_work.py', 'growth_work_record_busy'),
                ('build_daily_growth_plan.py', 'daily_growth_plan_busy')):
            with self.subTest(script=script):
                args = ([sys.executable, str(REPO_ROOT / 'scripts' / script),
                         'complete-existing', '--post-id', '1', '--edit-receipt',
                         str(self.base / 'missing.json'), '--work-log',
                         str(self.base / 'private-work-log.json')]
                        if script == 'record_growth_work.py' else
                        [sys.executable, str(REPO_ROOT / 'scripts' / script),
                         '--opportunities', str(self.base / 'missing.json'),
                         '--output-dir', str(self.base / 'output')])
                done = subprocess.run(args, env=self.env, cwd=REPO_ROOT,
                                      capture_output=True, text=True, encoding='utf-8', timeout=8)
                self.assertEqual(2, done.returncode, done.stderr)
                self.assertIn(reason, done.stderr)
        self.assertFalse((self.base / 'private-work-log.json').exists())
        self.assertFalse((self.base / 'output').exists())
        self.assertEqual(0, first.wait(timeout=12))

    def test_busy_exit_does_not_enter_pipeline_or_notify(self):
        sys.path.insert(0, str(AGENT_ROOT))
        import main as pipeline
        from agents.growth_run_lock import growth_run_lock
        with patch.dict(os.environ, self.env), growth_run_lock():
            with patch.object(pipeline, 'run_pipeline') as run, \
                 patch.object(pipeline, 'notify_pipeline_summary') as notify, \
                 redirect_stdout(io.StringIO()) as out:
                self.assertEqual(0, pipeline.main(['--category', 'health']))
        run.assert_not_called()
        notify.assert_not_called()
        self.assertEqual('already_running', _pipeline_result(out.getvalue())['status'])

    def test_exception_releases_lock(self):
        sys.path.insert(0, str(AGENT_ROOT))
        import main as pipeline
        with patch.dict(os.environ, self.env):
            with patch.object(pipeline, 'run_pipeline', side_effect=RuntimeError('injected')):
                with redirect_stdout(io.StringIO()) as out:
                    with self.assertRaisesRegex(RuntimeError, 'injected'):
                        pipeline.main(['--category', 'health'])
            self.assertIn('"state": "failed"', out.getvalue())
            with patch.object(pipeline, 'run_pipeline', return_value={
                    'growth_action': 'no_action', 'growth_outcome': 'input_failure',
                    'growth_reason': 'growth_inputs_unavailable_or_stale', 'errors': 0,
                    'published': 0}):
                with redirect_stdout(io.StringIO()) as out2:
                    self.assertEqual(1, pipeline.main(['--category', 'health']))
            self.assertEqual('failed', _pipeline_result(out2.getvalue())['status'])

    def test_unavailable_or_symlink_lock_fails_closed_before_pipeline(self):
        sys.path.insert(0, str(AGENT_ROOT))
        import main as pipeline
        unsafe = self.base / 'not-a-regular-lock'
        unsafe.mkdir()
        with patch.dict(os.environ, {**self.env, 'BLOGUITO_GROWTH_LOCK_PATH': str(unsafe)}):
            with patch.object(pipeline, 'run_pipeline') as run, \
                 patch.object(pipeline, 'notify_pipeline_summary') as notify, \
                 redirect_stdout(io.StringIO()) as out:
                self.assertEqual(1, pipeline.main(['--category', 'health']))
        run.assert_not_called()
        notify.assert_not_called()
        result = _pipeline_result(out.getvalue())
        self.assertEqual('failed', result['status'])
        self.assertEqual('input_failure', result['growth_outcome'])
        self.assertEqual('growth_run_lock_unavailable', result['growth_reason'])

    def test_pipeline_lock_exception_is_not_falsely_classified_as_busy(self):
        sys.path.insert(0, str(AGENT_ROOT))
        import main as pipeline
        from agents.growth_run_lock import GrowthRunAlreadyRunning
        with patch.dict(os.environ, self.env), \
             patch.object(pipeline, 'run_pipeline',
                          side_effect=GrowthRunAlreadyRunning('nested_failure')), \
             redirect_stdout(io.StringIO()) as out:
            with self.assertRaisesRegex(GrowthRunAlreadyRunning, 'nested_failure'):
                pipeline.main(['--category', 'health'])
        self.assertNotIn('PIPELINE_RESULT ', out.getvalue())
        self.assertIn('"state": "failed"', out.getvalue())

    @unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'cron shell requires Linux')
    def test_cron_and_direct_main_share_same_lock(self):
        first = self._launch()
        self._await_entry()
        app = self.base / 'cron-app'
        (app / 'venv' / 'bin').mkdir(parents=True)
        (app / 'venv' / 'bin' / 'python').symlink_to(sys.executable)
        (app / 'main.py').write_text(DRIVER, encoding='utf-8')
        log = self.base / 'cron.log'
        env = dict(self.env, BLOGUITO_APP_DIR=str(app), BLOGUITO_CRON_LOG_FILE=str(log))
        cron = subprocess.run(['bash', str(AGENT_ROOT / 'run_daily.sh')],
                              cwd=REPO_ROOT, env=env, capture_output=True,
                              text=True, encoding='utf-8', timeout=10)
        self.assertEqual(0, cron.returncode, cron.stderr)
        self.assertEqual('already_running', _pipeline_result(log.read_text())['status'])
        self.assertIn('exit=0', log.read_text())
        self.assertEqual(0, first.wait(timeout=10))
        self.assertEqual(['entered'], self.marker.read_text().splitlines())


if __name__ == '__main__':
    unittest.main()
