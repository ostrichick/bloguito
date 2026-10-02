from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import subprocess
import unittest
from unittest.mock import Mock, patch

from agents.wordpress_transport import run_wordpress, wordpress_transport


class WordPressTransportTests(unittest.TestCase):
    def test_explicit_transport_does_not_replace_other_subprocess_calls(self):
        remote = Mock(return_value='remote result')
        with patch('subprocess.run', return_value='local result') as local:
            with wordpress_transport(remote):
                self.assertEqual('remote result', run_wordpress(['wp', 'read']))
                self.assertEqual('local result', subprocess.run(['unrelated', 'command']))
            self.assertEqual('local result', run_wordpress(['wp', 'read']))
        remote.assert_called_once_with(['wp', 'read'])
        self.assertEqual(2, local.call_count)

    def test_context_propagates_only_to_explicitly_copied_worker(self):
        remote = Mock(return_value='remote')
        with patch('subprocess.run', return_value='local'), wordpress_transport(remote):
            context = copy_context()
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertEqual('remote', pool.submit(context.run, run_wordpress, ['wp']).result())
                self.assertEqual('local', pool.submit(run_wordpress, ['wp']).result())

    def test_nested_transport_restores_outer_runner_on_failure(self):
        outer = Mock(return_value='outer')
        with wordpress_transport(outer):
            with self.assertRaises(ValueError):
                with wordpress_transport(Mock()):
                    raise ValueError('interrupted')
            self.assertEqual('outer', run_wordpress(['wp']))
