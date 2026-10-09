# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The state of every entry of a manifest, from the stages of a check (capability manufacturing-exports,
"Artefact states"; user guide ``docs/exports.md``, "States").

The states are a ladder: ``generated``, ``checked``, ``roundtrip-ok``, ``oracle-verified``,
``native-verified``. An entry has the highest state it reaches together with every lower one that
applies to its kind, and ``held`` says what the next one is missing. Nothing is judged here: a state is
read from a stage result, from the RT1 verdict of a sheet and from hashes, and never says more than they
do.

``assign`` is pure and knows no stage implementation: the command turns a ``CheckReport`` into the
mapping it takes (``exports`` does not import ``checks``).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from fenolite.core.evidence import Level
from fenolite.exports.manifest import STATES, ArtifactEntry, State

Role = Literal["board", "sheet", "board-support", "schematic-support", "other", "derived"]
Need = Literal["stages", "sheet-rt1", "board", "sources"]
StageMap = Mapping[str, tuple[str, str]]
"""Stage name → ``(status, evidence level)`` of a check; a stage that did not run is absent."""

DERIVED = frozenset(
    {"gerbers", "drill", "pos", "ipcd356", "ipc2581", "odb", "step", "pdf", "dxf", "sch-pdf"}
    | {"fab-drawing", "assembly-drawing"}
    | {"bom", "pnp", "testpoints", "render"}
)
"""The kinds of a file made from the design; any other kind is a design file."""
BOARD_KIND, SHEET_KIND = "kicad_pcb", "kicad_sch"
SYMBOL_KIND = "kicad_sym"
SYMBOL_TABLE = "sym-lib-table"
BOARD_SUPPORT = frozenset({"kicad_pro", "kicad_dru", "kicad_mod", "kicad_wks", "lib-table"})
"""The kinds KiCad loads to judge a board (a ``lib-table`` named ``sym-lib-table`` is not one)."""
SOURCE_KINDS: Mapping[str, str] = {"board": BOARD_KIND, "schematic": SHEET_KIND}
"""A key of an entry's ``from`` → the kind of the design file it names."""
CHECKED_STAGES = ("model.validate", "copper.clearance")
ROUNDTRIP_STAGE = "roundtrip"
NATIVE_STAGE = "drc.kicad"
SCHEMATIC_STAGE = "erc.kicad"
"""The stage whose verdict is the format's own tool's on the schematic side: KiCad's ERC (change c0062)."""
NATIVE_LEVEL = Level.KICAD_VERIFIED.value
OK = "ok"


@dataclass(frozen=True, slots=True)
class Rule:
    """What one state asks of a file: the stages that must be ``ok`` (each at ``level`` when one is
    named), or another ``need``: the RT1 verdict of the sheet, the board's own state, or the sources."""

    state: State
    need: Need = "stages"
    stages: tuple[str, ...] = ()
    level: str = ""


_CHECKED = Rule("checked", stages=CHECKED_STAGES)
RULES: Mapping[Role, tuple[Rule, ...]] = {
    "board": (
        _CHECKED,
        Rule("roundtrip-ok", stages=(ROUNDTRIP_STAGE,)),
        Rule("native-verified", stages=(NATIVE_STAGE,), level=NATIVE_LEVEL),
    ),
    "sheet": (
        _CHECKED,
        Rule("roundtrip-ok", need="sheet-rt1"),
        Rule("native-verified", stages=(SCHEMATIC_STAGE,), level=NATIVE_LEVEL),
    ),
    "board-support": (_CHECKED, Rule("native-verified", need="board")),
    "schematic-support": (_CHECKED, Rule("native-verified", stages=(SCHEMATIC_STAGE,), level=NATIVE_LEVEL)),
    "other": (_CHECKED,),
    "derived": (Rule("checked", need="sources"),),
}
"""The rules of each role, in rising order. A state without a rule for a role is skipped, and no role
has a rule for ``oracle-verified``: that state waits for a tool that is neither the producer of a file
nor its format's own application."""

PENDING: Mapping[Role, tuple[State, str]] = {}
"""The state a role cannot reach yet, and the stage whose rule is missing. It is empty since change c0062:
KiCad's ERC is the stage ``erc.kicad`` of ``check``, and its rules stand in ``RULES``. A sheet, a symbol
library and the symbol table reach ``native-verified`` when that stage is ``ok`` at ``KICAD-VERIFIED``: the
ERC loaded the sheets with the libraries the table names. A role listed here would stop below its top
state whatever ``stages`` holds, and ``held`` would say so."""


def rank(state: str) -> int:
    """The position of ``state`` on the ladder; ``generated`` is 0."""
    return STATES.index(state)  # type: ignore[arg-type]


