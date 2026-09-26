"""Project-level transport defaults for restricted WordPress SSH adapters."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]+")
_MODES = {"direct", "wsl", "tailscale"}


def _clean(value):
    value = (value or "").strip()
    return value or None


@dataclass(frozen=True)
class RemoteTransportConfig:
    mode: str = "direct"
    host: str = "bloguito"
    user: str | None = None
    wsl_distro: str | None = None

    @classmethod
    def from_env(cls):
        config = cls(
            mode=(os.getenv("BLOGUITO_SSH_MODE") or "direct").strip().lower(),
            host=(os.getenv("BLOGUITO_SSH_HOST") or "bloguito").strip(),
            user=_clean(os.getenv("BLOGUITO_SSH_USER")),
            wsl_distro=_clean(os.getenv("BLOGUITO_WSL_DISTRO")),
        )
        config.validate()
        return config

    def validate(self):
        if self.mode not in _MODES:
            raise ValueError("invalid_bloguito_ssh_mode")
        for label, value in (("ssh_host", self.host), ("ssh_user", self.user),
                             ("wsl_distro", self.wsl_distro)):
            if value is not None and not _IDENTIFIER.fullmatch(value):
                raise ValueError("invalid_" + label)
        if self.mode in {"wsl", "tailscale"} and not self.wsl_distro:
            raise ValueError("bloguito_wsl_distro_required")
        return self


def resolve_transport(*, ssh_mode=None, ssh_host=None, ssh_user=None, wsl_distro=None,
                      tailscale_ssh=False):
    """Merge CLI overrides with stable project environment defaults.

    Explicit legacy --wsl-distro/--tailscale-ssh options remain compatible;
    ordinary calls can omit them once BLOGUITO_SSH_* is configured.
    """
    base = RemoteTransportConfig.from_env()
    mode = _clean(ssh_mode)
    if mode is None:
        if tailscale_ssh:
            mode = "tailscale"
        elif _clean(wsl_distro):
            mode = "wsl"
        else:
            mode = base.mode
    config = RemoteTransportConfig(
        mode=mode,
        host=_clean(ssh_host) or base.host,
        user=_clean(ssh_user) if ssh_user is not None else base.user,
        wsl_distro=_clean(wsl_distro) if wsl_distro is not None else base.wsl_distro,
    )
    return config.validate()
