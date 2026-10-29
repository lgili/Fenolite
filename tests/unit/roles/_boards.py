# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The reference boards of the net roles (change c0222; ``examples/roles``), built for the tests.

``build(board, variant, target, out)`` builds ``examples/roles/<board>/<variant>.py`` with ``fenolite build``
in-process. A KiCad build writes its zones without fills, as KiCad leaves a new zone; ``fill_as_outline``
gives each zone of the written board the fill KiCad gives it there: the zone outline itself, because every
zone of the reference boards is drawn clear of the copper of other nets by more than its clearance, so
KiCad's fill keeps the whole outline (to within the rounding of its corners). The KiCad oracle test
``tests/kicad/roles/test_reference_drc.py`` fills the same boards with KiCad and checks that the role
findings do not change. An Altium build pours its polygons itself (``--altium-pour computed``).
"""

from __future__ import annotations

import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import fenolite.cli.main as cli_main
from fenolite.backends import registry
from fenolite.backends.base import BoardFrame, BoardPad
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design
from fenolite.model.rules import RoleSet
from fenolite.roles.judge import Judged, run, split_roles
from fenolite.roles.measure import Inputs

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "examples" / "roles"
BOARDS = ("buck_shunt", "half_bridge", "bms")
VARIANTS = ("good", "bad")


@dataclass(frozen=True, slots=True)
class Built:
    """A built variant: its output folder and the board file."""

    out: Path
    board: Path


def build(board: str, variant: str, out: Path, *, target: str = "kicad", fill: bool = True) -> Built:
    """Build one variant into ``out``; a KiCad build gets the fill of ``fill_as_outline`` unless ``fill`` is
    false."""
    script = EXAMPLES / board / f"{variant}.py"
    args = ["build", str(script), "--out", str(out), "--confirm", "--json"]
    if target == "altium":
        args += ["--target", "altium"]
    stdout, stderr = io.StringIO(), io.StringIO()
    import contextlib

    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main.main(args)
    envelope = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
    assert code == 0, (
        code,
        stderr.getvalue(),
        [i for i in envelope.get("issues", []) if i["severity"] == "error"],
    )
    if target == "altium":
        found = sorted(out.glob("*.PcbDoc"))
        assert found, sorted(out.iterdir())
        return Built(out, found[0])
    path = out / f"{board}_{variant}.kicad_pcb"
    if fill:
        path.write_text(fill_as_outline(path.read_text(encoding="utf-8")), encoding="utf-8")
    return Built(out, path)


def fill_as_outline(text: str) -> str:
    """The board text with every zone filled by its outline on each of its copper layers, flagged as filled
    the way KiCad flags a filled zone."""
    root = parse(text)
    children: list[object] = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "zone":
            child = _filled(child)
        children.append(child)
    return dumps(root.with_children(children))  # type: ignore[arg-type]


def _filled(zone: Node) -> Node:
    polygon = zone.find("polygon")
    assert polygon is not None
    points = polygon.find("pts")
    assert points is not None
    layers = zone.find("layers") or zone.find("layer")
    assert layers is not None
    names = [atom.value for atom in layers.atoms()]
    kept = [
        child for child in zone.children if not (isinstance(child, Node) and child.name == "filled_polygon")
    ]
    made: list[object] = []
    for child in kept:
        if isinstance(child, Node) and child.name == "fill":
            text = dumps(child, style="compact")
            if not text.startswith("(fill yes"):
                child = parse(text.replace("(fill", "(fill yes", 1))
        made.append(child)
    pts = dumps(points, style="compact")
    for name in names:
        made.append(parse(f'(filled_polygon (layer "{name}") {pts})'))
    return zone.with_children(made)  # type: ignore[arg-type]


def read(built: Built) -> tuple[Design, tuple[BoardPad, ...]]:
    """The board model of a built variant and its pads in the board frame."""
    backend = registry.for_path(built.board)
    assert backend is not None
    design = backend.read(built.board).content
    assert isinstance(design, Design) and isinstance(backend, BoardFrame)
    return design, tuple(backend.board_pads(design, issues=[]))


def judge(
    built: Built,
    *,
    currents: Mapping[str, int] | None = None,
    declared: RoleSet | None = None,
    stored: RoleSet | None = None,
    inputs: Inputs | None = None,
    check: bool = True,
) -> Judged:
    """The roles of a built variant judged as ``fenolite roles --check`` judges them: the roles stored in its
    ``.fenolite/`` model, else ``declared`` and ``stored``, with the circuit of the model."""
    design, pads = read(built)
    model = load_dir(built.out / ".fenolite")
    own_declared, own_confirmed = split_roles(model.rules.roles if model.rules is not None else None)
    return run(
        design,
        pads,
        circuit=model.circuit,
        stored=stored if stored is not None else own_confirmed,
        declared=declared if declared is not None else own_declared,
        currents=currents,
        inputs=inputs,
        check=check,
    )
