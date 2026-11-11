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
from collections import Counter, defaultdict
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from fenolite.backends.altium.adapter.arcring import ArcPolygon
from fenolite.backends.altium.pcbrecords import to_units
from fenolite.backends.kicad import dru, resolver, sch, sym
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.mod import prepare_authored_definition, read_footprint, write_footprint
from fenolite.backends.kicad.outline import edge_outline
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import TARGET_MAJORS
from fenolite.convert import altium_frame, strokefonts, texttails
from fenolite.convert.arrays import ArrayItem, Copies, copies
from fenolite.convert.direction import Direction, Options, Written
from fenolite.convert.models import Placed, place_models
from fenolite.convert.report import (
    DOWNGRADE_KINDS,
    DOWNGRADE_PREFIX,
    EMBEDDED_BOARD_CUTOUT_COPIED,
    OVERLAP_NO_UNION,
    OVERLAP_NOT_ONE_RING,
    ConversionReport,
    census,
)
from fenolite.convert.sources import KICAD, SourceProject
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.trig import FULL_TURN
from fenolite.geometry.errors import BackendUnavailable, GeometryError
from fenolite.geometry.rings import MERGE_TOL, CurvedRing, merge_groups, overlap_groups
from fenolite.model import holes as model_holes
from fenolite.model.board import (
    FootprintAttribute,
    FootprintInstance,
    Hole,
    ModelRef,
    OutlineArc,
)
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.model.library import PPM, FootprintDef, ModelPlacement

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
    from fenolite.convert import altium_planes
    from fenolite.convert.altium_to_kicad import Ledger
    from fenolite.convert.rulecarrier import Carried

EDGE_LAYER = "Edge.Cuts"
HOLE_KIND = "hole"
CUTOUT_KIND = "cutout"
EMBEDDED_BOARD_KIND = "embedded-board"
SHARED_FOOTPRINT_KIND = "shared-footprint"
SHARED_FOOTPRINT_REASON = "the source links several footprints to one component"
PAD_MARGIN_KIND = "pad-margin"
"""The report kind of an imported pad whose margin is not certain (change c0223, ``convert.openings``)."""
FOOTPRINT_GRAPHIC_KIND = "footprint-graphic"
"""The report kind of a line, arc, circle, rectangle or region of an imported footprint (change c0409): the
footprint's own graphics, written as its ``fp_*`` children on the layer ``map_layers`` gives them."""
FOOTPRINT_TEXT_KIND = "footprint-text"
"""The report kind of a text of an imported footprint that is not its designator or comment (change c0409):
since change c0422 written as an ``fp_text user`` of its footprint on the layer ``map_layers`` gives it."""
MODEL_KIND = "model"
"""The report kind of an embedded 3D model of an imported footprint (change c0223, ``convert.models``)."""
BODY_KIND = "body"
"""The report kind of a component body (change c0423, ``convert.models``): a generated or carried model."""
PLATED_REASON = "a plated hole is written as a pad of its footprint without a net"
"""The reason a plated board hole is counted changed under ``hole`` (change c0170): KiCad holds it as the
numbered pad of a generated footprint, which no net reaches."""
HOLE_REASON = "a board hole is written as a board-only footprint of the Fenolite_Holes library"
"""The reason an unplated board hole is counted changed under ``hole`` (change c0420): KiCad holds no hole
outside a footprint (c0167), so the hole is the unnumbered pad of a generated footprint
(``generated_holes``), a component without a reference that the generated schematic does not show."""
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


