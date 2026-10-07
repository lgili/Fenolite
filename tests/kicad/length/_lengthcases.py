# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The oracle runs of the length benches (capability kicad-oracle, "Net length parity canaries"; change
c0106). KiCad prints the length of a net only as the ``actual`` of a ``length_out_of_range`` violation, so
each case runs ``pcb drc`` twice: with one rule ``length (max T − 1 µm)`` per net, which must report every
net, and with ``length (max T + 1 µm)``, which must report none. ``T`` is the net's total in
``length_facts`` for the running major. Every rules file holds the scoped canary of c0071."""

from __future__ import annotations

import contextlib
import dataclasses
import io
import os
import re
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from unittest import mock

import _lengthbench as lb
import _meanderdesign as md

import fenolite.cli.main as cli_main
from fenolite.backends.base import DrcReport, LengthFacts
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, write_board
from fenolite.core.ids import derived_id
from fenolite.model.board import Track
from fenolite.model.circuit import Net
from fenolite.model.design import Design

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
DELTA_NM = 1_000
LENGTH_TYPE = "length_out_of_range"
SKEW_TYPE = "skew_out_of_range"
_ACTUAL = re.compile(r"actual (-?[0-9.]+) mm")


@dataclass(frozen=True)
class Bracket:
    """The two runs of one case: the totals Fenolite gives, and what KiCad reports below and above them."""

    case: str
    facts: LengthFacts
    totals: Mapping[str, int]
    below: DrcReport | None
    above: DrcReport | None

    def reported(self, report: DrcReport | None, kind: str = LENGTH_TYPE) -> dict[str, str]:
        """Net → the last ``actual`` (millimetres, as printed) of its violations of ``kind``."""
        return reported(report, lb.bench(self.case, self.facts.major or 0), kind)

    @property
    def canary(self) -> bool:
        return canary_fired(self.below, self.case, self.facts.major or 0) and canary_fired(
            self.above, self.case, self.facts.major or 0
        )

    @property
    def outcome(self) -> str:
        if self.below is None or self.above is None:
            return "inconclusive"
        low, high = self.reported(self.below), self.reported(self.above)
        return "equal" if set(low) == set(self.totals) and not high else "different"


def reported(report: DrcReport | None, design: object, kind: str) -> dict[str, str]:
    if report is None:
        return {}
    nets = lb.net_uuids(design)  # type: ignore[arg-type]
    found: dict[str, str] = {}
    for violation in report.violations:
        if violation.type != kind:
            continue
        match = _ACTUAL.search(violation.description)
        for item in violation.items:
            net = nets.get(item.uuid)
            if net is not None:
                found[net] = match.group(1) if match else ""
    return found


def canary_fired(report: DrcReport | None, case: str, target: int) -> bool:
    """Whether the report holds the clearance violation between the two canary tracks."""
    if report is None:
        return False
    board = lb.bench(case, target).board
    assert board is not None
    names = {net.id: net.name for net in lb.bench(case, target).circuit.nets}
    wanted = {kicad_uuid(t) for t in board.tracks if names.get(t.net_id or "") in lb.CANARY_NETS}
    return any(
        v.type == "clearance" and len({i.uuid for i in v.items} & wanted) == 2 for v in report.violations
    )


def _drc(cli: KicadCli, case: str, target: int, rules: str) -> DrcReport | None:
    with tempfile.TemporaryDirectory() as tmp:
        project = lb.write_case(case, target, Path(tmp), rules)
        files = {name: path for name, path in project.files.items() if name != project.board}
        return cli.drc(project.files[project.board], files=files).report


def facts_of(case: str, target: int) -> LengthFacts:
    """The facts of the bench as written and read back, with its project file, for ``target``."""
    with tempfile.TemporaryDirectory() as tmp:
        project = lb.write_case(case, target, Path(tmp))
        design = read_board(lb.bench_text(case, target))
        return KicadBackend().length_facts(design, project=project, major=target)


@cache
def bracket(cli: KicadCli, case: str, totals_from: str | None = None) -> Bracket:
    """The two runs of ``case``. With ``totals_from``, the totals are those of that case's facts while the
    board is still the one of ``case`` (the unprojected node, judged with the totals of its thicknesses)."""
    target = cli.major()
    facts = facts_of(totals_from or case, target)
    totals = {net: facts.nets[net].total for net in lb.nets_of(case)}
    below = _drc(cli, case, target, lb.bracket_rules(totals, -DELTA_NM))
    above = _drc(cli, case, target, lb.bracket_rules(totals, DELTA_NM))
    return Bracket(case, facts, totals, below, above)


@cache
def rules_run(cli: KicadCli, case: str) -> tuple[bool, tuple[tuple[str, str], ...], tuple[str, ...]]:
    """One rules case on the rules bench: whether the canary fired, the (violation type, net) pairs KiCad
    reports, and the descriptions of those violations."""
    target = cli.major()
    report = _drc(cli, "rules", target, lb.rules_case_text(case))
    pairs: set[tuple[str, str]] = set()
    texts: list[str] = []
    if report is not None:
        design = lb.bench("rules", target)
        for kind in (LENGTH_TYPE, SKEW_TYPE):
            pairs |= {(kind, net) for net in reported(report, design, kind)}
        texts = [v.description for v in report.violations if v.type in (LENGTH_TYPE, SKEW_TYPE)]
    return canary_fired(report, "rules", target), tuple(sorted(pairs)), tuple(texts)


def probe_id(case: str) -> str:
    return f"length-via-{case}" if case in lb.VIA_CASES else f"length-total-{case}"


def length_probes(runner: Callable[[], KicadCli]) -> Probes:
    """The ``length-total-*`` and ``length-via-*`` probes of the running ``kicad-cli``."""
    probes: Probes = {}
    for case in lb.CASES:
        if case not in ("rules", "four-unprojected"):
            probes[probe_id(case)] = (lambda case=case: bracket(runner(), case).outcome, (9, 10))
    # ``equal`` when KiCad counts the thicknesses of a stack-up node that the reader does not project
    probes[probe_id("four-unprojected")] = (
        lambda: bracket(runner(), "four-unprojected", "four-explicit").outcome,
        (9, 10),
    )
    return probes


# --- meanders (capability kicad-oracle, "Meanders pass the oracle") ---------------------------------

MEANDER_CASES: Mapping[str, str] = {"axis": "axis", "pair": "pair4", "angle": "angle"}
"""Probe case → the design script of ``tests/_meanderdesign.py``."""
PAIR_SKEW = (
    '(rule "pair_skew"\n\t(constraint skew (max 0.001mm) (within_diff_pairs))\n'
    "\t(condition \"A.inDiffPair('USB')\")\n)\n"
)


@dataclass(frozen=True)
class MeanderRun:
    """One meander case on the running major: the target, Fenolite's total of the meandered net, whether
    the canary fired in every run, whether KiCad reports the net 1 µm below and 1 µm above the target, the
    violation types the meandered board holds beyond the board without the meander, and the skew
    violations of the pair."""

    target: int
    total: int
    canary: bool
    below: bool
    above: bool
    extra: tuple[str, ...]
    skew: int

    @property
    def outcome(self) -> str:
        fine = self.below and not self.above and not self.extra and self.skew == 0
        return "equal" if fine else "different"


def _built(case: str, target: int, folder: Path, *, meander: bool) -> Design:
    """The board of the design script of ``case``, built by ``fenolite build`` for ``target`` and read
    back, with the canary pair added."""
    root = folder / ("with" if meander else "without")
    script = md.write_script(root, MEANDER_CASES[case], meander=meander)
    out = script.parent / "out"
    args = ["--kicad-version", str(target), "build", str(script), "--out", str(out), "--confirm", "--json"]
    stdout = io.StringIO()
    with (
        mock.patch.dict(os.environ, {"KICAD_CONFIG_HOME": str(folder / "kicad-config")}),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        code = cli_main.main(args)
    assert code == 0, stdout.getvalue()[-800:]
    design = read_board((out / f"{MEANDER_CASES[case]}.kicad_pcb").read_text(encoding="utf-8"))
    assert design.board is not None
    nets = tuple(Net(id=derived_id("net", "tests", name), name=name) for name in lb.CANARY_NETS)
    tracks = tuple(
        Track(
            id=derived_id("trk", "tests", f"canary-{k}"),
            start=lb.mm(30, 5 + k),
            end=lb.mm(40, 5 + k),
            width=lb.WIDTH,
            layer="F.Cu",
            net_id=net.id,
        )
        for k, net in enumerate(nets)
    )
    return dataclasses.replace(
        design,
        circuit=dataclasses.replace(design.circuit, nets=(*design.circuit.nets, *nets)),
        board=dataclasses.replace(design.board, tracks=(*design.board.tracks, *tracks)),
    )


def _run_design(cli: KicadCli, design: Design, target: int, rules: str) -> tuple[DrcReport | None, bool]:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / f"{lb.STEM}.kicad_pcb"
        board.write_text(write_board(design, target=target).text, encoding="utf-8", newline="\n")
        project, dru = folder / f"{lb.STEM}.kicad_pro", folder / f"{lb.STEM}.kicad_dru"
        project.write_text(lb.PROJECT, encoding="utf-8")
        dru.write_text(rules, encoding="utf-8")
        report = cli.drc(board, files={project.name: project, dru.name: dru}).report
    assert design.board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    wanted = {kicad_uuid(t) for t in design.board.tracks if names.get(t.net_id or "") in lb.CANARY_NETS}
    fired = report is not None and any(
        v.type == "clearance" and len({i.uuid for i in v.items} & wanted) == 2 for v in report.violations
    )
    return report, fired


def _types(report: DrcReport | None) -> Counter[str]:
    if report is None:
        return Counter()
    found = Counter(v.type for v in (*report.violations, *report.unconnected_items))
    for kind in (LENGTH_TYPE, SKEW_TYPE):
        found.pop(kind, None)
    return found


@cache
def meander_run(cli: KicadCli, case: str) -> MeanderRun:
    target = cli.major()
    script_case = MEANDER_CASES[case]
    net = md.NETS[script_case][0]
    with tempfile.TemporaryDirectory() as tmp:
        tuned = _built(case, target, Path(tmp), meander=True)
        plain = _built(case, target, Path(tmp), meander=False)
    facts = KicadBackend().length_facts(tuned, major=target)
    total = facts.nets[net].total
    wanted = facts.nets["USB_P"].total if case == "pair" else md.TARGETS[script_case] * lb.MM
    more = PAIR_SKEW if case == "pair" else ""
    below, canary_a = _run_design(cli, tuned, target, lb.bracket_rules({net: wanted}, -DELTA_NM) + more)
    above, canary_b = _run_design(cli, tuned, target, lb.bracket_rules({net: wanted}, DELTA_NM) + more)
    base, canary_c = _run_design(cli, plain, target, lb.bracket_rules({net: wanted}, DELTA_NM) + more)
    uuids = lb.net_uuids(tuned)

    def names(report: DrcReport | None, kind: str) -> set[str]:
        if report is None:
            return set()
        return {
            uuids[i.uuid] for v in report.violations if v.type == kind for i in v.items if i.uuid in uuids
        }

    extra = _types(above) - _types(base)
    skew = len([v for v in (above.violations if above is not None else ()) if v.type == SKEW_TYPE])
    return MeanderRun(
        target=wanted,
        total=total,
        canary=canary_a and canary_b and canary_c,
        below=net in names(below, LENGTH_TYPE),
        above=net in names(above, LENGTH_TYPE),
        extra=tuple(sorted(extra.elements())),
        skew=skew,
    )


def meander_probes(runner: Callable[[], KicadCli]) -> Probes:
    """The ``length-meander-*`` probes of the running ``kicad-cli``."""
    return {
        f"length-meander-{case}": (lambda case=case: meander_run(runner(), case).outcome, (9, 10))
        for case in MEANDER_CASES
    }
