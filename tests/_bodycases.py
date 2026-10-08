# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The probe ``altium-pcbx-bodies``: the sample ``body2`` built with and without component bodies, each PCB
document imported by ``kicad-cli pcb import`` (change c0121; hypothesis ``H-A-PCBX-BODY-KICAD``).

KiCad's importer shows nothing for an extruded body, so it is no oracle for the body itself. The probe
says ``equal`` when KiCad reads the document with bodies as it reads the document without them: both
imports exit 0 with the same warnings, the two imported boards hold the same lines but for the ids that
KiCad draws at random (it also orders the footprints by those ids, so the lines are compared as a
multiset), they are equivalent at every level that both hold (the sample has no copper, so levels 1
to 4), and no footprint of either holds a 3D model.
``pcb import`` exists from 10.0 only.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path

from _altium_body2 import NAME, body2_build
from _pcbxcases import Imported, import_document

from fenolite.checks.equivalence import EquivalenceReport, compare_designs, max_level

MAJORS = (10,)
PROBE = "altium-pcbx-bodies"
MODEL = re.compile(r"\(model\s")
"""A 3D model of a footprint in a KiCad board file."""
RANDOM_ID = re.compile(r'\((uuid|path) "[^"]*"\)')
"""What KiCad's import draws anew on every run: the uuid of an item and the path of a footprint."""
MESSAGE = re.compile(r"(Warning|Error).*$")


@cache
def imported(mode: str) -> Imported:
    """The sample's PCB document, built with ``--altium-bodies`` ``mode``, as ``kicad-cli pcb import`` reads
    it."""
    with tempfile.TemporaryDirectory() as folder:
        output = body2_build(Path(folder) / "build", bodies=mode)
    assert not [found for found in output.issues if found.severity == "error"]
    return import_document(output.files[f"{NAME}.PcbDoc"], f"{NAME}.PcbDoc")


def judge() -> EquivalenceReport:
    """The two imports compared at the highest level that both hold."""
    with_bodies, without = imported("extruded"), imported("off")
    level = max_level(with_bodies.board, without.board)
    return compare_designs(with_bodies.board, without.board, level=level)


def models() -> tuple[int, int]:
    """The 3D models in KiCad's board with bodies and in the one without."""
    return len(MODEL.findall(imported("extruded").text)), len(MODEL.findall(imported("off").text))


def masked(text: str) -> list[str]:
    """The lines of a KiCad board file without the ids that the import draws at random, sorted: the
    import orders the footprints by those ids, so the order of the blocks changes from run to run."""
    return sorted(RANDOM_ID.sub("(id)", text).splitlines())


def messages(found: Imported) -> list[str]:
    """The warnings and errors of an import, without their time stamps."""
    return [match.group(0) for line in found.output.splitlines() if (match := MESSAGE.search(line))]


def bodies() -> bool:
    with_bodies, without = imported("extruded"), imported("off")
    report = judge()
    return (
        with_bodies.code == without.code == 0
        and messages(with_bodies) == messages(without)
        and masked(with_bodies.text) == masked(without.text)
        and report.equivalent
        and len(report.levels) >= 4
        and models() == (0, 0)
    )


def body_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """Probe id → (function, majors)."""
    return {PROBE: (lambda: "equal" if bodies() else "different", MAJORS)}
