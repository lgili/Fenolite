# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite --version`` and ``python -m fenolite --version`` behave identically."""

from __future__ import annotations

import shutil
import subprocess
import sys

import fenolite

EXPECTED = f"fenolite {fenolite.__version__}"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def test_module_version() -> None:
    result = _run([sys.executable, "-m", "fenolite", "--version"])
    assert result.returncode == 0
    assert result.stdout.strip() == EXPECTED


def test_console_script_matches_module() -> None:
    exe = shutil.which("fenolite")
    assert exe is not None, "console script not installed"
    script = _run([exe, "--version"])
    module = _run([sys.executable, "-m", "fenolite", "--version"])
    assert (script.returncode, script.stdout) == (module.returncode, module.stdout)
