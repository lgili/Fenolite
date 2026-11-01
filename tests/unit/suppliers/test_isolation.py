# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""All ordinary commands and staged confirm stay outside the supplier runtime."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_build_pick_capabilities_and_explain_never_import_suppliers(tmp_path: Path) -> None:
    code = """
import io, os, socket, ssl, sys
from contextlib import redirect_stdout, redirect_stderr
from fenolite.cli.main import main
socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError('network'))
os.environ['FENOLITE_MOUSER_API_KEY'] = 'AUTHORED-NOT-READ'
os.environ['FENOLITE_STATE_DIR'] = 'off'
commands = [
    ['capabilities', '--no-tools', '--json'],
    ['capabilities', '--brief', '--no-tools', '--json'],
    ['explain', 'supplier.proposed', '--json'],
    ['pick', 'examples/picks', '--json'],
    ['build', 'examples/picks/design.py', '--out', sys.argv[1], '--dry-run', '--json'],
]
for args in commands:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        result = main(args)
    assert result == 0, (args, result, out.getvalue(), err.getvalue())
    assert not any(n == 'fenolite.suppliers' or n.startswith('fenolite.suppliers.') for n in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "out")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
