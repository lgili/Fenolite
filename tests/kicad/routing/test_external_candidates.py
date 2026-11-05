# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pinned local router candidates judged by KiCad; H-K-EXTERNAL-CANDIDATES.

These are real-tool tests. Missing adapters skip locally and fail in the router CI job
through FENOLITE_REQUIRE. An authored fake is never an oracle for this hypothesis.
"""

from dataclasses import replace
from pathlib import Path

import pytest
from _probes import major
from _search_project import bench, cli

from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from fenolite.routing.plugins.specctra.freerouting import FreeroutingRouter
from tests.kicad.routing.test_search import drc

pytestmark = pytest.mark.needs_kicad

SCRIPT = """
from fenolite.dsl import Design, Net, Part, connect, mm
design = Design("external_candidate")
design.board(mm(30), mm(20), copper={layers})
a = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
b = Part("R2", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
design.add(a, b)
net = Net("SIGNAL")
connect(net, a[1], b[1])
design.rules.netclass("SIGNAL", clearance=mm("0.2"), track_width=mm("0.25"),
                     via_diameter=mm("0.6"), via_drill=mm("0.3"), nets=(net,))
a.place(mm(6), mm(10), rot=90)
b.place(mm(24), mm(10), rot=90)
"""


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("kicadroutingtools", marks=pytest.mark.needs_router),
        pytest.param("freerouting", marks=pytest.mark.needs_freerouting),
    ],
)
@pytest.mark.parametrize("layers", [2, 4])
def test_pinned_external_candidate_passes_review_and_native_drc(tmp_path: Path, monkeypatch, name, layers):
    monkeypatch.chdir(tmp_path)
    router = KicadRoutingToolsRouter() if name == "kicadroutingtools" else FreeroutingRouter()
    status = router.available()
    assert status.available, status.reason
    assert status.version == ("0.22.1" if name == "kicadroutingtools" else "2.4.1")
    built = bench(tmp_path, "external_candidate", SCRIPT.format(layers=layers))
    if major() != 10:
        out = tmp_path / "oracle"
        code, _, err = cli(
            "build",
            str(tmp_path / "external_candidate.py"),
            "--out",
            str(out),
            "--kicad-version",
            str(major()),
            "--confirm",
        )
        assert code == 0, err
        built = replace(built, out=out, board=out / built.board.name)
    before = built.board.read_bytes()
    script = (tmp_path / "external_candidate.py").read_bytes()
    violations, opens = drc(built.board)
    words = (
        "route",
        str(built.board),
        "--router",
        "octilinear",
        "--propose-with",
        name,
        "--nets",
        "SIGNAL",
        "--timeout",
        "120",
    )
    code, reply, err = cli(*words, "--propose")
    assert code == 0, err
    assert built.board.read_bytes() == before
    candidates = [
        c for p in reply["result"]["proposals"] for c in p["candidates"] if c["source"] == f"external:{name}"
    ]
    assert candidates, (reply["result"]["proposals"], reply.get("issues"), reply["result"].get("external"))
    candidate = candidates[0]
    assert candidate["tool"]["version"] == status.version
    assert candidate["facts"]["open"]["after"] == candidate["facts"]["open"]["before"] - 1
    code, planned, err = cli(*words, "--accept", candidate["id"], "--gate", "drc", "--dry-run")
    assert code == 0 and planned["result"]["accepted"], (err, planned)
    assert built.board.read_bytes() == before
    code, _, err = cli(
        *words,
        "--accept",
        candidate["id"],
        "--gate",
        "drc",
        "--confirm",
        "--plan",
        planned["result"]["plan_id"],
    )
    assert code == 0, err
    after, remaining = drc(built.board)
    assert remaining == opens - 1
    assert all(after[kind] <= violations[kind] for kind in after), (violations, after)
    assert (tmp_path / "external_candidate.py").read_bytes() == script
