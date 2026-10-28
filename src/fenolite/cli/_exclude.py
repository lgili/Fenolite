# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check BOARD --exclude CODE:ITEM_A:ITEM_B --reason TEXT``: one KiCad DRC exclusion written into
the board's project file under the mutation protocol (change c0209; ``docs/cli-contract.md``, "check",
"Writing a DRC exclusion").

The finding is looked up in a ``pcb drc`` run on a copy: ``CODE`` is the tool's own type
(``unconnected_items``) or its Fenolite code (``kicad.drc.unconnected-items``), and each ``ITEM`` a KiCad
uuid or a name as the finding's ``where`` prints it (``R1-1``), in either order; ``ITEM_B`` is left out
for an entry of one item. ``backends.kicad.exclusions`` finds the marker position the key needs and
confirms the written key on a copy, so only a key that ``pcb drc`` applies is planned. Nothing else of
the check runs: an exclusion run plans one write, and its own findings decide its exit code.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import os
from pathlib import Path
from typing import Any

from fenolite.backends.base import NIL_UUID, DrcReport, DrcViolation
from fenolite.backends.kicad import exclusions
from fenolite.backends.kicad.cli import KicadCliError
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.checks.codes import issue
from fenolite.checks.drc_json import finding_entries, type_code
from fenolite.cli._kicadtool import preflight
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.model.design import Design

ORACLE = "kicad"
UNMATCHED = "check.exclusion-unmatched"
AMBIGUOUS = "check.exclusion-ambiguous"
UNLOCATED = "check.exclusion-unlocated"
PRESENT = "check.exclusion-present"


@dataclasses.dataclass(frozen=True, slots=True)
class ExcludeSpec:
    """The parts of ``--exclude``: the type or code, and one or two item names."""

    kind: str
    items: tuple[str, ...]

    @property
    def text(self) -> str:
        return ":".join((self.kind, *self.items))


def parse_exclude(text: str) -> ExcludeSpec:
    """``CODE:ITEM_A[:ITEM_B]``; ``FEN-2001`` for another shape."""
    parts = [part.strip() for part in text.split(":")]
    if len(parts) not in (2, 3) or not all(parts):
        raise CliError(
            "FEN-2001",
            f"--exclude {text!r} is not CODE:ITEM_A:ITEM_B",
            hint="for example --exclude kicad.drc.unconnected-items:R1-1:R2-1 (ITEM_B left out for an entry "
            "of one item)",
            where="--exclude",
        )
    return ExcludeSpec(parts[0], tuple(parts[1:]))


def _kind_matches(spec: str, entry: DrcViolation) -> bool:
    return spec == entry.type or spec == type_code(ORACLE, entry.type)


def _item_matches(spec: str, uuid: str, name: str) -> bool:
    return spec.lower() == uuid.lower() or spec == name


def matches(spec: ExcludeSpec, entry: DrcViolation, names: tuple[str, ...]) -> bool:
    """Whether ``entry`` is the finding ``spec`` names: its type or code, and its items in either order."""
    if not _kind_matches(spec.kind, entry):
        return False
    pairs = [
        (item.uuid, names[index] if index < len(names) else "") for index, item in enumerate(entry.items)
    ]
    if len(spec.items) != len(pairs):
        return False
    if len(pairs) == 1:
        return _item_matches(spec.items[0], *pairs[0])
    a, b = spec.items
    return (_item_matches(a, *pairs[0]) and _item_matches(b, *pairs[1])) or (
        _item_matches(a, *pairs[1]) and _item_matches(b, *pairs[0])
    )


def _design(board: Path) -> tuple[Design | None, list[Issue]]:
    found: list[Issue] = []
    try:
        return read_board(board.read_text(encoding="utf-8"), file=board.name, issues=found), found
    except FormatError:
        return None, found


def _report(run_report: DrcReport | None, run: Any) -> DrcReport:
    if run_report is None:
        raise KicadCliError("kicad-cli wrote no DRC report", run)
    return run_report


