# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCadRoutingTools adapter. The external router runs as a subprocess; its file is never adopted.

One process routes one group of nets: the nets of a tier whose track width, via diameter and via drill
are equal (capability routing, "KiCadRoutingTools plugin"; change c0109). Every process is started through
the job's one time budget (``routing.budget``).

Change c0110: before every other step, one ``bga_fanout.py`` (dog-bones) or ``qfn_fanout.py`` process per
escape request of the job; then, tier by tier, one ``route_diff.py`` process per job pair whose names the
tool pairs (``PAIR_NAME_FORMS``), before the groups of that tier. Each is one run of the budget. The
features ``pairs`` and ``escape`` are declared only when the gate of c0110 holds for them
(``GATED_FEATURES``); until then ``fenolite route`` gives this router no pair and no escape request.
"""

from __future__ import annotations

import dataclasses
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends.kicad.dru import write_rules
from fenolite.backends.kicad.pcb import read_board, source_info, write_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import DEFAULT_TARGET
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence
from fenolite.model.board import Arc, Track, Via
from fenolite.model.pairs import split_pair_name
from fenolite.routing.budget import Budget, exhausted
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.protocol import (
    FinishedRun,
    JobEscape,
    JobNet,
    JobPair,
    RouterRun,
    RouterStatus,
    RoutingJob,
    RoutingResult,
)

PINNED_TAG = "v0.22.1"
DEFAULT_BUDGET = 900
"""Seconds for the whole job when neither the job nor the constructor names a budget."""
GROUP_OPTION = "group-nets"
"""The router option that splits a group into runs of at most N nets; it is not passed to the tool."""
OWN_OPTIONS = ("nets", "output", "overwrite")
"""Options of the tool that the plugin decides itself: ignored with ``route.option-ignored``."""
REFUSED_OPTIONS = ("polarity-swap-nets", "impedance", "rip-existing-nets", "force-reroute")
"""Options that never reach a step (change c0110): a swap changes the netlist, impedance is c0105's and
would choose the width, and the last two remove copper the plugin keeps."""
GRID_OPTION = "grid-step"
"""The router option that reaches the escape steps as well as ``route.py``, as the tool's help asks."""
PAIR_NAME_FORMS = ("X_P/X_N", "X_P<digits>/X_N<digits>", "X+/X-", "X_DP/X_DN")
"""The pair names that ``route_diff.py`` routes coupled, as measured on the name bench of c0110
(measurement 4; ``H-K-KRT-PAIRNAMES``): ``P``/``N`` after ``_`` with a tail of digits or none, a
polarity ``+``/``-`` with no tail, and a base ending in ``_D``. ``DP1``/``DN1``, which KiCad pairs, is not
paired by the tool."""
GATED_FEATURES = frozenset({"pairs", "escape"})
"""The features the plugin implements; it declares those whose gate outcomes hold (task 1.6 of c0110)."""
EVIDENCE = Evidence(
    oracle="KiCadRoutingTools v0.22.1", hypotheses=("H-K-KRT-CLI", "H-K-KRT-GROUP", "H-K-KRT-ROUTE")
)
"""Describes the plugin; a route itself is always ``UNVERIFIED``. ``H-K-KRT-GROUP``, the grouped run of
change c0109, is ``KICAD-VERIFIED (9.0.x, 10.0.x)``: the routing job recorded it on both majors."""


def _mm(value: int) -> str:
    sign = "-" if value < 0 else ""
    whole, fraction = divmod(abs(value), 1_000_000)
    suffix = f"{fraction:06d}".rstrip("0")
    return f"{sign}{whole}" + (f".{suffix}" if suffix else "")


def _line(value: object, folder: Path | None = None) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    line = str(value or "").splitlines()[0].strip() if value else ""
    if folder:
        line = line.replace(str(folder), "<run-dir>")
    return re.sub(r"[\x00-\x1f\x7f]", " ", line)[:300] or "no diagnostic output"


def _copper(design: object) -> tuple[Track | Arc | Via, ...]:
    board = getattr(design, "board", None)
    return () if board is None else (*board.tracks, *board.arcs, *board.vias)


def _named(names: tuple[str, ...]) -> str:
    """The names of a run for a message: the first five, then the count of the others."""
    shown = ", ".join(names[:5])
    return shown + (f" and {len(names) - 5} more" if len(names) > 5 else "")


