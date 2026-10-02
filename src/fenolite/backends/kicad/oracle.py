# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``kicad-cli`` as the DRC oracle of ``fenolite check`` (capability kicad-oracle, "Check canary injection";
backend-protocol, "Oracle protocol").

``KicadOracle.drc`` runs ``pcb drc`` on the project's copy set through the package runner, with the
canary staged into private copies of the board and rules file when it applies, so that the report also
says whether the custom rules were loaded. The decision order, the verdict and the stripping follow c0013
Decision 6; facts come from here, and the issues and severities are ``checks``'s policy.
"""

from __future__ import annotations

import dataclasses
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from fenolite.backends.base import CanaryState, DrcOutcome, DrcReport, ProjectSet
from fenolite.backends.kicad import canary
from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad.cli import DRC_REPORT, CliRun, KicadCli
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-CHECK-COPYSET", "H-K-CHECK-CANARY-2"))
"""``KICAD-VERIFIED``: both hypotheses hold on 9.0.9 and 10.0.6; ``H-K-CHECK-CANARY-2`` succeeds the refuted
neutrality of ``H-K-CHECK-CANARY`` (c0013 task 9.2)."""


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

    def __init__(self, cli: KicadCli) -> None:
        self.cli = cli

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


__all__ = ["EVIDENCE", "KicadOracle"]
