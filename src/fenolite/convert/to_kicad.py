# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The direction from KiCad to KiCad (capability design-conversion, "KiCad to KiCad direction", "KiCad
downgrade direction" and "KiCad downgrade report"; changes c0159 and c0162).

The board read from the source keeps its opaque content and is written with ``write_board`` for the target
(``write_triad``, with the source's project file updated by ``pro.update_project``); the rules file is the
source's, read and written again for the target with ``dru.write_rules``, which keeps its order and names.
The schematic files are copied byte for byte when the source's major equals the target, and are reported
as not converted for a newer target.

A target older than the source's major is a downgrade (change c0162): every file is written with
``downgrade=True``, so the capability resolver (``backends/kicad/resolver.py``) decides each construct of
the newer major, and its edits become one report row per resolver id (kind ``downgrade:<id>``). The
schematic sheets are re-targeted (``sch.retarget_schematic``), the footprint and symbol libraries of the
project's own tables are written for the target (``mod.write_footprint``, ``sym.retarget_symbol_library``),
and the library tables and drawing sheets, whose formats both majors read, are copied. The writers run
with ``allow_lossy``: the consent to a ``design`` loss is ``convert_project``'s, by the report.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from fenolite.backends.altium.pcbrecords import to_units
from fenolite.backends.kicad import dru, resolver, sch, sym
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.mod import prepare_authored_definition, read_footprint, write_footprint
from fenolite.backends.kicad.outline import edge_outline
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import TARGET_MAJORS
from fenolite.convert.direction import Direction, Options, Written
from fenolite.convert.report import (
    DOWNGRADE_KINDS,
    DOWNGRADE_PREFIX,
    OVERLAP_NO_UNION,
    OVERLAP_NOT_ONE_RING,
    ConversionReport,
    census,
)
from fenolite.convert.sources import KICAD, SourceProject
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.trig import FULL_TURN
from fenolite.geometry.errors import BackendUnavailable, GeometryError
from fenolite.geometry.rings import MERGE_TOL, CurvedRing, merge_groups, overlap_groups
from fenolite.model import holes as model_holes
from fenolite.model.board import FootprintAttribute, FootprintInstance, Hole, OutlineArc
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-CONV-RETARGET", "H-K-PCB-WRITE"))
"""The board writer's re-target: a KiCad 9 project converted to 10 loads in 10.0.6 and gives the DRC of the
source in 9.0.9 (``H-K-CONV-RETARGET``, confirmed on 2026-10-09)."""
DOWNGRADE_EVIDENCE = resolver.EVIDENCE
"""A downgrade: the evidence of the resolver's table (``H-K-DOWN-ROWS``, ``H-K-DOWN-DEMOS``)."""
PROFILE = "kicad-to-kicad"
DOWNGRADE_PROFILE = "kicad-downgrade"
ALTIUM = "altium"
SCHEMATIC = "schematic"
SCHEMATIC_SUFFIX = ".kicad_sch"
FOOTPRINT_SUFFIX = ".kicad_mod"
SYMBOL_SUFFIX = ".kicad_sym"
LIBRARY_FOLDER = ".pretty"
WRITER_KINDS: tuple[str, ...] = (SCHEMATIC, *(row.name for row in DOWNGRADE_KINDS))
"""The kinds this direction's writer names besides the census: the schematic files, and one kind per row
of the downgrade resolver."""
REASONS: dict[resolver.Action, str] = {
    "rewrite": "written in the form of the target",
    "same": "dropped: the target behaves the same without it",
    "presentation": "dropped: a drawing, a text or metadata of the target differs",
    "design": "dropped: what is made or checked differs",
}


def _text(data: bytes) -> str:
    return data.decode("utf-8")


def _renamed(key: str, source: SourceProject, name: str) -> str:
    """The written name of the project file ``key``: the files of the source's stem take ``name``."""
    path = PurePosixPath(key)
    if len(path.parts) == 1 and path.stem == source.name:
        return f"{name}{path.suffix}"
    return key


def write(source: SourceProject, options: Options) -> Written:
    """The KiCad project of a KiCad source for ``options.kicad_version``, with its report."""
    target = options.kicad_version
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    if source.major is not None and target < source.major:
        return _downgrade(source, options)
    name = options.name or source.name
    design = source.design
    project_name = f"{source.name}.kicad_pro"
    rules_name = f"{source.name}.kicad_dru"
    existing = _text(source.files[project_name].read_bytes()) if project_name in source.files else None
    issues: list[Issue] = []
    # the rules of the source were read from its rules file: that file is written again below, so the
    # triad lowers no rule of its own (``lowering.lower_rules`` refuses a set read from a file)
    texts = write_triad(
        dataclasses.replace(design, rules=None),
        name=name,
        target=target,
        existing_project=existing,
        issues=issues,
    )
    if rules_name in source.files:
        path = source.files[rules_name]
        ruleset = dru.read_rules(_text(path.read_bytes()), file=path.name)
        texts[f"{name}.kicad_dru"] = dru.write_rules(ruleset, target=target, issues=issues)
    files: dict[str, bytes] = {key: text.encode("utf-8") for key, text in texts.items()}
    sheets = sorted(key for key in source.files if key.endswith(SCHEMATIC_SUFFIX))
    lost: dict[str, dict[str, tuple[str, ...]]] = {}
    if sheets and source.major == target:
        for key in sheets:
            written = f"{name}{SCHEMATIC_SUFFIX}" if key == f"{source.name}{SCHEMATIC_SUFFIX}" else key
            files[written] = source.files[key].read_bytes()
    elif sheets:
        reason = (
            f"a schematic of KiCad {source.major} is not re-targeted to KiCad {target}: the board and its "
            "project files are converted alone"
        )
        lost[SCHEMATIC] = {reason: tuple(sheets)}
    counts = census(design)
    if sheets:
        counts[SCHEMATIC] = len(sheets)
    report = ConversionReport.of(source=counts, lost=lost)
    return Written(dict(sorted(files.items())), report, design, f"{name}.kicad_pcb", tuple(i for i in issues))


def _downgrade(source: SourceProject, options: Options) -> Written:
    """The project of a source of a newer major written for ``options.kicad_version`` (change c0162)."""
    target = options.kicad_version
    name = options.name or source.name
    design = source.design
    project_name = f"{source.name}.kicad_pro"
    rules_name = f"{source.name}.kicad_dru"
    existing = _text(source.files[project_name].read_bytes()) if project_name in source.files else None
    issues: list[Issue] = []
    edits: list[resolver.Edit] = []
    found: list[resolver.Edit] = []
    texts = write_triad(
        dataclasses.replace(design, rules=None),
        name=name,
        target=target,
        existing_project=existing,
        allow_lossy=True,
        issues=issues,
        downgrade=True,
        edits=found,
    )
    for edit in found:
        suffix = ".kicad_pro" if edit.row.startswith(resolver.PROJECT_PREFIX) else ".kicad_pcb"
        edits.append(dataclasses.replace(edit, file=f"{name}{suffix}"))
    if rules_name in source.files:
        path = source.files[rules_name]
        ruleset = dru.read_rules(_text(path.read_bytes()), file=path.name)
        found = []
        texts[f"{name}.kicad_dru"] = dru.write_rules(
            ruleset, target=target, allow_lossy=True, issues=issues, downgrade=True, edits=found
        )
        edits += [dataclasses.replace(edit, file=f"{name}.kicad_dru") for edit in found]
    files: dict[str, bytes] = {key: text.encode("utf-8") for key, text in texts.items()}
    written_triad = set(files)
    sheets = 0
    for key, path in sorted(source.files.items()):
        out = _renamed(key, source, name)
        if out in written_triad or key in (project_name, rules_name, f"{source.name}.kicad_pcb"):
            continue
        if key.endswith(SCHEMATIC_SUFFIX):
            sheet = sch.read_schematic(path, file=key)
            found = []
            text = sch.retarget_schematic(
                sheet, target=target, downgrade=True, allow_lossy=True, issues=issues, edits=found
            )
            files[out] = text.encode("utf-8")
            edits += [dataclasses.replace(edit, file=out) for edit in found]
            sheets += 1
        elif key.endswith(SYMBOL_SUFFIX) and path.is_file():
            found = []
            text = sym.retarget_symbol_library(
                _text(path.read_bytes()), target=target, downgrade=True, allow_lossy=True, file=key,
                issues=issues, edits=found,
            )  # fmt: skip
            files[out] = text.encode("utf-8")
            edits += [dataclasses.replace(edit, file=out) for edit in found]
        elif key.endswith(LIBRARY_FOLDER) and path.is_dir():
            files.update(_footprints(key, path, target, issues, edits))
        elif path.is_file():
            files[out] = path.read_bytes()
    counts = census(design)
    if sheets:
        counts[SCHEMATIC] = sheets
    changed: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    lost: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for edit in edits:
        into = changed if edit.action in resolver.CHANGED else lost
        into[DOWNGRADE_PREFIX + edit.row][REASONS[edit.action]].append(f"{edit.file}:{edit.where}")
    report = ConversionReport.of(
        source=counts,
        changed={kind: {r: tuple(ids) for r, ids in reasons.items()} for kind, reasons in changed.items()},
        lost={kind: {r: tuple(ids) for r, ids in reasons.items()} for kind, reasons in lost.items()},
    )
    return Written(
        dict(sorted(files.items())),
        report,
        design,
        f"{name}.kicad_pcb",
        tuple(issues),
        schematic=f"{name}{SCHEMATIC_SUFFIX}" if f"{name}{SCHEMATIC_SUFFIX}" in files else None,
        profile=DOWNGRADE_PROFILE,
        evidence=DOWNGRADE_EVIDENCE,
    )


def _footprints(
    key: str, folder: Path, target: int, issues: list[Issue], edits: list[resolver.Edit]
) -> dict[str, bytes]:
    """The footprints of the library folder ``key``, each written for ``target``; any other file of the
    folder copied."""
    found: dict[str, bytes] = {}
    for path in sorted(folder.iterdir()):
        out = f"{key}/{path.name}"
        if path.suffix == FOOTPRINT_SUFFIX and path.is_file():
            defn = read_footprint(path, library=folder.stem)
            mine: list[resolver.Edit] = []
            text = write_footprint(
                defn, target=target, allow_lossy=True, issues=issues, downgrade=True, edits=mine
            )
            found[out] = text.encode("utf-8")
            edits += [dataclasses.replace(edit, file=out) for edit in mine]
        elif path.is_file():
            found[out] = path.read_bytes()
    return found


DIRECTION = Direction(
    source=KICAD,
    target=KICAD,
    write=write,
    evidence=EVIDENCE,
    experimental=False,
    profile=PROFILE,
    targets=TARGET_MAJORS,
    kinds=WRITER_KINDS,
    downgrade=True,
)

__all__ = ["DIRECTION", "DOWNGRADE_PROFILE", "EVIDENCE", "PROFILE", "WRITER_KINDS", "write"]


if TYPE_CHECKING:
    from fenolite.convert.altium_to_kicad import Ledger

EDGE_LAYER = "Edge.Cuts"
HOLE_KIND = "hole"
CUTOUT_KIND = "cutout"
PLATED_REASON = "a plated hole is written as a pad of its footprint without a net"
"""The reason a plated board hole is counted changed under ``hole`` (change c0170): KiCad holds it as the
numbered pad of a generated footprint, which no net reaches."""
MERGED_REASON = "merged"
"""The reason a group of overlapping cut-outs is counted changed under ``cutout`` (change c0170): it is
written as one ring, the union of its members, which is the area that is milled."""
HOLE_FOLDER = f"lib/{model_holes.HOLE_LIBRARY}.pretty"
"""Where the generated hole footprints are written beside the board, as a build writes those of
``design.hole`` (its ``fp-lib-table`` row ``${KIPRJMOD}/lib/Fenolite_Holes.pretty``)."""
HOLE_ATTRIBUTES: tuple[FootprintAttribute, ...] = ("board_only", "exclude_from_pos_files", "exclude_from_bom")
"""The attributes of a generated hole footprint of a conversion: its definition's flags, and
``board_only``, because the generated schematic holds no symbol for a hole."""


MICRON = 1_000


def metric(value: int) -> int:
    """``value``, an imported Altium length, as the whole micrometre that the document's binary unit
    (2.54 nm) cannot tell from it, else unchanged (change c0170): a hole of 1 mm is read as 1 000 001 nm,
    and its footprint is then ``NPTH_1mm``, the name a script gives it. The written length maps to the
    same binary units as the read one (``pcbrecords.to_units``), so nothing the document holds changes."""
    whole = (value + MICRON // 2) // MICRON * MICRON
    return whole if whole > 0 and to_units(whole) == to_units(value) else value


def _instance(
    hole: Hole, definition: FootprintDef, copper: tuple[str, ...]
) -> tuple[FootprintInstance, Component]:
    """The board-only instance of ``definition`` at ``hole``, turned by its rotation, with its component,
    placed as a build places the footprint of ``design.hole`` (``embed.place_footprint``: its fields, its
    courtyards and its pad as the library holds them). Its ids and uuids follow from the hole's id."""
    key = f"generated:{hole.id}"
    lib_ref = f"{definition.library}:{definition.name}"
    component = Component(
        id=derived_id("cmp", ALTIUM, key),
        provenance=hole.provenance,
        ref="",
        value=definition.name,
        lib_footprint_ref=lib_ref,
    )
    placed = place_footprint(
        prepare_authored_definition(definition),
        component=component,
        at=hole.position,
        rotation=hole.rotation % FULL_TURN,
        locked=True,
        key=key,
        copper=copper,
    )
    # no provenance: the writer keeps the design's order of footprints without one (c0161's created
    # content), which ``footprint_files`` pairs with the written board's
    footprint = dataclasses.replace(placed, id=derived_id("fp", ALTIUM, key), attributes=HOLE_ATTRIBUTES)
    return footprint, component


def generated_holes(design: Design) -> tuple[Design, dict[str, FootprintDef], tuple[str, ...]]:
    """``design`` with each board ``Hole`` as a board-only footprint of the definition that
    ``design.hole`` generates (``model.holes.hole_footprint``; capability kicad-file-backend, "Board holes
    as generated footprints in a conversion"; change c0170), placed at the hole and turned by its rotation;
    each length taken to the whole micrometre the document cannot tell from it (``metric``);
    the definitions by name, for the library written beside the board; and the ids of the plated holes,
    whose copper is the hole itself (a pad without a net). KiCad refuses ``Board.holes`` (c0167)."""
    board = design.board
    if board is None or not board.holes:
        return design, {}, ()
    definitions: dict[str, FootprintDef] = {}
    footprints: list[FootprintInstance] = []
    components: list[Component] = []
    plated: list[str] = []
    copper = tuple(
        layer.name for layer in sorted(board.layers, key=lambda item: item.ordinal) if layer.kind == "copper"
    )
    for hole in board.holes:
        length = metric(hole.length) if hole.length is not None else None
        definition = model_holes.hole_footprint(metric(hole.drill), length=length, plated=hole.plated)
        definitions.setdefault(definition.name, definition)
        footprint, component = _instance(hole, definition, copper)
        footprints.append(footprint)
        components.append(component)
        if hole.plated:
            plated.append(hole.id)
    return (
        dataclasses.replace(
            design,
            circuit=dataclasses.replace(design.circuit, components=(*design.circuit.components, *components)),
            board=dataclasses.replace(board, footprints=(*board.footprints, *footprints), holes=()),
        ),
        dict(sorted(definitions.items())),
        tuple(plated),
    )


def _where(names: tuple[int, ...]) -> str:
    """``cutout/<k>`` of each cut-out of a group, joined by ``+`` (the ``where`` of the Altium direction)."""
    return "+".join(f"cutout/{k + 1}" for k in names)


def merged_cutouts(design: Design, ledger: Ledger) -> tuple[Design, int]:
    """``design`` whose overlapping edge rings are merged (change c0170), with the number of cut-out items
    (a group of overlapping rings counts once). The edges are taken with ``edge_outline``; when two inner
    rings overlap, each group is united (``merge_groups``) and the board gets the model outline of the
    board ring and every inner ring, its edge graphics replaced, each group counted ``changed`` with
    ``MERGED_REASON``. A group that cannot be united is not written and is a ``refuse`` loss
    (``report.OVERLAP_NO_UNION``, ``OVERLAP_NOT_ONE_RING``): KiCad calls overlapping rings a malformed
    outline. Without an overlap the edges are written as read."""
    board = design.board
    if board is None or board.outline is not None:
        return design, 0
    edges = edge_outline(design)
    if edges is None or not edges.cutouts:
        return design, 0
    mids = {(arc.ring, arc.edge): arc.mid for arc in edges.arcs}
    rings = [
        CurvedRing(tuple(ring), tuple(mids.get((r, k)) for k in range(len(ring))))
        for r, ring in enumerate(edges.cutouts, start=1)
    ]
    groups = overlap_groups(rings, tol=MERGE_TOL)
    if all(len(group) == 1 for group in groups):
        return design, len(groups)
    kept: list[CurvedRing] = []
    for group in groups:
        if len(group) == 1:
            kept.append(rings[group[0]])
            continue
        where = _where(group)
        try:
            (merged,) = merge_groups([rings[i] for i in group], tol=MERGE_TOL, names=where.split("+"))
        except BackendUnavailable:
            ledger.drop(CUTOUT_KIND, where, OVERLAP_NO_UNION)
            continue
        except GeometryError:
            ledger.drop(CUTOUT_KIND, where, OVERLAP_NOT_ONE_RING)
            continue
        ledger.change(CUTOUT_KIND, where, MERGED_REASON)
        kept.append(merged.ring)
    outer = tuple(edges.points)
    arcs = [OutlineArc(0, k, mid) for k in range(len(outer)) if (mid := mids.get((0, k))) is not None]
    for r, ring in enumerate(kept, start=1):
        arcs += [OutlineArc(r, k, mid) for k, mid in enumerate(ring.mids) if mid is not None]
    outline = dataclasses.replace(
        edges, cutouts=tuple(ring.points for ring in kept), arcs=tuple(arcs), slots=()
    )
    layers = {layer.name for layer in board.layers if layer.kind == "edge"} or {EDGE_LAYER}
    graphics = tuple(graphic for graphic in board.graphics if graphic.layer not in layers)
    board = dataclasses.replace(board, outline=outline, graphics=graphics)
    return dataclasses.replace(design, board=board), len(groups)


def write_altium(source: SourceProject, options: Options) -> Written:
    """Altium to a coherent KiCad project and derived libraries (c0161). Overlapping cut-outs are merged
    (``merged_cutouts``), and each board hole is the generated footprint of ``design.hole``
    (``generated_holes``), its library written beside the board (change c0170)."""
    from fenolite.convert.altium_to_kicad import Ledger, footprint_files, prepare, schematic_files

    ledger = Ledger()
    counts = census(source.design)
    merged, cutouts = merged_cutouts(source.design, ledger)
    if cutouts:
        counts[CUTOUT_KIND] = cutouts
    board = merged.board
    holes = board.holes if board is not None else ()
    if board is not None:
        merged = dataclasses.replace(merged, board=dataclasses.replace(board, holes=()))
    source = dataclasses.replace(source, design=merged)
    name = options.name or source.name
    design = prepare(source, name, options.kicad_version, ledger)
    # the holes join the prepared board as placed footprints, which ``prepare`` would derive and clean
    assert design.board is not None
    design, holes, plated = generated_holes(
        dataclasses.replace(design, board=dataclasses.replace(design.board, holes=holes))
    )
    for ident in plated:
        ledger.change(HOLE_KIND, ident, PLATED_REASON)
    issues: list[Issue] = []
    texts = write_triad(design, name=name, target=options.kicad_version, allow_lossy=True, issues=issues)
    texts.update(
        footprint_files(design, texts[f"{name}.kicad_pcb"], name, options.kicad_version, ledger, holes=holes)
    )
    for key, definition in holes.items():
        texts[f"{HOLE_FOLDER}/{key}{FOOTPRINT_SUFFIX}"] = write_footprint(
            definition, target=options.kicad_version
        )
    schematic, notes = schematic_files(source, design, name, options.kicad_version, ledger)
    texts.update(schematic)
    issues.extend(notes)
    counts["schematic"] = 1
    unmapped = [issue for issue in source.issues if issue.code == "altium.import.rule-unmapped"]
    counts["rule"] = counts.get("rule", 0) + len(unmapped)
    for index, issue in enumerate(unmapped):
        ledger.drop("rule", f"unmapped-rule-group-{index}", f"unmapped imported rule group: {issue.message}")
    report = ConversionReport.of(
        source=counts,
        changed={
            kind: {r: tuple(ids) for r, ids in reasons.items()} for kind, reasons in ledger.changed.items()
        },
        lost={kind: {r: tuple(ids) for r, ids in reasons.items()} for kind, reasons in ledger.lost.items()},
    )
    return Written(
        {key: value.encode("utf-8") for key, value in sorted(texts.items())},
        report,
        design,
        f"{name}.kicad_pcb",
        tuple(issues),
        schematic=f"{name}.kicad_sch" if schematic else None,
    )


ALTIUM_EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-K-CONV-A2K-LOAD",
        "H-K-CONV-A2K-IMPORT",
        "H-K-CONV-A2K-SCH",
        "H-K-BOARD-USERLAYERS",
        "H-A-IMP-KEEPOUT-LAYER",
    ),
)
ALTIUM_DIRECTION = Direction(
    source="altium",
    target=KICAD,
    write=write_altium,
    evidence=ALTIUM_EVIDENCE,
    experimental=True,
    profile="altium-to-kicad",
    targets=TARGET_MAJORS,
    kinds=("schematic", HOLE_KIND, CUTOUT_KIND),
)
