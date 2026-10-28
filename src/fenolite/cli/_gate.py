# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``--gate drc`` of the commands that write copper (change c0225; capability kicad-oracle, "DRC gate on
writing commands", "DRC gate report" and "DRC gate units"; ``docs/cli-contract.md``, "DRC gate").

A gated command makes its edit as before, then hands the board as read and as edited to ``gate``: the ids of
the entity groups that differ are the edit, ``fenolite.api.trial(..., gate=True)`` judges them on the board it
reads (the items grafted onto it), and the command writes its own model with the dropped items put back.
``preflight`` runs before the command edits anything, so a missing tool changes nothing.
"""

from __future__ import annotations

import argparse
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.api.trials import GROUPS, revert, trial
from fenolite.cli._kicadtool import preflight as tool_preflight
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design

GATES = ("drc",)
"""The values of ``--gate``."""
DROPPED = "gate.dropped"
UNNAMED = "gate.unnamed"
ISSUE_CODES = {DROPPED: ("warning",), UNNAMED: ("warning",)}
"""The issue codes of ``--gate drc`` (``fenolite explain``)."""


def register(parser: argparse.ArgumentParser, *, kicad_cli: bool = False) -> None:
    """Add ``--gate`` (and ``--kicad-cli`` when the command has none) to ``parser``."""
    parser.add_argument(
        "--gate",
        choices=GATES,
        default=None,
        help="drc: judge the edit with kicad-cli DRC and write it without the items that bring new findings",
    )
    if kicad_cli:
        parser.add_argument(
            "--kicad-cli",
            dest="kicad_cli",
            metavar="PATH",
            help="kicad-cli binary or docker:<image> for --gate",
        )


def preflight(args: argparse.Namespace, board: Path, timeout: float, *, own_option: bool = False) -> None:
    """With ``--gate drc``, the ``kicad-cli`` pre-flight of ``check`` on ``board`` (exit 6 without a tool).
    ``own_option``: ``--kicad-cli`` was added by ``register`` and needs ``--gate`` (``FEN-2001``)."""
    if args.gate == "drc":
        tool_preflight(args.kicad_cli, timeout, board)
    elif own_option and args.kicad_cli:
        raise CliError("FEN-2001", "--kicad-cli needs --gate drc", where="--kicad-cli", hint="add --gate drc")


def edit_ids(before: Design, after: Design) -> tuple[str, ...]:
    """The ids of the items of ``trial.GROUPS`` that ``after`` adds, removes or changes against ``before``,
    in group order, then in the order of ``after`` (removed items last, in the order of ``before``)."""
    old_board, new_board = before.board, after.board
    if old_board is None or new_board is None:
        return ()
    found: list[str] = []
    for group in GROUPS:
        old = {entity.id: entity for entity in getattr(old_board, group)}
        now = {entity.id for entity in getattr(new_board, group)}
        found += [entity.id for entity in getattr(new_board, group) if old.get(entity.id) != entity]
        found += [entity_id for entity_id in old if entity_id not in now]
    return tuple(dict.fromkeys(found))


def joined(groups: Iterable[Collection[str]]) -> list[frozenset[str]]:
    """``groups`` with every two that share an id joined into one: an edit that changes an item another edit
    made goes with it."""
    units: list[set[str]] = []
    for group in groups:
        merged = set(group)
        rest: list[set[str]] = []
        for unit in units:
            if unit & merged:
                merged |= unit
            else:
                rest.append(unit)
        units = [*rest, merged]
    return [frozenset(unit) for unit in units]


def untouched() -> dict[str, Any]:
    """``result.gate`` of an edit that holds no item: no DRC run."""
    return {"tool_version": None, "runs": 0, "refilled": False, "items": 0, "kept": 0, "dropped": [],
            "findings": []}  # fmt: skip


@dataclass(frozen=True, slots=True)
class Gated:
    """The edited model without the dropped items, ``result.gate``, the issues and, when no new finding is
    left, the trial's evidence."""

    design: Design
    dropped: frozenset[str]
    result: dict[str, Any]
    issues: tuple[Issue, ...]
    evidence: Evidence | None


def gate(
    board: Path,
    before: Design,
    after: Design,
    *,
    kicad_cli: str | None,
    timeout: float,
    together: Iterable[Collection[str]] = (),
) -> Gated:
    """Judge the edit from ``before`` (the board as read) to ``after`` with ``trial(..., gate=True)`` on
    ``board``; see the module."""
    ids = edit_ids(before, after)
    if not ids:
        return Gated(after, frozenset(), untouched(), (), None)
    judged = trial(
        board,
        lambda fresh: (revert(fresh, after, ids), ids),
        kicad_cli=kicad_cli,
        gate=True,
        timeout=timeout,
        together=together,
    )
    dropped = frozenset(item.id for item in judged.dropped)
    issues = list(judged.issues)
    for item in judged.dropped:
        first = item.findings[0]
        issues.append(
            Issue(
                DROPPED,
                "warning",
                f"{item.id} is not written: kicad-cli {judged.tool_version} DRC finds {first.type} "
                f"({first.description}) that the board without the edit lacks",
                where=item.id,
                hint="route or tidy that copper again after moving what it clashes with",
            )
        )
    for finding in judged.findings:
        issues.append(
            Issue(
                UNNAMED,
                "warning",
                f"kicad-cli {judged.tool_version} DRC finds {finding.type} ({finding.description}) on the "
                "edited board that names no item of the edit; it may be noise of the tool",
                where=finding.type,
                hint="run fenolite check on the written board",
            )
        )
    result = {
        "tool_version": judged.tool_version,
        "runs": judged.runs,
        "refilled": judged.refilled,
        "items": len(ids),
        "kept": len(judged.kept),
        "dropped": [
            {"id": item.id, "findings": [finding.to_json() for finding in item.findings]}
            for item in judged.dropped
        ],
        "findings": [finding.to_json() for finding in judged.findings],
    }
    kept = revert(after, before, dropped) if dropped else after
    return Gated(kept, dropped, result, tuple(issues), judged.evidence if judged.clean else None)


__all__ = [
    "GATES",
    "ISSUE_CODES",
    "Gated",
    "edit_ids",
    "gate",
    "joined",
    "preflight",
    "register",
    "untouched",
]
