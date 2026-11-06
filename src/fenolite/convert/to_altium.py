# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The direction from KiCad to Altium (capability design-conversion, "KiCad to Altium direction" and
"Changes of the Altium direction"; change c0159).

The design read from KiCad keeps the drawings of its footprints and the corner ratios of its pads in
KiCad's own slots, so it is projected first (``fpitems.with_footprint_items``, as ``lens.altium.write_model``
does), then written with ``lower.write_design(..., allow_lossy=True)``: the consent to a loss is the
conversion's, which judges the report. What the write leaves out is mapped per kind and reason into the
report; a polygon written unpoured or poured by Fenolite and the generated schematic are changes, not
losses (the reason of a polygon is that of its pour mode, change c0215). The edges of the
board are given to the write as an outline (``edge_outline``, change c0170): its board ring is the
document's outline and every inner ring a cut-out region, counted under ``cutout``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from fenolite.backends.altium import lower
from fenolite.backends.altium.cfb import CompoundTooLarge
from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.outline import edge_outline
from fenolite.convert import pads, schematic
from fenolite.convert.direction import Direction, Options, TargetLimitError, Written
from fenolite.convert.report import SOURCE_RULE_LOST, ConversionReport, census
from fenolite.convert.sources import ALTIUM, KICAD, SourceProject
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-VER-RTA2-3", "H-A-VER-RTA3", "H-K-CONV-TRIANGLE"))
"""The level of the Altium writers (``lower.EVIDENCE``), with the triangle that checks this direction
(``H-K-CONV-TRIANGLE``, partly confirmed on 2026-10-09: the samples and 14 of 16 demo boards)."""
PROFILE = "kicad-to-altium"
CHANGES: Mapping[str, str] = {
    "zone-fill": "a polygon is written unpoured; Altium fills it on a repour",
    "schematic": "the schematic is generated from the circuit on one sheet with generic symbols",
}
"""The kinds this direction writes in another form, with the reason the report gives them."""
CHANGE_KINDS = frozenset(CHANGES)
ZONE_FILL = "zone-fill"
POURED = "the pour is computed by Fenolite from the written document (experimental)"
"""The reason of a zone whose polygons Fenolite poured (pour mode ``computed``, change c0215); a zone with a
refused polygon keeps the reason of ``CHANGES``."""
WRITER_KINDS: tuple[str, ...] = (
    *lower.KINDS,
    *lower.MORE_KINDS,
    lower.PLACEMENT_RULE_KIND,
    lower.KEEPOUT_FOOTPRINTS_KIND,
)
"""Every kind the Altium write can name: the kinds of its account and its two infos."""
SCHEMATIC = "schematic"
SCHEMATIC_REFUSED = "the schematic writer refuses the circuit: no schematic and no project file are written"
"""The reason of a schematic that is not written; the writer's own message stays an issue of the
conversion (``altium.not-lowered``, where ``schematic``), since it names items of the design."""


def _named(design: Design, name: str | None) -> Design:
    if not name:
        return design
    return dataclasses.replace(design, header=dataclasses.replace(design.header, name=name))


def _extra_losses(design: Design, write: lower.ProjectWrite) -> dict[str, dict[str, tuple[str, ...]]]:
    """The losses that the write reports as infos outside its account: the placement rules, the
    restriction on footprints of a rule area, and a schematic that the writer refused."""
    found: dict[str, dict[str, tuple[str, ...]]] = {}
    for issue in write.issues:
        if issue.code != lower.NOT_LOWERED:
            continue
        if issue.where == lower.PLACEMENT_RULE_KIND and design.rules is not None:
            # a placement rule has no id: its key is its name, and a height limit's its area
            ids = (
                *(f"proximity:{rule.name}" for rule in design.rules.proximity),
                *(f"height:{limit.area}" for limit in design.rules.heights),
            )
            reason = "a placement rule is in no Altium document: fenolite check judges it"
            found[issue.where] = {reason: ids}
        elif issue.where == lower.KEEPOUT_FOOTPRINTS_KIND and design.board is not None:
            ids = tuple(k.id for k in design.board.keepouts if k.no_footprints)
            reason = "the keep-out record holds tracks, vias, pads and copper only, not footprints"
            found[issue.where] = {reason: ids}
        elif issue.where == SCHEMATIC:
            found[issue.where] = {SCHEMATIC_REFUSED: (design.header.id,)}
    return found


