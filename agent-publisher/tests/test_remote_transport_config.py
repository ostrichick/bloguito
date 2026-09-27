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

    def test_tailscale_environment_does_not_override_ordinary_direct_default(self):
        env = {
            'BLOGUITO_SSH_MODE': 'tailscale',
            'BLOGUITO_SSH_HOST': '100.99.177.119',
            'BLOGUITO_SSH_USER': 'ubuntu',
            'BLOGUITO_WSL_DISTRO': 'Ubuntu-24.04',
        }
        with patch.dict(os.environ, env, clear=True):
            config = resolve_transport()
        self.assertEqual('direct', config.mode)
        self.assertEqual('bloguito', config.host)
        self.assertIsNone(config.user)
        self.assertIsNone(config.wsl_distro)

    def test_explicit_tailscale_mode_can_reuse_tailscale_environment_parameters(self):
        env = {
            'BLOGUITO_SSH_MODE': 'tailscale',
            'BLOGUITO_SSH_HOST': '100.99.177.119',
            'BLOGUITO_SSH_USER': 'ubuntu',
            'BLOGUITO_WSL_DISTRO': 'Ubuntu-24.04',
        }
        with patch.dict(os.environ, env, clear=True):
            config = resolve_transport(ssh_mode='tailscale')
        self.assertEqual('tailscale', config.mode)
        self.assertEqual('100.99.177.119', config.host)
        self.assertEqual('ubuntu', config.user)
        self.assertEqual('Ubuntu-24.04', config.wsl_distro)

    def test_direct_environment_parameters_are_kept_for_direct_default(self):
        env = {
            'BLOGUITO_SSH_MODE': 'direct',
            'BLOGUITO_SSH_HOST': 'bloguito-prod',
            'BLOGUITO_SSH_USER': 'ubuntu',
        }
        with patch.dict(os.environ, env, clear=True):
            config = resolve_transport()
        self.assertEqual('direct', config.mode)
        self.assertEqual('bloguito-prod', config.host)
        self.assertEqual('ubuntu', config.user)
        self.assertIsNone(config.wsl_distro)

    def test_explicit_legacy_wsl_argument_overrides_direct_environment(self):
        with patch.dict(os.environ, {'BLOGUITO_SSH_MODE': 'direct'}, clear=True):
            config = resolve_transport(wsl_distro='Ubuntu-24.04')
        self.assertEqual('wsl', config.mode)

    def test_tailscale_requires_wsl_distro(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'bloguito_wsl_distro_required'):
                resolve_transport(ssh_mode='tailscale')


if __name__ == '__main__':
    unittest.main()
