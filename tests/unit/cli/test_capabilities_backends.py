# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Backends in ``fenolite capabilities`` (capability cli-contract, change c0009)."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import _schema
import pytest
from _resources import posix_tools

from fenolite.cli import cmd_capabilities
from fenolite.cli.main import main

pytestmark = posix_tools  # the fake tool of this file is a shell script

ENVELOPE = _schema.load("fenolite.envelope.v0.json")


@pytest.fixture(autouse=True)
def _fresh_detection() -> Iterator[None]:
    cmd_capabilities.detect_tools.cache_clear()
    yield
    cmd_capabilities.detect_tools.cache_clear()


def _envelope(capsys: pytest.CaptureFixture[str], *extra: str) -> dict[str, Any]:
    assert main(["capabilities", "--json", *extra]) == 0
    data: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert _schema.validate(data, ENVELOPE) == []
    return data


def test_kicad_backend_listed(capsys: pytest.CaptureFixture[str]) -> None:
    backends = _envelope(capsys, "--no-tools")["result"]["backends"]
    assert [b["name"] for b in backends] == ["kicad"]
    kicad = backends[0]
    keys = {"name", "read_kinds", "write_kinds", "targets", "default_target", "downgrade", "operations"}
    assert set(kicad) == keys | {"evidence"}
    assert {"kicad_pcb", "kicad_mod", "kicad_sym"} <= set(kicad["read_kinds"])
    assert "kicad_pcb" in kicad["write_kinds"] and "kicad_pro" in kicad["write_kinds"]
    assert {"detect", "read", "write", "lower", "validate"} == set(kicad["operations"])
    assert (
        kicad["targets"] == [9, 10] and kicad["default_target"] == 10 and kicad["downgrade"] == "unsupported"
    )
    assert kicad["evidence"]["level"] == "INFERRED"


def test_backends_do_not_depend_on_tools(capsys: pytest.CaptureFixture[str]) -> None:
    without = _envelope(capsys, "--no-tools")["result"]["backends"]
    with_tools = _envelope(capsys)["result"]["backends"]
    assert without == with_tools


def test_backend_field_projection(capsys: pytest.CaptureFixture[str]) -> None:
    result = _envelope(capsys, "--no-tools", "--fields", "backends")["result"]
    assert list(result) == ["backends"]


def test_tool_path_from_find_kicad_cli(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "fake.py").write_text("print('10.0.6')\n")
    script = tmp_path / "kicad-cli"
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{tmp_path / "fake.py"}" "$@"\n')
    script.chmod(0o755)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(script))
    tool = _envelope(capsys)["result"]["tools"]["kicad-cli"]
    assert tool == {"path": str(script), "version": "10.0.6"}