def role_of(entry: ArtifactEntry) -> Role:
    """The role of an entry, from its kind: the board, a schematic sheet, a file KiCad loads with the
    board (project, rules, footprint table and libraries, drawing sheet), a file it loads with the
    schematic (symbol table and libraries), a file made from the design, or any other file of the
    project, which no tool is known to load and which therefore stops at ``checked`` (a vendored 3D model,
    kind ``3d-model``, is one: the DRC does not load it, and the STEP export that reads it judges nothing)."""
    if entry.kind in DERIVED:
        return "derived"
    if entry.kind == BOARD_KIND:
        return "board"
    if entry.kind == SHEET_KIND:
        return "sheet"
    if entry.kind == SYMBOL_KIND or PurePosixPath(entry.path).name == SYMBOL_TABLE:
        return "schematic-support"
    if entry.kind in BOARD_SUPPORT:
        return "board-support"
    return "other"


def _stages_missing(rule: Rule, stages: StageMap) -> str:
    """What ``stages`` lacks for ``rule``, or ``""``."""
    for name in rule.stages:
        found = stages.get(name)
        if found is None:
            return f"{name} did not run"
        status, level = found
        if status != OK:
            return f"{name} was skipped" if status == "skipped" else f"{name} reported errors"
        if rule.level and level != rule.level:
            return f"{name} is {level}, below {rule.level}"
    return ""


def _climb(
    entry: ArtifactEntry,
    role: Role,
    *,
    stages: StageMap,
    sheets_ok: Mapping[str, bool],
    boards: Sequence[str],
) -> tuple[State, str]:
    """The state of a current design entry and what holds it there."""
    state: State = "generated"
    for rule in RULES[role]:
        if rule.need == "stages":
            missing = _stages_missing(rule, stages)
        elif rule.need == "sheet-rt1":
            verdict = sheets_ok.get(entry.path)
            missing = "" if verdict else ("RT1 was not judged" if verdict is None else "RT1 failed")
        else:  # the files KiCad loads with the board follow it
            lowest = min(boards, key=rank, default=None)
            missing = "" if lowest == rule.state else f"the board is {lowest or 'not listed'}"
        if missing:
            return state, f"{rule.state}: {missing}"
        state = rule.state
    pending = PENDING.get(role)
    if pending is not None:
        return state, f"{pending[0]}: {pending[1]} is not a stage of this version of Fenolite"
    return state, ""


def _derived(
    entry: ArtifactEntry, designs: Sequence[ArtifactEntry], current: Mapping[str, str]
) -> tuple[State, bool, str]:
    """``(state, stale, held)`` of a file made from the design: ``checked`` when it and every source its
    ``from`` names are the files that were hashed, and those sources are ``checked``."""
    if current.get(entry.path) != entry.sha256:
        return "generated", True, "checked: the file changed since it was listed"
    if not entry.from_:
        return "generated", False, "checked: no source is recorded"
    waiting = ""
    for name, sha in sorted(entry.from_.items()):
        kind = SOURCE_KINDS.get(name)
        if kind is None:
            waiting = waiting or f"checked: the source {name!r} is not known"
            continue
        sources = [d for d in designs if d.kind == kind and current.get(d.path) == sha == d.sha256]
        if not sources:
            return "generated", True, f"checked: the {name} changed since the file was made"
        lowest = min((d.state for d in sources), key=rank)
        if rank(lowest) < rank("checked"):
            waiting = waiting or f"checked: the {name} is {lowest}"
    if waiting:
        return "generated", False, waiting
    return "checked", False, ""


def assign(
    entries: Sequence[ArtifactEntry],
    *,
    stages: StageMap,
    sheets_ok: Mapping[str, bool],
    current: Mapping[str, str],
) -> tuple[ArtifactEntry, ...]:
    """``entries`` with their ``state``, ``stale`` and ``held``, in the order given.

    ``stages`` maps a stage name to its status and evidence level (empty when no check ran), ``sheets_ok``
    the path of a sheet to its RT1 verdict, and ``current`` a path to the file's present SHA-256. An entry
    whose file is not the one that was hashed stays ``generated``; so does every entry without a check."""
    found: dict[int, ArtifactEntry] = {}
    roles: list[Role] = [role_of(item) for item in entries]

    def settle(index: int, boards: Sequence[str]) -> None:
        item, role = entries[index], roles[index]
        if current.get(item.path) != item.sha256:
            state, held = "generated", "checked: the file changed since it was listed"
        else:
            state, held = _climb(item, role, stages=stages, sheets_ok=sheets_ok, boards=boards)
        found[index] = dataclasses.replace(item, state=state, stale=False, held=held)

    for index, role in enumerate(roles):
        if role == "board":
            settle(index, ())
    boards = [found[index].state for index, role in enumerate(roles) if role == "board"]
    for index, role in enumerate(roles):
        if role not in ("board", "derived"):
            settle(index, boards)
    designs = list(found.values())
    for index, role in enumerate(roles):
        if role == "derived":
            state, stale, held = _derived(entries[index], designs, current)
            found[index] = dataclasses.replace(entries[index], state=state, stale=stale, held=held)
    return tuple(found[index] for index in range(len(entries)))


__all__ = [
    "DERIVED",
    "PENDING",
    "RULES",
    "Role",
    "Rule",
    "StageMap",
    "assign",
    "rank",
    "role_of",
]
