# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The plan of ``fenolite sync --to-source`` (``docs/lens.md``, "sync").

``plan_sync`` reads the board of a built project, matches it with the design as a build does, and gives
the text of ``edits.toml`` (``lens.edits.capture_edits``: what the next build writes, minus the script)
together with what the next build would drop or overwrite: orphaned footprints, copper on nets the design
no longer has, and, for parts without a base record, values edited in KiCad. It reads and writes no file;
the command does. ``sync`` records; only ``fenolite build --take`` resolves a conflict.
``plan_drawn`` (change c0276) gives the text of the drawn schematic file from the project's sheets, after
proving that they still mean the recorded circuit: a sync never changes nets.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.backends.kicad import drawn as kicad_drawn
from fenolite.backends.kicad import pcb
from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.lens import edits as edits_mod
from fenolite.lens import preserve, schplacements
from fenolite.lens.drawn import write_drawn
from fenolite.lens.extract import extract_placements
from fenolite.lens.moved import Aliases, resolve_aliases
from fenolite.lens.placements import FILE_NAME as PLACEMENTS_FILE
from fenolite.lens.placements import read_placements
from fenolite.model.circuit import Circuit
from fenolite.model.design import Design
from fenolite.model.drawn_connect import compare
from fenolite.model.drawn_connect import issue as drawn_issue
from fenolite.model.schematic import SchematicSheet

SYNC_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "sync.would-change": "error",
        "sync.conflict": "error",
        "sync.orphan": "warning",
        "sync.net-dropped": "warning",
        "sync.value-differs": "warning",
        "sync.symbol-off-grid": "warning",
        "sync.placements-migrated": "info",
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


def _value_issues(
    design: Design, board: Design, match: preserve.LayoutMatch, only: frozenset[str] | None = None
) -> list[Issue]:
    """One ``sync.value-differs`` per value, library footprint or user property of a matched part that the
    board holds differently from the script; with ``only``, for those parts alone (the parts without a base
    entry: the values of the others are merged three ways)."""
    found: list[Issue] = []
    on_board = {c.id: c for c in board.circuit.components}
    for path, component in preserve.component_paths(design).items():
        matched = match.matches.get(path)
        if matched is None or (only is not None and path not in only):
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
                    "change the script, or leave it and let the build restore it; once the build has written "
                    "its base record (fenolite-base.json), a value edited in KiCad is kept",
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
    edits_text: str | None = None,
    placements_text: str | None = None,
    symbol_placements_text: str | None = None,
    sheets: Sequence[SchematicSheet] | None = None,
    base: edits_mod.BaseRecord | None = None,
    requests: Mapping[str, edits_mod.RequestLike] | None = None,
) -> SyncPlan:
    """What ``sync --to-source`` writes and reports for the board text of ``existing``.

    ``aliases`` holds the script's aliases: its ``parts`` and ``modules``, and in ``nets`` the names of
    ``moved_net()``; the net aliases that the module aliases give are resolved against the board here.
    ``edits_text`` is the current text of ``edits.toml`` (``None`` without the file) and ``placements_text``
    that of a legacy ``placements.toml``, read only without ``edits.toml``: its entries are position edits,
    and those of parts the board does not place are carried into ``edits.toml``
    (``sync.placements-migrated``). ``base`` is the base record of the output folder and ``requests`` the
    script's ``place()`` requests. ``sheets`` are the sheets of the project's schematic, the root and every
    sheet file it names, as ``sch.read_schematic`` gives them: they are the second CAD side of values and
    footprints, and with them the symbol placements are planned as ``schematic-placements.toml``, against
    ``symbol_placements_text``. Without ``sheets``, ``result.symbols`` is ``None``. A conflict gives
    ``sync.conflict`` and plans no file.
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
    held: dict[str, edits_mod.PartEdits] = {}
    if edits_text is not None:
        found = edits_mod.read_edits(edits_text, origin=origin, file=edits_mod.EDITS_FILE)
        issues += found.issues
        held.update(found.parts)
    elif placements_text is not None:
        legacy = read_placements(placements_text, origin=origin, file=PLACEMENTS_FILE)
        issues += legacy.issues
        held.update(preserve.legacy_edits(legacy.entries))
        placed = {path for path in match.matches if path not in extracted.unplaced}
        for path, entry in legacy.entries.items():
            if path in placed:
                continue
            request = (requests or {}).get(path)
            script_pos = (request.at.x, request.at.y) if request is not None else None
            script_rot = (request.rotation, request.side) if request is not None else None
            held[path] = edits_mod.PartEdits(
                MappingProxyType(
                    {"position": (entry.at.x, entry.at.y), "rotation": (entry.rotation, entry.side)}
                ),
                MappingProxyType({"position": script_pos, "rotation": script_rot})
                if script_pos is not None
                else MappingProxyType({"position": None, "rotation": None}),
                entry.locked,
            )
    footprints = {path: m.footprint for path, m in match.matches.items()}
    known = set(preserve.component_paths(design))
    captured = edits_mod.capture_edits(
        design,
        board=board,
        sheets=sheets,
        match=footprints,
        base=base,
        edits={path: edits for path, edits in held.items() if path in known},
        origin=origin,
        requests=requests,
        off_board=frozenset(extracted.unplaced),
        aliases=resolved.parts,
    )
    files: dict[str, str] = {}
    text = edits_mod.write_edits(captured.parts, origin=origin)
    if text != edits_text and not captured.conflicts:
        files[edits_mod.EDITS_FILE] = text
    if edits_text is None and placements_text is not None:
        issues.append(
            issue(
                "sync.placements-migrated",
                f"the entries of {PLACEMENTS_FILE} are carried into {edits_mod.EDITS_FILE}, which "
                "replaces it",
                PLACEMENTS_FILE,
                f"delete {PLACEMENTS_FILE} after reviewing {edits_mod.EDITS_FILE}",
            )
        )
    issues += captured.issues
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
    issues += _value_issues(design, board, match, frozenset(captured.no_base))
    symbols: int | None = None
    if sheets is not None:
        entries, off_grid = schplacements.extract_symbol_placements(sheets, design=design)
        issues += off_grid
        symbols = len(entries)
        symbol_text = schplacements.write_placements(entries)
        if symbol_text != symbol_placements_text and not captured.conflicts:
            files[SYMBOL_FILE_NAME] = symbol_text
    result: dict[str, object] = {
        "board": file,
        "placements": sum(
            1 for edits in captured.parts.values() if {"position", "rotation"} & set(edits.values)
        ),
        "edits": list(captured.captured),
        "pending": list(captured.pending),
        "conflicts": [conflict.record() for conflict in captured.conflicts],
        "unplaced": list(extracted.unplaced),
        "orphans": orphans,
        "board_only": [refs.get(fp.component_id, "?") for fp in match.board_only],
        "symbols": symbols,
        "files": sorted(files),
    }
    return SyncPlan(MappingProxyType(files), MappingProxyType(result), tuple(issues))


@dataclass(frozen=True)
class DrawnPlan:
    """``text``: the canonical drawn schematic of the project's sheets, or ``None`` when its nets differ
    from the circuit; ``changed``: whether it differs from the current file; ``issues``: the resolver's and
    the comparison's issues, with ``drawn.frozen`` for a freeze."""

    text: str | None
    changed: bool
    issues: tuple[Issue, ...]
    counts: Mapping[str, int]


