# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The runs of the pair gate of change c0110 (Decision 1; tasks 1.4 and 6.1), apart from their judge so that
they can be run where no ``kicad-cli`` is: the pinned KiCadRoutingTools scripts on the pair and name benches,
with the arguments of the design (Context, measurement 3; Decision 6), and the merge of the copper they add.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import _gate as gate
import _namebench as nb
import _routepairbench as pairb

from fenolite.backends.kicad.pcb import read_board
from fenolite.model.design import Design


@dataclass(frozen=True)
class PairRun:
    """The built bench, its board after the tool's steps merged on the bench's nets, and the steps."""

    built: Path
    merged: Path
    design: Design
    steps: tuple[tuple[str, gate.ToolRun], ...]


def _diff_arguments(board: Path, output: Path, nets: tuple[str, ...], width: int, gap: int, clearance: int,
                    via: tuple[int, int], layers: tuple[str, ...]) -> list[str]:  # fmt: skip
    return [
        str(board), str(output), "--nets", *nets,
        "--track-width", gate.mm(width), "--diff-pair-gap", gate.mm(gap), "--clearance", gate.mm(clearance),
        "--via-size", gate.mm(via[0]), "--via-drill", gate.mm(via[1]), "--layers", *layers,
        "--no-gnd-vias", "--keep-input-copper", "--same-net-pad-clearance", gate.mm(clearance),
        "--escalation", "off", "--no-fix-drc-settings",
    ]  # fmt: skip


def pair_run(folder: Path, target: int, *, match: bool = False) -> PairRun:
    """The pair bench built for ``target``; ``route_diff.py`` on its two pairs, then ``route.py`` on its four
    single nets, each step reading the board of the step before; the added copper merged with
    ``routing.merge.apply``. ``match`` adds ``--diff-pair-intra-match`` with the skew limit."""
    built = gate.build("_routepairbench", "bench_design", folder / "build", target)
    work = gate.copy_project(built, folder / "work")
    pairs = tuple(name for pair in pairb.PAIRS for name in pair)
    diffed = work.with_name("diffed.kicad_pcb")
    sizes = (pairb.WIDTH, pairb.GAP, pairb.CLEARANCE, pairb.VIA, pairb.LAYERS)
    arguments = _diff_arguments(work, diffed, pairs, *sizes)
    if match:
        arguments += ["--diff-pair-intra-match", "--length-match-tolerance", "0.1"]
    steps = [("route_diff.py", gate.krt("route_diff.py", *arguments, folder=work.parent))]
    source = diffed if diffed.is_file() else work
    routed = work.with_name("routed.kicad_pcb")
    singles = [
        str(source), str(routed), "--nets", *pairb.SINGLES, "--track-width", gate.mm(pairb.WIDTH),
        "--via-size", gate.mm(pairb.VIA[0]), "--via-drill", gate.mm(pairb.VIA[1]),
        "--escalation", "off", "--no-fix-drc-settings",
    ]  # fmt: skip
    steps.append(("route.py", gate.krt("route.py", *singles, folder=work.parent)))
    final = routed if routed.is_file() else source
    merged, design = gate.merged_board(built, final, pairb.NETS, target, "merged")
    return PairRun(built, merged, design, tuple(steps))


def names_run(folder: Path, target: int) -> PairRun:
    """The name bench built for ``target`` and ``route_diff.py`` on its ten nets."""
    built = gate.build("_namebench", "bench_design", folder / "build", target)
    work = gate.copy_project(built, folder / "work")
    diffed = work.with_name("diffed.kicad_pcb")
    arguments = _diff_arguments(work, diffed, nb.NETS, nb.WIDTH, nb.GAP, nb.CLEARANCE, nb.VIA, nb.LAYERS)
    step = gate.krt("route_diff.py", *arguments, folder=work.parent)
    merged, design = gate.merged_board(built, diffed if diffed.is_file() else work, nb.NETS, target, "merged")
    return PairRun(built, merged, design, (("route_diff.py", step),))


def nets_with_copper(design: Design) -> set[str]:
    """The names of the nets that hold a track or an arc on ``design``."""
    assert design.board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    return {names.get(item.net_id or "", "") for item in (*design.board.tracks, *design.board.arcs)}


def coupled(design: Design, positive: str, negative: str) -> bool:
    """Whether both nets of a pair hold copper (the gate's reading of "routed as a pair"; KiCad's gap and
    uncoupled rules judge the coupling itself)."""
    held = nets_with_copper(design)
    return positive in held and negative in held


def reread(path: Path) -> Design:
    return read_board(path.read_text(encoding="utf-8"))


__all__ = ["PairRun", "coupled", "names_run", "nets_with_copper", "pair_run", "reread"]