def _carried_rules(source: SourceProject, design: Design, rules_text: str | None) -> tuple[Carried, ...]:
    """Every rule record of the source's PCB document with the rule lists of ``rules_text`` that its rules
    gave (change c0434, ``rulecarrier``); none when the document cannot be read or holds no rule."""
    from fenolite.backends.altium.adapter.rules import kept_fields, kept_text
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.backends.kicad.lowering import written_names
    from fenolite.convert.altium_to_kicad import board_document
    from fenolite.convert.rulecarrier import Carried, dru_blocks, dru_shapes

    path = board_document(source, source.design)
    if path is None:
        return ()
    try:
        records = read_pcbdoc(path.read_bytes(), file=path.name).rules
    except (OSError, FormatError):
        return ()
    names: dict[int, list[str]] = {}
    if design.rules is not None and source.design.rules is not None:
        # the prepared rules keep their ids, not their provenance: the source's rules name the record
        written = written_names(design.rules, design)
        for rule in source.design.rules.rules:
            locator = rule.provenance.locator if rule.provenance is not None else ""
            head, _, index = locator.partition("#")
            if head.endswith("/Data") and index.isdigit():
                names.setdefault(int(index), []).extend(written.get(rule.id, ()))
    blocks, shapes = dru_blocks(rules_text), dru_shapes(rules_text)
    carried: list[Carried] = []
    for index, record in enumerate(records):
        fields = tuple(record.record.fields)
        if "RULEKIND" not in [key for key, _value in fields]:
            continue
        number, pairs = kept_fields(kept_text(record.kind_number, fields))
        held = {n: blocks[n] for n in names.get(index, ()) if n in blocks}
        carried.append(Carried(number, pairs, held, {n: shapes[n] for n in held}))
    return tuple(carried)