def plan_drawn(
    root: SchematicSheet,
    children: Mapping[str, SchematicSheet],
    *,
    circuit: Circuit,
    name: str,
    root_file: str,
    current: str | None,
    file: str,
    freeze: bool = False,
) -> DrawnPlan:
    """The drawn schematic file that ``sync --to-source`` plans for the sheets ``root`` and ``children`` of a
    built project (capability layout-lens, "Drawn schematic in the source tree" and "Drawn schematic sync
    refuses changed nets"; change c0276).

    The sheets are extracted and resolved (``backends.kicad.drawn.resolve_sheets``) and compared with the
    recorded ``circuit``: a connectivity difference plans nothing and keeps the ``drawn.netlist-differs``
    error. Otherwise the canonical text is planned when it differs from ``current``. ``freeze`` (a generated
    schematic frozen into a drawn one) adds ``drawn.frozen`` with the hint to load the file."""
    drawn, netlist, found = kicad_drawn.resolve_sheets(
        root, children, circuit=circuit, name=name, root_file=root_file
    )
    issues = [i for i in found if i.code.startswith("drawn.") or i.severity != "info"]
    compared = compare(netlist, circuit)
    issues += compared
    counts = kicad_drawn.drawn_counts(drawn)
    if any(i.severity == "error" for i in issues):
        return DrawnPlan(None, False, tuple(issues), counts)
    text = write_drawn(drawn)
    if freeze:
        issues.append(
            drawn_issue(
                "drawn.frozen",
                f"{file} is written from the generated schematic of the built project",
                file,
                f'add design.load_schematic("{file}") to the script; the next build draws the sheets from it',
            )
        )
    return DrawnPlan(text, text != current, tuple(issues), counts)


__all__ = [
    "EVIDENCE",
    "SYMBOL_FILE_NAME",
    "SYNC_ISSUE_CODES",
    "DrawnPlan",
    "SyncPlan",
    "issue",
    "plan_drawn",
    "plan_sync",
]