def run_exclude(args: argparse.Namespace, ctx: Context, board: Path) -> Result:
    """Plan the exclusion ``args.exclude`` with ``args.reason`` in the project of ``board``."""
    spec = parse_exclude(args.exclude)
    reason = (args.reason or "").strip()
    if not reason:
        raise CliError("FEN-2001", "--exclude needs --reason TEXT, the comment stored with the exclusion",
                       where="--reason")  # fmt: skip
    project = project_set(board)
    cli = preflight(args.kicad_cli, args.timeout, board)
    version = cli.version()
    design, read_issues = _design(board)
    text = exclusions.project_text(project)
    first = exclusions.run_with_project(cli, project, None)
    report = _report(first.report, first.run)
    found = [
        (entry, names)
        for _, names, entry in finding_entries(report, oracle=ORACLE, design=design)
        if matches(spec, entry, names)
    ]
    data = board.read_bytes()
    target = os.path.relpath(board.with_suffix(".kicad_pro"), ctx.cwd)
    base: dict[str, Any] = {"project": Path(target).as_posix(), "tool_version": version, "exclusion": None}
    given = InputRef(board.name, hashlib.sha256(data).hexdigest(), "kicad_pcb", None)
    depends = depends_on(ctx.cwd, *project.files.values())
    evidence = dataclasses.replace(exclusions.EVIDENCE, oracle=f"kicad-cli {version}")
    if len(found) != 1:
        code, why = (
            (UNMATCHED, "no finding of the current DRC report")
            if not found
            else (AMBIGUOUS, f"{len(found)} findings of the current DRC report")
        )
        hint = (
            "run 'fenolite check' and copy the code and the item names of the finding's where, or give the "
            "items' KiCad uuids"
        )
        made = issue(code, f"--exclude {spec.text} matches {why}: nothing is written", where=spec.text,
                     hint=hint)  # fmt: skip
        return Result(result=base, issues=(*read_issues, made), evidence=evidence, input=given,
                      depends=depends)  # fmt: skip
    entry, names = found[0]
    first_uuid, second_uuid = exclusions.item_uuids(entry)
    items = [
        {"uuid": uuid, "name": names[index] if index < len(names) else ""}
        for index, uuid in enumerate((first_uuid, second_uuid))
        if uuid != NIL_UUID
    ]
    row: dict[str, Any] = {"type": entry.type, "code": type_code(ORACLE, entry.type), "items": items,
                           "reason": reason, "position": None, "keys": []}  # fmt: skip
    where = ", ".join(item["name"] or item["uuid"] for item in items)
    position = exclusions.stored_position(text, entry) if entry.excluded else None
    if position is None:
        position = exclusions.locate(cli, project, entry, exclusions.anchors(design, entry), text)
    if position is None:
        made = issue(UNLOCATED, f"no exclusion key of {entry.type} at an anchor of its items is applied by "
                     f"kicad-cli {version}: nothing is written", where=where,
                     hint="exclude the entry in KiCad's DRC dialog")  # fmt: skip
        return Result(result={**base, "exclusion": row}, issues=(*read_issues, made), evidence=evidence,
                      input=given, depends=depends)  # fmt: skip
    keys = exclusions.mirrored_keys(entry.type, position, first_uuid, second_uuid)
    row.update(position={"x": position.x, "y": position.y}, keys=list(keys))
    new = [key for key in keys if key not in exclusions.stored_keys(text)]
    if not new:
        made = issue(PRESENT, f"the exclusion of {entry.type} is already stored: nothing is written",
                     where=where)  # fmt: skip
        return Result(result={**base, "exclusion": row}, issues=(*read_issues, made), evidence=evidence,
                      input=given, depends=depends)  # fmt: skip
    written = exclusions.add_exclusions(text, [(key, reason) for key in keys])
    check = exclusions.run_with_project(cli, project, written)
    if not exclusions.confirmed(check.report, entry, reason):
        made = issue(UNLOCATED, f"the written exclusion of {entry.type} is not applied by kicad-cli "
                     f"{version} on a copy: nothing is written", where=where,
                     hint="exclude the entry in KiCad's DRC dialog")  # fmt: skip
        return Result(result={**base, "exclusion": row}, issues=(*read_issues, made), evidence=evidence,
                      input=given, depends=depends)  # fmt: skip
    return Result(
        result={**base, "exclusion": row},
        issues=tuple(read_issues),
        evidence=evidence,
        input=given,
        writes=(PlannedWrite(target, written.encode("utf-8"), "kicad_pro"),),
        depends=depends,
    )


__all__ = ["AMBIGUOUS", "PRESENT", "UNLOCATED", "UNMATCHED", "ExcludeSpec", "matches", "parse_exclude",
           "run_exclude"]  # fmt: skip
