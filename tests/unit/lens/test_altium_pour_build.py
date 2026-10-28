# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pour mode of an Altium build (change c0215; capability altium-build, "Pour mode of an Altium build";
capability altium-pour, "Computed pours are experimental").

The routed sample is the model of ``tests/_altium_copper.py``: one ``GND`` zone on ``In1.Cu`` and ``B.Cu``,
two polygons. The command-line scenarios build ``examples/board_40parts/design.py``, whose script declares
one ``GND`` zone on ``F.Cu`` and ``B.Cu``: the kit's ``routed`` sample gets its polygon from ``kit_model``,
which only the kit's own build runs, so ``fenolite build`` of that script writes no polygon.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from _altium_copper import NAME, routed_build, routed_kicad_design

import fenolite.cli.main as cli_main
from fenolite.backends.altium.pour import PourMode
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.lens.altium import write_model

GEO = importlib.util.find_spec("pyclipper") is not None
needs_geo = pytest.mark.skipif(not GEO, reason="needs the geo extra")
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "examples" / "board_40parts" / "design.py"


def _cli(
    monkeypatch: pytest.MonkeyPatch, out: Path, *flags: str, target: str = "altium"
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    """The exit code, the envelope and the error object (on stderr) of a dry run of the script."""
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    args = ["build", str(SCRIPT), "--out", str(out), "--target", target, "--dry-run", "--json", *flags]
    code = cli_main.main(args)
    error = stderr.getvalue().strip().splitlines()
    return (
        code,
        json.loads(stdout.getvalue()) if stdout.getvalue() else {},
        json.loads(error[0]) if error else {},
    )


def _issues(envelope: dict[str, Any], code: str) -> list[dict[str, Any]]:
    return [found for found in envelope["issues"] if found["code"] == code]


@needs_geo
@pytest.mark.parametrize("mode", (None, "computed", "outline"))
def test_model_helper_selects_pour_mode(mode: PourMode | None) -> None:
    """The model helper preserves its computed default and can reproduce unpoured historical inputs."""
    written = write_model(routed_kicad_design(), allow_lossy=True, pour=mode)
    assert written.pour_mode == (mode or "computed")
    document = read_pcbdoc(next(data for name, data in written.files.items() if name.endswith(".PcbDoc")))
    indices = {
        region.prefix.polygon
        for region in document.regions
        if isinstance(region, RegionRecord) and region.prefix.polygon is not None
    }
    assert indices == (set() if mode == "outline" else {0, 1})


@needs_geo
def test_computed_pour_of_the_routed_sample(tmp_path: Path) -> None:
    """Scenario "Computed pour of the routed sample": both polygons poured, regions with the index of each
    polygon, and no error."""
    output = routed_build(tmp_path, pour="computed")
    pour = output.summary["pcb"]["pour"]  # type: ignore[index]
    assert pour["poured"] == 2 and pour["unpoured"] == {}  # type: ignore[index]
    assert not [i for i in output.issues if i.severity == "error"]
    document = read_pcbdoc(output.files[f"{NAME}.PcbDoc"])
    indices = {
        r.prefix.polygon
        for r in document.regions
        if isinstance(r, RegionRecord) and r.prefix.polygon is not None
    }
    assert indices == {0, 1}


@needs_geo
def test_routed_built_with_a_computed_pour(tmp_path: Path) -> None:
    """Scenario "Routed built with a computed pour" (altium-pour): the mode, the level ``INFERRED``, the
    hypotheses of the engine, one ``altium.zones-poured`` that names 2 polygons and "Repour All", and the
    build's evidence names the engine's hypotheses."""
    output = routed_build(tmp_path, pour="computed")
    pour = output.summary["pcb"]["pour"]  # type: ignore[index]
    assert pour["mode"] == "computed" and pour["evidence"] == "INFERRED"  # type: ignore[index]
    assert "H-A-POUR-OPEN" in pour["hypotheses"]  # type: ignore[index]
    (info,) = [i for i in output.issues if i.code == "altium.zones-poured"]
    assert info.severity == "info" and info.message.startswith("2 polygon(s) poured")
    assert "Repour All" in info.message
    assert not [i for i in output.issues if i.code == "altium.zones-unpoured"]
    assert "H-A-POUR-OPEN" in output.evidence.hypotheses


def test_outline_keeps_the_earlier_document(tmp_path: Path) -> None:
    """``outline`` writes no region of a polygon, and the summary names the mode with nothing poured."""
    output = routed_build(tmp_path, pour="outline")
    assert output.summary["pcb"]["pour"] == {  # type: ignore[index]
        "mode": "outline", "poured": 0, "unpoured": {}, "evidence": None, "hypotheses": [],
    }  # fmt: skip
    document = read_pcbdoc(output.files[f"{NAME}.PcbDoc"])
    assert not [r for r in document.regions if isinstance(r, RegionRecord) and r.prefix.polygon is not None]
    assert "H-A-POUR-OPEN" not in output.evidence.hypotheses


@needs_geo
def test_the_default_pours(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "The default pours": without ``--altium-pour`` the build pours both polygons."""
    code, envelope, _ = _cli(monkeypatch, tmp_path / "out")
    assert code == 0, envelope
    pour = envelope["result"]["pcb"]["pour"]
    assert pour["mode"] == "computed" and pour["poured"] == 2
    (info,) = _issues(envelope, "altium.zones-poured")
    assert info["message"].startswith("2 polygon(s) poured")


def test_the_extra_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "The extra is missing": an explicit ``computed`` exits 6 naming ``fenolite[geo]`` and plans
    nothing; the default writes both polygons unpoured with ``altium.zones-unpoured`` and one
    ``altium.pour-unavailable``."""
    with mock.patch.dict(sys.modules, {"pyclipper": None}):
        code, envelope, error = _cli(monkeypatch, tmp_path / "a", "--altium-pour", "computed")
        assert code == 6 and error["code"] == "FEN-6001"
        assert "fenolite[geo]" in error["hint"] and error["where"] == "--altium-pour"
        assert not envelope["ok"] and not envelope["result"]
        code, envelope, _ = _cli(monkeypatch, tmp_path / "b")
    assert code == 0, envelope
    assert envelope["result"]["pcb"]["pour"]["mode"] == "outline"
    (unpoured,) = _issues(envelope, "altium.zones-unpoured")
    assert unpoured["message"].startswith("2 polygon(s)")
    (warning,) = _issues(envelope, "altium.pour-unavailable")
    assert warning["severity"] == "warning" and "fenolite[geo]" in warning["hint"]
    assert not _issues(envelope, "altium.zones-poured")


def test_kicad_target_refuses_the_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``--altium-pour`` with the KiCad target is a usage error."""
    code, _, error = _cli(monkeypatch, tmp_path, "--altium-pour", "outline", target="kicad")
    assert code == 2 and error["code"] == "FEN-2001" and error["where"] == "--altium-pour"