def write_altium(source: SourceProject, options: Options) -> Written:
    """Altium to a coherent KiCad project and derived libraries (c0161). Overlapping cut-outs are merged
    (``merged_cutouts``), and each board hole is the generated footprint of ``design.hole``
    (``generated_holes``), its library written beside the board (change c0170)."""
    from fenolite.backends.altium.read.cfb import holds_embedded_boards
    from fenolite.convert.altium_to_kicad import (
        PLANE_KIND,
        ZONE_ARC_FLAT,
        ZONE_NO_AREA,
        Ledger,
        board_document,
        distinct_designators,
        footprint_files,
        plane_losses,
        prepare,
    )

    ledger = Ledger()
    arrays: tuple[ArrayItem, ...] = ()
    copied = Copies(source.design, ())
    document = board_document(source, source.design)
    if document is not None and holds_embedded_boards(data := document.read_bytes()):  # change c0374
        copied = copies(document, data, source.design, source.root)  # changes c0386 and c0428: the copies
        arrays = copied.items
        source = dataclasses.replace(source, design=copied.design)
    counts = census(source.design)
    planes = plane_losses(source, source.design, ledger)  # change c0461: no plane has copper in KiCad
    if planes:
        counts[PLANE_KIND] = planes
    if arrays:
        counts[EMBEDDED_BOARD_KIND] = len(arrays)
    for entry in arrays:
        (ledger.change if entry.placed else ledger.drop)(EMBEDDED_BOARD_KIND, entry.item, entry.reason)
    for ident in copied.outlined:  # change c0428: a copy's zones take their records' outlines
        ledger.change("zone", ident, ZONE_ARC_FLAT)
    for ident, why in copied.dropped:  # a pour without area is left out as a change (change c0428)
        (ledger.change if why == ZONE_NO_AREA else ledger.drop)("zone", ident, why)
    if copied.dropped:
        counts["zone"] = counts.get("zone", 0) + len(copied.dropped)
    for ident in copied.cutouts:  # change c0428: a copy carries its board's cut-outs
        ledger.change(CUTOUT_KIND, ident, EMBEDDED_BOARD_CUTOUT_COPIED)
    source_board = source.design.board
    if source_board is not None:  # change c0223: the openings and the models of the imported footprints
        counts[PAD_MARGIN_KIND] = sum(len(fp.pads) for fp in source_board.footprints)
        bodies = [body for fp in source_board.footprints for body in fp.bodies]
        counts[MODEL_KIND] = sum(1 for body in bodies if body.kind == "model")
        # the footprints' own graphics (change c0409) and texts (change c0422) are counted and written
        counts[FOOTPRINT_GRAPHIC_KIND] = sum(len(fp.graphics) for fp in source_board.footprints)
        counts[FOOTPRINT_TEXT_KIND] = sum(len(fp.texts) for fp in source_board.footprints)
        # change c0371: a component that several footprints link reads back as several components
        linked = Counter(fp.component_id for fp in source_board.footprints)
        shared = [fp.id for fp in source_board.footprints if linked[fp.component_id] > 1]
        if shared:
            counts[SHARED_FOOTPRINT_KIND] = len(shared)
            for ident in shared:
                ledger.change(SHARED_FOOTPRINT_KIND, ident, SHARED_FOOTPRINT_REASON)
    merged, cutouts = merged_cutouts(source.design, ledger)
    if cutouts or copied.cutouts:
        counts[CUTOUT_KIND] = max(cutouts, len(copied.cutouts))
    board = merged.board
    holes = board.holes if board is not None else ()
    if board is not None:
        merged = dataclasses.replace(merged, board=dataclasses.replace(board, holes=()))
    source = dataclasses.replace(source, design=merged)
    name = options.name or source.name
    design = prepare(source, name, options.kicad_version, ledger)
    assert design.board is not None
    carried_storages = _carried_storages(source, design, ledger, counts)  # change c0450
    # the holes join the prepared board as placed footprints, which ``prepare`` would derive and clean
    assert design.board is not None
    design, holes, plated = generated_holes(
        dataclasses.replace(design, board=dataclasses.replace(design.board, holes=holes))
    )
    for hole in board.holes if board is not None else ():  # change c0420: no hole changes kind unreported
        ledger.change(HOLE_KIND, hole.id, PLATED_REASON if hole.id in plated else HOLE_REASON)
    issues: list[Issue] = []
    placed = _placed_models(source, design, name, copied)
    design = _with_models(design, placed.placements)  # change c0409: the board's footprints hold them too
    texts = write_triad(design, name=name, target=options.kicad_version, allow_lossy=True, issues=issues)
    texts.update(
        footprint_files(
            design,
            texts[f"{name}.kicad_pcb"],
            name,
            options.kicad_version,
            ledger,
            holes=holes,
            placements=placed.placements,
        )
    )
    used = {p.path.removeprefix("${KIPRJMOD}/") for key, text in texts.items() for p in placed_in(text, key)}
    model_files = {path: data for path, data in placed.files.items() if path in used}
    for body, reason in placed.changed.items():
        ledger.change(MODEL_KIND, body, reason)
    for body, reason in placed.lost.items():
        ledger.drop(MODEL_KIND, body, reason)
    for body, reason in placed.bodies_changed.items():  # change c0423: every body is a model file or a loss
        ledger.change(BODY_KIND, body, reason)
    for body, reason in placed.bodies_lost.items():
        ledger.drop(BODY_KIND, body, reason)
    for key, definition in holes.items():
        texts[f"{HOLE_FOLDER}/{key}{FOOTPRINT_SUFFIX}"] = write_footprint(
            definition, target=options.kicad_version
        )
    design = distinct_designators(design, ledger)  # change c0428: after the board is written
    schematic, notes, carried_documents = _drawing_files(
        source, design, name, options.kicad_version, ledger, counts
    )
    model_files.update(carried_documents)  # change c0483: the documents Fenolite does not model
    texts.update(schematic)
    issues.extend(notes)
    counts["schematic"] = 1
    from fenolite.convert import altium_rules  # change c0424: each rule record has its own fate

    records = altium_rules.record_fates(source.design, ledger)
    if records:
        counts["rule"] = counts.get("rule", 0) + records
    carried = _carried_rules(source, design, texts.get(f"{name}.kicad_dru"))
    board_items = dict(carried_storages)
    # change c0449, task 4.3: the stored heights of each placed model, for the way back; c0464: the layers
    if placed.heights or placed.layers:
        from fenolite.convert.models import HEIGHTS_PROPERTY, heights_text

        board_items[HEIGHTS_PROPERTY] = heights_text(placed.heights, placed.layers).encode("utf-8")
    if placed.ids:  # change c0449: each placed model's record ID and checksums, for the way back
        from fenolite.convert.models import IDS_PROPERTY, ids_text

        board_items[IDS_PROPERTY] = ids_text(placed.ids).encode("utf-8")
    if placed.kept:  # change c0484: the source records of each generated model's bodies, for the way back
        from fenolite.convert.models import BODIES_PROPERTY, bodies_text, kept_key

        written = {fp.id: fp for fp in design.board.footprints} if design.board is not None else {}
        board_items[BODIES_PROPERTY] = bodies_text(
            (kept_key(sha, written[ident]), pairs) for ident, sha, pairs in placed.kept if ident in written
        ).encode("utf-8")
    arcs = _carried_arcs(source, design)
    if arcs:  # change c0463, task 1.3: the arc vertices of each chorded polygon, for the way back
        from fenolite.convert import zonearcs

        board_items[zonearcs.PROPERTY] = zonearcs.carrier_text(arcs).encode("utf-8")
    pours = _carried_pours(source, design)
    if pours:  # change c0482: the poured regions of each polygon, for the way back
        from fenolite.convert import zonepours

        board_items[zonepours.PROPERTY] = zonepours.carrier_text(pours).encode("utf-8")
    from fenolite.convert import straightarcs

    straight = straightarcs.found(source.design)
    if straight:  # change c0485: the record of each arc that draws a straight track, for the way back
        board_items[straightarcs.PROPERTY] = straightarcs.carrier_text(straight).encode("utf-8")
    planes = _carried_planes(source, design)
    if (
        planes.planes or planes.signals or planes.names
    ):  # change c0466: each plane's net, pull-back and splits, and the
        # inner signal layers' ids, for the way back
        from fenolite.convert import altium_planes

        board_items[altium_planes.PROPERTY] = altium_planes.carrier_text(planes).encode("utf-8")
    fonts = strokefonts.found(source.design.board)
    if fonts:  # change c0460, S-2253: each stroke text's font name and flags, for the way back
        board_items[strokefonts.PROPERTY] = strokefonts.carrier_text(fonts)
    tails = texttails.found(source.design.board)
    if tails:  # change c0450, task 4.5: the long form of each text on Mechanical 17 to 32, for the way back
        board_items[texttails.PROPERTY] = texttails.carrier_text(tails)
    frame = altium_frame.found(source.design.board, design.board)
    if frame is not None:  # change c0467: the source's origin and the edge's corner, for the way back
        board_items[altium_frame.PROPERTY] = altium_frame.carrier_text(frame).encode("utf-8")
    if carried:  # change c0434: every rule record travels in the board, for the way back
        from fenolite.convert import rulecarrier

        board_items[rulecarrier.PROPERTY] = rulecarrier.carrier_text(carried).encode("utf-8")
    if board_items:  # changes c0434 and c0450: one write of every carried board property
        from fenolite.backends.kicad.boardcarrier import with_carried

        texts[f"{name}.kicad_pcb"] = with_carried(texts[f"{name}.kicad_pcb"], board_items)
    report = ConversionReport.of(
        source=counts,
        changed={
            kind: {r: tuple(ids) for r, ids in reasons.items()} for kind, reasons in ledger.changed.items()
        },
        lost={kind: {r: tuple(ids) for r, ids in reasons.items()} for kind, reasons in ledger.lost.items()},
        kept={kind: {r: tuple(ids) for r, ids in reasons.items()} for kind, reasons in ledger.kept.items()},
    )
    files = {key: value.encode("utf-8") for key, value in texts.items()}
    files.update(model_files)
    return Written(
        dict(sorted(files.items())),
        report,
        design,
        f"{name}.kicad_pcb",
        tuple(issues),
        schematic=f"{name}.kicad_sch" if schematic else None,
    )