def _zone_fills(
    reasons: Mapping[str, tuple[str, ...]], write: lower.ProjectWrite
) -> dict[str, tuple[str, ...]]:
    """The reasons of the kind ``zone-fill`` by the pour of the write: with ``computed``, a zone none of whose
    polygons was refused is poured; every other zone is written unpoured."""
    summary = write.pour.pour if write.pour is not None and write.pour_mode == "computed" else None
    if summary is None or not summary.poured:
        return dict(reasons)
    refused = {zone for _, zone, _ in summary.refused}
    ids = tuple(i for found in reasons.values() for i in found)
    found = {
        CHANGES[ZONE_FILL]: tuple(i for i in ids if i in refused),
        POURED: tuple(i for i in ids if i not in refused),
    }
    return {reason: ids for reason, ids in found.items() if ids}


@dataclasses.dataclass(frozen=True, slots=True)
class _Carried:
    """What the rule records carried beside the project give the way back (change c0434): the design
    without the rules those records give again, the records written as they are, the names of the rules
    that came from a record and were edited in KiCad, and how many rules the records stand for (the rules
    taken out, and one per record that gave none)."""

    design: Design
    records: tuple[tuple[int, tuple[tuple[str, str], ...]], ...] = ()
    edited: frozenset[str] = frozenset()
    count: int = 0


def _carried(source: SourceProject, design: Design) -> _Carried:
    """The rule records an Altium conversion wrote in the board (``rulecarrier.PROPERTY``), read against the
    project's rules file as it is now; nothing without the property or for one that does not read."""
    from fenolite.backends.kicad.boardcarrier import carried as board_carried
    from fenolite.convert.rulecarrier import PROPERTY, dru_blocks, read_carrier

    rules = design.rules
    if rules is None or source.path.suffix != ".kicad_pcb":
        return _Carried(design)
    try:
        payload = board_carried(source.path.read_text(encoding="utf-8")).get(PROPERTY)
        if payload is None:
            return _Carried(design)
        carried = read_carrier(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, FormatError):
        return _Carried(design)
    dru = source.files.get(source.path.stem + ".kicad_dru")
    current = dru_blocks(dru.read_text(encoding="utf-8") if dru is not None else None)
    kept = [record for record in carried if record.kept(current)]
    taken = {name for record in kept for name in record.blocks}
    edited = frozenset(name for record in carried if not record.kept(current) for name in record.blocks)
    left = tuple(rule for rule in rules.rules if rule.name not in taken)
    count = len(rules.rules) - len(left) + sum(1 for record in kept if not record.blocks)
    design = dataclasses.replace(design, rules=dataclasses.replace(rules, rules=left))
    return _Carried(design, tuple((r.number, r.fields) for r in kept), edited, count)


def _source_rule_losses(
    lost: dict[str, tuple[str, ...]], design: Design, edited: frozenset[str]
) -> dict[str, tuple[str, ...]]:
    """The rule losses with each rule that came from a source record and was edited in KiCad moved to
    ``SOURCE_RULE_LOST``, which needs consent (change c0434)."""
    names = {rule.id: rule.name for rule in design.rules.rules} if design.rules is not None else {}
    moved: list[str] = []
    found: dict[str, tuple[str, ...]] = {}
    for reason, ids in lost.items():
        stay = tuple(i for i in ids if names.get(i) not in edited)
        moved += [i for i in ids if names.get(i) in edited]
        if stay:
            found[reason] = stay
    if moved:
        found[SOURCE_RULE_LOST] = tuple(moved)
    return found


