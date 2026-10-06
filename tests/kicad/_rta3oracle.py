# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad side of RT-A3 (capability altium-verification, "Round-trip level RT-A3"; change c0090;
``H-A-VER-RTA3-KICAD``): a PCB document is read, its model is written as a new PCB document under a
temporary folder, and ``kicad-cli pcb import`` (a subprocess, on that copy) reads the rewrite. Fenolite's
read of the rewrite and KiCad's are compared at the levels 1 to 5 of ``equivalent`` under the profile of
the running version."""

from __future__ import annotations

import tempfile
from functools import cache
from pathlib import Path

from _triangle import Sides, report, sides

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.lower import write_design
from fenolite.checks.equivalence.model import EquivalenceReport

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "altium"
OWN = ("routed/routed.PcbDoc", "board6/board6.PcbDoc")
"""Fenolite's own PCB documents with copper: the probe runs on them, without the corpus."""
IGNORED_REFS = ("", "[*]")
"""The references that a document holds several times and that cannot be paired (c0045)."""
_FOLDER = tempfile.TemporaryDirectory(prefix="fenolite-rta3-oracle-")


@cache
def rewritten(source: Path) -> Path:
    """The PCB document that ``lower.write_design`` gives for the model of ``source``, in a folder of this
    session."""
    written = write_design(AltiumBackend().read(source).design, allow_lossy=True)
    (name,) = [name for name in written.files if name.endswith(".PcbDoc")]
    folder = Path(_FOLDER.name) / f"{abs(hash(str(source))):x}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    target.write_bytes(written.files[name])
    return target


def rewrite_sides(source: Path, row: str = "") -> Sides:
    """Fenolite's read and KiCad's import of the rewrite of ``source``."""
    return sides(rewritten(source), row)


def judge(source: Path, row: str = "") -> EquivalenceReport:
    """The comparison of the two reads of the rewrite at levels 1 to 5."""
    return report(rewrite_sides(source, row), ignore_refs=IGNORED_REFS, level=5)


def outcome() -> str:
    """The probe ``altium-rta3-kicad``: ``equal`` when KiCad reads the rewrite of each document of ``OWN``
    as Fenolite does at levels 1 to 5, with at least one net compared at level 5; ``different``
    otherwise."""
    for name in OWN:
        found = judge(SAMPLES / name)
        if not found.equivalent or found.levels[-1].compared == 0:
            return "different"
    return "equal"


__all__ = ["IGNORED_REFS", "OWN", "SAMPLES", "judge", "outcome", "rewrite_sides", "rewritten"]
