# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``kicad-cli`` as the oracle of ``fenolite check`` (capability kicad-oracle, "Check canary injection",
"Netlist oracle from IPC-D-356" and "RT2 oracle"; backend-protocol, "Oracle protocol" and "Netlist and
round-trip oracles").

``KicadOracle.drc`` runs ``pcb drc`` on the project's copy set through the package runner, with the
canary staged into private copies of the board and rules file when it applies, so that the report also
says whether the custom rules were loaded. The decision order, the verdict and the stripping follow c0013
Decision 6; facts come from here, and the issues and severities are ``checks``'s policy.

``netlist`` exports IPC-D-356 and pairs its records with the board's pads (``padnets``); ``rt2`` runs DRC
twice on the board and once on Fenolite's re-dump of it, both re-saved by ``pcb upgrade`` on 10.0 (c0020
Decisions 9 and 10).
"""

from __future__ import annotations

import dataclasses
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from fenolite.backends.base import (
    CanaryState,
    DrcOutcome,
    DrcReport,
    NetlistOracle,
    NetlistOutcome,
    Oracle,
    PlotOutcome,
    PlotView,
    ProjectSet,
    RoundTripOracle,
    Rt2Outcome,
)
from fenolite.backends.kicad import canary, padnets
from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad import plot as plotmod
from fenolite.backends.kicad.cli import DRC_REPORT, CliRun, KicadCli, KicadCliError
from fenolite.backends.kicad.ipcd356 import read_ipcd356
from fenolite.backends.kicad.pcb import read_board, rebuild_board
from fenolite.backends.kicad.sexpr import dumps
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-CHECK-COPYSET", "H-K-CHECK-CANARY-2"))
"""``KICAD-VERIFIED``: both hypotheses hold on 9.0.9 and 10.0.6; ``H-K-CHECK-CANARY-2`` succeeds the refuted
neutrality of ``H-K-CHECK-CANARY`` (c0013 task 9.2)."""
RT2_EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-RT2-STABLE-2",))
"""``KICAD-VERIFIED``: ``H-K-RT2-STABLE-2`` holds on 9.0.9 and 10.0.6 (c0020 task 9.2); it succeeds
``H-K-RT2-STABLE``, which the corpus run refuted."""
RT2_REPEATS = 3
"""Further runs of each side when the first re-dump report differs from the original."""
NORMALISE_EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-FMT-RESAVE",))
"""``pcb upgrade --force`` of a board and of its re-dump give equal trees (10.0.x); combined when
normalised."""


@dataclasses.dataclass(frozen=True)
class _Plan:
    """The canary decision before the run: the state and reason, and the staged texts when it applies."""

    state: CanaryState
    reason: str = ""
    board: bytes | None = None
    rules: bytes | None = None


def _first_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else ""


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
        self, project: ProjectSet, staged: Path | None, plan: _Plan
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
            result = self.cli.drc(board, files=others)
        except FormatError as exc:  # the tool wrote a file that is no DRC report
            return CliRun("exit", None, "", "", {}), None, f"unreadable DRC report: {exc}"
        return result.run, result.report, ""

    def drc(self, project: ProjectSet) -> DrcOutcome:
        """``pcb drc`` on the copy set, with the canary when it applies; nothing is written under the root."""
        version, major = self.version(), self.major()
        plan = self._plan(project, major)
        applies = plan.board is not None
        staged: Path | None = None
        try:
            if applies:
                staged = Path(tempfile.mkdtemp(prefix="fenolite-check-"))
                if staged.resolve().is_relative_to(project.root.resolve()):
                    raise RuntimeError("the canary staging folder lies inside the project")
            if applies and major in canary.CANARY_TWO_RUN:
                plain_run, report, problem = self._run(project, None, plan)
                canary_run, verdict_report, _ = self._run(project, staged, plan)
                fired = verdict_report is not None and canary.canary_fired(verdict_report)
                run = plain_run
            else:
                run, report, problem = self._run(project, staged, plan)
                fired = report is not None and canary.canary_fired(report)
                canary_run = run
        finally:
            if staged is not None:
                shutil.rmtree(staged, ignore_errors=True)
        state, reason = plan.state, plan.reason
        if applies:
            verdict_ok = report is not None and (canary_run.outcome == "exit")
            state, reason = (
                ("fired" if fired else "absent", "") if verdict_ok else ("inconclusive", "no-report")
            )
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
            message=problem or _first_line(run.stderr),
            evidence=evidence,
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
            sides["redump"].write_text(redump, encoding="utf-8")
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


def _protocols(oracle: KicadOracle) -> tuple[Oracle, NetlistOracle, RoundTripOracle]:  # pyright: ignore[reportUnusedFunction]
    """``KicadOracle`` as each of the three oracle protocols; ``pyright`` checks the assignment."""
    return oracle, oracle, oracle


__all__ = ["EVIDENCE", "NORMALISE_EVIDENCE", "RT2_EVIDENCE", "KicadOracle"]