def write(source: SourceProject, options: Options) -> Written:
    """The Altium project of a KiCad source, with its report. Its copper graphics take the net their KiCad
    slot names (``fpitems.with_graphic_nets``), as a build's do: without it a netted copper shape is written
    with no net and shorts the copper it touches (changes c0439, c0441)."""
    projected = fpitems.with_footprint_items(_named(source.design, options.name)).design
    design = pads.project(fpitems.with_graphic_nets(projected))
    carried = _carried(source, design)  # change c0434: the source's own rule records
    design = carried.design
    sch, symbols, changed_comments = schematic.inputs(source, design)
    board = design.board
    # the edges as an outline (change c0170): the board ring as before, each inner ring a cut-out region
    edges = edge_outline(design) if board is not None and board.outline is None else None
    try:
        written = lower.write_design(
            design,
            allow_lossy=True,
            full_drill=True,  # a via whose hole equals its diameter, as a saved document holds (c0441)
            bodies=options.bodies,
            derive_library=True,
            schematic=sch,
            symbols=symbols,
            sheets="modules" if sch is not None else "flat",
            edges=edges,
            # a conversion never falls back to unpoured polygons without saying so (change c0436): the
            # default mode is asked for explicitly, so a missing geo extra raises BackendUnavailable
            pour=options.pour or "computed",
            source_rules=carried.records,
        )
    except CompoundTooLarge as error:
        raise TargetLimitError(
            f"the PCB document of {source.name} cannot be written: {error}",
            hint="the version 3 compound-file limit was exceeded; nothing was converted",
        ) from None
    inputs = written.inputs
    lost: dict[str, dict[str, tuple[str, ...]]] = {
        kind: dict(reasons) for kind, reasons in inputs.lost.items() if kind not in CHANGE_KINDS
    }
    changed: dict[str, dict[str, tuple[str, ...]]] = {
        kind: {CHANGES[kind]: tuple(i for ids in reasons.values() for i in ids)}
        for kind, reasons in inputs.lost.items()
        if kind in CHANGE_KINDS
    }
    for kind, reasons in inputs.changed.items():
        changed[kind] = {**changed.get(kind, {}), **reasons}
    if ZONE_FILL in changed:
        changed[ZONE_FILL] = _zone_fills(changed[ZONE_FILL], written)
    if changed_comments:
        changed["schematic-text"] = {
            "a literal comment starting with = is written with a leading space": changed_comments
        }
    lost.update(_extra_losses(design, written))
    if "rule" in lost and carried.edited:
        lost["rule"] = _source_rule_losses(lost["rule"], design, carried.edited)
    counts = census(design)
    held = dict(inputs.written)
    if carried.count:  # the rules the source's records give again, as they were read
        counts["rule"] = counts.get("rule", 0) + carried.count
        held["rule"] = held.get("rule", 0) + carried.count
    if design.circuit.components:
        counts[SCHEMATIC] = 1
    name = inputs.name
    if f"{name}.SchDoc" in written.files:
        changed[SCHEMATIC] = {
            "positions and wires are not converted" if sch is not None else CHANGES[SCHEMATIC]: (
                design.header.id,
            )
        }
    report = ConversionReport.of(source=counts, written=held, changed=changed, lost=lost)
    issues = tuple(
        issue for issue in written.issues if issue.code != lower.NOT_LOWERED or issue.where == SCHEMATIC
    )
    summary = written.pour.pour if written.pour is not None else None
    return Written(
        written.files,
        report,
        design,
        f"{name}.PcbDoc",
        issues,
        schematic=f"{name}.PrjPcb" if sch is not None else None,
        evidence=Evidence.combine(EVIDENCE, summary.evidence)
        if summary is not None and summary.poured
        else None,
    )


DIRECTION = Direction(
    source=KICAD,
    target=ALTIUM,
    write=write,
    evidence=EVIDENCE,
    experimental=True,
    profile=PROFILE,
    kinds=WRITER_KINDS,
)

__all__ = ["CHANGES", "DIRECTION", "EVIDENCE", "PROFILE", "WRITER_KINDS", "write"]
