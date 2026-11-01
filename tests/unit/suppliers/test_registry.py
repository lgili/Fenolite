# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The named providers register without loading credentials or third-party packages."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from fenolite.suppliers.policy import policy_for

ROOT = Path(__file__).resolve().parents[3]
NAMES = {"digikey", "mouser", "nexar", "farnell"}


def test_registry_and_extra() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["dependencies"] == []
    assert project["optional-dependencies"]["suppliers"] == ["keyring>=25"]
    entries = project["entry-points"]["fenolite.suppliers"]
    assert set(entries) == NAMES and "jlc" not in entries
    for name, target in entries.items():
        module, cls = target.split(":")
        plugin = getattr(importlib.import_module(module), cls)()
        assert plugin.name == name and not plugin.available()
        assert plugin.policy == policy_for(name)
        assert not plugin.policy.ready and plugin.policy.persist == ()


def test_plugins_import_without_extra_or_credentials() -> None:
    code = "sys.modules['keyring'] = None; " + "; ".join(
        f"__import__('fenolite.suppliers.{name}')" for name in sorted(NAMES)
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("FENOLITE_")}
    result = subprocess.run(
        [sys.executable, "-c", "import sys, socket, ssl; socket.socket = lambda *a, **k: 1/0; " + code],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
