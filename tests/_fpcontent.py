# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An Altium source whose footprints draw everything a footprint can (change c0422), authored for Fenolite.

Fenolite's two-layer sample board (``tests/data/kicad/board/two_layer.kicad_pcb``) gains three user layers
named after Altium mechanical layers (``Mech.5``, ``Mech.13``, ``Mech.10``). Its resistor R1 gains a
silkscreen arc, a filled silkscreen polygon (a region in Altium), a filled silkscreen rectangle (a fill), a
line on each of two of those layers and a circle on the third, a free silkscreen text and a free text on a
mechanical layer; its bottom LED D1 gains a silkscreen arc, a filled polygon and a mirrored free text.
``convert --to altium`` writes it as a PcbDoc with its PcbLib, the Altium source of the tests."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from _coppershapes import KICAD_ROUTED

from fenolite.api import convert
from fenolite.backends.kicad.sexpr import Node

NAME = "fpcontent"
USER_LAYERS = (
    '\t\t(43 "User.3" user "Mech.5")\n\t\t(59 "User.11" user "Mech.13")\n\t\t(61 "User.12" user "Mech.10")\n'
)
TEXTS = 3
"""The free texts of the footprints: two of R1, one of D1."""
GRAPHICS = 13
"""The drawings of the footprints in the Altium source: R1's four fabrication lines, six added drawings and
D1's circle and two added drawings."""


class _Ids:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f'(uuid "6c1e3d0a-0422-4b01-8000-{self.n:012d}")'


def _stroke(width: str) -> str:
    return f"(stroke (width {width}) (type solid))"


def _text(uid: _Ids, string: str, at: str, layer: str, *, mirror: bool = False) -> str:
    justify = " (justify mirror)" if mirror else ""
    return (
        f'\n\t\t(fp_text user "{string}" (at {at}) (layer "{layer}") {uid()} '
        f"(effects (font (size 0.8 0.8) (thickness 0.12)){justify}))"
    )


def _drawing(uid: _Ids, head: str, geometry: str, width: str, layer: str, fill: str = "") -> str:
    filled = f" (fill {fill})" if fill else ""
    return f'\n\t\t({head} {geometry} {_stroke(width)}{filled} (layer "{layer}") {uid()})'


def _insert(board: str, ref: str, children: str) -> str:
    at = board.index(f'(property "Reference" "{ref}"')
    pad = board.index("\t\t(pad ", at)
    return board[:pad] + children.lstrip("\n") + "\n" + board[pad:]


def authored() -> str:
    """The text of the authored KiCad board."""
    uid = _Ids()
    text = KICAD_ROUTED.read_text()
    anchor = '\t\t(33 "B.Fab" user)\n'
    text = text.replace(anchor, anchor + USER_LAYERS)
    resistor = "".join(
        (
            _drawing(uid, "fp_arc", "(start -1.5 -1) (mid 0 -1.6) (end 1.5 -1)", "0.12", "F.SilkS"),
            _drawing(uid, "fp_poly", "(pts (xy -0.4 1.2) (xy 0.4 1.2) (xy 0 1.7))", "0", "F.SilkS", "yes"),
            _drawing(uid, "fp_rect", "(start 1.6 -0.3) (end 2 0.3)", "0", "F.SilkS", "yes"),
            _drawing(uid, "fp_line", "(start -2 2) (end 2 2)", "0.1", "User.3"),
            _drawing(uid, "fp_line", "(start -2 2.5) (end 2 2.5)", "0.1", "User.11"),
            _drawing(uid, "fp_circle", "(center 0 0) (end 2.5 0)", "0.1", "User.12", "no"),
            _text(uid, "NOTE A", "0 -2.2 0", "F.SilkS"),
            _text(uid, "ASSY", "0 3 90", "User.11"),
        )
    )
    led = "".join(
        (
            _drawing(uid, "fp_arc", "(start 0 2.5) (mid 1.27 3) (end 2.54 2.5)", "0.12", "B.SilkS"),
            _drawing(uid, "fp_poly", "(pts (xy -1 -1) (xy -0.5 -1) (xy -0.75 -1.5))", "0", "B.SilkS", "yes"),
            _text(uid, "NOTE B", "1.27 4 30", "B.SilkS", mirror=True),
        )
    )
    return _insert(_insert(text, "R1", resistor), "D1", led)


def altium_document(folder: Path) -> Path:
    """The authored board written as an Altium project in ``folder / "altium"``; the PcbDoc's path."""
    source = folder / "kicad" / f"{NAME}.kicad_pcb"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(authored(), encoding="utf-8")
    written = convert(source, to="altium", allow_lossy=True).conversion
    rows = {row.kind: row for row in written.report.rows}
    assert (rows["footprint-text"].written, rows["footprint-graphic"].lost) == (TEXTS, 0)
    for key, data in written.files.items():
        target = folder / "altium" / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return folder / "altium" / f"{NAME}.PcbDoc"


def converted(document: Path, out: Path, *, kicad_version: int = 10) -> Path:
    """``document`` converted to KiCad ``kicad_version`` into ``out``, losses allowed; the board's path."""
    conversion = convert(document, to="kicad", allow_lossy=True, kicad_version=kicad_version).conversion
    for key, data in conversion.files.items():
        target = out / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return out / conversion.read_back


def drawn(footprint: Node) -> Counter[tuple[str, str]]:
    """``(head, layer)`` of each drawn child of a KiCad footprint node."""
    found: Counter[tuple[str, str]] = Counter()
    for child in footprint.nodes():
        layer = child.find("layer")
        if child.name.startswith("fp_") and layer is not None:
            found[(child.name, layer.atoms()[0].value)] += 1
    return found


def by_ref(pcb: Node, ref: str) -> Node:
    """The footprint of ``pcb`` whose Reference property is ``ref``."""
    for footprint in pcb.nodes("footprint"):
        for prop in footprint.nodes("property"):
            if [atom.value for atom in prop.atoms()[:2]] == ["Reference", ref]:
                return footprint
    raise AssertionError(f"no footprint {ref}")