def _drawing_files(
    source: SourceProject, design: Design, name: str, target: int, ledger: Ledger, counts: dict[str, int]
) -> tuple[dict[str, str], tuple[Issue, ...], dict[str, bytes]]:
    """The KiCad schematic of an Altium source: its own drawing (change c0470, ``convert.schematic``) when
    the project holds sheets and the drawing can be written, else the schematic generated from the circuit
    (``altium_to_kicad.schematic_files``), whose row says why. A circuit that holds a designator twice keeps
    the generated schematic too: a drawing names its symbols by component path, and the generator's
    renaming of a duplicate (change c0425) is the reported way to write that circuit. So does a circuit
    with a part that no sheet draws and no board places. With the drawing come the bytes of the source's
    documents that Fenolite does not model (``schematic.carried_documents``, change c0483)."""
    from collections import Counter

    from fenolite.convert import codes
    from fenolite.convert import schematic as drawing_lib
    from fenolite.convert.altium_to_kicad import schematic_files

    drawing = drawing_lib.drawing_of(source)
    if drawing is None:
        return (*schematic_files(source, design, name, target, ledger), {})
    # a designator held twice by parts of the board alone names no symbol of the drawing (change c0470)
    undrawn = {c.id for c in drawing_lib.undrawn(drawing.extracted.drawn, source.design.circuit)}
    board = source.design.board
    placed = {fp.component_id for fp in board.footprints} if board is not None else set[str]()
    refs = Counter(c.ref for c in source.design.circuit.components if c.ref and c.id not in undrawn)
    # a part that neither a sheet draws nor the board places would be written nowhere: generated too
    if any(count > 1 for count in refs.values()) or undrawn - placed:
        return (*schematic_files(source, design, name, target, ledger), {})
    links = drawing_lib.links_of(source.design)  # ``prepare`` keeps no native ids
    written = drawing_lib.write_kicad_drawing(drawing, design, name, target, links)
    errors = [i for i in (*drawing.extracted.issues, *written.issues) if i.severity == "error"]
    if errors or not written.files:
        files, notes = schematic_files(source, design, name, target, ledger)
        reason = f"{codes.DRAWING_REFUSED}: {errors[0].message}" if errors else codes.DRAWING_REFUSED
        ledger.change("schematic", design.header.id, reason)
        return files, (*notes, *(dataclasses.replace(i, severity="warning") for i in errors)), {}
    source_counts, changes = drawing_lib.drawing_rows(drawing, written)
    for kind, count in source_counts.items():
        counts[kind] = counts.get(kind, 0) + count
    for kind, item, reason in changes:
        ledger.change(kind, item, reason)
    for component in drawing_lib.undrawn(drawing.extracted.drawn, design.circuit):
        ledger.change("schematic", component.id, codes.DRAWING_BOARD_ONLY)
    notes = tuple(i for i in (*drawing.extracted.issues, *written.issues) if i.severity != "error")
    return dict(written.files), notes, drawing_lib.carried_documents(source)


