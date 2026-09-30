# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Output mode follows the real terminal: text on a pseudo-terminal, JSON through a pipe."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform == "win32", reason="pty is POSIX-only")
def test_terminal_gets_text(monkeypatch: pytest.MonkeyPatch) -> None:
    import pty
    import select

    from fenolite.cli.main import main

    master, slave = pty.openpty()
    try:
        with os.fdopen(slave, "w", encoding="utf-8") as tty_out:
            assert tty_out.isatty()
            monkeypatch.setattr(sys, "stdout", tty_out)
            code = main(["_echo"])
            tty_out.flush()
            chunks: list[bytes] = []
            while select.select([master], [], [], 0.5)[0]:
                chunk = os.read(master, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
    finally:
        os.close(master)
    text = b"".join(chunks).decode("utf-8", "replace").replace("\r\n", "\n")
    assert code == 0
    assert text.startswith("fenolite _echo: ok")
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)


def test_pipe_gets_json() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "fenolite", "capabilities", "--no-tools"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["command"] == "capabilities"
