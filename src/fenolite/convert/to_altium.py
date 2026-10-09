# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The direction from KiCad to Altium (capability design-conversion, "KiCad to Altium direction" and
"Changes of the Altium direction"; change c0159).

The design read from KiCad keeps the drawings of its footprints and the corner ratios of its pads in
KiCad's own slots, so it is projected first (``fpitems.with_footprint_items``, as ``lens.altium.write_model``
does), then written with ``lower.write_design(..., allow_lossy=True)``: the consent to a loss is the
conversion's, which judges the report. What the write leaves out is mapped per kind and reason into the
report; a polygon written unpoured and the generated schematic are changes, not losses.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from fenolite.backends.altium import lower
from fenolite.backends.altium.cfb import CompoundTooLarge
from fenolite.backends.kicad import fpitems
from fenolite.convert.direction import Direction, Options, TargetLimitError, Written
from fenolite.convert.report import ConversionReport, census
from fenolite.convert.sources import ALTIUM, KICAD, SourceProject
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-VER-RTA2-3", "H-A-VER-RTA3", "H-K-CONV-TRIANGLE"))
"""The level of the Altium writers (``lower.EVIDENCE``), with the triangle that checks this direction."""
PROFILE = "kicad-to-altium"
CHANGES: Mapping[str, str] = {
    "zone-fill": "a polygon is written unpoured; Altium fills it on a repour",
    "schematic": "the schematic is generated from the circuit on one sheet with generic symbols",
}
"""The kinds this direction writes in another form, with the reason the report gives them."""
CHANGE_KINDS = frozenset(CHANGES)
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


def write(source: SourceProject, options: Options) -> Written:
    """The Altium project of a KiCad source, with its report."""
    design = fpitems.with_footprint_items(_named(source.design, options.name)).design
    try:
        written = lower.write_design(design, allow_lossy=True, bodies=options.bodies)
    except CompoundTooLarge as error:
        raise TargetLimitError(
            f"the PCB document of {source.name} cannot be written: {error}",
            hint="the Altium writer does not write DIFAT sectors yet; nothing was converted",
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
    lost.update(_extra_losses(design, written))
    counts = census(design)
    if design.circuit.components:
        counts[SCHEMATIC] = 1
    name = inputs.name
    if f"{name}.SchDoc" in written.files:
        changed[SCHEMATIC] = {CHANGES[SCHEMATIC]: (design.header.id,)}
    report = ConversionReport.of(source=counts, written=dict(inputs.written), changed=changed, lost=lost)
    issues = tuple(
        issue for issue in written.issues if issue.code != lower.NOT_LOWERED or issue.where == SCHEMATIC
    )
    return Written(written.files, report, design, f"{name}.PcbDoc", issues)


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
