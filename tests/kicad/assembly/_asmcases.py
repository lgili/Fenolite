# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Cases of change c0064 (capability kicad-oracle, "Assembly tables agree with kicad-cli"): the ``pos-rows``
row of ``_probes.PROBES``.

The placement table of ``fenolite.exports.placement`` under the default template, with DNP parts kept, is
compared with the rows of ``pcb export pos --format csv --units mm --side both`` (``H-K-POS-ROWS``) on
four subjects: the authored board, the blink built for the running major (its ``D1`` is on the bottom),
that blink with its three parts turned to 270°, 180° and 270°, and that blink with ``R1`` marked DNP and
``U1`` left out of position files. The moves and flags are made up for these cases.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import tempfile
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import _lenscases as lc
import _placecases as pc
from _boards import FIXTURE

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.replace import footprint_ref, move_footprint
from fenolite.core.units import parse_angle, parse_length
from fenolite.exports import placement
from fenolite.exports.assembly import DEFAULT, FULL_TURN, PlacementTemplate, format_length
from fenolite.model.board import FootprintAttribute
from fenolite.model.design import Design

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
Files = dict[str, str | bytes]
HEADER = ["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"]
TURNS: Mapping[str, int] = {"U1": 270_000_000, "D1": 270_000_000, "R1": 180_000_000}
"""The turned blink: ``U1`` (top) and ``D1`` (bottom) at 270°, ``R1`` at 180°."""
FLAGS: Mapping[str, FootprintAttribute] = {"R1": "dnp", "U1": "exclude_from_pos_files"}
"""The flagged blink: one part marked DNP and one left out of position files."""
SUBJECTS = ("fixture", "blink", "turned", "flagged")
KEEP_DNP: PlacementTemplate = dataclasses.replace(DEFAULT.placement, exclude_dnp=False)
"""The default template with DNP parts kept, which is what ``pcb export pos`` lists without an option."""


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


@cache
def flagged_files(target: int) -> Files:
    """The built blink of ``target`` with the attributes of ``FLAGS`` added to its footprints."""
    files = dict(lc.built_files(target))
    design = read_board(lc.text_of(files), file=lc.BOARD)
    assert design.board is not None
    footprints = tuple(
        dataclasses.replace(fp, attributes=(*fp.attributes, FLAGS[ref]))
        if (ref := footprint_ref(design, fp)) in FLAGS
        else fp
        for fp in design.board.footprints
    )
    flagged = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=footprints))
    files[lc.BOARD] = write_board(flagged, target=target).text
    return files


@cache
def turned_files(target: int) -> Files:
    """The built blink of ``target`` with the rotations of ``TURNS``."""
    files = dict(lc.built_files(target))
    design = read_board(lc.text_of(files), file=lc.BOARD)
    known = pc.definitions(design, target)
    for ref, rotation in TURNS.items():
        footprint = pc.by_ref(design)[ref]
        design = move_footprint(design, footprint.id, rotation=rotation, definitions=known, force=True)
    files[lc.BOARD] = write_board(design, target=target).text
    return files


@cache
def subject(name: str) -> tuple[Design, str]:
    """``(the design Fenolite reads, the position CSV kicad-cli writes)`` for one subject."""
    if name == "fixture":
        return read_board(FIXTURE), runner().export_pos_csv(FIXTURE)
    target = major()
    files = {"blink": lc.built_files, "turned": turned_files, "flagged": flagged_files}[name](target)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for rel, data in files.items():
            path = folder / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        design = read_board(folder / lc.BOARD)
    return design, pc.pos_text(files)


def kicad_rows(text: str) -> list[dict[str, str]]:
    """The rows of a position CSV as ``kicad-cli`` spells them, keyed by its header."""
    reader = csv.DictReader(io.StringIO(text))
    assert reader.fieldnames == HEADER, reader.fieldnames
    return [{key: value.strip() for key, value in row.items()} for row in reader]


def model_rows(design: Design) -> tuple[tuple[placement.PlacedRow, ...], tuple[tuple[str, ...], ...]]:
    """The placed rows of ``design`` under the default template with DNP kept, and their cells."""
    rows = placement.apply(placement.rows_from_model(design), KEEP_DNP, outline=board_outline(design))
    return rows, placement.table(rows, KEEP_DNP)


def row_problems(name: str) -> list[str]:
    """What differs between Fenolite's placement table and KiCad's position file for one subject."""
    design, text = subject(name)
    exported = {row["Ref"]: row for row in kicad_rows(text)}
    rows, cells = model_rows(design)
    problems: list[str] = []
    if sorted(exported) != sorted(row.ref for row in rows):
        problems.append(f"{name}: KiCad lists {sorted(exported)}, Fenolite {sorted(r.ref for r in rows)}")
    for row, cell in zip(rows, cells, strict=True):
        found = exported.get(row.ref)
        if found is None:
            continue
        ref, value, package, x, y, rotation, side = cell
        kicad_x = parse_length(found["PosX"], default_unit="mm")
        kicad_y = parse_length(found["PosY"], default_unit="mm")
        kicad_turn = parse_angle(found["Rot"], default_unit="deg") % FULL_TURN
        wanted = (
            found["Ref"],
            found["Val"],
            found["Package"],
            format_length(kicad_x, "mm", KEEP_DNP.decimals),
            format_length(kicad_y, "mm", KEEP_DNP.decimals),
            found["Side"],
        )
        if (ref, value, package, x, y, side) != wanted:
            problems.append(f"{name} {row.ref}: Fenolite {cell}, KiCad {tuple(found.values())}")
        if abs(row.x - kicad_x) >= 1_000 or abs(row.y - kicad_y) >= 1_000:
            problems.append(f"{name} {row.ref}: off by a micrometre or more")
        if row.rotation != kicad_turn or parse_angle(rotation, default_unit="deg") != kicad_turn:
            problems.append(f"{name} {row.ref}: rotation {rotation}, KiCad {found['Rot']}")
    return problems


def spelled_rotations(name: str) -> dict[str, tuple[str, str]]:
    """``reference → (the rotation Fenolite prints, the rotation KiCad prints)`` for one subject."""
    design, text = subject(name)
    exported = {row["Ref"]: row["Rot"] for row in kicad_rows(text)}
    rows, cells = model_rows(design)
    column = [c.field for c in KEEP_DNP.columns].index("rotation")
    return {row.ref: (cell[column], exported[row.ref]) for row, cell in zip(rows, cells, strict=True)}


def pos_rows_outcome() -> str:
    return "equal" if not any(row_problems(name) for name in SUBJECTS) else "different"


def assembly_probes() -> Probes:
    return {"pos-rows": (pos_rows_outcome, (9, 10))}


__all__ = [
    "FLAGS",
    "HEADER",
    "KEEP_DNP",
    "SUBJECTS",
    "TURNS",
    "assembly_probes",
    "kicad_rows",
    "model_rows",
    "pos_rows_outcome",
    "row_problems",
    "spelled_rotations",
    "subject",
]
