# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An authored KiCad project for the file-safety tests (change c0201): the example board, a project file, a
footprint library table with one path inside the project and one outside, and a library folder."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
OLD = "/old/place"


def table(uri_inside: str = "${KIPRJMOD}/Local.pretty", uri_outside: str = f"{OLD}/Shared.pretty") -> str:
    return (
        "(fp_lib_table\n  (version 7)\n"
        f'  (lib (name "Local")(type "KiCad")(uri "{uri_inside}")(options "")(descr ""))\n'
        f'  (lib (name "Shared")(type "KiCad")(uri "{uri_outside}")(options "")(descr ""))\n)\n'
    )


def project(folder: Path, name: str = "proj") -> Path:
    """The project folder ``folder/name``; returns its board."""
    root = folder / name
    (root / "Local.pretty").mkdir(parents=True)
    board = root / "board.kicad_pcb"
    board.write_bytes(BOARD.read_bytes())
    (root / "board.kicad_pro").write_text('{\n  "meta": {"version": 3}\n}\n', encoding="utf-8")
    (root / "fp-lib-table").write_text(table(), encoding="utf-8")
    (root / "Local.pretty" / "R.kicad_mod").write_text(
        '(footprint "R"\n  (layer "F.Cu")\n)\n', encoding="utf-8"
    )
    (root / "notes.txt").write_text("not a design file\n", encoding="utf-8")
    (root / "other.kicad_pcb").write_bytes(BOARD.read_bytes())
    return board


__all__ = ["BOARD", "OLD", "project", "table"]
