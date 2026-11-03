# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 project with an explicitly posed custom footprint property (c0345)."""

from pathlib import Path

import _drawn_fonts

from fenolite.backends.kicad.sexpr import Atom, dumps, parse


def original(
    folder: Path, rotation: int, target: int, *, visible: bool = False, styled: bool = False
) -> Path:
    _drawn_fonts.original(folder, target=target)
    path = folder / "font_probe.kicad_pcb"
    root = parse(path.read_text())
    (footprint,) = root.nodes("footprint")
    at = footprint.find("at")
    assert at is not None
    changed_at = at.with_children((*at.atoms()[:2], Atom.integer(rotation)))
    prop = parse(
        '(property "Author" "Fenolite CC0 control" (at 1.27 -2.54 0) '
        '(layer "F.Fab") (uuid "a2583e46-c38d-4f23-9c49-2d29b44bb7bc") '
        + ("" if visible else "(hide yes) ")
        + "(effects (font (size 1 1) (thickness 0.15)"
        + (' bold italic (face "KiCad Font")' if styled else "")
        + ")"
        + (" (justify right bottom)" if styled else "")
        + "))"
    )
    changed = footprint.with_children(
        (*tuple(changed_at if c is at else c for c in footprint.children), prop)
    )
    path.write_text(dumps(root.with_children(tuple(changed if c is footprint else c for c in root.children))))
    return folder / "font_probe.kicad_pro"
