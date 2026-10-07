# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The yardstick board builds for KiCad 10 from the verified cache of the official libraries (capability
release-gate, "Yardstick board", scenario "Builds with the official libraries"; change c0119). Built only
into ``tmp_path``; nothing generated from the official libraries is committed, and only counts are
recorded."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _libcensus import census_sources
from _resources import libs_cache_dir

import fenolite.cli.main as cli_main

pytestmark = pytest.mark.needs_libs
ROOT = Path(__file__).resolve().parents[2]
YARDSTICK = ROOT / "examples" / "yardstick" / "design.py"
LIBRARY_VARIABLES = (
    "KICAD10_FOOTPRINT_DIR",
    "KICAD10_SYMBOL_DIR",
    "KICAD9_FOOTPRINT_DIR",
    "KICAD9_SYMBOL_DIR",
)


def test_yardstick_builds_with_the_official_libraries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not any(source.kind == "cache" and source.major == 10 for source in census_sources()):
        pytest.skip("no verified library cache of a 10.0 tag")
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    monkeypatch.setenv("FENOLITE_LIBS_CACHE", str(libs_cache_dir()))
    for name in LIBRARY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    folder = tmp_path / "yard"
    code = cli_main.main(
        ["build", str(YARDSTICK), "--out", str(folder), "--kicad-version", "10", "--confirm", "--json"]
    )
    assert code == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    assert not [issue for issue in envelope["issues"] if issue["severity"] == "error"]
    result = envelope["result"]
    assert (
        result["components"] >= 300
        and result["staged"] == []
        and len(result["placed"]) == result["components"]
    )
    assert set(result["libraries"].values()) == {"scan"}  # every lib id came from the cache
    assert result["copper_check"]["shorts"] == 0 and result["copper_check"]["clearance"] == 0
    assert result["schematic"]["sheets"] == 15  # the root and one sheet per module
    for suffix in (".kicad_pcb", ".kicad_pro", ".kicad_dru", ".kicad_sch"):
        assert (folder / f"yardstick{suffix}").is_file()
    board = (folder / "yardstick.kicad_pcb").read_text(encoding="utf-8")
    assert '"In1.Cu"' in board and '"In2.Cu"' in board and '"In3.Cu"' not in board
    print(f"yardstick: {result['components']} parts, {result['nets']} nets, {len(result['vendored'])} lands")
