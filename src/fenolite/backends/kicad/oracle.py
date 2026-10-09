# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``kicad-cli`` as the oracle of ``fenolite check`` (capability kicad-oracle, "Check canary injection",
"Netlist oracle from IPC-D-356" and "RT2 oracle"; backend-protocol, "Oracle protocol" and "Netlist and
round-trip oracles").

``KicadOracle.drc`` runs ``pcb drc`` on the project's copy set through the package runner, with the
canary staged into private copies of the board and rules file when it applies, so that the report also
says whether the custom rules were loaded. The decision order, the verdict and the stripping follow c0013
Decision 6; a canary missing from a saturated report gives no verdict (c0051 Decision 5). Facts come from
here, and the issues and severities are ``checks``'s policy.

``netlist`` exports IPC-D-356 and pairs its records with the board's pads (``padnets``); ``rt2`` runs DRC
twice on the board and once on Fenolite's re-dump of it, both re-saved by ``pcb upgrade`` on 10.0 (c0020
Decisions 9 and 10).

Change c0062 (capability kicad-oracle, "ERC oracle", "Parity in the DRC run" and "Schematic RT2 over the
corpus"): ``erc`` runs ``sch erc`` on the schematic of the board's stem and locates the items of its report
as ``REF-PIN``; ``drc`` passes ``--schematic-parity`` when the copy set holds that schematic, and runs
again without it when the flagged run writes no report, so that the copper verdict never depends on the
schematic; ``rt2_erc`` runs ERC twice on the project and once on Fenolite's re-dump of its sheets.
"""

from __future__ import annotations

import dataclasses
import re
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Literal

from fenolite.backends.base import (
    CanaryState,
    DrcLimits,
    DrcOutcome,
    DrcReport,
    ErcOracle,
    ErcOutcome,
    ErcReport,
    ErcRt2Outcome,
    FillOutcome,
    LimitedOracle,
    NetlistOracle,
    NetlistOutcome,
    Oracle,
    PadAssignment,
    PadNetList,
    PlotOutcome,
    PlotView,
    ProjectSet,
    RoundTripOracle,
    Rt2Outcome,
    SchematicNetlistOracle,
)
from fenolite.backends.kicad import canary, padnets, sch
from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad import erc as ercmod
from fenolite.backends.kicad import netlist as netlistmod
from fenolite.backends.kicad import plot as plotmod
from fenolite.backends.kicad.cli import (
    DRC_REPORT,
    ERC_REPORT,
    NETLIST,
    CliRun,
    KicadCli,
    KicadCliError,
    KicadCliVersionError,
)
from fenolite.backends.kicad.fill import EVIDENCE as FILL_EVIDENCE
from fenolite.backends.kicad.fill import fill_set, zone_fills
from fenolite.backends.kicad.ipcd356 import read_ipcd356
from fenolite.backends.kicad.pcb import read_board, rebuild_board
from fenolite.backends.kicad.sch import EVIDENCE as SCH_EVIDENCE
from fenolite.backends.kicad.sch import read_schematic, rebuild_schematic
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-CHECK-COPYSET", "H-K-CHECK-CANARY-3"))
"""``KICAD-VERIFIED``: both hypotheses hold on 9.0.9 and 10.0.6; ``H-K-CHECK-CANARY-3`` succeeds
``H-K-CHECK-CANARY-2`` (the canary can be missing from a saturated report, c0051), which succeeded the
refuted neutrality of ``H-K-CHECK-CANARY`` (c0013 task 9.2)."""
RT2_EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-RT2-STABLE-2",))
"""``KICAD-VERIFIED``: ``H-K-RT2-STABLE-2`` holds on 9.0.9 and 10.0.6 (c0020 task 9.2); it succeeds
``H-K-RT2-STABLE``, which the corpus run refuted."""
RT2_REPEATS = 3
"""Further runs of each side when the first re-dump report differs from the original."""
NORMALISE_EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-FMT-RESAVE",))
"""``pcb upgrade --force`` of a board and of its re-dump give equal trees (10.0.x); combined when
normalised."""
PARITY_NOT_JUDGED = "Failed to fetch schematic netlist"
"""What ``pcb drc --schematic-parity`` prints when it writes its report without having compared the board
with a schematic (``docs/formats/kicad/erc.md``; observed on 9.0.9 and 10.0.6)."""
SCHEMATIC_SUFFIX = ".kicad_sch"
_CLOCK = re.compile(r"^\d{1,2}:\d{2}:\d{2}(\s?[AP]M)?:\s+")
"""The time of day that ``kicad-cli`` writes before some of its error lines."""


@dataclasses.dataclass(frozen=True)
class _Plan:
    """The canary decision before the run: the state and reason, and the staged texts when it applies."""

    state: CanaryState
    reason: str = ""
    board: bytes | None = None
    rules: bytes | None = None


def _first_line(text: str) -> str:
    """The first line of ``text`` that is not blank, without the time of day the tool may put before it:
    a message that is copied into the output of ``check`` must not change from run to run."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return _CLOCK.sub("", lines[0]) if lines else ""


@dataclasses.dataclass(frozen=True)
class SchematicExport:
    """KiCad's netlist of a project's schematic: ``netlist`` is ``None`` when no export was read, and
    ``message`` then says why (the first line of the tool's output, or of the reader's error)."""

    netlist: netlistmod.KicadNetlist | None
    outcome: Literal["exit", "timeout"] = "exit"
    returncode: int | None = 0
    message: str = ""


def schematic_name(project: ProjectSet) -> str:
    """The name of the root schematic of ``project``: the stem of its board with ``.kicad_sch``."""
    return f"{PurePosixPath(project.board).stem}.kicad_sch"


def with_sheets(schematic: Path, files: Mapping[str, Path]) -> dict[str, Path]:
    """``files`` (names relative to the folder of ``schematic``) with the root schematic and the sheet
    files it names inside that folder, for the names ``files`` does not hold."""
    found = dict(files)
    if schematic.name in found:
        return found
    found[schematic.name] = schematic
    try:
        sheets = sch.sheet_files(schematic).files
    except (FormatError, OSError, UnicodeDecodeError, ValueError):
        sheets = ()  # the root alone; KiCad decides what to do with it
    for rel in sheets:
        if (schematic.parent / rel).is_file():
            found.setdefault(rel, schematic.parent / rel)
    return found


def schematic_files(project: ProjectSet) -> dict[str, Path]:
    """The files of an export run: the copy set, which holds the root schematic of the board's stem and the
    sheet files its hierarchy reaches (``projectset.project_set``, change c0062). Empty without that
    schematic: ERC, the parity test and the netlist export all read the one set."""
    return dict(project.files) if schematic_name(project) in project.files else {}


def export_schematic_netlist(cli: KicadCli, project: ProjectSet) -> SchematicExport:
    """``sch export netlist --format kicadsexpr`` of the project's schematic on copies, read by
    ``netlist.read_netlist``. Nothing of the export's ``design`` and ``libraries`` sections is kept, and
    nothing is written under ``project.root``."""
    name = schematic_name(project)
    files = schematic_files(project)
    if name not in files:
        return SchematicExport(None, returncode=None, message=f"the project has no schematic {name}")
    return export_netlist_of(cli, name, files)


def export_netlist_of(cli: KicadCli, name: str, files: Mapping[str, Path]) -> SchematicExport:
    """The netlist of the schematic ``name``, one of ``files`` (relative name → source), which are all
    copied for the run."""
    others = {rel: path for rel, path in files.items() if rel != name}
    run = cli.export_netlist(files[name], files=others)
    if run.outcome == "timeout":
        return SchematicExport(None, "timeout", None, _first_line(run.stderr) or "kicad-cli timed out")
    data = run.outputs.get(NETLIST)
    if data is None:
        message = _first_line(run.stderr) or _first_line(run.stdout) or "kicad-cli wrote no netlist"
        return SchematicExport(None, "exit", run.returncode, message)
    try:
        found = netlistmod.read_netlist(data.decode("utf-8"), file=NETLIST)
    except (FormatError, UnicodeDecodeError) as exc:
        return SchematicExport(
            None, "exit", run.returncode, f"unreadable netlist export: {_first_line(str(exc))}"
        )
    return SchematicExport(found, "exit", run.returncode)


class KicadOracle:
    """DRC verdicts from a ``kicad-cli`` binary, always on copies (``Oracle`` protocol)."""

    name = "kicad"

    def __init__(self, cli: KicadCli, *, rt2_normalise: bool = True) -> None:
        self.cli = cli
        self.rt2_normalise = rt2_normalise

    def version(self) -> str:
        return self.cli.version()

    def major(self) -> int:
        return self.cli.major()

    def report_limits(self) -> DrcLimits:
        """Where the DRC report of this ``kicad-cli`` stops, per type (``LimitedOracle``;
        ``drc.REPORT_LIMITS``). ``ValueError`` for a major that no probe measured."""
        return drcmod.report_limits(self.major())

    def refill(self, project: ProjectSet) -> FillOutcome:
        """Refill a copy of the exact project set, without staging a DRC canary."""
        version = self.version()
        if self.major() < 10:
            return FillOutcome(None, version, supported=False, message="kicad-cli 10.0 is required")
        others = {name: path for name, path in project.files.items() if name != project.board}
        try:
            result = self.cli.refill(project.files[project.board], files=others)
        except KicadCliVersionError:
            return FillOutcome(None, version, supported=False, message="kicad-cli 10.0 is required")
        run = result.run
        if run.outcome == "exit" and run.returncode != 0:
            return FillOutcome(
                None,
                version,
                outcome=run.outcome,
                returncode=run.returncode,
                message=_first_line(run.stderr) or "refill failed",
            )
        if result.board is None:
            return FillOutcome(
                None, version, outcome=run.outcome, returncode=run.returncode, message="refill saved no board"
            )
        try:
            design = read_board(result.board.decode("utf-8"), file=project.board)
        except (FormatError, UnicodeDecodeError) as exc:
            return FillOutcome(
                None,
                version,
                outcome=run.outcome,
                returncode=run.returncode,
                message=f"unreadable saved board: {exc}",
            )
        repeat = self.cli.refill(project.files[project.board], files=others)
        if repeat.run.outcome == "exit" and repeat.run.returncode != 0:
            return FillOutcome(
                None,
                version,
                outcome=repeat.run.outcome,
                returncode=repeat.run.returncode,
                message=_first_line(repeat.run.stderr) or "repeat refill failed",
            )
        if repeat.board is None:
            return FillOutcome(
                None,
                version,
                outcome=repeat.run.outcome,
                returncode=repeat.run.returncode,
                message="repeat refill saved no board",
            )
        try:
            repeated = read_board(repeat.board.decode("utf-8"), file=project.board)
        except (FormatError, UnicodeDecodeError) as exc:
            return FillOutcome(None, version, message=f"unreadable repeat refill: {exc}")
        first_zones = {zone.id: zone for zone in design.board.zones} if design.board else {}
        second_zones = {zone.id: zone for zone in repeated.board.zones} if repeated.board else {}
        stable = first_zones.keys() == second_zones.keys() and all(
            fill_set(zone) == fill_set(second_zones[key]) and zone.filled == second_zones[key].filled
            for key, zone in first_zones.items()
        )
        return FillOutcome(
            zone_fills(design),
            version,
            outcome=run.outcome,
            returncode=run.returncode,
            message=_first_line(run.stderr),
            evidence=dataclasses.replace(FILL_EVIDENCE, oracle=f"kicad-cli {version}"),
            stable=stable,
        )

    def _plan(self, project: ProjectSet, major: int) -> _Plan:
        stem = PurePosixPath(project.board).stem
        if not (project.has_project and project.has_rules):
            return _Plan("not-applicable")
        if major not in canary.CANARY_SUPPORT:
            return _Plan("inconclusive", "placement-unproven")
        rule_text = canary.canary_rule_text(major)
        if rule_text is None:
            return _Plan("inconclusive", "selector-unproven")
        project_bytes = project.files[f"{stem}.kicad_pro"].read_bytes()
        if canary.clearance_ignored(project_bytes.decode("utf-8", "replace")):
            return _Plan("inconclusive", "clearance-ignored")
        try:
            rules = canary.append_rule(
                project.files[f"{stem}.kicad_dru"].read_bytes(), rule_text, major=major
            )
            board = canary.inject_board(project.files[project.board].read_bytes(), file=project.board)
        except canary.CanaryError as exc:
            return _Plan("inconclusive", exc.reason)
        except FormatError:
            return _Plan("inconclusive", "board-unparsed")
        return _Plan("fired", board=board, rules=rules)  # the state after the run decides fired or absent

    def _run(
        self, project: ProjectSet, staged: Path | None, plan: _Plan, parity: bool = False
    ) -> tuple[CliRun, DrcReport | None, str]:
        others = {name: path for name, path in project.files.items() if name != project.board}
        board = project.files[project.board]
        if staged is not None and plan.board is not None and plan.rules is not None:
            rules = f"{PurePosixPath(project.board).stem}.kicad_dru"
            board = staged / project.board
            board.write_bytes(plan.board)
            (staged / rules).write_bytes(plan.rules)
            others[rules] = staged / rules
        try:
            result = self.cli.drc(board, files=others, schematic_parity=parity)
        except FormatError as exc:  # the tool wrote a file that is no DRC report
            return CliRun("exit", None, "", "", {}), None, f"unreadable DRC report: {exc}"
        return result.run, result.report, ""

    def _runs(
        self, project: ProjectSet, staged: Path | None, plan: _Plan, major: int, parity: bool
    ) -> tuple[CliRun, DrcReport | None, str, CliRun, DrcReport | None]:
        """The counted run with its report and problem, and the run and report that carry the canary."""
        if plan.board is not None and major in canary.CANARY_TWO_RUN:
            run, report, problem = self._run(project, None, plan, parity)
            canary_run, verdict_report, _ = self._run(project, staged, plan, parity)
            return run, report, problem, canary_run, verdict_report
        run, report, problem = self._run(project, staged, plan, parity)
        return run, report, problem, run, report

    def drc(self, project: ProjectSet) -> DrcOutcome:
        """``pcb drc`` on the copy set, with the canary when it applies and with the parity test when the
        set holds the board's schematic; nothing is written under the root."""
        version, major = self.version(), self.major()
        plan = self._plan(project, major)
        applies = plan.board is not None
        parity = schematic_name(project) in project.files
        parity_note = ""
        staged: Path | None = None
        try:
            if applies:
                staged = Path(tempfile.mkdtemp(prefix="fenolite-check-"))
                if staged.resolve().is_relative_to(project.root.resolve()):
                    raise RuntimeError("the canary staging folder lies inside the project")
            run, report, problem, canary_run, verdict_report = self._runs(
                project, staged, plan, major, parity
            )
            judged = parity and report is not None and PARITY_NOT_JUDGED not in run.stderr
            if parity and report is None and run.outcome == "exit":
                # The tool wrote no report with the flag: a schematic it cannot load stops the whole run
                # (probe drc-parity-unloadable). The copper verdict must not depend on the schematic, so
                # DRC runs again without the flag, and parity is reported as not judged.
                parity_note = problem or _first_line(run.stderr) or "no DRC report with --schematic-parity"
                run, report, problem, canary_run, verdict_report = self._runs(
                    project, staged, plan, major, False
                )
            elif parity and not judged:
                parity_note = _first_line(run.stderr)
            fired = verdict_report is not None and canary.canary_fired(verdict_report)
            # Without the pair, a saturated report proves nothing: KiCad stops reporting clearance
            # violations near the limit and may have left the canary's out (H-K-DRC-LIMIT).
            saturated = verdict_report is not None and canary.clearance_saturated(verdict_report)
        finally:
            if staged is not None:
                shutil.rmtree(staged, ignore_errors=True)
        state, reason = plan.state, plan.reason
        if applies:
            verdict_ok = report is not None and (canary_run.outcome == "exit")
            if not verdict_ok:
                state, reason = "inconclusive", "no-report"
            elif fired:
                state, reason = "fired", ""
            elif saturated:
                state, reason = "inconclusive", "clearance-limit"
            else:
                state, reason = "absent", ""
        removed = 0
        if report is not None:
            report, removed = canary.strip_canary(report)
        evidence = Evidence()
        if report is not None:
            combined = Evidence.combine(drcmod.EVIDENCE, EVIDENCE)
            evidence = dataclasses.replace(combined, oracle=f"kicad-cli {version}")
        return DrcOutcome(
            report=report,
            tool_version=version,
            canary=state,
            canary_reason=reason,
            canary_removed=removed,
            tool_writes=tuple(sorted(name for name in run.outputs if name != DRC_REPORT)),
            outcome=run.outcome,
            returncode=run.returncode,
            message=(parity_note if report is not None else "") or problem or _first_line(run.stderr),
            evidence=evidence,
            parity_judged=judged and report is not None,
        )

    # -- ERC (c0062)

    def _sheets(self, project: ProjectSet) -> dict[str, Node]:
        """The parsed sheet files of the copy set; a file that does not parse is left out."""
        trees: dict[str, Node] = {}
        for name, path in project.files.items():
            if not name.endswith(SCHEMATIC_SUFFIX):
                continue
            try:
                trees[name] = parse(Path(path).read_text(encoding="utf-8"), file=name)
            except (FormatError, OSError, UnicodeDecodeError):
                continue
        return trees

    def _erc(self, schematic: Path, others: dict[str, Path]) -> tuple[CliRun, ErcReport | None, str]:
        try:
            result = self.cli.erc(schematic, files=others)
        except FormatError as exc:  # the tool wrote a file that is no ERC report
            return CliRun("exit", None, "", "", {}), None, f"unreadable ERC report: {_first_line(str(exc))}"
        return result.run, result.report, ""

    def erc(self, project: ProjectSet) -> ErcOutcome:
        """``sch erc`` on the copy set, its items located from the sheet files; nothing is written under
        the root and no canary is staged."""
        version = self.version()
        name = schematic_name(project)
        if name not in project.files:
            return ErcOutcome(None, version, message="the project has no schematic of the board's stem")
        others = {key: path for key, path in project.files.items() if key != name}
        run, report, problem = self._erc(project.files[name], others)
        writes = tuple(sorted(key for key in run.outputs if key != ERC_REPORT))
        if report is None:
            message = problem or _first_line(run.stderr) or _first_line(run.stdout) or "no ERC report"
            return ErcOutcome(
                None, version, writes, outcome=run.outcome, returncode=run.returncode, message=message
            )
        locations = ercmod.item_locations(self._sheets(project), PurePosixPath(project.board).stem)
        combined = Evidence.combine(ercmod.EVIDENCE, EVIDENCE)
        return ErcOutcome(
            ercmod.located(report, locations),
            version,
            writes,
            outcome=run.outcome,
            returncode=run.returncode,
            message=_first_line(run.stderr),
            evidence=dataclasses.replace(combined, oracle=f"kicad-cli {version}"),
        )

    def rt2_erc(self, project: ProjectSet) -> ErcRt2Outcome:
        """ERC twice on the project as it is and once on a copy in which every sheet file that Fenolite
        reads is its re-dump; a sheet it cannot read stays as it is and is counted in ``kept``."""
        version = self.version()
        name = schematic_name(project)

        def failed(
            before: tuple[ErcReport, ...],
            message: str,
            run: CliRun | None = None,
            counts: tuple[int, int] = (0, 0),
        ) -> ErcRt2Outcome:
            timeout = run is not None and run.outcome == "timeout"
            return ErcRt2Outcome(
                before, None, version, outcome="timeout" if timeout else "exit",
                returncode=None if timeout else (run.returncode if run is not None else 0), message=message,
                redumped=counts[0], kept=counts[1],
            )  # fmt: skip

        if name not in project.files:
            return failed((), "the project has no schematic of the board's stem")
        others = {key: path for key, path in project.files.items() if key != name}
        before: list[ErcReport] = []
        for _ in range(2):
            run, report, problem = self._erc(project.files[name], others)
            if report is None:
                return failed(tuple(before), problem or _first_line(run.stderr) or "no ERC report", run)
            before.append(report)
        staged = Path(tempfile.mkdtemp(prefix="fenolite-rt2-erc-"))
        try:
            if staged.resolve().is_relative_to(project.root.resolve()):
                raise RuntimeError("the RT2 staging folder lies inside the project")
            sides = dict(project.files)
            redumped = kept = 0
            for key, path in project.files.items():
                if not key.endswith(SCHEMATIC_SUFFIX):
                    continue
                try:
                    sheet = read_schematic(Path(path).read_text(encoding="utf-8"), file=key)
                    text = dumps(rebuild_schematic(sheet))
                except (FormatError, ValueError, OSError, UnicodeDecodeError):
                    kept += 1
                    continue
                target = staged / key
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8", newline="\n")
                sides[key] = target
                redumped += 1
            run, after, problem = self._erc(sides[name], {k: v for k, v in sides.items() if k != name})
        finally:
            shutil.rmtree(staged, ignore_errors=True)
        if after is None:
            message = problem or _first_line(run.stderr) or "no ERC report"
            return failed(tuple(before), message, run, (redumped, kept))
        combined = Evidence.combine(ercmod.EVIDENCE, SCH_EVIDENCE, EVIDENCE)
        return ErcRt2Outcome(
            tuple(before),
            after,
            version,
            evidence=dataclasses.replace(combined, oracle=f"kicad-cli {version}"),
            redumped=redumped,
            kept=kept,
        )

    # -- review views (c0024)

    def plot(self, project: ProjectSet) -> PlotOutcome:
        """The four review views of the copy set (``Plotter`` protocol): name, size and hash of each view
        produced, and the names of those that were not."""
        version = self.version()
        board = project.files[project.board]
        others = {name: path for name, path in project.files.items() if name != project.board}
        views: list[PlotView] = []
        failed: list[str] = []
        messages: list[str] = []
        for name in sorted(plotmod.VIEWS):
            data, message = plotmod.plot_view(self.cli, name, board, others)
            if data is None:
                failed.append(name)
                messages.append(f"{name}: {message}")
                continue
            views.append(PlotView(name, len(data), plotmod.view_digest(name, data)))
        evidence = (
            dataclasses.replace(plotmod.EVIDENCE, oracle=f"kicad-cli {version}") if views else Evidence()
        )
        return PlotOutcome(tuple(views), version, tuple(failed), "; ".join(messages), evidence)

    # -- netlist (c0020 Decision 9)

    def netlist(self, project: ProjectSet, *, board: Design) -> NetlistOutcome:
        """``pcb export ipcd356`` on the copy set, its records paired with the pads of ``board``."""
        version = self.version()
        others = {name: path for name, path in project.files.items() if name != project.board}
        try:
            text = self.cli.export_ipcd356(project.files[project.board], files=others)
        except KicadCliError as exc:
            run = exc.run
            return NetlistOutcome(
                None, version, outcome=run.outcome, returncode=run.returncode,
                message=_first_line(run.stderr) or _first_line(str(exc)),
            )  # fmt: skip
        try:
            export = read_ipcd356(text)
        except FormatError as exc:
            return NetlistOutcome(
                None, version, message=f"unreadable IPC-D-356 export: {_first_line(str(exc))}"
            )
        combined = Evidence.combine(padnets.EVIDENCE, EVIDENCE)
        return NetlistOutcome(
            padnets.export_netlist(board, export),
            version,
            evidence=dataclasses.replace(combined, oracle=f"kicad-cli {version}"),
        )

    # -- the schematic's netlist (c0063 Decision 6)

    def schematic_netlist(self, project: ProjectSet) -> NetlistOutcome:
        """KiCad's netlist of the project's schematic as assignments ``REF-PIN`` → net name (source
        ``schematic``; ``SchematicNetlistOracle``). A pin the tool does not list is not an element."""
        version = self.version()
        export = export_schematic_netlist(self.cli, project)
        if export.netlist is None:
            return NetlistOutcome(
                None, version, outcome=export.outcome, returncode=export.returncode, message=export.message
            )
        assignments = tuple(
            PadAssignment(node.element, net.name) for net in export.netlist.nets for node in net.nodes
        )
        combined = Evidence.combine(netlistmod.EVIDENCE, EVIDENCE)
        return NetlistOutcome(
            PadNetList("schematic", assignments),
            version,
            returncode=export.returncode,
            evidence=dataclasses.replace(combined, oracle=f"kicad-cli {version}"),
        )

    # -- RT2 (c0020 Decision 10)

    def rt2(self, project: ProjectSet) -> Rt2Outcome:
        """DRC twice on the board and once on Fenolite's re-dump, re-saved first on 10.0; no canary."""
        version, major = self.version(), self.major()
        normalise = major >= 10 and self.rt2_normalise
        original = project.files[project.board]
        others = {name: path for name, path in project.files.items() if name != project.board}

        def failed(before: tuple[DrcReport, ...], message: str, run: CliRun | None = None) -> Rt2Outcome:
            timeout = run is not None and run.outcome == "timeout"
            return Rt2Outcome(
                before, None, normalise, version, outcome="timeout" if timeout else "exit",
                returncode=None if timeout else (run.returncode if run is not None else 0), message=message,
            )  # fmt: skip

        try:
            design = read_board(original.read_text(encoding="utf-8"), file=project.board)
            redump = dumps(rebuild_board(design))
        except (FormatError, ValueError, UnicodeDecodeError) as exc:
            return failed((), f"board not read: {_first_line(str(exc))}")
        staged = Path(tempfile.mkdtemp(prefix="fenolite-rt2-"))
        try:
            if staged.resolve().is_relative_to(project.root.resolve()):
                raise RuntimeError("the RT2 staging folder lies inside the project")
            sides = {
                "original": staged / "original" / project.board,
                "redump": staged / "redump" / project.board,
            }
            for path in sides.values():
                path.parent.mkdir(parents=True)
            sides["original"].write_bytes(original.read_bytes())
            sides["redump"].write_text(redump, encoding="utf-8", newline="\n")
            if normalise:
                for path in sides.values():
                    try:
                        path.write_bytes(self.cli.upgrade_board(path, files=others))
                    except KicadCliError as exc:
                        return failed((), f"pcb upgrade failed: {_first_line(str(exc))}", exc.run)
            before: list[DrcReport] = []
            for _ in range(2):
                run, report, problem = self._plain(sides["original"], others)
                if report is None:
                    return failed(tuple(before), problem or _first_line(run.stderr) or "no DRC report", run)
                before.append(report)
            run, after, problem = self._plain(sides["redump"], others)
            if after is None:
                return failed(tuple(before), problem or _first_line(run.stderr) or "no DRC report", run)
            repeats: list[DrcReport] = []
            if _entries(after) != _entries(before[0]):
                # The first re-dump report differs. On large boards KiCad does not repeat its own report,
                # so each side runs RT2_REPEATS more times: a difference stands only where both repeat.
                for side, reports in (("original", before), ("redump", repeats)):
                    for _ in range(RT2_REPEATS):
                        run, report, problem = self._plain(sides[side], others)
                        if report is None:
                            message = problem or _first_line(run.stderr) or "no DRC report"
                            return failed(tuple(before), message, run)
                        reports.append(report)
        finally:
            shutil.rmtree(staged, ignore_errors=True)
        parts = [drcmod.EVIDENCE, RT2_EVIDENCE, EVIDENCE, *([NORMALISE_EVIDENCE] if normalise else [])]
        evidence = dataclasses.replace(Evidence.combine(*parts), oracle=f"kicad-cli {version}")
        return Rt2Outcome(tuple(before), after, normalise, version, evidence=evidence, repeats=tuple(repeats))

    def _plain(self, board: Path, others: dict[str, Path]) -> tuple[CliRun, DrcReport | None, str]:
        try:
            result = self.cli.drc(board, files=others)
        except FormatError as exc:
            return CliRun("exit", None, "", "", {}), None, f"unreadable DRC report: {exc}"
        return result.run, result.report, ""


def _entries(report: DrcReport) -> object:
    """``report.entries()`` with the run's temporary folder left out of the descriptions."""
    folder = str(PurePosixPath(report.source).parent)
    if folder in ("", ".", "/"):
        return report.entries()
    return tuple(
        (group, kind, severity, excluded, tuple((d.replace(folder, "<tmp>"), x, y) for d, x, y in items))
        for group, kind, severity, excluded, items in report.entries()
    )


def _protocols(  # pyright: ignore[reportUnusedFunction]
    oracle: KicadOracle,
) -> tuple[Oracle, NetlistOracle, RoundTripOracle, ErcOracle]:
    """``KicadOracle`` as each of the four oracle protocols; ``pyright`` checks the assignment."""
    return oracle, oracle, oracle, oracle


def _limited_protocol(oracle: KicadOracle) -> LimitedOracle:  # pyright: ignore[reportUnusedFunction]
    """``KicadOracle`` as the oracle that states its report limits; ``pyright`` checks the assignment."""
    return oracle


def _schematic_protocol(oracle: KicadOracle) -> SchematicNetlistOracle:  # pyright: ignore[reportUnusedFunction]
    """``KicadOracle`` as the schematic netlist oracle; ``pyright`` checks the assignment."""
    return oracle


__all__ = [
    "EVIDENCE",
    "NORMALISE_EVIDENCE",
    "PARITY_NOT_JUDGED",
    "RT2_EVIDENCE",
    "KicadOracle",
    "SchematicExport",
    "export_netlist_of",
    "export_schematic_netlist",
    "schematic_files",
    "schematic_name",
    "with_sheets",
]
