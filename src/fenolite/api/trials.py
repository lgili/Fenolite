# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Trial edits gated by KiCad's DRC (capability kicad-oracle, "Trial edits gated by DRC"; change c0209).

``trial(board, edit)`` reads a KiCad board, applies ``edit`` to its model, writes the unedited and the
edited model with the same writer for the board's major, and runs ``kicad-cli pcb drc`` on a copy of each
with the board's project files, the zones refilled first on KiCad 10. A finding of the edited copy that the
unedited copy does not hold (same type, same set of item uuids, counted) is new, and is mapped to the ids
of the edit's items that it names. With ``gate=True`` the items that new findings name are dropped (an
added item removed, a changed or removed item put back as it was) and the trial runs again, until no new
finding names an item of the edit or none is left to drop; ``TrialResult.board_text`` is then the board to
write. ``together`` names groups of the edit's ids that the gate drops as one (change c0225: a tidy edit's
removed, replaced and added items). Nothing is written: the caller decides.

Two runs of one unchanged board can differ in entries of ``clearance``, ``hole_clearance`` and
``unconnected_items`` (``H-K-DRC-REPEAT``), so a new finding of those types that names no item of the edit
can be noise; one that names an item of the edit is not.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections import Counter
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.api.sides import NO_TOOL_HINT, ToolMissingError
from fenolite.backends.base import DrcReport, DrcViolation, ProjectSet
from fenolite.backends.kicad.cli import KicadCli, KicadCliError, cli_for, find_kicad_cli
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, source_info, write_board
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

Edit = Callable[[Design], tuple[Design, Collection[str]]]
"""An edit: the board model in, the edited model and the ids of the items it added, removed or changed
out."""
GROUPS = ("footprints", "tracks", "arcs", "vias", "zones", "keepouts", "texts", "graphics")
"""The board's entity groups whose items an edit's ids may name."""
NOT_REFILLED = "trial.not-refilled"
ISSUE_CODES = {NOT_REFILLED: ("warning",)}
"""The issue codes of ``trial`` (``fenolite explain``)."""
DEFAULT_TIMEOUT = 300.0


@dataclass(frozen=True, slots=True)
class TrialFinding:
    """One finding of the edited copy that the unedited copy does not hold: the tool's ``type``,
    ``severity`` and ``description``, the item ``uuids`` in report order, and ``items``, the ids of the
    edit's items it names (none for a finding the edit caused elsewhere)."""

    type: str
    severity: str
    description: str
    uuids: tuple[str, ...]
    items: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {"type": self.type, "severity": self.severity, "description": self.description,
                "uuids": list(self.uuids), "items": list(self.items)}  # fmt: skip


@dataclass(frozen=True, slots=True)
class DroppedItem:
    """An item of the edit the gate dropped, with the new findings that named it."""

    id: str
    findings: tuple[TrialFinding, ...]


@dataclass(frozen=True, slots=True)
class TrialResult:
    """What ``trial`` found. ``findings`` are the new findings of the last run (after the gate's drops);
    ``board_text`` is the edited board as kept, written for the board's major; ``kept`` and ``dropped``
    split the edit's ids; ``baseline`` and ``edited`` count the entries of the unedited copy and of the
    last edited run; ``refilled`` says whether KiCad refilled the zones before each run."""

    board_text: str
    findings: tuple[TrialFinding, ...]
    kept: tuple[str, ...]
    dropped: tuple[DroppedItem, ...]
    baseline: int
    edited: int
    runs: int
    refilled: bool
    tool_version: str
    evidence: Evidence
    issues: tuple[Issue, ...] = ()

    @property
    def clean(self) -> bool:
        """Whether no new finding remains."""
        return not self.findings


def _entries(report: DrcReport) -> tuple[DrcViolation, ...]:
    return (*report.violations, *report.unconnected_items, *report.schematic_parity)


def _key(entry: DrcViolation) -> tuple[str, tuple[str, ...]]:
    return entry.type, tuple(sorted(item.uuid.lower() for item in entry.items))


def new_entries(baseline: DrcReport, edited: DrcReport) -> tuple[DrcViolation, ...]:
    """The entries of ``edited`` that ``baseline`` does not hold, by type and item uuid set, counted: two
    equal entries in ``edited`` and one in ``baseline`` give one new entry. Report order."""
    left = Counter(_key(entry) for entry in _entries(baseline))
    found: list[DrcViolation] = []
    for entry in _entries(edited):
        key = _key(entry)
        if left[key] > 0:
            left[key] -= 1
        else:
            found.append(entry)
    return tuple(found)


def owners(design: Design, ids: Collection[str]) -> dict[str, str]:
    """``KiCad uuid → edit id`` for the items of ``ids`` in ``design``; a footprint's pads map to the
    footprint when the footprint is one of ``ids``."""
    board = design.board
    found: dict[str, str] = {}
    if board is None:
        return found
    for group in GROUPS:
        for entity in getattr(board, group):
            if entity.id in ids:
                found[kicad_uuid(entity).lower()] = entity.id
    for footprint in board.footprints:
        for pad in footprint.pads:
            owner = pad.id if pad.id in ids else footprint.id if footprint.id in ids else None
            if owner is not None:
                found[kicad_uuid(pad).lower()] = owner
    return found


def findings(entries: Iterable[DrcViolation], owned: dict[str, str]) -> tuple[TrialFinding, ...]:
    out: list[TrialFinding] = []
    for entry in entries:
        uuids = tuple(item.uuid.lower() for item in entry.items)
        items = tuple(dict.fromkeys(owned[uuid] for uuid in uuids if uuid in owned))
        out.append(TrialFinding(entry.type, entry.severity, entry.description, uuids, items))
    return tuple(out)


