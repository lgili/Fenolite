# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The official-library blink builds where the official libraries are installed (capability design-dsl,
"Blink examples", scenario "Official variant where libraries exist"; change c0011), with every placed
footprint vendored and, where ``kicad-cli`` runs, a clean library check (kicad-oracle, "Official libraries
where they are installed"; change c0027). Built only into ``tmp_path``; nothing generated from the
official libraries is committed, and only counts are recorded."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest
from _libcensus import census_sources
from _resources import kicad_cli, libs_cache_dir

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.cli import KicadCli

pytestmark = pytest.mark.needs_libs
ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "examples" / "blink_official" / "design.py"


LIBRARY_VARIABLES = ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR")


def _cached() -> bool:
    """Whether the verified cache is one of the ``needs_libs`` sources: the build then sees what the census
    sees (c0021 Decision 16)."""
    return any(s.kind == "cache" and s.major == 10 for s in census_sources())


def _build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    if not census_sources():
        pytest.skip("no official library source with a known major")
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))
    if _cached():
        monkeypatch.setenv("FENOLITE_LIBS_CACHE", str(libs_cache_dir()))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", str(OFFICIAL), "--out", str(tmp_path / "O"), "--confirm", "--json"])
    assert code == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    assert (tmp_path / "O" / "blink_official.kicad_pcb").is_file()
    return envelope


def test_official_variant_builds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    envelope = _build(tmp_path, monkeypatch)
    vendored = envelope["result"]["vendored"]  # type: ignore[index]
    assert len(vendored) == 3 and all(v.startswith("lib/") for v in vendored)  # type: ignore[union-attr]
    for rel in vendored:  # type: ignore[union-attr]
        assert (tmp_path / "O" / rel).is_file()
    if _cached() and not any(os.environ.get(name) for name in LIBRARY_VARIABLES):
        # the pinned cache ranks above an install, and its rows come from the directory scan
        assert envelope["result"]["libraries"]["Device:R"] == "scan"  # type: ignore[index]


@pytest.mark.needs_kicad
def test_official_variant_passes_the_library_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build(tmp_path, monkeypatch)
    path = kicad_cli()
    assert path is not None
    folder = tmp_path / "O"
    files = {
        p.name: p for p in folder.iterdir() if p.name != "blink_official.kicad_pcb" and p.name != ".fenolite"
    }
    run = KicadCli(Path(path), timeout=600).drc(folder / "blink_official.kicad_pcb", files=files)
    assert run.report is not None
    types = [v.type for v in run.report.violations]
    print(f"official blink: lib_footprint_issues {types.count('lib_footprint_issues')}, "
          f"lib_footprint_mismatch {types.count('lib_footprint_mismatch')}")  # fmt: skip
    assert "lib_footprint_issues" not in types and "lib_footprint_mismatch" not in types


@pytest.mark.needs_kicad
def test_official_variant_passes_kicad_erc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """KiCad's ERC reports nothing on the schematic of the example (release-gate, "Release record of v0.2",
    the examples; change c0093): its supply pins are connected and its unused pins are marked."""
    _build(tmp_path, monkeypatch)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    code = cli_main.main(["check", str(tmp_path / "O"), "--stages", "erc.kicad", "--json"])
    envelope = json.loads(out.getvalue())
    stages = {stage["name"]: stage for stage in envelope["result"]["stages"]}
    found = [(issue["code"], issue.get("where")) for issue in envelope["issues"]]
    assert code == 0 and stages["erc.kicad"]["status"] == "ok" and found == [], found
