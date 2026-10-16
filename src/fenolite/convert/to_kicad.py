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

from fenolite.backends.kicad import dru, resolver, sch, sym
from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import TARGET_MAJORS
from fenolite.convert.direction import Direction, Options, Written
from fenolite.convert.report import DOWNGRADE_KINDS, DOWNGRADE_PREFIX, ConversionReport, census
from fenolite.convert.sources import KICAD, SourceProject
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.model.board import FootprintInstance, Hole, Pad, Padstack
from fenolite.model.circuit import Component
from fenolite.model.design import Design

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


HOLE_NATIVE = "hole:"
"""The prefix of the native id of a board hole read from an Altium document (``adapter.board.free_hole``)."""


def _free_index(native: str) -> int | None:
    """``i`` of ``fp:pad#i`` or ``hole:pad#i``; ``None`` for another native id."""
    head, _, tail = native.partition("pad#")
    if head not in ("fp:", HOLE_NATIVE) or not tail.split("#")[0].isdigit():
        return None
    return int(tail.split("#")[0])


def _hole_footprint(hole: Hole, native: str, copper: tuple[str, ...]) -> tuple[FootprintInstance, Component]:
    fp_native = "fp:" + native.removeprefix(HOLE_NATIVE)
    pairs = dict(hole.ext[ALTIUM].payload) if ALTIUM in hole.ext else {}
    pad_native = pairs.get("pad") or f"{fp_native}:pad::0"
    slot = hole.length is not None
    stack = None
    if slot:
        stack = Padstack(
            id=derived_id("pst", ALTIUM, f"{pad_native}:stack"),
            native_ids={ALTIUM: f"{pad_native}:stack"},
            provenance=hole.provenance,
            hole_shape="slot",
            hole_length=hole.length,
            hole_rotation=hole.rotation,
        )
    pad = Pad(
        id=derived_id("pad", ALTIUM, pad_native),
        native_ids={ALTIUM: pad_native},
        provenance=hole.provenance,
        number="",
        shape="oval" if slot else "circle",
        size=Size(hole.length if hole.length is not None else hole.drill, hole.drill),
        position=Point(0, 0),
        kind="thru_hole" if hole.plated else "np_thru_hole",
        rotation=hole.rotation if slot else 0,
        drill=hole.drill,
        layers=copper,
        padstack=stack,
    )
    component = Component(
        id=derived_id("cmp", ALTIUM, f"cmp:{fp_native}"),
        native_ids={ALTIUM: f"cmp:{fp_native}"},
        provenance=hole.provenance,
        ref="",
    )
    footprint = FootprintInstance(
        id=derived_id("fp", ALTIUM, fp_native),
        native_ids={ALTIUM: fp_native},
        provenance=hole.provenance,
        component_id=component.id,
        lib_ref="",
        position=hole.position,
        attributes=("board_only",),
        pads=(pad,),
    )
    return footprint, component


def hole_footprints(design: Design) -> Design:
    """``design`` with each board ``Hole`` that the Altium import made of a free pad (change c0168; its
    native id ``hole:pad#<i>``) given back as the board-only footprint of one unnumbered pad that the import
    made of that pad before, with its component, in the order of the pads (capability design-conversion;
    c0168 Decision 6). KiCad refuses ``Board.holes`` (c0167), so a conversion to KiCad writes what it wrote
    before; c0170 replaces this by a generated footprint. Other holes are kept."""
    board = design.board
    if board is None or not board.holes:
        return design
    # the import gave a pad on Multi-Layer every copper layer of the chain, top to bottom
    copper = tuple(
        layer.name for layer in sorted(board.layers, key=lambda item: item.ordinal) if layer.kind == "copper"
    )
    made: list[tuple[int, FootprintInstance, Component]] = []
    kept: list[Hole] = []
    for hole in board.holes:
        native = hole.native_ids.get(ALTIUM, "")
        index = _free_index(native) if native.startswith(HOLE_NATIVE) else None
        if index is None:
            kept.append(hole)
            continue
        footprint, component = _hole_footprint(hole, native, copper)
        made.append((index, footprint, component))
    if not made:
        return design

    # the import put the free pads' footprints and components last, in the order of the pads
    free = [(_free_index(fp.native_ids.get(ALTIUM, "")), fp) for fp in board.footprints]
    rest = [fp for index, fp in free if index is None]
    tail = sorted(
        [(index, fp) for index, fp in free if index is not None] + [(i, fp) for i, fp, _ in made],
        key=lambda pair: pair[0],
    )
    owners = {fp.component_id: index for index, fp in tail}
    components = [*design.circuit.components, *(component for _, _, component in made)]
    placed = [c for c in components if c.id not in owners]
    last = sorted((c for c in components if c.id in owners), key=lambda c: owners[c.id])
    footprints = [*rest, *(fp for _, fp in tail)]
    return dataclasses.replace(
        design,
        circuit=dataclasses.replace(design.circuit, components=(*placed, *last)),
        board=dataclasses.replace(board, footprints=tuple(footprints), holes=tuple(kept)),
    )


def write_altium(source: SourceProject, options: Options) -> Written:
    """Altium to a coherent KiCad project and derived libraries (c0161). The board holes of the import are
    the board-only footprints they were before change c0168 (``hole_footprints``)."""
    from fenolite.convert.altium_to_kicad import Ledger, footprint_files, prepare, schematic_files

    source = dataclasses.replace(source, design=hole_footprints(source.design))
    ledger = Ledger()
    name = options.name or source.name
    design = prepare(source, name, options.kicad_version, ledger)
    issues: list[Issue] = []
    texts = write_triad(design, name=name, target=options.kicad_version, allow_lossy=True, issues=issues)
    texts.update(footprint_files(design, texts[f"{name}.kicad_pcb"], name, options.kicad_version, ledger))
    schematic, notes = schematic_files(source, design, name, options.kicad_version, ledger)
    texts.update(schematic)
    issues.extend(notes)
    counts = census(source.design)
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
    kinds=("schematic",),
)
