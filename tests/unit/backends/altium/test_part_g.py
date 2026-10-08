# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of Part G of the author report (``docs/evidence/altium-pcb.md``, "Part G: footprint items of a
rewrite"; change c0126, task 8.2; ``H-A-PCBX-FPGFX-AD``).

``part_g(folder)`` writes four things into ``folder``: ``original/``, the committed project ``board6``;
``rewrite/``, its import written again by ``AltiumBackend().write`` (the write of a model, with
``rewrite=True`` as RT-A3 writes it); ``rewrite-mech/``, the same model with two lines added to ``R1`` on
Mechanical 1 and Mechanical 5, written the same way; and ``expected.md``, the values the steps compare
(lines and arcs per component and layer, the corner percentages of four pads, the places of the
designators and comments) and the SHA-256 of every file. Every value of ``expected.md`` is read back from
the written files with Fenolite's own reader.

With ``FENOLITE_ALTIUM_PART_G=<folder outside the repository>`` the files are written there for the
maintainer's Altium session: ``FENOLITE_ALTIUM_PART_G=~/fenolite-altium-checks/c0126-part-g uv run pytest
tests/unit/backends/altium/test_part_g.py``. Without it they are written under the test's own folder. No file
that Altium wrote is in the repository.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import os
import shutil
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.lower import pairs_of
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.geometry.transform import Transform
from fenolite.model.board import PPM_PER_PERCENT, Graphic
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
BOARD6 = ROOT / "tests" / "data" / "altium" / "board6"
HANDOVER = os.environ.get("FENOLITE_ALTIUM_PART_G")
MM = 1_000_000
NM_PER_MIL = 25_400
MECH_LINES = (("Mech.1", 2 * MM), ("Mech.5", -2 * MM))
"""The two lines that ``rewrite-mech`` adds to ``R1``: layer and the Y of a 2 mm line in the pad frame."""


def layer_name(layer: str) -> str:
    """The name Altium Designer shows for a layer of the model."""
    names = {
        "F.SilkS": "Top Overlay",
        "B.SilkS": "Bottom Overlay",
        "F.Cu": "Top Layer",
        "B.Cu": "Bottom Layer",
    }
    if layer.startswith("Mech."):
        return f"Mechanical {layer[5:]}"
    return names.get(layer, layer)


def _mil(nm: int) -> str:
    text = f"{nm / NM_PER_MIL:.4f}".rstrip("0").rstrip(".")
    return f"{text} mil"


def with_mechanical_lines(design: Design) -> Design:
    """``design`` with two lines added to the footprint of ``R1``, one on Mechanical 1 and one on
    Mechanical 5, each 2 mm long and 0.1 mm wide, 2 mm above and below the footprint's origin."""
    board = design.board
    assert board is not None
    ident = next(component.id for component in design.circuit.components if component.ref == "R1")
    footprints = []
    for footprint in board.footprints:
        if footprint.component_id == ident:
            added = tuple(
                Graphic(
                    id=derived_id("gfx", "altium", f"part-g:{layer}"),
                    kind="line",
                    layer=layer,
                    points=(Point(-MM, y), Point(MM, y)),
                    width=MM // 10,
                )
                for layer, y in MECH_LINES
            )
            footprint = dataclasses.replace(footprint, graphics=(*footprint.graphics, *added))
        footprints.append(footprint)
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=tuple(footprints)))


def _write(design: Design, folder: Path) -> None:
    written = AltiumBackend().write(design, allow_lossy=True, rewrite=True)
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in written.files.items():
        (folder / name).write_bytes(data)


def _items(document: Path) -> tuple[Design, dict[str, str]]:
    design = AltiumBackend().read(document).design
    refs = {component.id: component.ref for component in design.circuit.components}
    return design, refs