def _carried_planes(source: SourceProject, design: Design) -> altium_planes.Carried:
    """The internal planes of the source to carry into ``design``, the written KiCad design (change c0466,
    ``altium_planes.found``)."""
    from fenolite.convert import altium_planes
    from fenolite.convert.altium_to_kicad import pcb_document

    return altium_planes.found(source.design, design, pcb_document(source, source.design))


def _carried_arcs(source: SourceProject, design: Design) -> list[tuple[str, str, ArcPolygon]]:
    """The arc polygons of the source's board document whose zones the written board holds (change c0463,
    task 1.3; ``altium_to_kicad.arc_zones``), each as ``(KiCad uuid, UNIQUEID, polygon)`` for
    ``zonearcs.carrier_text``."""
    from fenolite.backends.kicad.pcb import kicad_uuid
    from fenolite.convert.altium_to_kicad import arc_zones

    board = design.board
    found = arc_zones(source, source.design)
    if board is None or not found:
        return []
    return [(kicad_uuid(zone), *found[zone.id]) for zone in board.zones if zone.id in found]


def _carried_pours(source: SourceProject, design: Design) -> list[tuple[str, Any]]:
    """The pours of the source's board document whose zones the written board holds (change c0482;
    ``altium_to_kicad.pour_zones``), each as ``(KiCad uuid, pour)`` for ``zonepours.carrier_text``."""
    from fenolite.backends.kicad.pcb import kicad_uuid
    from fenolite.convert.altium_to_kicad import pour_zones

    board = design.board
    found = pour_zones(source, source.design)
    if board is None or not found:
        return []
    return [(kicad_uuid(zone), found[zone.id]) for zone in board.zones if zone.id in found]


