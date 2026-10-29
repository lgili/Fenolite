# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite render --region`` (change c0211; capability manufacturing-exports, "Region renders"), on the
authored benches of ``tests/_regionviewbench.py`` and ``tests/_crossbench.py`` written as KiCad boards.
Hermetic: no tool runs, and the tests read the SVG's elements and their coordinates."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import _crossbench as cb
import _regionviewbench as rv
import pytest
from _checkcli import run
from _projects import tree_snapshot

from fenolite.backends.kicad.pcb import write_board
from fenolite.model.design import Design

CUT = "10mm,20mm,27.78mm,20mm"


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def written(tmp_path: Path, design: Design, name: str = "bench") -> Path:
    path = tmp_path / f"{name}.kicad_pcb"
    path.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
    return path


def render(
    monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    code, env, err, _ = run(monkeypatch, cwd, "render", *args)
    return code, env, err


def of_class(root: ET.Element, name: str) -> list[ET.Element]:
    return [element for element in root.iter() if element.get("class") == name]


def test_open_connections_in_a_region(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Open connections in a region": ``render <board> --region 0mm,0mm,20mm,20mm --nets --open
    -o views --confirm`` writes ``views/region.svg`` with two open-connection lines and one label per pad."""
    board = written(tmp_path, rv.bench())
    code, env, err = render(
        monkeypatch,
        tmp_path,
        str(board),
        "--region",
        rv.REGION,
        "--nets",
        "--open",
        "-o",
        "views",
        "--confirm",
    )
    assert code == 0, err
    data = (tmp_path / "views" / "region.svg").read_bytes()
    root = ET.fromstring(data)
    assert len(of_class(root, "open")) == 2
    assert sorted(label.get("data-pad") for label in of_class(root, "net-label")) == list(rv.LABELLED)
    (view,) = env["result"]["views"]
    assert view == {
        "path": "region.svg",
        "kind": "svg",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    region = env["result"]["region"]
    assert (region["x0"], region["y1"], region["grid"], region["copper"]) == (
        0,
        20_000_000,
        2_000_000,
        ["saved_fill"],
    )
    assert [(o["net"], o["a"]["where"], o["b"]["where"], o["length"]) for o in region["open"]] == [
        ("L1", "A1-1", "B1-1", 10_000_000),
        ("L2", "A2-1", "B2-1", 10_000_000),
    ]
    assert region["counts"]["open"] == 2 and region["counts"]["label"] == 5 and region["counts"]["slot"] == 1
    assert env["issues"] == [] and env["result"]["tool_version"] is None
    assert env["evidence"]["level"] == "INFERRED" and "H-G-REGION-RENDER" in env["evidence"]["hypotheses"]
    assert [w["path"] for w in env["receipt"]["written"]] == ["views/region.svg"]


def test_plan_then_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The mutation protocol: a dry run plans the file and writes nothing; the same bytes are written."""
    board = written(tmp_path, rv.bench())
    args = (str(board), "--region", "20mm,20mm,0mm,0mm", "--open", "-o", "views")
    before = tree_snapshot(tmp_path)
    code, env, _ = render(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0 and [p["path"] for p in env["result"]["plan"]] == ["views/region.svg"]
    assert tree_snapshot(tmp_path) == before
    planned = env["result"]["views"][0]["sha256"]
    code, env, _ = render(monkeypatch, tmp_path, *args, "--confirm")
    assert (
        code == 0 and hashlib.sha256((tmp_path / "views" / "region.svg").read_bytes()).hexdigest() == planned
    )


def test_unfilled_zone_says_its_copper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A zone without a stored fill is drawn as its simulated pour; the reply and an info issue say so."""
    board = written(tmp_path, rv.bench(fill=False))
    code, env, err = render(monkeypatch, tmp_path, str(board), "--region", rv.REGION, "-o", "v", "--confirm")
    assert code == 0, err
    assert env["result"]["region"]["copper"] == ["simulated"]
    assert [(i["code"], i["severity"]) for i in env["issues"]] == [("render.copper-simulated", "info")]
    root = ET.fromstring((tmp_path / "v" / "region.svg").read_bytes())
    assert [zone.get("data-state") for zone in of_class(root, "zone")] == ["simulated"]


def test_cut_and_its_ways(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``--cut`` draws the cut and its ways per layer from the crossing analysis: the seven gaps of the
    row on each layer, two tracks of 0.25 mm each, the first from 10.7 mm to 11.84 mm less the nanometre
    of rounding."""
    board = written(tmp_path, cb.row(links=2), "row")
    code, env, err = render(
        monkeypatch, tmp_path, str(board), "--region", "5mm,5mm,35mm,35mm", "--open", "--cut", CUT,
        "--cut-width", "0.25mm", "--cut-clearance", "0.2mm", "-o", "v", "--confirm",
    )  # fmt: skip
    assert code == 0, err
    root = ET.fromstring((tmp_path / "v" / "region.svg").read_bytes())
    (cut,) = of_class(root, "cut")
    assert (cut.get("x1"), cut.get("y1"), cut.get("x2"), cut.get("y2")) == ("10", "20", "27.78", "20")
    ways = of_class(root, "way")
    assert len(ways) == 14 and {way.get("data-tracks") for way in ways} == {"2"}
    first = min(
        (way for way in ways if way.get("data-layer") == "F.Cu"), key=lambda w: float(w.get("x1") or 0)
    )
    # the analysis rounds a way inward to the nanometre, so it ends 1 nm short of 11.84 mm
    assert (first.get("x1"), first.get("x2"), first.get("y1")) == ("10.7", "11.839999", "20")
    assert env["result"]["region"]["cuts"] == [{"cut": CUT, "supply": 28, "open": 2, "routed": 0}]
    assert "H-G-CROSSINGS" in env["evidence"]["hypotheses"]


def test_manifest_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = written(tmp_path, rv.bench())
    code, env, err = render(
        monkeypatch, tmp_path, str(board), "--region", rv.REGION, "-o", "v", "--manifest", "--confirm"
    )
    assert code == 0, err
    listed = json.loads((tmp_path / "v" / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    text = json.dumps(listed)
    assert "region.svg" in text and '"render"' in text and "fenolite " in text


def test_region_outside_the_copper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = written(tmp_path, rv.bench())
    code, env, _ = render(
        monkeypatch, tmp_path, str(board), "--region", "100mm,100mm,110mm,110mm", "-o", "v", "--confirm"
    )
    assert code == 0 and [i["code"] for i in env["issues"]] == ["render.region-empty"]


@pytest.mark.parametrize(
    ("args", "where"),
    [
        (("--region", "0mm,0mm,20mm"), "--region"),
        (("--region", "0,0,20,20"), "--region"),
        (("--region", "0mm,0mm,0mm,20mm"), "--region"),
        (("--region", "0mm,0mm,20mm,20mm", "--grid", "0.01mm"), "--grid"),
        (("--region", "0mm,0mm,20mm,20mm", "--svg"), "--region"),
        (("--nets",), "--nets"),
        (("--svg", "--cut", CUT), "--cut"),
        (("--region", "0mm,0mm,20mm,20mm", "--cut-width", "0.2mm"), "--cut-width"),
    ],
)
def test_usage_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...], where: str
) -> None:
    board = written(tmp_path, rv.bench())
    code, _, err = render(monkeypatch, tmp_path, str(board), "-o", "v", *args, "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001" and err["where"] == where, err
    assert not (tmp_path / "v").exists()