def _unit(names: tuple[str, ...]) -> str:
    """The name of a run as a unit of progress: its first net, and the count of the others."""
    return names[0] if len(names) == 1 else f"{names[0]} and {len(names) - 1} more"


def tool_pairs(positive: str, negative: str) -> bool:
    """Whether the names of a pair take one of the forms of ``PAIR_NAME_FORMS``."""
    split = split_pair_name(positive)
    if split is None or split_pair_name(negative) is None:
        return False
    if split.polarity == "+":
        return split.tail == ""
    if split.polarity != "P":
        return False
    if split.base.endswith("_"):
        return split.tail == "" or split.tail.isdigit()
    return split.base.endswith("_D") and split.tail == ""


@dataclass(frozen=True, slots=True)
class _Step:
    """One tool process of a job: its nets, tier, unit of progress, the label and place of a failure,
    whether it is an escape step, and its arguments after the interpreter, from the checkout, the input
    board and the output board."""

    nets: tuple[str, ...]
    tier: int
    unit: str
    label: str
    where: str
    escape: bool
    arguments: Callable[[Path, Path, Path], list[str]]


def plan_runs(nets: tuple[JobNet, ...], group_nets: int | None = None) -> tuple[tuple[JobNet, ...], ...]:
    """The runs of a job, in the order they start.

    A group is the nets of one tier whose width, via diameter and via drill are equal, in job order;
    ``group_nets`` splits a group into runs of at most that many nets. Tiers go lowest first, and inside
    a tier the runs go in the order of their first net in the job.
    """
    groups: dict[tuple[int, int, int, int], list[JobNet]] = {}
    for net in sorted(nets, key=lambda item: item.tier):  # stable: job order inside a tier
        groups.setdefault((net.tier, net.width, net.via_diameter, net.via_drill), []).append(net)
    first = {net.name: index for index, net in reversed(list(enumerate(nets)))}
    ordered = sorted(groups.values(), key=lambda group: (group[0].tier, first[group[0].name]))
    runs: list[tuple[JobNet, ...]] = []
    for group in ordered:
        size = group_nets or len(group)
        runs.extend(tuple(group[start : start + size]) for start in range(0, len(group), size))
    return tuple(runs)


