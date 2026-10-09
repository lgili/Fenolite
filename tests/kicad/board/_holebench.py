# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The hole benches of change c0102 (capability kicad-oracle, "Outline shapes and holes pass the oracle";
hypotheses H-K-HOLE-FOOTPRINT, H-K-HOLE-COURTYARD and H-K-HOLE-SYMBOL).

The board is the blink with six holes, authored here with round values: a round hole of 3.2 mm and two
slots of 1 × 3 mm that are not plated (one turned 30°), a plated hole of 3.2 mm with 6 mm of copper on
``GND``, and two holes of 1 mm with a courtyard of 3 mm over the courtyard of ``R1`` (top) and of ``D1``
(bottom); ``U1`` is clear of every hole. It is built in two forms: with footprints authored through the
``Footprint`` builder and given the hole flags (``form`` ``authored``), and from a script with
``design.hole()`` (``form`` ``script``). The probes record the first; the tests require the second to give
the same outcome.
"""

from __future__ import annotations

import dataclasses
import re
import tempfile
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import _lenscases as lc
from _buildcases import _folder
from _layout_edit import add_items
from _outlinebench import drc, drill_hits, target
from _outlinehelp import build_script, variant

from fenolite.backends.base import DrcReport
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import Footprint, Part, connect, holes, mm
from fenolite.lens.preserve import footprint_uuid

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
FORMS = ("authored", "script")
BOARD = "blink.kicad_pcb"
SCRIPT_HOLES = (
    'design.hole("H1", mm(4), mm(4), drill=mm(3.2))\n'
    'h2 = design.hole("H2", mm(46), mm(4), drill=mm(3.2), pad=mm(6))\n'
    "connect(gnd, h2[1])\n"
    'design.hole("H3", mm(25), mm(26), drill=mm(1), length=mm(3))\n'
    'design.hole("H4", mm(6), mm(26), drill=mm(1), length=mm(3), rot=30)\n'
    'design.hole("H5", mm(32), mm(9), drill=mm(1), courtyard=mm(3))\n'
    'design.hole("H6", mm(38), mm(22.5), drill=mm(1), courtyard=mm(3))\n'
)
"""The six holes as the lines of a script."""
ROOT_PAD = (
    '(pad "" np_thru_hole circle (at 110 125) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask") '
    '(uuid "00000000-0000-4000-8000-0000000f0001"))'
)
"""A hole as a pad outside every footprint, the form KiCad does not load."""


class _Flagged(Footprint):
    """An authored footprint with the flags that keep a hole out of the position file and the BOM."""

    @property
    def definition(self):  # type: ignore[no-untyped-def]
        flags = ("exclude_from_pos_files", "exclude_from_bom")
        return dataclasses.replace(super().definition, flags=flags)


def _authored_hole(
    name: str, drill: float, *, length: float = 0, pad: float = 0, yard: float = 0
) -> Footprint:
    """A hole footprint written with the ``Footprint`` builder alone, in a library of the bench."""
    fp = _Flagged("Bench_Holes", name)
    width = pad or drill
    long = (length + width - drill) if length else width
    fp.pad(
        "1" if pad else "",
        at=(mm(0), mm(0)),
        size=(mm(long), mm(width)),
        shape="oval" if length else "circle",
        kind="thru_hole" if pad else "np_thru_hole",
        drill=mm(drill),
        drill_shape="slot" if length else "round",
        drill_length=mm(length) if length else None,
    )
    wide = yard or width
    for layer in ("F.CrtYd", "B.CrtYd"):
        if length:
            x, y = (long + wide - width) / 2, wide / 2
            fp.rect((mm(-x), mm(-y)), (mm(x), mm(y)), layer=layer, width=mm(0.05))
        else:
            fp.circle((mm(0), mm(0)), (mm(wide / 2), mm(0)), layer=layer, width=mm(0.05))
    return fp


def authored_design() -> DslDesign:
    """The blink with the six holes as parts of authored footprints and of the two hole symbols."""
    design = variant()
    gnd = design.nets["GND"]
    spots = (
        ("H1", "Round_3.2", 4, 4, 0, {"drill": 3.2}),
        ("H2", "Plated_3.2", 46, 4, 0, {"drill": 3.2, "pad": 6}),
        ("H3", "Slot_1x3", 25, 26, 0, {"drill": 1, "length": 3}),
        ("H4", "Slot_1x3", 6, 26, 30, {"drill": 1, "length": 3}),
        ("H5", "Round_1_Yard_3", 32, 9, 0, {"drill": 1, "yard": 3}),
        ("H6", "Round_1_Yard_3", 38, 22.5, 0, {"drill": 1, "yard": 3}),
    )
    for plated in (False, True):
        holder = holes.HoleSymbol(holes.hole_symbol(plated=plated))
        design.symbols[holder.lib_id] = holder
    for ref, name, x, y, rot, sizes in spots:
        if f"Bench_Holes:{name}" not in design.footprints:
            design.add_footprint(_authored_hole(name, **sizes))  # type: ignore[arg-type]
        symbol = "Fenolite_Holes:Hole_Pad" if "pad" in sizes else "Fenolite_Holes:Hole"
        part = Part(ref, symbol, footprint=f"Bench_Holes:{name}", value=name)
        design.add(part)
        part.place(mm(x), mm(y), rot=rot, locked=True)
        if "pad" in sizes:
            connect(gnd, part[1])
    return design


@cache
def hole_files(form: str = "authored") -> tuple[tuple[str, str | bytes], ...]:
    design = variant(append=SCRIPT_HOLES) if form == "script" else authored_design()
    output = build_script(design, target())
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return tuple((k, v) for k, v in output.files.items() if not k.startswith(".fenolite/"))


def board_of(form: str) -> str:
    data = dict(hole_files(form))[BOARD]
    return data.decode("utf-8") if isinstance(data, bytes) else data


# --- the root pad ------------------------------------------------------------------------------------


@cache
def root_pad() -> str:
    """``reject`` when ``kicad-cli`` cannot load a board with a pad outside every footprint."""
    from _probes import load

    return load(add_items(board_of("authored"), ROOT_PAD))


# --- drill, position and test files --------------------------------------------------------------------


def _numbers(line: str) -> list[float]:
    return [float(value) for value in re.findall(r"[XY](-?\d+(?:\.\d+)?)", line)]


@cache
def drill(form: str = "authored") -> str:
    """``equal`` when the NPTH file holds the round hole of 3.2 mm at its place, the two holes of 1 mm, and
    each slot as one ``G85`` slot between its centres, 2 mm apart; and the PTH file holds the plated hole
    with the two pads of the LED."""
    hits = drill_hits(dict(hole_files(form)))
    if hits is None:
        return "inconclusive"
    npth = next((lines for name, lines in hits.items() if "NPTH" in name), None)
    pth = next((lines for name, lines in hits.items() if "NPTH" not in name and "PTH" in name), None)
    if npth is None or pth is None:
        return "inconclusive"
    slots = [_numbers(line) for line in npth if "G85" in line]
    rounds = [_numbers(line) for line in npth if "G85" not in line]
    spans = sorted(round(((s[2] - s[0]) ** 2 + (s[3] - s[1]) ** 2) ** 0.5, 3) for s in slots)
    at_h1 = [r for r in rounds if abs(abs(r[0]) - 104) < 0.002 and abs(abs(r[1]) - 104) < 0.002]
    plated = [_numbers(line) for line in pth]
    at_h2 = [r for r in plated if abs(abs(r[0]) - 146) < 0.002 and abs(abs(r[1]) - 104) < 0.002]
    good = (
        len(slots) == 2
        and spans == [2.0, 2.0]
        and len(rounds) == 3
        and len(at_h1) == 1
        and len(plated) == 3
        and len(at_h2) == 1
    )
    return "equal" if good else "different"


def _export(args: list[str], out: str, form: str) -> str | None:
    files = dict(hole_files(form))
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        run = lc.runner().run([*args, "-o", out, BOARD], files=tops)
    data = run.outputs.get(out)
    return None if not run.ok or data is None else data.decode("utf-8", "replace")


@cache
def position_file(form: str = "authored") -> str:
    """``absent`` when ``pcb export pos`` lists no hole, and lists the resistor."""
    text = _export(
        ["pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both"], "pos.csv", form
    )
    if text is None or '"R1"' not in text:
        return "inconclusive"
    return "present" if re.search(r'^"?H\d', text, flags=re.MULTILINE) else "absent"


@cache
def test_records(form: str = "authored") -> int | None:
    """The number of ``367`` records of the IPC-D-356 netlist: one per pad that is not plated."""
    text = _export(["pcb", "export", "ipcd356"], "board.d356", form)
    return None if text is None else sum(1 for line in text.split("\n") if line.startswith("367"))


# --- courtyards on both sides --------------------------------------------------------------------------


@cache
def _report(form: str) -> DrcReport | None:
    return drc(dict(hole_files(form)))


def _overlaps(form: str, hole: str, part: str) -> bool | None:
    report = _report(form)
    if report is None:
        return None
    pair = {footprint_uuid(hole), footprint_uuid(part)}
    return any(
        violation.type == "courtyards_overlap" and pair <= {item.uuid for item in violation.items}
        for violation in report.violations
    )


def courtyard(side: str, form: str = "authored") -> str:
    """``present`` when ``courtyards_overlap`` names the hole over the ``top`` part (``H5`` and ``R1``) or
    over the ``bottom`` part (``H6`` and ``D1``); for ``clear``, ``absent`` when none names ``U1``."""
    if side == "clear":
        report = _report(form)
        if report is None:
            return "inconclusive"
        named = any(
            violation.type == "courtyards_overlap"
            and footprint_uuid("U1") in {item.uuid for item in violation.items}
            for violation in report.violations
        )
        return "present" if named else "absent"
    found = _overlaps(form, *{"top": ("H5", "R1"), "bottom": ("H6", "D1")}[side])
    return "inconclusive" if found is None else "present" if found else "absent"


# --- the symbol library ----------------------------------------------------------------------------------


@cache
def symbol_load(form: str = "authored") -> str:
    """``equal`` when ``sym export svg`` exports both symbols of ``lib/Fenolite_Holes.kicad_sym``: the one
    without pins and the one with one passive pin, both outside the bill of materials."""
    files: Mapping[str, str | bytes] = dict(hole_files(form))
    library = files.get("lib/Fenolite_Holes.kicad_sym")
    if library is None:
        return "inconclusive"
    text = library.decode("utf-8") if isinstance(library, bytes) else library
    if text.count("(in_bom no)") != 2:
        return "different"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "Fenolite_Holes.kicad_sym"
        path.write_text(text, encoding="utf-8")
        run = lc.runner().run(
            ["sym", "export", "svg", "-o", "svg", path.name], files={path.name: path}, folders=["svg"]
        )
    drawn = sorted(name for name in run.outputs if name.startswith("svg/") and name.endswith(".svg"))
    if not run.ok:
        return "reject"
    names = " ".join(drawn).lower()
    return "equal" if len(drawn) >= 2 and "hole_pad" in names else "different"


def hole_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    return {
        "hole-root-pad": (root_pad, both),
        "hole-drill": (drill, both),
        "hole-pos": (position_file, both),
        "hole-courtyard-top": (lambda: courtyard("top"), both),
        "hole-courtyard-bottom": (lambda: courtyard("bottom"), both),
        "hole-courtyard-clear": (lambda: courtyard("clear"), both),
        "hole-symbol-load": (symbol_load, both),
    }


__all__ = [
    "FORMS",
    "SCRIPT_HOLES",
    "authored_design",
    "courtyard",
    "drill",
    "hole_files",
    "hole_probes",
    "position_file",
    "root_pad",
    "symbol_load",
    "test_records",
]
