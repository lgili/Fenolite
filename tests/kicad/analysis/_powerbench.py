# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Recorded KiCad behaviours of change c0115 (capability board-analyses, "Power and insulation KiCad
probes"): what ``pcb drc`` does with a groove width, with a conductor on a creepage path, with the
connection width of a pour and with copper on two layers.

Each bench is a board written by ``write_board`` with a project file and a rules text that holds a canary
scoped to its own two nets: its violation shows that the rules file was loaded. A probe records ``equal``
when KiCad behaves as the measurement of 2026-10-05 found, ``different`` otherwise and ``absent`` when the
canary did not fire. The outcomes are supporting data: they gate nothing and raise no label. Every length
here is authored for Fenolite and illustrative.
"""

from __future__ import annotations

import dataclasses
import json
import re
import tempfile
from collections.abc import Callable
from pathlib import Path

from _analysis import CANARY_NETS, MM, SHIFT, SLOT, SLOT_OUTER, at, box, with_outline
from _coppercheck import Copper
from _power import DUMBBELL, SPLIT4

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import kicad_uuid, write_board
from fenolite.core.coords import Point
from fenolite.model.board import ZoneSettings
from fenolite.model.design import Design

BENCHES = ("groove-slot", "creepage-split", "neck-plain", "neck-split", "layers")
PROBE_IDS = {
    "groove-slot": "analysis-groove-slot",
    "creepage-split": "analysis-creepage-split",
    "neck-plain": "analysis-neck-plain",
    "neck-split": "analysis-neck-split",
    "layers": "insulation-layers",
}
MAJORS = {name: (10,) for name in BENCHES}
"""``insulation-layers`` is also stated for major 9; its 9.0.9 run is owed, so only 10 is registered."""
CANARY = (
    "(rule canary\n"
    f"\t(condition \"A.NetName == '{CANARY_NETS[0]}' && B.NetName == '{CANARY_NETS[1]}'\")\n"
    "\t(constraint clearance (min 3mm))\n)\n"
)
ACTUAL = re.compile(r"actual ([0-9.]+) ?mm")


def _shift(point: Point) -> Point:
    return Point(point.x + SHIFT * MM, point.y + SHIFT * MM)


def _moved(ring: tuple[Point, ...]) -> tuple[Point, ...]:
    return tuple(_shift(point) for point in ring)


def _canary(made: Copper, x: float, y: float, layer: str = "F.Cu") -> None:
    for index, name in enumerate(CANARY_NETS):
        made.track(name, _shift(at(x, y + index)), _shift(at(x + 2, y + index)), width=250_000, layer=layer)


def _pair(rule: str, a: str, b: str, constraint: str) -> str:
    condition = f"A.NetName == '{a}' && B.NetName == '{b}'"
    return f'(rule {rule}\n\t(condition "{condition}")\n\t(constraint {constraint})\n)\n'


def bench(name: str) -> Design:
    """The board of one bench, every coordinate positive."""
    if name == "groove-slot":
        made = Copper()
        made.track("A", _shift(at(-2, 0)), _shift(at(0, 0)), width=MM)
        made.track("B", _shift(at(10, 0)), _shift(at(12, 0)), width=MM)
        _canary(made, -8, 7)
        return with_outline(made.build(), _moved(SLOT_OUTER), (_moved(SLOT),))
    if name == "creepage-split":
        made = Copper()
        made.track("A", _shift(at(-2, 0)), _shift(at(0, 0)), width=MM)
        made.track("B", _shift(at(10, 0)), _shift(at(12, 0)), width=MM)
        made.track("C", _shift(at(5, -2)), _shift(at(5, 2)), width=MM)
        _canary(made, -8, 7)
        return with_outline(made.build(), _moved(SLOT_OUTER))
    if name in ("neck-plain", "neck-split"):
        made = Copper()
        ring = _moved(DUMBBELL if name == "neck-plain" else SPLIT4)
        zone = made.zone("P", ring, fills=(ring,) if name == "neck-plain" else (), clearance=500_000)
        made.zones[-1] = dataclasses.replace(
            zone,
            settings=dataclasses.replace(
                ZoneSettings(clearance=500_000), connection="solid", island_removal="never"
            ),
        )
        made.via("P", _shift(at(5, 5)), diameter=MM)
        made.via("P", _shift(at(18, 5)), diameter=MM)
        if name == "neck-split":
            made.via("Q", _shift(at(11.5, 5)), diameter=600_000)
        _canary(made, 0, 13)
        return with_outline(made.build(), _moved(box(-5, -5, 28, 20)))
    if name == "layers":
        made = Copper(layers=4)
        made.track("A", _shift(at(0, 0)), _shift(at(10, 0)), width=MM, layer="In1.Cu")
        made.track("B", _shift(at(0, 0)), _shift(at(10, 0)), width=MM, layer="In2.Cu")
        _canary(made, 0, 5, "In1.Cu")
        return with_outline(made.build(), _moved(box(-5, -5, 15, 12)))
    raise KeyError(name)


def rules(name: str, minimum_mm: str = "30") -> str:
    """The rules text of a bench: the canary and the rules whose reports the probe reads."""
    text = "(version 1)\n" + CANARY
    if name == "groove-slot":
        text += _pair("probe_ab", "A", "B", f"creepage (min {minimum_mm}mm)")
    elif name == "creepage-split":
        for rule, a, b in (("probe_ab", "A", "B"), ("probe_ac", "A", "C"), ("probe_cb", "C", "B")):
            text += _pair(rule, a, b, f"creepage (min {minimum_mm}mm)")
    elif name in ("neck-plain", "neck-split"):
        width = f"connection_width (min {minimum_mm}mm)"
        text += f"(rule probe_width\n\t(condition \"A.NetName == 'P'\")\n\t(constraint {width})\n)\n"
    elif name == "layers":
        text += _pair("probe_clearance", "A", "B", "clearance (min 1mm)")
        text += _pair("probe_physical", "A", "B", "physical_clearance (min 1mm)")
    return text


def project(name: str) -> str:
    if name == "groove-slot":
        return json.dumps({"board": {"design_settings": {"rules": {"min_groove_width": 3.0}}}}) + "\n"
    return "{}\n"


def _uuids(design: Design, nets: tuple[str, ...]) -> set[str]:
    board = design.board
    assert board is not None
    ids = {net.id for net in design.circuit.nets if net.name in nets}
    return {kicad_uuid(item) for item in (*board.tracks, *board.vias) if item.net_id in ids}


def run_drc(runner: KicadCli, name: str, minimum_mm: str = "30") -> tuple[Design, DrcReport | None]:
    """``pcb drc`` on the bench; a bench with a zone is refilled first and the saved board is checked."""
    design = bench(name)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "bench.kicad_pcb"
        board.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
        (folder / "bench.kicad_pro").write_text(project(name), encoding="utf-8", newline="\n")
        (folder / "bench.kicad_dru").write_text(rules(name, minimum_mm), encoding="utf-8", newline="\n")
        files = {"bench.kicad_pro": folder / "bench.kicad_pro", "bench.kicad_dru": folder / "bench.kicad_dru"}
        if name.startswith("neck"):
            saved = runner.refill(board, files=files).board
            if saved is None:
                return design, None
            board.write_bytes(saved)
        return design, runner.drc(board, files=files).report


def _canary_fired(design: Design, report: DrcReport) -> bool:
    wanted = _uuids(design, CANARY_NETS)
    return any(v.type == "clearance" and {item.uuid for item in v.items} == wanted for v in report.violations)


def _actuals(design: Design, report: DrcReport, kind: str, nets: tuple[str, ...]) -> list[str]:
    """The ``actual`` values of the violations of one type whose items all belong to the nets."""
    wanted = _uuids(design, nets)
    found: list[str] = []
    for violation in report.violations:
        items = {item.uuid for item in violation.items}
        if violation.type == kind and items and (items <= wanted or kind == "connection_width"):
            match = ACTUAL.search(violation.description)
            found.append(match.group(1) if match else "?")
    return sorted(found)


def observe(runner: KicadCli, name: str) -> dict[str, object]:
    """What KiCad reported on the bench."""
    seen: dict[str, object] = {}
    if name == "groove-slot":
        design, report = run_drc(runner, name)
        if report is not None:
            seen = {
                "canary": _canary_fired(design, report),
                "creepage": _actuals(design, report, "creepage", ("A", "B")),
            }
    elif name == "creepage-split":
        design, report = run_drc(runner, name)
        if report is not None:
            seen = {"canary": _canary_fired(design, report)}
            for label, nets in (("ab", ("A", "B")), ("ac", ("A", "C")), ("cb", ("C", "B"))):
                both = [
                    ACTUAL.search(v.description)
                    for v in report.violations
                    if v.type == "creepage"
                    and {item.uuid for item in v.items} <= _uuids(design, nets)
                    and all({item.uuid for item in v.items} & _uuids(design, (net,)) for net in nets)
                ]
                seen[label] = sorted(match.group(1) if match else "?" for match in both)
    elif name in ("neck-plain", "neck-split"):
        for label, minimum in (
            (("below", "1.95"), ("above", "2.05")) if name == "neck-plain" else (("above", "2.45"),)
        ):
            design, report = run_drc(runner, name, minimum)
            if report is None:
                return {}
            seen[label] = _actuals(design, report, "connection_width", ("P",))
            seen["canary"] = bool(seen.get("canary", True)) and _canary_fired(design, report)
    elif name == "layers":
        design, report = run_drc(runner, name)
        if report is not None:
            wanted = _uuids(design, ("A", "B"))
            between = [v.type for v in report.violations if {item.uuid for item in v.items} == wanted]
            seen = {"canary": _canary_fired(design, report), "between": sorted(between)}
    return seen


def outcome(name: str, seen: dict[str, object]) -> str:
    """``absent`` without the canary; ``equal`` when KiCad behaves as measured on 2026-10-05."""
    if not seen or not seen.get("canary"):
        return "absent"
    if name == "groove-slot":
        return "equal" if seen["creepage"] == ["11.0000"] else "different"
    if name == "creepage-split":
        return (
            "equal" if (seen["ab"], seen["ac"], seen["cb"]) == ([], ["4.0000"], ["4.0000"]) else "different"
        )
    if name == "neck-plain":
        return "equal" if (seen["below"], seen["above"]) == ([], ["2.0000"]) else "different"
    if name == "neck-split":
        found = seen["above"]
        ok = (
            isinstance(found, list)
            and len(found) >= 1
            and all(v not in ("1.2000", "2.4000", "?") for v in found)
        )
        return "equal" if ok else "different"
    return "equal" if seen["between"] == [] else "different"


def _probe(name: str) -> str:
    from _probes import runner  # imported here: ``_probes`` registers this module's probes

    return outcome(name, observe(runner(), name))


def power_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)``."""
    return {PROBE_IDS[name]: ((lambda name=name: _probe(name)), MAJORS[name]) for name in BENCHES}


__all__ = [
    "BENCHES",
    "MAJORS",
    "PROBE_IDS",
    "bench",
    "observe",
    "outcome",
    "power_probes",
    "project",
    "rules",
]
