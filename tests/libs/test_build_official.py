# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The official-library blink builds where the official libraries are installed (capability design-dsl,
"Blink examples", scenario "Official variant where libraries exist"; change c0011). Built only into
``tmp_path``; nothing generated from the official libraries is committed."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _libcensus import census_sources

import fenolite.cli.main as cli_main

pytestmark = pytest.mark.needs_libs
ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "examples" / "blink_official" / "design.py"


def test_official_variant_builds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not census_sources():
        pytest.skip("no official library source with a known major")
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", str(OFFICIAL), "--out", str(tmp_path / "O"), "--confirm", "--json"])
    assert code == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    assert (tmp_path / "O" / "blink_official.kicad_pcb").is_file()
    assert envelope["result"]["vendored"] == []  # official footprints come from template or global rows
