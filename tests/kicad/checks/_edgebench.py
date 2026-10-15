# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edge clearance benches of change c0169 (capability kicad-oracle, "Edge clearance agrees with KiCad";
hypotheses H-K-EDGE-CENTRE, H-K-EDGE-RESOLVE and H-K-EDGE-AGREE).

Every board is authored here with round values and built by ``build_design`` from a script:

- **Centre.** A 60 × 30 mm board with a milled slot ``S1`` 54 mm long and 2 mm wide about (30, 10) mm, its
  lower edge at y = 11 mm, and five plated hole parts of 1 mm drill and 2 mm copper whose copper lies
  0.47, 0.52, 0.548, 0.552 and 0.6 mm below that edge. The project is the template's (edge clearance
  0.5 mm) without a custom rule. A probe ``edge-centre-<gap>`` is ``present`` when ``pcb drc`` gives a
  ``copper_edge_clearance`` that names the pad at that gap.
- **Resolve.** The same board with two parts, 0.4 and 0.7 mm from the slot, and a rules file of one
  board-wide ``edge_clearance`` rule of 0.3 or 0.8 mm beside the project's minimum of 0.5 mm. A probe
  ``edge-resolve-<rule>-<gap>`` is ``present`` when the pad at that gap is reported.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import cache

from _outlinebench import drc, target
from _outlinehelp import build_script

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.pcb import kicad_uuid, read_board
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import mm

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
Files = dict[str, str | bytes]
EDGE = "copper_edge_clearance"
CENTRE_GAPS = {"047": 0.47, "052": 0.52, "0548": 0.548, "0552": 0.552, "060": 0.6}
"""Probe label → the gap in mm from the copper of a part to the slot's lower edge."""
RESOLVE_GAPS = {"04": 0.4, "07": 0.7}
RESOLVE_RULES = {"03": "0.3", "08": "0.8"}
"""Probe label → the ``min`` in mm of the board-wide ``edge_clearance`` rule of a resolve board."""
SLOT_EDGE = 11.0
"""The y of the slot's lower edge, in mm of the script."""


def slot_board(name: str, gaps: Mapping[str, float]) -> DslDesign:
    """The 60 × 30 mm board with the slot ``S1`` and one plated hole part ``H<k>`` per gap, its 2 mm copper
    that far below the slot's lower edge."""
    d = DslDesign(name)
    d.board(mm(60), mm(30))
    d.slot(mm(30), mm(10), length=mm(54), width=mm(2), name="S1")
    for k, gap in enumerate(gaps.values()):
        d.hole(f"H{k + 1}", mm(6 + 12 * k), mm(SLOT_EDGE + 1 + gap), drill=mm(1), pad=mm(2))
    return d


@cache
def built(name: str, labels: tuple[str, ...]) -> tuple[tuple[str, str | bytes], ...]:
    """The files of the board ``name`` built for the running major, ``.fenolite/`` left out."""
    gaps = {**CENTRE_GAPS, **RESOLVE_GAPS}
    design = slot_board(name, {label: gaps[label] for label in labels})
    output = build_script(design, target())
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return tuple((k, v) for k, v in output.files.items() if not k.startswith(".fenolite/"))


def pad_uuids(text: str) -> dict[str, str]:
    """Reference → the KiCad uuid of the one pad of that part, on the board ``text``."""
    design = read_board(text)
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    found: dict[str, str] = {}
    for footprint in design.board.footprints:
        ref = refs.get(footprint.component_id, footprint.id)
        for pad in footprint.pads:
            found[ref] = kicad_uuid(pad)
    return found


def edge_uuids(report: DrcReport) -> set[str]:
    """The uuids of every item that a ``copper_edge_clearance`` entry names."""
    return {item.uuid for v in report.violations if v.type == EDGE for item in v.items}


def _text(files: Mapping[str, str | bytes], board: str) -> str:
    data = files[board]
    return data.decode("utf-8") if isinstance(data, bytes) else data


# --- centre ---------------------------------------------------------------------------------------------

CENTRE = "edgecentre"


@cache
def centre_report() -> DrcReport | None:
    files = dict(built(CENTRE, tuple(CENTRE_GAPS)))
    return drc(files, f"{CENTRE}.kicad_pcb")


def centre(label: str) -> str:
    """``present`` when the part at the gap ``label`` gets a ``copper_edge_clearance``."""
    report = centre_report()
    if report is None:
        return "inconclusive"
    files = dict(built(CENTRE, tuple(CENTRE_GAPS)))
    pads = pad_uuids(_text(files, f"{CENTRE}.kicad_pcb"))
    ref = f"H{list(CENTRE_GAPS).index(label) + 1}"
    return "present" if pads[ref] in edge_uuids(report) else "absent"


# --- resolve --------------------------------------------------------------------------------------------


def rules_text(minimum: str) -> str:
    """A rules file of one board-wide ``edge_clearance`` rule of ``minimum`` mm."""
    return f'(version 1)\n(rule "edge_probe"\n\t(constraint edge_clearance (min {minimum}mm)))\n'


@cache
def resolve_files(rule: str) -> tuple[tuple[str, str | bytes], ...]:
    """The resolve board of the rule ``rule`` (a label of ``RESOLVE_RULES``): the template project, whose
    edge clearance is 0.5 mm, and the rules file of that rule."""
    name = f"edgeresolve{rule}"
    files = dict(built(name, tuple(RESOLVE_GAPS)))
    files[f"{name}.kicad_dru"] = rules_text(RESOLVE_RULES[rule])
    return tuple(files.items())


@cache
def resolve_report(rule: str) -> DrcReport | None:
    return drc(dict(resolve_files(rule)), f"edgeresolve{rule}.kicad_pcb")


def resolve(rule: str, gap: str) -> str:
    """``present`` when the part at ``gap`` gets a ``copper_edge_clearance`` beside the rule ``rule``."""
    report = resolve_report(rule)
    if report is None:
        return "inconclusive"
    files = dict(resolve_files(rule))
    pads = pad_uuids(_text(files, f"edgeresolve{rule}.kicad_pcb"))
    ref = f"H{list(RESOLVE_GAPS).index(gap) + 1}"
    return "present" if pads[ref] in edge_uuids(report) else "absent"


def edge_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    probes: Probes = {}
    for label in CENTRE_GAPS:
        probes[f"edge-centre-{label}"] = (lambda label=label: centre(label), both)
    for rule in RESOLVE_RULES:
        for gap in RESOLVE_GAPS:
            probes[f"edge-resolve-{rule}-{gap}"] = (lambda rule=rule, gap=gap: resolve(rule, gap), both)
    return probes


__all__ = [
    "CENTRE_GAPS",
    "EDGE",
    "RESOLVE_GAPS",
    "RESOLVE_RULES",
    "built",
    "centre",
    "edge_probes",
    "edge_uuids",
    "pad_uuids",
    "resolve",
    "resolve_files",
    "rules_text",
    "slot_board",
]
