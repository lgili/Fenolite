# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pad zone connection requests against KiCad's library check (change c0068; capability design-dsl, "Pad
zone connections in a build", scenario "KiCad reports no library mismatch"; ``H-K-PAD-ZONE-LIB``).

The blink pour variant is built once per connection value with ``d1.zone_connection(1, <value>)``, so pad
``1`` of ``D1`` differs from the pad of its vendored library footprint by a ``(zone_connect N)`` child
only. ``pcb drc`` runs on the built project with its vendored library and its ``fp-lib-table`` in place.
"""

from __future__ import annotations

from functools import cache

import _buildcases as bc
from _buildhelp import build, pour_variant

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad.pcb import read_board
from fenolite.dsl import pad_zones
from fenolite.lens.build import BuildOutput

BOARD = "blink.kicad_pcb"
CONNECTIONS = {"none": 0, "thermal": 1, "solid": 2, "thru_hole_only": 3}
"""A request's value → the code of the ``(zone_connect N)`` it writes."""


@cache
def built(connection: str, target: int) -> BuildOutput:
    design = pour_variant()
    design.parts["D1"].zone_connection(1, connection)
    output = build(design, target, pad_zones=pad_zones(design))
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return output


def pad_uuid(output: BuildOutput) -> str:
    """The KiCad uuid of pad ``1`` of ``D1`` on the written board."""
    design = read_board(output.files[BOARD].decode("utf-8"), file=BOARD, issues=[])
    assert design.board is not None
    d1 = design.by_ref["D1"].id
    footprint = next(fp for fp in design.board.footprints if fp.component_id == d1)
    (pad,) = [pad for pad in footprint.pads if pad.number == "1"]
    return pad.native_ids["kicad"]


@cache
def report(connection: str) -> DrcReport | None:
    """The DRC report of the variant built for the running major."""
    output = built(connection, bc.major())
    return bc.drc(bc._files(output), BOARD).report  # noqa: SLF001


def mismatches(found: DrcReport) -> int:
    return len(found.of_type(drcmod.LIB_FOOTPRINT_MISMATCH))


def naming_the_pad(found: DrcReport, uuid: str) -> list[str]:
    """The types of the violations that name the pad (unconnected items are not violations)."""
    return sorted(v.type for v in found.violations if any(item.uuid == uuid for item in v.items))


def pad_zone_lib() -> str:
    """``absent`` when no value gives a ``lib_footprint_mismatch`` nor a violation naming the pad;
    ``present`` otherwise, and ``reject`` when a run writes no report."""
    for connection in CONNECTIONS:
        found = report(connection)
        if found is None:
            return "reject"
        if mismatches(found) or naming_the_pad(found, pad_uuid(built(connection, bc.major()))):
            return "present"
    return "absent"


__all__ = [
    "BOARD",
    "CONNECTIONS",
    "built",
    "mismatches",
    "naming_the_pad",
    "pad_uuid",
    "pad_zone_lib",
    "report",
]
