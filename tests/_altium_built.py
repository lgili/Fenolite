# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium builds of the examples for tests (change c0044): ``fenolite build --target altium --confirm`` run
in-process into a folder of the test, seeing only the example's own library tables."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
BLINK = EXAMPLES / "blink_2layer" / "design.py"
LIBRARY_VARIABLES = (
    "KICAD10_SYMBOL_DIR",
    "KICAD9_SYMBOL_DIR",
    "KICAD10_FOOTPRINT_DIR",
    "KICAD9_FOOTPRINT_DIR",
)


def build_altium_example(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, script: Path = BLINK, *flags: str, out: str = "built"
) -> tuple[int, Path, str]:
    """``(exit code, output folder, stderr)`` of the Altium build of ``script`` into ``tmp_path/<out>``. No
    global library table and no library variable is seen, so the build is the same on every machine."""
    config = tmp_path / "kicad-config"
    config.mkdir(exist_ok=True)
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(config))
    for name in LIBRARY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    folder = tmp_path / out
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        args = [
            "build",
            str(script),
            "--out",
            str(folder),
            "--target",
            "altium",
            *flags,
            "--confirm",
            "--json",
        ]
        code = cli_main.main(args)
    return code, folder, stderr.getvalue()


def built_blink(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *flags: str) -> Path:
    """The folder of the built blink project (``blink.PrjPcb``, its documents and ``.fenolite/``)."""
    code, folder, error = build_altium_example(monkeypatch, tmp_path, BLINK, *flags)
    assert code == 0, error
    return folder


__all__ = ["BLINK", "EXAMPLES", "build_altium_example", "built_blink"]
