# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored variants of the public Altium blink for the sheets and pages of a generated schematic
(change c0372), made in memory; shared by the unit and the KiCad tests."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.convert.sources import SourceProject, read_source

BLINK = Path(__file__).resolve().parent / "data" / "altium" / "blink" / "blink.PrjPcb"


def two_sheets() -> SourceProject:
    """The blink with its LED drawn on ``Power.SchDoc`` and its other parts on ``Logic.SchDoc``."""
    source = read_source(BLINK)
    components = tuple(
        dataclasses.replace(
            c,
            provenance=dataclasses.replace(
                c.provenance, file="Power.SchDoc" if c.ref == "D1" else "Logic.SchDoc"
            ),
        )
        if c.provenance is not None
        else c
        for c in source.design.circuit.components
    )
    circuit = dataclasses.replace(source.design.circuit, components=components)
    return dataclasses.replace(source, design=dataclasses.replace(source.design, circuit=circuit))


def sheets(files: dict[str, bytes]) -> list[str]:
    return sorted(name for name in files if name.endswith(".kicad_sch"))


def refusing_more_than(monkeypatch: pytest.MonkeyPatch, most: int) -> None:
    """Make the layout refuse a sheet of more than ``most`` units, as a page too small would."""
    import fenolite.backends.kicad.schlayout as schlayout
    from fenolite.core.errors import Issue

    layout = schlayout.layout_units

    def small(units, *args, sheet: str = "", **kwargs):  # type: ignore[no-untyped-def]
        found = layout(units, *args, sheet=sheet, **kwargs)
        if len(units) <= most:
            return found
        refused = Issue("build.schematic-too-large", "error", f"sheet {sheet}: too many units", sheet)
        return dataclasses.replace(found, issues=(*found.issues, refused))

    monkeypatch.setattr(schlayout, "layout_units", small)
