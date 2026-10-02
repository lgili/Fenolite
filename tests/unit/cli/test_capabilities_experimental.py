# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``result.experimental`` of ``fenolite capabilities`` (capability cli-contract, "Experimental features in
capabilities"; change c0032)."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator

import _schema
import pytest

from fenolite.cli import cmd_capabilities
from fenolite.cli.main import main
from fenolite.verify import parse_level, release_verified

KEYS = ["name", "command", "option", "write_kinds", "evidence"]


@pytest.fixture(autouse=True)
def _fresh_detection() -> Iterator[None]:
    cmd_capabilities.detect_tools.cache_clear()
    yield
    cmd_capabilities.detect_tools.cache_clear()


def _envelope(capsys: pytest.CaptureFixture[str], *extra: str) -> dict[str, object]:
    assert main(["capabilities", "--json", *extra]) == 0
    return json.loads(capsys.readouterr().out)


def test_altium_writer_listed_as_experimental(capsys: pytest.CaptureFixture[str]) -> None:
    envelope = _envelope(capsys, "--no-tools")
    assert _schema.validate(envelope, _schema.load("fenolite.envelope.v0.json")) == []
    result = envelope["result"]
    assert isinstance(result, dict)
    (entry,) = result["experimental"]
    assert list(entry) == KEYS
    assert entry["name"] == "altium-schematic-writer" and entry["command"] == "build"
    assert entry["option"] == "--target altium"
    assert entry["write_kinds"] == [
        "altium_prjpcb",
        "altium_schdoc_ascii",
        "altium_schdoc_binary",
        "altium_schlib",
    ]
    assert entry["evidence"]["level"] == "INFERRED" and entry["evidence"]["oracle"] is None
    assert "H-A-SCH-OPEN" in entry["evidence"]["hypotheses"]
    assert "H-A-SCHBIN-VIEWER" in entry["evidence"]["hypotheses"]
    assert all(b["name"] != "altium" for b in result["backends"])


def test_same_entry_without_tool_detection(capsys: pytest.CaptureFixture[str]) -> None:
    with_tools = _envelope(capsys)["result"]
    without = _envelope(capsys, "--no-tools")["result"]
    assert isinstance(with_tools, dict) and isinstance(without, dict)
    assert with_tools["experimental"] == without["experimental"]


def test_field_projection(capsys: pytest.CaptureFixture[str]) -> None:
    result = _envelope(capsys, "--no-tools", "--fields", "experimental")["result"]
    assert isinstance(result, dict) and list(result) == ["experimental"]


def test_experimental_evidence_is_never_release_verified(capsys: pytest.CaptureFixture[str]) -> None:
    result = _envelope(capsys, "--no-tools")["result"]
    assert isinstance(result, dict)
    for entry in result["experimental"]:
        assert release_verified(parse_level(entry["evidence"]["level"])) is False


def test_entries_sorted_by_name(capsys: pytest.CaptureFixture[str]) -> None:
    result = _envelope(capsys, "--no-tools")["result"]
    assert isinstance(result, dict)
    names = [e["name"] for e in result["experimental"]]
    assert names == sorted(names)


def test_entry_module_imported_only_by_run() -> None:
    code = (
        "import sys, fenolite.cli.cmd_capabilities\n"
        "assert 'fenolite.lens.altium' not in sys.modules, 'imported with cmd_capabilities'\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
