# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The recorded KiCad bracket of a creepage value (capability board-analyses, "KiCad creepage bracket is
recorded"; change c0047).

Each bench of ``tests/_analysis.creep_bench`` is written as a board with a ``{}`` project file and a rules
text that holds the canary and one ``creepage`` rule on the two probe nets (S-0272). The rule is run twice
through ``pcb drc``: with ``min`` 50 µm below Fenolite's value, which must report nothing, and 50 µm above,
which must report a violation. The outcome is supporting data: it gates nothing and raises no label.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from _analysis import BRACKET_NM, CANARY_NETS, CreepBench, creep_bench

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import kicad_uuid, write_board

BENCHES = ("slot", "edge")
CREEPAGE_TYPE = "creepage"
PROJECT = "{}\n"


def probe_id(name: str) -> str:
    return f"analysis-creepage-{name}"


def _uuids(bench: CreepBench, nets: tuple[str, ...]) -> set[str]:
    board = bench.design.board
    assert board is not None
    ids = {net.id for net in bench.design.circuit.nets if net.name in nets}
    return {kicad_uuid(track) for track in board.tracks if track.net_id in ids}


def drc(
    runner: KicadCli, bench: CreepBench, minimum: int, target: int = 10, *, rules: str | None = None
) -> DrcReport | None:
    """``pcb drc`` on the bench with a creepage rule of ``minimum``; ``None`` when no report was written.
    ``rules`` replaces the bench's own rules text (change c0071 passes the text its writer gives)."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "bench.kicad_pcb"
        board.write_text(write_board(bench.design, target=target).text, encoding="utf-8")
        (folder / "bench.kicad_pro").write_text(PROJECT, encoding="utf-8")
        text = bench.rules(minimum) if rules is None else rules
        (folder / "bench.kicad_dru").write_text(text, encoding="utf-8")
        files = {"bench.kicad_pro": folder / "bench.kicad_pro", "bench.kicad_dru": folder / "bench.kicad_dru"}
        return runner.drc(board, files=files).report


def canary_fired(report: DrcReport, bench: CreepBench) -> bool:
    wanted = _uuids(bench, CANARY_NETS)
    return any(
        violation.type == "clearance" and {item.uuid for item in violation.items} == wanted
        for violation in report.violations
    )


def creepage_found(report: DrcReport, bench: CreepBench) -> bool:
    wanted = _uuids(bench, ("A", "B"))
    return any(
        violation.type == CREEPAGE_TYPE and {item.uuid for item in violation.items} <= wanted
        for violation in report.violations
    )


def observe(runner: KicadCli, name: str) -> dict[str, object]:
    """What KiCad reports below and above Fenolite's value: the canary and the creepage violation of each
    run, and the types of every violation."""
    bench = creep_bench(name)
    seen: dict[str, object] = {"fenolite_nm": bench.creepage}
    for label, minimum in (("below", bench.creepage - BRACKET_NM), ("above", bench.creepage + BRACKET_NM)):
        report = drc(runner, bench, minimum)
        seen[label] = (
            None
            if report is None
            else {
                "canary": canary_fired(report, bench),
                "creepage": creepage_found(report, bench),
                "types": sorted({violation.type for violation in report.violations}),
            }
        )
    return seen


def outcome(seen: dict[str, object]) -> str:
    """``equal``: nothing below and a violation above. ``absent``: a run without the canary (the rules
    file was not loaded). ``different``: anything else."""
    below, above = seen.get("below"), seen.get("above")
    if not isinstance(below, dict) or not isinstance(above, dict):
        return "absent"
    if not below["canary"] or not above["canary"]:
        return "absent"
    return "equal" if (not below["creepage"] and above["creepage"]) else "different"


def _probe(name: str) -> str:
    from _probes import runner  # imported here: ``_probes`` registers this module's probes

    return outcome(observe(runner(), name))


def creepage_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)``: the bracket is recorded on major 10 only."""
    return {probe_id(name): ((lambda name=name: _probe(name)), (10,)) for name in BENCHES}


__all__ = ["BENCHES", "creepage_probes", "drc", "observe", "outcome", "probe_id"]