class KicadRoutingToolsRouter:
    """Run one tool process per group of nets and lift only copper that its input board lacked."""

    name = "kicadroutingtools"
    description = "Routes nets with the external KiCadRoutingTools grid A* router."
    sends_data_offsite = False
    default_budget: float = DEFAULT_BUDGET
    features: frozenset[str] = frozenset()
    """None of ``GATED_FEATURES`` until the gate of c0110 is recorded on both majors (its task 1.6)."""

    def __init__(
        self,
        path: str | Path | None = None,
        python: str | Path | None = None,
        budget: float | None = None,
    ) -> None:
        raw_path = path or os.environ.get("FENOLITE_KRT")
        self.path = Path(raw_path).expanduser() if raw_path else None
        self.python = str(python or os.environ.get("FENOLITE_KRT_PYTHON") or shutil.which("python3") or "")
        self.budget = budget
        """Seconds for a job that names no budget of its own; ``None`` gives ``DEFAULT_BUDGET``."""

    def available(self) -> RouterStatus:
        """Check required files and interpreter without launching the external tool."""
        if self.path is None:
            return RouterStatus(False, reason="set FENOLITE_KRT to the KiCadRoutingTools v0.22.1 checkout")
        route = self.path / "py_router" / "route.py"
        if not route.is_file():
            return RouterStatus(False, path=str(self.path), reason=f"missing {route}")
        if not (self.path / "rust_router" / "grid_router.so").is_file():
            return RouterStatus(
                False, path=str(self.path), reason="missing rust_router/grid_router.so; run build_router.py"
            )
        if not self.python or (not Path(self.python).is_file() and shutil.which(self.python) is None):
            return RouterStatus(
                False, path=str(self.path), reason="set FENOLITE_KRT_PYTHON to its Python interpreter"
            )
        version_file = self.path / "VERSION"
        version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "unknown"
        return RouterStatus(True, str(self.path), version)

    def _options(self, job: RoutingJob, issues: list[Issue]) -> tuple[list[str], int | None]:
        """The tool arguments of the job's router options, and the value of ``group-nets``."""
        passed: list[str] = []
        group_nets: int | None = None
        for key, value in job.options.items():
            if key == GROUP_OPTION:
                if value.isdigit() and int(value) > 0:
                    group_nets = int(value)
                else:
                    issues.append(
                        Issue(
                            "route.option-ignored",
                            "warning",
                            f"the router option {key}={value} is not a positive integer and was ignored",
                            key,
                        )
                    )
            elif key in REFUSED_OPTIONS:
                issues.append(
                    Issue(
                        "route.option-ignored",
                        "warning",
                        f"the router option {key}={value} is refused by {self.name} and was ignored",
                        key,
                        hint="pair polarity, impedance and ripping are not left to the tool",
                    )
                )
            elif key in OWN_OPTIONS:
                issues.append(
                    Issue(
                        "route.option-ignored",
                        "warning",
                        f"the router option {key}={value} is set by {self.name} itself and was ignored",
                        key,
                        hint="select nets with --nets and --order; the output is a temporary file",
                    )
                )
            else:
                passed.extend((f"--{key}", value))
        return passed, group_nets

    # --- the steps of a job (change c0110) -------------------------------------------------------------

    def _pairs(self, job: RoutingJob, issues: list[Issue]) -> tuple[tuple[JobPair, ...], set[str]]:
        """The job pairs the tool pairs, and the nets of the others, which no step routes: each such pair
        gives ``route.pair-skipped``."""
        sent: list[JobPair] = []
        held: set[str] = set()
        for pair in job.pairs:
            if tool_pairs(pair.positive, pair.negative):
                sent.append(pair)
                continue
            held.update((pair.positive, pair.negative))
            issues.append(
                Issue(
                    "route.pair-skipped",
                    "warning",
                    f"the pair {pair.name} is not routed: {self.name} does not pair names of that form; "
                    f"it pairs {', '.join(PAIR_NAME_FORMS)}",
                    pair.name,
                    hint="rename the nets to a form the tool pairs, or pass --pairs-as-nets",
                )
            )
        return tuple(sent), held

    @staticmethod
    def _layers(job: RoutingJob, net: JobNet) -> tuple[str, ...]:
        """The layers of a pair or escape step: the net's own, else the job's without its plane layers."""
        if net.layers is not None:
            return net.layers
        return tuple(layer for layer in job.layers if layer not in job.plane_layers)

    def _pair_step(self, job: RoutingJob, pair: JobPair, by_name: dict[str, JobNet]) -> _Step:
        positive = by_name[pair.positive]
        negative = by_name.get(pair.negative, positive)
        tier = min(positive.tier, negative.tier)
        layers = self._layers(job, positive)
        names = (pair.positive, pair.negative)

        def arguments(checkout: Path, board: Path, output: Path) -> list[str]:
            words = [
                str(checkout / "py_router" / "route_diff.py"),
                str(board),
                str(output),
                "--nets",
                *names,
                "--track-width",
                _mm(pair.width),
                "--diff-pair-gap",
                _mm(pair.gap),
                "--clearance",
                _mm(positive.clearance),
                "--via-size",
                _mm(positive.via_diameter),
                "--via-drill",
                _mm(positive.via_drill),
                "--layers",
                *layers,
                "--no-gnd-vias",
                "--keep-input-copper",
                "--same-net-pad-clearance",
                _mm(positive.clearance),
                "--escalation",
                "off",
                "--no-fix-drc-settings",
            ]
            if pair.skew_max is not None:
                words += ["--diff-pair-intra-match", "--length-match-tolerance", _mm(pair.skew_max)]
            return words

        return _Step(names, tier, pair.name, f"pair {pair.name}", pair.positive, False, arguments)

    def _escape_step(
        self,
        job: RoutingJob,
        request: JobEscape,
        pairs: tuple[JobPair, ...],
        by_name: dict[str, JobNet],
        tier: int,
    ) -> _Step:
        nets = [by_name[name] for name in request.nets if name in by_name]
        width = min(net.width for net in nets)
        clearance = max(net.clearance for net in nets)
        diameter = min(net.via_diameter for net in nets)
        drill = min(net.via_drill for net in nets)
        layers = self._layers(job, nets[0])
        grid = job.options.get(GRID_OPTION)
        on_part = set(request.nets)
        part_pairs = [pair for pair in pairs if pair.positive in on_part or pair.negative in on_part]
        names = tuple(net.name for net in nets)

        def arguments(checkout: Path, board: Path, output: Path) -> list[str]:
            if request.kind == "grid":
                words = [
                    str(checkout / "py_router" / "bga_fanout.py"),
                    str(board),
                    "--component",
                    request.ref,
                    "--output",
                    str(output),
                    "--escape-method",
                    "dogbone",
                    "--nets",
                    *names,
                    "--layers",
                    *layers,
                    "--track-width",
                    _mm(width),
                ]
            else:
                words = [
                    str(checkout / "py_router" / "qfn_fanout.py"),
                    str(board),
                    "--output",
                    str(output),
                    "--component",
                    request.ref,
                    "--nets",
                    *names,
                    "--width",
                    _mm(width),
                ]
            words += ["--clearance", _mm(clearance), "--via-size", _mm(diameter), "--via-drill", _mm(drill)]
            if request.kind == "grid":
                words += ["--plane-drop", "off"]
            words += [
                "--same-net-pad-clearance",
                _mm(clearance),
                "--escalation",
                "off",
                "--no-fix-drc-settings",
            ]
            if request.kind == "grid" and part_pairs:
                members = [name for pair in part_pairs for name in (pair.positive, pair.negative)]
                gap = min(pair.gap for pair in part_pairs)
                words += ["--diff-pairs", *members, "--diff-pair-gap", _mm(gap)]
            if grid is not None:
                words += ["--grid-step", grid]
            return words

        label = f"escape of {request.ref}"
        return _Step(names, tier, f"escape {request.ref}", label, request.ref, True, arguments)

    def _group_step(self, group: tuple[JobNet, ...], passed: list[str]) -> _Step:
        names = tuple(net.name for net in group)

        def arguments(checkout: Path, board: Path, output: Path) -> list[str]:
            return [
                str(checkout / "py_router" / "route.py"),
                str(board),
                str(output),
                "--nets",
                *names,
                "--track-width",
                _mm(group[0].width),
                "--via-size",
                _mm(group[0].via_diameter),
                "--via-drill",
                _mm(group[0].via_drill),
                # the sizes are the job's: a net that does not fit stays open (measured, c0109)
                "--escalation",
                "off",
                # the project file of the run folder stays the one written above
                "--no-fix-drc-settings",
                *passed,
            ]

        return _Step(names, group[0].tier, _unit(names), _named(names), names[0], False, arguments)

    def route(self, job: RoutingJob) -> RoutingResult:
        """Route the job's nets group by group in a temporary project folder, inside the job's budget,
        returning the copper of the runs that finished and the issues of the others."""
        status = self.available()
        if not status.available or self.path is None:
            return RoutingResult(
                unrouted=tuple(net.name for net in job.nets),
                issues=(Issue("route.tool-missing", "error", status.reason or "router unavailable"),),
                tool=self.name,
                tool_version=status.version or "",
                evidence=Evidence(),
            )
        budget = Budget(job.budget or self.budget or DEFAULT_BUDGET)
        issues: list[Issue] = []
        routed: list[str] = []
        unrouted: list[str] = []
        not_attempted: list[str] = []
        runs: list[RouterRun] = []
        cut_nets = 0
        tracks: list[Track] = []
        arcs: list[Arc] = []
        vias: list[Via] = []
        logs: list[str] = []
        passed, group_nets = self._options(job, issues)
        info = source_info(job.design)
        target = int(info.major) if info is not None and info.major is not None else DEFAULT_TARGET
        kept = sorted(net.name for net in job.nets if net.layers is not None)
        if job.plane_layers or kept:
            # the tool takes no layer or plane option: its board and rules files hold the row types and
            # the track layer rules, and what it does with them is not settled (H-K-KRT-PLANES: inconclusive)
            told = [f"plane layers {', '.join(job.plane_layers)}"] if job.plane_layers else []
            told += [f"the layers of {', '.join(kept)}"] if kept else []
            issues.append(
                Issue(
                    "route.constraint-not-sent",
                    "warning",
                    f"KiCadRoutingTools takes no option for {' and '.join(told)}: its tracks may lie on "
                    "a plane layer or on a layer a track layer rule forbids",
                    hint="run check, or route with freerouting, which is told both",
                )
            )
        try:
            with tempfile.TemporaryDirectory(prefix="fenolite-route-") as name:
                folder = Path(name)
                stem = "fenolite-routing"
                # The rules of the job's design may have been read from the project's rules file
                # (change c0107): such a set is written back by ``write_rules``, which keeps its order and
                # names, and not lowered again. A set that cannot be written leaves the empty rules file.
                rules = job.design.rules
                bare = dataclasses.replace(job.design, rules=None)
                for filename, contents in write_triad(bare, name=stem, target=target).items():
                    (folder / filename).write_text(contents, encoding="utf-8", newline="\n")
                if rules is not None and rules.rules:
                    try:
                        rules_text = write_rules(rules, target=target, allow_lossy=True)
                    except FenoliteError as error:
                        logs.append(f"rules file not written: {_line(error, folder)}")
                    else:
                        (folder / f"{stem}.kicad_dru").write_text(rules_text, encoding="utf-8", newline="\n")
                board_path = folder / f"{stem}.kicad_pcb"
                project_set(board_path)
                current = job.design
                env = {**os.environ, "LANG": "C", "LC_ALL": "C"}
                by_name = {net.name: net for net in job.nets}
                sent_pairs, held_back = self._pairs(job, issues)
                in_pairs = {name for pair in sent_pairs for name in (pair.positive, pair.negative)}
                for name in sorted(held_back):
                    unrouted.append(name)
                singles = tuple(
                    net for net in job.nets if net.name not in in_pairs and net.name not in held_back
                )
                planned = plan_runs(singles, group_nets)
                first_tier = min((net.tier for net in job.nets), default=0)
                steps: list[_Step] = []
                for request in job.escape:
                    steps.append(self._escape_step(job, request, sent_pairs, by_name, first_tier))
                pair_steps = [self._pair_step(job, pair, by_name) for pair in sent_pairs]
                tiers = sorted({step.tier for step in pair_steps} | {group[0].tier for group in planned})
                for tier in tiers:
                    steps.extend(step for step in pair_steps if step.tier == tier)
                    steps.extend(
                        self._group_step(group, passed) for group in planned if group[0].tier == tier
                    )
                for index, step in enumerate(steps):
                    names = step.nets
                    unit = step.unit
                    tier = step.tier
                    counted = () if step.escape else names  # escaped nets are routed by later steps
                    if budget.left() <= 0:  # no process starts once the budget is spent
                        not_attempted.extend(counted)
                        unrouted.extend(counted)
                        continue
                    # the board of this run holds the copper of every run before it
                    board_text = write_board(current, target=target).text
                    board_path.write_text(board_text, encoding="utf-8", newline="\n")
                    baseline = read_board(board_text, file=board_path.name)
                    output_path = folder / f"routed-{index}.kicad_pcb"
                    args = [self.python, *step.arguments(self.path, board_path, output_path)]
                    if budget.left() <= 0:  # the board of the run took the last of the budget
                        not_attempted.extend(counted)
                        unrouted.extend(counted)
                        continue
                    # each process is one unit of progress (change c0120)
                    job.progress.step(unit, index=index + 1, total=len(steps))
                    done = budget.run(args, cwd=folder, env=env)
                    if not done.started:
                        not_attempted.extend(counted)
                        unrouted.extend(counted)
                        job.progress.done(unit, detail="timeout")
                        continue
                    if done.cut:
                        # a killed process may leave a missing or cut board: it is not read
                        runs.append(RouterRun(names, tier, done.seconds, "cut"))
                        unrouted.extend(counted)
                        cut_nets += len(names)
                        job.progress.done(unit, detail="timeout")
                        continue
                    output_line = _line(done.stderr or done.stdout, folder)
                    if output_line != "no diagnostic output":
                        logs.append(output_line)

                    seconds = done.seconds
                    why = ""
                    result = None
                    if done.returncode or not output_path.is_file():
                        why = f"exit {done.returncode}" if done.returncode else "output board missing"
                        why = f"{why}: {output_line}"
                    else:
                        try:
                            result = read_board(
                                output_path.read_text(encoding="utf-8"), file=output_path.name
                            )
                        except Exception as exc:
                            why = _line(exc, folder)
                    if result is None:
                        issues.append(Issue("route.tool-failed", "error", f"{step.label}: {why}", step.where))
                        unrouted.extend(counted)
                        runs.append(RouterRun(names, tier, seconds, "failed"))
                        job.progress.done(unit, detail="failed")
                        continue
                    old_ids = {item.id for item in _copper(baseline)}
                    after = _copper(result)
                    absent = old_ids - {item.id for item in after}
                    issues.extend(
                        Issue(
                            "route.copper-removed",
                            "warning",
                            "router removed existing copper; preserved",
                            item_id,
                        )
                        for item_id in sorted(absent)
                    )
                    baseline_net_names = {entry.id: entry.name for entry in baseline.circuit.nets}
                    current_net_ids = {entry.name: entry.id for entry in current.circuit.nets}
                    run_ids = {by_name[name].net_id for name in names if name in by_name}
                    lifted = tuple(
                        dataclasses.replace(
                            item,
                            net_id=current_net_ids.get(
                                baseline_net_names.get(item.net_id or "", ""), item.net_id
                            ),
                        )
                        for item in after
                        if item.id not in old_ids
                    )
                    # only copper on the nets of this run is taken, and later runs see exactly that
                    kept = tuple(item for item in lifted if item.net_id in run_ids)
                    delta = RoutingResult(
                        tracks=tuple(item for item in kept if isinstance(item, Track)),
                        arcs=tuple(item for item in kept if isinstance(item, Arc)),
                        vias=tuple(item for item in kept if isinstance(item, Via)),
                    )
                    try:
                        current = apply(current, delta)
                    except RoutingError as exc:
                        issues.extend(exc.issues)
                        unrouted.extend(counted)
                        runs.append(RouterRun(names, tier, seconds, "failed"))
                        job.progress.done(unit, detail="failed")
                        continue
                    runs.append(RouterRun(names, tier, seconds, "done"))
                    with_copper = {item.net_id for item in kept}
                    for name in counted:
                        (routed if by_name[name].net_id in with_copper else unrouted).append(name)
                    tracks.extend(delta.tracks)
                    arcs.extend(delta.arcs)
                    vias.extend(delta.vias)
                    if kept and job.on_run is not None:  # before the next process starts (change c0120)
                        job.on_run(
                            FinishedRun(
                                nets=tuple(name for name in names if by_name[name].net_id in with_copper),
                                tracks=delta.tracks,
                                arcs=delta.arcs,
                                vias=delta.vias,
                                tier=tier,
                                seconds=seconds,
                            )
                        )
                    job.progress.done(unit, detail="routed" if kept else "no copper")
        except Exception as exc:
            return RoutingResult(
                unrouted=tuple(net.name for net in job.nets),
                issues=(Issue("route.tool-failed", "error", _line(exc)),),
                tool=self.name,
                tool_version=status.version,
                log=(_line(exc),),
                evidence=Evidence(),
            )
        if cut_nets or not_attempted:
            issues.append(exhausted(budget.seconds, cut_nets, len(not_attempted), self.name))
        if status.version != PINNED_TAG.removeprefix("v"):
            issues.append(
                Issue(
                    "route.tool-unpinned",
                    "warning",
                    f"expected {PINNED_TAG}, found {status.version}",
                    str(self.path),
                )
            )
        return RoutingResult(
            tracks=tuple(tracks),
            arcs=tuple(arcs),
            vias=tuple(vias),
            routed=tuple(routed),
            unrouted=tuple(unrouted),
            issues=tuple(issues),
            tool=self.name,
            tool_version=status.version,
            log=tuple(logs[:20]),
            evidence=dataclasses.replace(EVIDENCE, oracle=f"KiCadRoutingTools {status.version}"),
            runs=tuple(runs),
            not_attempted=tuple(not_attempted),
        )


__all__ = [
    "DEFAULT_BUDGET",
    "EVIDENCE",
    "GATED_FEATURES",
    "GRID_OPTION",
    "PAIR_NAME_FORMS",
    "PINNED_TAG",
    "REFUSED_OPTIONS",
    "KicadRoutingToolsRouter",
    "plan_runs",
    "tool_pairs",
]