def _carried_storages(
    source: SourceProject, design: Design, ledger: Ledger, counts: dict[str, int]
) -> dict[str, bytes]:
    """The carried storages of the source's PCB document as ``boardcarrier.with_carried`` items, by property
    name (change c0450, ``convert.altium_storages``); each index-bound storage that holds a record, and each
    frame-bound one that holds data (change c0459), is counted lost under ``altium-storage``. A document that
    cannot be read carries nothing."""
    from fenolite.backends.altium import unions
    from fenolite.convert import altium_storages as storages
    from fenolite.convert.altium_to_kicad import board_document
    from fenolite.core.errors import FenoliteError

    board = design.board
    path = board_document(source, source.design)
    if board is None or path is None:
        return {}
    try:
        found = storages.found_in(path)
    except (OSError, FenoliteError):
        return {}
    if not found.carried and not found.index_bound and not found.frame_bound:
        return {}
    # change c0464: the Board6 settings are fields of a record, not a storage, and are not counted
    held = [name for name in found.carried if name != storages.PREFIX + storages.SETTINGS]
    if held or found.index_bound or found.frame_bound:
        counts[storages.KIND] = len(held) + len(found.index_bound) + len(found.frame_bound)
    for name in found.index_bound:
        ledger.drop(storages.KIND, name, storages.INDEX_BOUND_REASON)
    for name in found.frame_bound:  # change c0459: a copy would lie in the source's frame
        ledger.drop(storages.KIND, name, storages.FRAME_BOUND[name])
    items = storages.items(found)
    members = unions.members(source.design.board)
    if storages.PREFIX + "UnionNames" in found.carried and members:  # change c0460: the union members
        items[storages.PREFIX + unions.CARRIER] = unions.carried_map(members)
    return items


def _placed_models(source: SourceProject, design: Design, name: str, copied: Copies | None = None) -> Placed:
    """The embedded models of the source board's bodies, placed for the derived library ``name`` (change
    c0223, ``convert.models``), and a generated model per footprint for its other bodies (change c0423);
    none when the source has no board. The bodies of an array's copies take the models of their referenced
    document, in the frame of the footprint they were copied from (change c0428)."""
    from fenolite.backends.altium.backend import AltiumBackend
    from fenolite.backends.altium.models3d import body_records
    from fenolite.convert.altium_to_kicad import board_document

    board, prepared = source.design.board, design.board
    if board is None or prepared is None:
        return Placed()
    document = board_document(source, source.design)
    backend = AltiumBackend()
    names = {fp.id: fp.lib_ref.rsplit(":", 1)[-1] for fp in prepared.footprints}
    return place_models(
        board.footprints,
        backend.body_models(document) if document is not None else (),
        name,
        lambda fp: names.get(fp.id, fp.lib_ref.rsplit(":", 1)[-1]),
        backend.body_forms(document) if document is not None else (),
        {
            file: (backend.body_models(path), backend.body_forms(path))
            for file, path in (copied or Copies(source.design, ())).documents.items()
            if document is None or path.name != document.name
        },
        copied.frames if copied is not None else None,
        body_records(document) if document is not None else None,  # change c0484
    )


def _scale_text(ppm: int) -> str:
    """A scale in ppm as the decimal a ``ModelRef`` holds: 1 000 000 → ``"1"``, 1 250 000 → ``"1.25"``."""
    return format((Decimal(ppm) / PPM).normalize(), "f")


def _with_models(design: Design, placements: Mapping[str, tuple[ModelPlacement, ...]]) -> Design:
    """``design`` whose board footprints hold the models ``placements`` gives them (change c0409, B9): the
    board writes them as its footprints' ``model`` children, so an import, which derives its library from the
    board, keeps them as the derived library does."""
    board = design.board
    if board is None or not placements:
        return design
    footprints = tuple(
        dataclasses.replace(
            fp,
            models=tuple(
                ModelRef(
                    placement.path,
                    placement.offset,
                    placement.rotation,
                    (
                        _scale_text(placement.scale[0]),
                        _scale_text(placement.scale[1]),
                        _scale_text(placement.scale[2]),
                    ),
                )
                for placement in placements[fp.id]
            ),
        )
        if placements.get(fp.id)
        else fp
        for fp in board.footprints
    )
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=footprints))


def placed_in(text: str, key: str) -> list[ModelPlacement]:
    """The ``model`` paths of a written library footprint ``key`` (``.kicad_mod``) or of the footprints of a
    written board (``.kicad_pcb``, change c0423), as placements."""
    if not key.endswith((".kicad_mod", ".kicad_pcb")):
        return []
    from fenolite.backends.kicad.sexpr import parse

    root = parse(text)
    holders = root.nodes("footprint") if key.endswith(".kicad_pcb") else [root]
    return [
        ModelPlacement(path=child.atoms()[0].value)
        for holder in holders
        for child in holder.nodes("model")
        if child.atoms()
    ]


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
    kinds=("schematic", HOLE_KIND, CUTOUT_KIND, PAD_MARGIN_KIND, MODEL_KIND),
)
