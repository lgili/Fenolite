# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A footprint library made from a KiCad board, and the drift of a library from the board's instances
(capability design-conversion, "Library made from a board"; change c0223; ``docs/cli-contract.md``,
"library").

Each footprint of the board is brought back to its own origin, rotation 0 and the top side by
``embed.local_footprint``, the transform that the conversion's derived libraries use. Two instances of one
name whose written footprints differ (their uuids aside) give a second footprint ``<name>_2``. The drift
compares the model of each derived footprint with the library's footprint of the same name.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from fenolite.backends.kicad._fpmap import node
from fenolite.backends.kicad.embed import local_footprint
from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.transform import FULL_TURN
from fenolite.library.codes import issue
from fenolite.model.board import Graphic
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-LIB-FROM-BOARD",))
SUFFIX = ".kicad_mod"
KINDS = ("pads", "silkscreen", "courtyard", "models", "fields")
"""The kinds of a drift row, in report order; ``missing`` stands alone."""
MISSING = "missing"
SILK = ("F.SilkS", "B.SilkS")
COURTYARD = ("F.CrtYd", "B.CrtYd")
_UUID = re.compile(r'\(uuid "[^"]*"\)')


@dataclass(frozen=True, slots=True)
class Footprint:
    """One written footprint: its ``name`` in the library, the board's name it came from (``source``), the
    references of the instances it stands for, its definition and its text."""

    name: str
    source: str
    refs: tuple[str, ...]
    definition: FootprintDef
    text: str


@dataclass(frozen=True, slots=True)
class Derived:
    """The footprints of a board, in name order, and the issues of the derivation."""

    footprints: tuple[Footprint, ...] = ()
    issues: tuple[Issue, ...] = field(default=())

    def files(self) -> dict[str, str]:
        """``<name>.kicad_mod`` → text for each footprint."""
        return {f"{fp.name}{SUFFIX}": fp.text for fp in self.footprints}


def nickname_of(lib_ref: str, default: str) -> str:
    """The library nickname of a footprint lib id, ``default`` for an id without one."""
    head, colon, _ = lib_ref.partition(":")
    return head if colon and head else default


def derive_library(
    text: str, *, library: str, target: int, file: str = "", nickname: str | None = None, default: str = ""
) -> Derived:
    """The footprints of the KiCad board ``text`` brought back to their own frame, as a library named
    ``library`` written for KiCad ``target``. With ``nickname`` (change c0275), only the footprints whose
    lib id names that library (``default`` for an id without a nickname)."""
    return derive_from_model(read_board(text, file=file), text, library=library, target=target,
                             nickname=nickname, default=default)  # fmt: skip


def derive_from_model(
    design: Design,
    text: str,
    *,
    library: str,
    target: int,
    nickname: str | None = None,
    default: str = "",
    prepare: Callable[[Node], Node] | None = None,
) -> Derived:
    """``derive_library`` of a board already read into ``design`` from ``text`` (change c0275, design
    decision 8): the import reads the board once and derives one library per nickname from it; ``prepare``
    turns each instance's footprint node, brought back to its own frame, into the library's (the import
    drops the properties that belong to the instance) before instances are compared."""
    issues: list[Issue] = []
    board = design.board
    if board is None:
        return Derived()
    refs = {component.id: component.ref for component in design.circuit.components}
    nodes = parse(text).nodes("footprint")
    pairs = sorted(
        zip(board.footprints, nodes, strict=True), key=lambda p: (refs.get(p[0].component_id, ""), p[0].id)
    )
    variants: dict[str, list[tuple[str, str, FootprintDef, str, list[str]]]] = {}
    for fp, root in pairs:
        if nickname is not None and nickname_of(fp.lib_ref, default) != nickname:
            continue
        ref = refs.get(fp.component_id, "")
        source = fp.lib_ref.rsplit(":", 1)[-1] or ref or fp.id
        found: list[Issue] = []
        local = local_footprint(root, fp.rotation, fp.side, found)
        if found:
            issues.append(
                issue(
                    "library.not-local",
                    f"{ref or fp.id}: the footprint cannot be brought back to the top side; it is left out",
                    where=ref or fp.id,
                )
            )
            continue
        version = node("version", Atom.integer(FORMAT_VERSIONS[FileKind.FOOTPRINT][target]))
        local = local.with_children((local.children[0], version, *local.children[1:]))
        if prepare is not None:
            local = prepare(local)
        definition = read_footprint(dumps(local))
        rows = variants.setdefault(source, [])
        for _, signature, _, _, members in rows:
            if signature == _signature(definition, source, library, target):
                members.append(ref)
                break
        else:
            name = source if not rows else f"{source}_{len(rows) + 1}"
            definition = _named(definition, name, library)
            written = write_footprint(definition, target=target, allow_lossy=True)
            if rows:
                issues.append(
                    issue(
                        "library.instances-differ",
                        f"{ref} differs from the first instance of {source}: written as {name}",
                        where=ref,
                        hint="make the instances equal on the board, or keep both footprints",
                    )
                )
            rows.append((name, _signature(definition, source, library, target), definition, written, [ref]))
    footprints = [
        Footprint(name, source, tuple(members), definition, written)
        for source, rows in variants.items()
        for name, _, definition, written, members in rows
    ]
    return Derived(tuple(sorted(footprints, key=lambda fp: fp.name)), tuple(issues))


