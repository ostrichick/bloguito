import os
import unittest
from unittest.mock import patch

from agents.remote_transport_config import RemoteTransportConfig, resolve_transport


class RemoteTransportConfigTests(unittest.TestCase):
    def test_defaults_to_direct_bloguito_alias(self):
        with patch.dict(os.environ, {}, clear=True):
            config = RemoteTransportConfig.from_env()
        self.assertEqual('direct', config.mode)
        self.assertEqual('bloguito', config.host)
        self.assertIsNone(config.wsl_distro)

    def test_tailscale_environment_becomes_default_without_cli_flags(self):
        env = {
            'BLOGUITO_SSH_MODE': 'tailscale',
            'BLOGUITO_SSH_HOST': '100.99.177.119',
            'BLOGUITO_SSH_USER': 'ubuntu',
            'BLOGUITO_WSL_DISTRO': 'Ubuntu-24.04',
        }
        with patch.dict(os.environ, env, clear=True):
            config = resolve_transport()
        self.assertEqual('tailscale', config.mode)
        self.assertEqual('100.99.177.119', config.host)
        self.assertEqual('ubuntu', config.user)
        self.assertEqual('Ubuntu-24.04', config.wsl_distro)

    def test_explicit_legacy_wsl_argument_overrides_direct_environment(self):
        with patch.dict(os.environ, {'BLOGUITO_SSH_MODE': 'direct'}, clear=True):
            config = resolve_transport(wsl_distro='Ubuntu-24.04')
        self.assertEqual('wsl', config.mode)

    def test_tailscale_requires_wsl_distro(self):
        with patch.dict(os.environ, {'BLOGUITO_SSH_MODE': 'tailscale'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'bloguito_wsl_distro_required'):
                resolve_transport()


if __name__ == '__main__':
    unittest.main()