def expected_text(folder: Path) -> str:
    """The values of ``expected.md``, read back from the written files."""
    lines = [
        "# Part G: values to compare",
        "",
        "Read back from the written files with Fenolite's own reader.",
    ]
    for part in ("rewrite", "rewrite-mech"):
        design, refs = _items(folder / part / "board6.PcbDoc")
        board = design.board
        assert board is not None
        counts: Counter[tuple[str, str, str]] = Counter()
        for footprint in board.footprints:
            for graphic in footprint.graphics:
                kind = {"line": "tracks", "arc": "arcs", "circle": "arcs"}.get(graphic.kind, graphic.kind)
                counts[(refs.get(footprint.component_id, ""), layer_name(graphic.layer), kind)] += 1
        lines += ["", f"## `{part}/board6.PcbDoc`: primitives of each component", ""]
        lines += ["| component | layer | primitive | count |", "|---|---|---|---|"]
        lines += [
            f"| {ref} | {layer} | {kind} | {count} |" for (ref, layer, kind), count in sorted(counts.items())
        ]
    design, refs = _items(folder / "rewrite" / "board6.PcbDoc")
    board = design.board
    assert board is not None
    origin = pairs_of(board).get("origin", "")
    rounded = sorted(
        (refs.get(footprint.component_id, ""), pad.number, pad.corner_ratio)
        for footprint in board.footprints
        for pad in footprint.pads
        if pad.shape == "roundrect" and pad.corner_ratio is not None
    )
    lines += ["", "## Corner radius of four rounded pads", ""]
    lines += ["| component | pad | corner radius (%) |", "|---|---|---|"]
    lines += [f"| {ref} | {number} | {ratio // PPM_PER_PERCENT} |" for ref, number, ratio in rounded[:4]]
    lines += ["", "## Designators and comments", ""]
    lines += [
        f"Positions are those of the text records, in the document's own coordinates (the origin is at "
        f"`{origin or 'the default'}`); Altium shows them relative to the origin.",
        "",
        "| component | text | layer | X | Y | height | shown |",
        "|---|---|---|---|---|---|---|",
    ]
    for footprint in sorted(board.footprints, key=lambda fp: refs.get(fp.component_id, "")):
        ref = refs.get(footprint.component_id, "")
        if not ref:
            continue
        for field in footprint.fields:
            if field.name not in ("Reference", "Value"):
                continue
            # the field lies at position + R(rotation)·p in the model's frame, whose Y is the document's -Y
            at = Transform.placement(footprint.position, footprint.rotation).apply(field.position)
            text = "designator" if field.name == "Reference" else "comment"
            shown = "yes" if field.visible else "no"
            row = f"| {ref} | {text} | {layer_name(field.layer)} | {_mil(at.x)} | {_mil(-at.y)} |"
            lines.append(f"{row} {_mil(field.size.h)} | {shown} |")
    lines += ["", "## SHA-256 of the files", "", "| file | SHA-256 |", "|---|---|"]
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "expected.md"):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"| `{path.relative_to(folder).as_posix()}` | `{digest}` |")
    return "\n".join(lines) + "\n"


def part_g(folder: Path) -> None:
    """Write the files of Part G into ``folder`` (``original/``, ``rewrite/``, ``rewrite-mech/`` and
    ``expected.md``)."""
    original = folder / "original"
    original.mkdir(parents=True, exist_ok=True)
    for path in sorted(BOARD6.iterdir()):
        if path.is_file():
            shutil.copyfile(path, original / path.name)
    design = AltiumBackend().read(BOARD6 / "board6.PrjPcb").design
    _write(design, folder / "rewrite")
    _write(with_mechanical_lines(design), folder / "rewrite-mech")
    (folder / "expected.md").write_text(expected_text(folder), encoding="utf-8", newline="\n")


def _check(folder: Path) -> tuple[int, list[tuple[str, str]]]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli_main.main(["check", str(folder), "--json"])
    env = json.loads(out.getvalue())
    return code, [(stage["name"], stage["status"]) for stage in env["result"]["stages"]]


def test_part_g_files(tmp_path: Path) -> None:
    """The files of Part G: deterministic, the rewrite holds the 27 lines and arcs of the components of
    ``board6``, the second rewrite also the two lines on Mechanical 1 and 5, and ``fenolite check`` judges
    each rewrite as it judges the original (the same exit code and stages)."""
    first, second = tmp_path / "a", tmp_path / "b"
    part_g(first)
    part_g(second)
    names = sorted(p.relative_to(first).as_posix() for p in first.rglob("*") if p.is_file())
    assert names == sorted(p.relative_to(second).as_posix() for p in second.rglob("*") if p.is_file())
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in names)
    assert {
        "expected.md",
        "original/board6.PcbDoc",
        "rewrite/board6.PcbDoc",
        "rewrite-mech/board6.PcbDoc",
    } <= set(names)
    rewrite, _refs = _items(first / "rewrite" / "board6.PcbDoc")
    mech, _refs = _items(first / "rewrite-mech" / "board6.PcbDoc")
    assert rewrite.board is not None and mech.board is not None
    assert sum(len(fp.graphics) for fp in rewrite.board.footprints) == 27
    layers = Counter(graphic.layer for fp in mech.board.footprints for graphic in fp.graphics)
    assert (layers["Mech.1"], layers["Mech.5"]) == (1, 1) and sum(layers.values()) == 29
    text = (first / "expected.md").read_text(encoding="utf-8")
    assert "| R1 | Mechanical 1 | tracks | 1 |" in text and "| R1 | Mechanical 5 | tracks | 1 |" in text
    code, stages = _check(first / "original")
    assert _check(first / "rewrite") == (code, stages) == _check(first / "rewrite-mech")
    if HANDOVER:
        target = Path(HANDOVER).expanduser().resolve()
        assert ROOT.resolve() not in (target, *target.parents), "the folder is inside the repository"
        part_g(target)
        pytest.skip(f"the files of Part G are written into {target}")