def _named(definition: FootprintDef, name: str, library: str) -> FootprintDef:
    properties = {**definition.properties, "Reference": "REF**", "Value": name}
    return dataclasses.replace(definition, name=name, library=library, properties=properties)


def _signature(definition: FootprintDef, source: str, library: str, target: int) -> str:
    """The written text of ``definition`` under the name ``source``, its uuids left out."""
    written = write_footprint(_named(definition, source, library), target=target, allow_lossy=True)
    return _UUID.sub("", written)


def _graphics(definition: FootprintDef, layers: tuple[str, ...]) -> list[tuple[object, ...]]:
    def key(graphic: Graphic) -> tuple[object, ...]:
        points = tuple((p.x, p.y) for p in graphic.points)
        return (graphic.layer, graphic.kind, points, graphic.width, graphic.filled)

    return sorted((key(g) for g in definition.graphics if g.layer in layers), key=repr)


def _pads(definition: FootprintDef) -> list[tuple[object, ...]]:
    return sorted(
        (
            (
                pad.number,
                pad.kind,
                pad.shape,
                (pad.size.w, pad.size.h),
                (pad.position.x, pad.position.y),
                pad.rotation % FULL_TURN,
                tuple(pad.layers),
                pad.drill,
            )
            for pad in definition.pads
        ),
        key=repr,
    )


def _fields(definition: FootprintDef) -> dict[str, str]:
    return {k: v for k, v in definition.properties.items() if k not in ("Reference", "Value")}


def differences(board: FootprintDef, library: FootprintDef) -> tuple[str, ...]:
    """The kinds of ``KINDS`` in which a footprint made from a board differs from a library's footprint."""
    found: list[str] = []
    if _pads(board) != _pads(library):
        found.append("pads")
    if _graphics(board, SILK) != _graphics(library, SILK):
        found.append("silkscreen")
    if _graphics(board, COURTYARD) != _graphics(library, COURTYARD):
        found.append("courtyard")
    if sorted(board.models) != sorted(library.models):
        found.append("models")
    if _fields(board) != _fields(library):
        found.append("fields")
    return tuple(found)


def drift(derived: Derived, library: Path) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Per footprint of ``derived`` that differs from the footprint of its board name in the folder
    ``library``, ``(name, kinds)``; a footprint that the folder lacks gives ``(name, ("missing",))``."""
    rows: list[tuple[str, tuple[str, ...]]] = []
    for fp in derived.footprints:
        path = library / f"{fp.source}{SUFFIX}"
        if not path.is_file():
            rows.append((fp.name, (MISSING,)))
            continue
        kinds = differences(fp.definition, read_footprint(path))
        if kinds:
            rows.append((fp.name, kinds))
    return tuple(rows)


def drift_issues(
    rows: Mapping[str, tuple[str, ...]] | tuple[tuple[str, tuple[str, ...]], ...],
) -> list[Issue]:
    """One ``library.drift`` per drifted footprint."""
    items = rows.items() if isinstance(rows, Mapping) else rows
    return [
        issue(
            "library.drift",
            f"{name}: the library differs from the board in {', '.join(kinds)}",
            where=name,
            hint="write the library again from the board with --out, or edit the board's instances",
        )
        for name, kinds in items
    ]


__all__ = [
    "EVIDENCE",
    "KINDS",
    "MISSING",
    "Derived",
    "Footprint",
    "derive_library",
    "differences",
    "drift",
    "drift_issues",
]
