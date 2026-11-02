# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual native bytes of authored drawn projects for equivalent's level S (c0278)."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import _drawn

from fenolite.core.coords import Point
from fenolite.model.drawn import DrawnJunction


def project(folder: Path, name: str = "flat", *, cache: bool = False, crossing: bool = False) -> Path:
    value = _drawn.drawn(name)
    if crossing:
        assert name == "flat"
        sheet = value.sheets[0]
        wires = (
            (Point(114_300_000, 57_150_000), Point(130_810_000, 57_150_000)),
            (Point(127_000_000, 50_800_000), Point(127_000_000, 59_690_000)),
            (Point(120_650_000, 57_150_000), Point(120_650_000, 60_960_000)),
        )
        junctions = (
            DrawnJunction(Point(120_650_000, 57_150_000)),
            DrawnJunction(Point(127_000_000, 57_150_000)),
        )
        sheet = dataclasses.replace(sheet, wires=wires, junctions=junctions)
        value = dataclasses.replace(value, sheets=(sheet, *value.sheets[1:]))
    output = _drawn.build(name, value=value)
    assert output.files, [issue.message for issue in output.issues if issue.severity == "error"]
    for relative, data in output.files.items():
        if relative.startswith(".fenolite/") and not cache:
            continue
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if crossing:
        # The ordinary writer splits wires at a junction, making that junction electrically redundant
        # after deletion. This authored native-byte stand-in deliberately keeps the crossing unsplit.
        sheet = root(folder)
        text, count = re.subn(
            r"\n\t\(wire\n.*?\n\t\)", "", sheet.read_text(encoding="utf-8"), flags=re.DOTALL
        )
        assert count >= 3
        wires = (
            ("114.3 57.15", "130.81 57.15"),
            ("127 50.8", "127 59.69"),
            ("120.65 57.15", "120.65 60.96"),
        )
        authored = ""
        for number, (start, end) in enumerate(wires, 1):
            authored += (
                f"\n\t(wire (pts (xy {start}) (xy {end})) (stroke (width 0) (type default))"
                f' (uuid "00000000-0000-4000-8000-{100 + number:012d}"))\n'
            )
        assert text.rstrip().endswith(")")
        sheet.write_text(text.rstrip()[:-1] + authored + ")\n", encoding="utf-8")
    return folder


def root(folder: Path) -> Path:
    return next(folder.glob("*.kicad_pcb")).with_suffix(".kicad_sch")


def remove_one_junction(folder: Path, *, critical: bool = False) -> None:
    sheet = root(folder)
    text = sheet.read_text(encoding="utf-8")
    matches = list(re.finditer(r"\n\t\(junction\n.*?\n\t\)", text, flags=re.DOTALL))
    assert len(matches) == (2 if critical else 1), "the authored control must hold its planted junctions"
    match = matches[-1] if critical else matches[0]
    text = text[: match.start()] + text[match.end() :]
    sheet.write_text(text, encoding="utf-8")
