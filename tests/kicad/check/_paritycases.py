# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0072 (capability kicad-oracle, "Parity types are probed" and "Own parity agrees with
kicad-cli"): the ``parity-type-*`` rows and ``parity-own-agreement`` of ``_probes.PROBES``.

A case is a project (a board and its schematic in a folder), one footprint to edit and one edit of
``_parityedit.EDITS``. KiCad's side is the parity list of ``pcb drc --schematic-parity`` on copies;
Fenolite's side is ``checks.parity.compare``. The probes run on the blink that ``build`` writes, so they
need no corpus; the tests repeat every case on the ``pic_programmer`` demo of the running major's tag.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _erccases as cases
import _paritycorpus as corpus
import _parityedit as edits

from fenolite.backends.base import DrcReport
from fenolite.checks import parity

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
EXPECTED: Mapping[str, Mapping[str, int]] = {
    "none": {},
    "ref": {"missing_footprint": 1, "extra_footprint": 1},
    "value": {"footprint_symbol_mismatch": 1},
    "libid": {"footprint_symbol_mismatch": 1},
    "net": {"net_conflict": 1},
    "dup": {"duplicate_footprints": 1, "missing_footprint": 1},
    "extra": {"extra_footprint": 1},
    "value-and-libid": {"footprint_symbol_mismatch": 2},
}
"""The parity types of ``H-K-PARITY-TYPES`` per edit, with their counts."""
ALSO: Mapping[str, tuple[str, ...]] = {
    "dup": ("footprint_symbol_mismatch", "footprint_symbol_field_mismatch", "net_conflict"),
}
"""Types that an edit may give besides ``EXPECTED``: a footprint that takes another's reference is compared
with that reference's symbol when it comes first on the board, and then differs from it in whatever the
two parts differ."""
PROBED: tuple[str, ...] = (*edits.EDITS, "value-and-libid")


@dataclass(frozen=True)
class Target:
    """The footprint an edit changes: ``ref``; the footprint whose reference ``dup`` gives it; the pad
    that ``net`` moves."""

    ref: str
    other: str
    pad: str


BLINK = Target("R1", "D1", "2")
PIC = Target("R18", "C1", "1")
PIC_NAME = "pic_programmer"


def edited(edit: str, text: str, target: Target) -> str:
    if edit == "value-and-libid":
        return edits.relib(edits.revalue(text, target.ref), target.ref)
    return edits.apply(edit, text, target.ref, target.other, target.pad)


def blink_project(folder: Path) -> tuple[Path, Path]:
    """The blink of the running major written under ``folder``: its board and its schematic."""
    cases.write(cases.blink_files(cases.major()), folder)
    return folder / cases.BOARD, folder / cases.SHEET


NESTED = Target("R1", "C1", "2")
"""The nested design of c0070: ``R1`` is on the sheet of the module ``power``, ``C1`` one sheet below."""


def nested_project(folder: Path) -> tuple[Path, Path]:
    """The design with module sheets (``_schbuild.nested_design``) built for the running major under
    ``folder``, with the default layout: a root and three child sheets under ``sheets/``."""
    from _schbuild import built_nested, write_files

    write_files(built_nested(cases.major()), folder)
    return folder / "nested.kicad_pcb", folder / "nested.kicad_sch"


def pic_project(folder: Path) -> tuple[Path, Path] | None:
    """The ``pic_programmer`` demo of the running major's tag under ``folder``, or ``None`` when the
    corpus cache does not hold it."""
    major = cases.major()
    projects, _ = corpus.demo_projects(
        folder, corpus.TAG_OF_MAJOR[major], newest=corpus.newest_schematic(major)
    )
    found = [p for p in projects if p.name == PIC_NAME]
    return (found[0].board, found[0].schematic) if found else None


@dataclass(frozen=True)
class Compared:
    """One project compared by both: KiCad's report (``None`` when it wrote none), the counts per type of
    both, and the KiCad types that Fenolite has no code for."""

    report: DrcReport | None
    kicad: Mapping[str, int]
    own: Mapping[str, int]
    others: Mapping[str, int]
    findings: tuple[parity.ParityFinding, ...] = ()

    @property
    def agree(self) -> bool:
        return self.report is not None and dict(self.kicad) == dict(self.own)