def revert(edited: Design, baseline: Design, ids: Collection[str]) -> Design:
    """``edited`` with each item of ``ids`` as ``baseline`` has it: removed when ``baseline`` has none,
    put back in its place otherwise."""
    board, before = edited.board, baseline.board
    if board is None or before is None:
        return edited
    changes: dict[str, tuple[Any, ...]] = {}
    for group in GROUPS:
        old = {entity.id: entity for entity in getattr(before, group)}
        now: list[Any] = []
        present = set[str]()
        for entity in getattr(board, group):
            present.add(entity.id)
            if entity.id not in ids:
                now.append(entity)
            elif entity.id in old:
                now.append(old[entity.id])
        now += [entity for entity in getattr(before, group) if entity.id in ids and entity.id not in present]
        changes[group] = tuple(now)
    return dataclasses.replace(edited, board=dataclasses.replace(board, **changes))


def _units(ids: Collection[str], together: Iterable[Collection[str]]) -> dict[str, tuple[str, ...]]:
    """``id → the ids dropped with it``: the ids of ``ids`` in each group of ``together`` that holds it, in
    the order of ``ids``; an id in two groups takes both."""
    units: dict[str, tuple[str, ...]] = {}
    for group in together:
        held = set(group)
        members = tuple(item for item in ids if item in held)
        for item in members:
            units[item] = tuple(dict.fromkeys((*units.get(item, (item,)), *members)))
    return units


def _tool(kicad_cli: str | None, timeout: float) -> KicadCli:
    path = find_kicad_cli(kicad_cli)
    if path is None:
        raise ToolMissingError("trial needs kicad-cli to run DRC", hint=NO_TOOL_HINT)
    return cli_for(path, timeout=timeout)


def _drc(cli: KicadCli, project: ProjectSet, text: str, *, refill: bool) -> DrcReport:
    others = {name: path for name, path in project.files.items() if name != project.board}
    with tempfile.TemporaryDirectory(prefix="fenolite-trial-") as tmp:
        board = Path(tmp) / Path(project.board).name
        board.write_text(text, encoding="utf-8")
        run = cli.drc(board, files=others, refill_zones=refill)
    if run.report is None:
        raise KicadCliError(f"kicad-cli wrote no DRC report of the trial copy of {project.board}", run.run)
    return run.report


def trial(
    board: str | Path,
    edit: Edit,
    *,
    kicad_cli: str | None = None,
    refill: bool = True,
    gate: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
    together: Iterable[Collection[str]] = (),
) -> TrialResult:
    """Apply ``edit`` to a copy of the KiCad board ``board`` (a ``.kicad_pcb``, ``.kicad_pro`` or project
    folder) and judge it with ``kicad-cli`` DRC against the unedited copy; see the module. ``refill``
    refills the zones of both copies on KiCad 10 (``trial.not-refilled`` on 9 for a board with zones).
    ``together``: groups of the edit's ids that the gate drops as one, each with the finding that named one
    of them. ``ToolMissingError`` without a ``kicad-cli``."""
    path = resolve_board(Path(board))
    project = project_set(path)
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    info = source_info(design)
    cli = _tool(kicad_cli, timeout)
    major = info.major if info is not None and info.major is not None else cli.major()
    issues: list[Issue] = []
    zones = design.board is not None and bool(design.board.zones)
    refilled = refill and zones and cli.major() >= 10
    if refill and zones and not refilled:
        issues.append(Issue(NOT_REFILLED, "warning", f"kicad-cli {cli.version()} cannot refill zones: both "
                            "copies were checked with their stored fills", where=project.board))  # fmt: skip
    edited, changed = edit(design)
    ids = tuple(dict.fromkeys(changed))
    units = _units(ids, together)
    baseline = _drc(cli, project, write_board(design, target=major).text, refill=refilled)
    dropped: dict[str, list[TrialFinding]] = {}
    runs = 1
    while True:
        text = write_board(edited, target=major).text
        report = _drc(cli, project, text, refill=refilled)
        runs += 1
        kept = tuple(item for item in ids if item not in dropped)
        new = findings(new_entries(baseline, report), owners(edited, kept))
        named = [finding for finding in new if finding.items]
        if not gate or not named:
            break
        for finding in named:
            for item in finding.items:
                for each in units.get(item, (item,)):
                    found = dropped.setdefault(each, [])
                    if finding not in found:
                        found.append(finding)
        edited = revert(edited, design, dropped)
    evidence = Evidence(Level.KICAD_VERIFIED, oracle=f"kicad-cli {cli.version()}",
                        hypotheses=("H-K-DRC-TRIAL", "H-K-DRC-REPEAT"))  # fmt: skip
    return TrialResult(
        board_text=text,
        findings=new,
        kept=tuple(item for item in ids if item not in dropped),
        dropped=tuple(DroppedItem(item, tuple(found)) for item, found in dropped.items()),
        baseline=len(_entries(baseline)),
        edited=len(_entries(report)),
        runs=runs,
        refilled=refilled,
        tool_version=cli.version(),
        evidence=evidence,
        issues=tuple(issues),
    )


__all__ = [
    "DroppedItem",
    "Edit",
    "ISSUE_CODES",
    "TrialFinding",
    "TrialResult",
    "new_entries",
    "owners",
    "revert",
    "trial",
]
