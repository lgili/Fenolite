# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The plan of ``fenolite sync --to-source`` (``docs/lens.md``, "sync").

``plan_sync`` reads the board of a built project, matches it with the design as a build does, and gives
the text of ``placements.toml`` together with what the next build would drop or overwrite: orphaned
footprints, copper on nets the design no longer has, and values edited in KiCad. It reads and writes no
file; the command does.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.backends.kicad import pcb
from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.lens import preserve, schplacements
from fenolite.lens.extract import extract_placements
from fenolite.lens.moved import Aliases, resolve_aliases
from fenolite.lens.placements import FILE_NAME, write_placements
from fenolite.model.design import Design
from fenolite.model.schematic import SchematicSheet

SYNC_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "sync.would-change": "error",
        "sync.orphan": "warning",
        "sync.net-dropped": "warning",
        "sync.value-differs": "warning",
        "sync.symbol-off-grid": "warning",
    }
)
EVIDENCE = preserve.EVIDENCE
SYMBOL_FILE_NAME = schplacements.FILE_NAME
COPPER_KINDS: tuple[str, ...] = ("tracks", "arcs", "vias", "zones")


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, SYNC_ISSUE_CODES[code], message, where=where, hint=hint)


@dataclass(frozen=True)
class SyncPlan:
    """``files``: file name → the text to write beside the script, for the files that change. ``result``
    and ``issues`` are what the command reports."""

    files: Mapping[str, str]
    result: Mapping[str, object]
    issues: tuple[Issue, ...] = ()


def _value_issues(design: Design, board: Design, match: preserve.LayoutMatch) -> list[Issue]:
    """One ``sync.value-differs`` per value, library footprint or user property of a matched part that the
    board holds differently from the script."""
    found: list[Issue] = []
    on_board = {c.id: c for c in board.circuit.components}
    for path, component in preserve.component_paths(design).items():
        matched = match.matches.get(path)
        if matched is None:
            continue
        read = on_board.get(matched.footprint.component_id)
        pairs: list[tuple[str, str, str]] = []
        if read is not None and read.value != component.value:
            pairs.append(("value", read.value, component.value))
        wanted = component.lib_footprint_ref
        if wanted and matched.footprint.lib_ref != wanted:
            pairs.append(("footprint", matched.footprint.lib_ref, wanted))
        held = {
            name.casefold(): value for name, value in (read.properties if read is not None else {}).items()
        }
        for name, value in sorted(component.properties.items()):
            if name in ("Reference", "Value", PATH_PROPERTY):
                continue
            current = held.get(name.casefold())
            if current is not None and current != value:
                pairs.append((f"property {name}", current, value))
        for what, theirs, ours in pairs:
            found.append(
                issue(
                    "sync.value-differs",
                    f"{path}: {what} is {theirs!r} on the board and {ours!r} in the script; the next build "
                    "writes the script's",
                    path,
                    "change the script, or leave it and let the build restore it",
                )
            )
    return found


def _net_issues(design: Design, board: Design, nets: Mapping[str, str]) -> list[Issue]:
    """One ``sync.net-dropped`` per board net with copper that no design net or alias covers."""
    assert board.board is not None
    names = {net.id: net.name for net in board.circuit.nets}
    covered = {net.name for net in design.circuit.nets} | set(nets.values())
    counts: dict[str, Counter[str]] = {}
    items: tuple[tuple[str, Sequence[object]], ...] = (
        ("tracks", board.board.tracks),
        ("arcs", board.board.arcs),
        ("vias", board.board.vias),
        ("zones", board.board.zones),
    )
    for kind, entities in items:
        for entity in entities:
            name = names.get(getattr(entity, "net_id", None) or "")
            if name is not None and name not in covered:
                counts.setdefault(name, Counter())[kind] += 1
    return [
        issue(
            "sync.net-dropped",
            f"net {name!r} is not in the design: the next build drops its {found['tracks']} tracks, "
            f"{found['arcs']} arcs, {found['vias']} vias and {found['zones']} zones",
            name,
            "keep the net in the script, or name its new name with moved_net()",
        )
        for name, found in sorted(counts.items())
    ]


def plan_sync(
    design: Design,
    existing: preserve.ExistingProject,
    *,
    name: str,
    aliases: Aliases,
    origin: Point,
    placements_text: str | None,
    symbol_placements_text: str | None = None,
    sheets: Sequence[SchematicSheet] | None = None,
) -> SyncPlan:
    """What ``sync --to-source`` writes and reports for the board text of ``existing``.

    ``aliases`` holds the script's aliases: its ``parts`` and ``modules``, and in ``nets`` the names of
    ``moved_net()``; the net aliases that the module aliases give are resolved against the board here.
    ``placements_text`` is the current text of ``placements.toml`` (``None`` without the file). ``sheets``
    are the sheets of the project's schematic, the root and every sheet file it names, as
    ``sch.read_schematic`` gives them: with them the symbol placements are planned as
    ``schematic-placements.toml``, against ``symbol_placements_text``. Without ``sheets``,
    ``result.symbols`` is ``None``.
    """
    if existing.board is None:
        raise ValueError("plan_sync needs the board text of the built project")
    file = f"{name}.kicad_pcb"
    read: list[Issue] = []
    board = pcb.read_board(existing.board, file=file, issues=read)
    assert board.board is not None
    issues = [found for found in read if found.severity != "info"]
    resolved, _ = resolve_aliases(
        design, board, moves=aliases.parts, module_moves=aliases.modules, net_moves=aliases.nets
    )
    match = preserve.match_footprints(design, board, moves=resolved.parts)
    extracted = extract_placements(board, match, design=design)
    text = write_placements(extracted.placements, origin=origin)
    files: dict[str, str] = {}
    if text != placements_text:
        files[FILE_NAME] = text
    refs = {c.id: c.ref for c in board.circuit.components}
    paths = {c.id: c.properties.get(PATH_PROPERTY, "") for c in board.circuit.components}
    orphans: list[str] = []
    for fp in match.orphans:
        ref = refs.get(fp.component_id, "?")
        orphans.append(ref)
        issues.append(
            issue(
                "sync.orphan",
                f"{ref} ({paths.get(fp.component_id, '')}) is on the board and not in the design: the "
                "next build removes its footprint",
                paths.get(fp.component_id, ""),
                "keep the part in the script, or name its new path with moved()",
            )
        )
    issues += _net_issues(design, board, resolved.nets)
    issues += _value_issues(design, board, match)
    symbols: int | None = None
    if sheets is not None:
        entries, off_grid = schplacements.extract_symbol_placements(sheets, design=design)
        issues += off_grid
        symbols = len(entries)
        symbol_text = schplacements.write_placements(entries)
        if symbol_text != symbol_placements_text:
            files[SYMBOL_FILE_NAME] = symbol_text
    result: dict[str, object] = {
        "board": file,
        "placements": len(extracted.placements),
        "unplaced": list(extracted.unplaced),
        "orphans": orphans,
        "board_only": [refs.get(fp.component_id, "?") for fp in match.board_only],
        "symbols": symbols,
        "files": sorted(files),
    }
    return SyncPlan(MappingProxyType(files), MappingProxyType(result), tuple(issues))


__all__ = ["EVIDENCE", "SYMBOL_FILE_NAME", "SYNC_ISSUE_CODES", "SyncPlan", "issue", "plan_sync"]