def compare(board: Path, schematic: Path, *, own_netlist: bool = False) -> Compared:
    """KiCad's parity report of ``board`` and Fenolite's comparison of it with ``schematic``; the nodes of
    Fenolite's side come from ``kicad-cli``'s netlist export, or from its own netlist."""
    report = corpus.kicad_parity(cases.runner(), board)
    netlist = None if own_netlist else corpus.kicad_netlist(cases.runner(), schematic)
    if report is None or (netlist is None and not own_netlist):
        return Compared(None, {}, {}, {})
    own = corpus.own_report(board, schematic, netlist)
    return Compared(
        report, corpus.kicad_counts(report), corpus.own_counts(own), corpus.other_types(report), own.findings
    )


def with_edit(board: Path, edit: str, target: Target) -> None:
    board.write_text(edited(edit, board.read_text(encoding="utf-8"), target), encoding="utf-8")


def types_of(report: DrcReport) -> dict[str, int]:
    """Every parity type of ``report`` with its count."""
    found: dict[str, int] = {}
    for entry in report.schematic_parity:
        found[entry.type] = found.get(entry.type, 0) + 1
    return dict(sorted(found.items()))


MISMATCH = "footprint_symbol_mismatch"


def expected(edit: str, found: Mapping[str, int], *, mismatched: bool = False) -> bool:
    """Whether ``found`` (``types_of``) is what ``H-K-PARITY-TYPES`` says of ``edit``. ``mismatched`` says
    that the footprints of the project already differed from their symbols before the edit, as those of
    the published demo of tag 9.0.9.1 do: an edit of such a footprint may add or remove a mismatch, so
    that type is then not judged."""
    wanted = dict(EXPECTED[edit])
    found = dict(found)
    if mismatched:
        wanted.pop(MISMATCH, None)
        found.pop(MISMATCH, None)
    rest = {kind for kind in found if kind not in wanted}
    return all(found.get(kind, 0) == count for kind, count in wanted.items()) and rest <= set(
        ALSO.get(edit, ())
    )


@cache
def blink_types(edit: str) -> Mapping[str, int] | None:
    """The parity types of the blink after ``edit``, or ``None`` without a report."""
    folder = cases.workdir("parity-type")
    try:
        board, _ = blink_project(folder)
        with_edit(board, edit, BLINK)
        report = corpus.kicad_parity(cases.runner(), board)
        return None if report is None else types_of(report)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def type_probe(edit: str) -> str:
    found = blink_types(edit)
    if found is None:
        return "inconclusive"
    return "equal" if expected(edit, found) else "different"


@cache
def blink_agreement() -> tuple[str, ...]:
    """What differs between KiCad's counts and Fenolite's on the blink after each edit, with the nodes
    from the export and from the own netlist; ``()`` when every comparison holds."""
    differing: list[str] = []
    for edit in PROBED:
        folder = cases.workdir("parity-own")
        try:
            board, schematic = blink_project(folder)
            with_edit(board, edit, BLINK)
            for own_netlist in (False, True):
                found = compare(board, schematic, own_netlist=own_netlist)
                differing += differences(f"blink/{edit}/{'own' if own_netlist else 'export'}", found)
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    return tuple(differing)


@cache
def nested_agreement() -> tuple[str, ...]:
    """``blink_agreement`` for the design with module sheets (c0070): the own netlist reads the tree."""
    differing: list[str] = []
    for edit in ("none", *PROBED):
        folder = cases.workdir("parity-nested")
        try:
            board, schematic = nested_project(folder)
            if edit != "none":
                with_edit(board, edit, NESTED)
            for own_netlist in (False, True):
                found = compare(board, schematic, own_netlist=own_netlist)
                differing += differences(f"nested/{edit}/{'own' if own_netlist else 'export'}", found)
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    return tuple(differing)


def differences(name: str, found: Compared) -> list[str]:
    """One line per KiCad type whose two counts differ, naming the project, the type and both counts."""
    if found.report is None:
        return [f"{name}: kicad-cli wrote no parity report or no netlist"]
    return [
        f"{name}: {kind}: kicad-cli {found.kicad[kind]}, fenolite {found.own[kind]}"
        for kind in corpus.TYPES
        if found.kicad[kind] != found.own[kind]
    ]


def agreement_probe() -> str:
    return "equal" if not blink_agreement() else "different"


def parity_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {f"parity-type-{edit}": ((lambda e=edit: type_probe(e)), both) for edit in PROBED}
    probes["parity-own-agreement"] = (agreement_probe, both)
    return probes


__all__ = [
    "ALSO",
    "BLINK",
    "EXPECTED",
    "PIC",
    "PROBED",
    "Compared",
    "Target",
    "agreement_probe",
    "blink_agreement",
    "blink_project",
    "blink_types",
    "compare",
    "differences",
    "edited",
    "expected",
    "parity_probes",
    "pic_project",
    "type_probe",
    "types_of",
    "with_edit",
]
