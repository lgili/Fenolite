# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The runs of the escape half of the feasibility gate of change c0110 (Decision 1; task 1.5), apart from
their judge: the QFN and BGA benches of ``_escapebench``, built for a target, their plane pads joined by
c0107's fan-out, then routed on their signal nets with and without an escape step, by the pinned
KiCadRoutingTools scripts (``qfn_fanout.py`` or ``bga_fanout.py --escape-method dogbone`` before
``route.py``, Decision 9) and by the pinned Freerouting jar (its fanout stage on or off, Decision 10).
Every tool run is bounded by ``_gate.GATE_SECONDS``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import _escapebench as eb
import _gate as gate
import _planebench as pb

from fenolite.backends.specctra.dsn import DsnDefaults, write_dsn
from fenolite.model.design import Design

SIGNAL_LAYERS = ("F.Cu", "B.Cu")
"""The layers the KiCadRoutingTools steps may use on the plane benches: the outer two (c0107)."""


@dataclass(frozen=True)
class EscapeRun:
    """One routing of a bench: the merged board and its design, the tool runs and their seconds."""

    label: str
    merged: Path
    design: Design
    steps: tuple[tuple[str, gate.ToolRun], ...]

    @property
    def seconds(self) -> float:
        return round(sum(step.seconds for _name, step in self.steps), 1)


def built(folder: Path, kind: str, target: int, *, planes: bool = True) -> Path:
    """The bench ``kind`` built for ``target`` into ``folder``, with the plane fan-out when it has planes."""
    board = gate.build("_escapebench", "bench_design", folder, target, kind=kind, planes=planes)
    if planes:
        made = gate.fan_out_planes(board)
        assert made["nets"] == ["GND", "VCC"], made
    return board


def _sizes(kind: str) -> tuple[str, str, str, str]:
    size = eb.SIZES[kind]
    via = size["via"]
    assert isinstance(via, tuple)
    return gate.mm(size["width"]), gate.mm(size["clearance"]), gate.mm(via[0]), gate.mm(via[1])  # type: ignore[arg-type]


def krt_run(board: Path, folder: Path, kind: str, target: int, *, escape: bool) -> EscapeRun:
    """KiCadRoutingTools on the signal nets of ``board``: with ``escape``, the part's escape script first,
    then ``route.py``; without, ``route.py`` alone. The added copper is merged into a copy of ``board``."""
    work = gate.copy_project(board, folder)
    width, clearance, diameter, drill = _sizes(kind)
    nets = eb.signals(kind)
    steps: list[tuple[str, gate.ToolRun]] = []
    source = work
    if escape:
        escaped = work.with_name("escaped.kicad_pcb")
        if kind == "bga":
            script = "bga_fanout.py"
            arguments = [
                str(work), "--component", "U1", "--output", str(escaped), "--escape-method", "dogbone",
                "--nets", *nets, "--layers", *SIGNAL_LAYERS, "--track-width", width, "--clearance", clearance,
                "--via-size", diameter, "--via-drill", drill, "--plane-drop", "off",
            ]  # fmt: skip
        else:
            script = "qfn_fanout.py"
            arguments = [
                str(work), "--output", str(escaped), "--component", "U1", "--nets", *nets, "--width", width,
                "--clearance", clearance, "--via-size", diameter, "--via-drill", drill,
            ]  # fmt: skip
        arguments += ["--same-net-pad-clearance", clearance, "--escalation", "off", "--no-fix-drc-settings"]
        steps.append((script, gate.krt(script, *arguments, folder=work.parent)))
        if escaped.is_file():
            source = escaped
    routed = work.with_name("routed.kicad_pcb")
    arguments = [
        str(source), str(routed), "--nets", *nets, "--track-width", width, "--via-size", diameter,
        "--via-drill", drill, "--layers", *SIGNAL_LAYERS, "--escalation", "off", "--no-fix-drc-settings",
    ]  # fmt: skip
    steps.append(("route.py", gate.krt("route.py", *arguments, folder=work.parent)))
    final = routed if routed.is_file() else source
    label = "escape" if escape else "plain"
    merged, design = gate.merged_board(board, final, nets, target, f"krt-{label}")
    return EscapeRun(label, merged, design, tuple(steps))


def dsn_run(
    board: Path, folder: Path, kind: str, target: int, *, fanout: bool, planes: bool = True
) -> EscapeRun:
    """Freerouting on the signal nets of ``board`` (the other nets left out as the plugin does, the inner
    layers written as planes when the bench has them), its fanout stage on or off. The session's copper
    is merged into a copy of ``board``; without a session the copy holds no new copper."""
    found = pb.load(board)
    size = eb.SIZES[kind]
    via = size["via"]
    assert isinstance(via, tuple)
    defaults = DsnDefaults(
        width=size["width"],
        clearance=size["clearance"],
        via_diameter=via[0],
        via_drill=via[1],  # type: ignore[arg-type]
    )
    written = write_dsn(
        found.design, pads=found.pads, outline=found.outline, selected=eb.signals(kind), defaults=defaults,
        plane_layers=found.plane_layers if planes else (), others="netless",
    )  # fmt: skip
    settings = () if fanout else ("--router.fanout.enabled=false",)
    label = "fanout" if fanout else "off"
    run, session = gate.freerouting(written, folder, *settings)
    if session is None:
        design = pb.load(board).design
        return EscapeRun(label, board, design, (("freerouting", run),))
    merged, design = gate.session_board(board, written, session, eb.signals(kind), target, f"dsn-{label}")
    return EscapeRun(label, merged, design, (("freerouting", run),))


__all__ = ["EscapeRun", "SIGNAL_LAYERS", "built", "dsn_run", "krt_run"]
