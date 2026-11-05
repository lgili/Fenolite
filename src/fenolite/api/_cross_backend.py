# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The two sides of a comparison across backends, completed before ``compare_designs`` (change c0421).

A design read from one backend holds some of what it means in files or records the other backend keeps in
the model. Between two sides of one backend both hold it the same way, so nothing here runs; across
backends each side is completed so that the pure comparison sees the same things on both:

- a KiCad side with a traced project gets the project's net classes and memberships (``pro.apply_project``,
  as the importer reads them), the custom rules of ``<stem>.kicad_dru`` (``dru.read_rules``), and its
  footprint graphics and texts as model entities (``fpitems.with_footprint_items``);
- an Altium side's zones whose polygon has an arc vertex take the flattened outline of the polygon record
  (``altium_to_kicad.zone_outlines``, as ``convert`` gives them: the import leaves their outline empty); a
  zone that no record outlines stays as read;
- an Altium side's zones take the connection, thermal settings and clearance that its Polygon Connect Style
  and clearance rules govern (``convert.altium_zones``, change c0409 B5 and B6): the values a polygon stores
  are defaults those rules override;
- the keep-out layers of each side are named, so level 7 pairs their drawings with rule areas.

Nothing is written; what a completion cannot read is left as read.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from fenolite.api.sides import ReadSide
from fenolite.core.errors import FenoliteError, Issue
from fenolite.model.design import Design

KICAD = "kicad"
ALTIUM = "altium"


@dataclass(frozen=True, slots=True)
class Completed:
    """The two sides as compared, and the names of each side's keep-out layers."""

    a: ReadSide
    b: ReadSide
    keepout_layers: tuple[frozenset[str], frozenset[str]] = (frozenset(), frozenset())


def _traced(side: ReadSide, suffix: str) -> Path | None:
    found = [path for path, _ in side.source_files if path.suffix.lower() == suffix]
    return found[0] if len(found) == 1 else None


def _kicad(design: Design, side: ReadSide) -> Design:
    from fenolite.backends.kicad import dru, fpitems, pro

    issues: list[Issue] = []
    project = _traced(side, ".kicad_pro")
    board = _traced(side, ".kicad_pcb")
    if project is not None:
        try:
            info = pro.read_project(project.read_text(encoding="utf-8"), file=project.name, issues=issues)
            design = pro.apply_project(design, info, issues=issues)
        except (OSError, UnicodeDecodeError, FenoliteError):
            pass
    if board is not None:
        rules = board.with_suffix(".kicad_dru")
        if rules.is_file():
            try:
                read = dru.read_rules(rules.read_text(encoding="utf-8"), file=rules.name, issues=issues)
            except (OSError, UnicodeDecodeError, FenoliteError):
                read = None
            if read is not None:
                held = design.rules
                design = replace(design, rules=read if held is None else replace(held, rules=read.rules))
    return fpitems.with_footprint_items(design).design


def _altium(design: Design, read: Path | None) -> Design:
    from fenolite.convert import altium_zones
    from fenolite.convert.altium_to_kicad import Ledger, zone_outlines
    from fenolite.convert.sources import SourceProject

    if design.board is None or not design.board.zones:
        return design
    ledger = Ledger()  # its notes are not differences: a comparison reports what differs
    if (
        read is not None
        and read.suffix.lower() in (".pcbdoc", ".prjpcb")
        and not all(zone.outline for zone in design.board.zones)
    ):
        source = SourceProject(read, read, read.parent, ALTIUM, read.suffix.lower().lstrip("."), design)
        outlined = zone_outlines(source, design, ledger).board
        assert outlined is not None
        # a zone that no record outlines stays as read: dropping it, as a writer must, would hide it
        by_id = {zone.id: zone for zone in outlined.zones}
        zones = tuple(by_id.get(zone.id, zone) for zone in design.board.zones)
        design = replace(design, board=replace(design.board, zones=zones))
    board = design.board
    assert board is not None
    refs = {component.id: component.ref for component in design.circuit.components}
    styles = altium_zones.board_styles(board)
    board = altium_zones.connect_zones(board, design, styles, refs, ledger)
    board = altium_zones.zone_clearances(board, design, ledger)
    return replace(design, board=board)


def _keepout_layers(side: ReadSide) -> frozenset[str]:
    if side.backend != ALTIUM or side.design.board is None:
        return frozenset()
    from fenolite.backends.altium.adapter.copper import KEEPOUT_LAYER_ID
    from fenolite.backends.altium.adapter.layers import LAYERS

    name = LAYERS[KEEPOUT_LAYER_ID][0]
    return frozenset(layer.name for layer in side.design.board.layers if layer.name == name)


def _completed(side: ReadSide, given: Path | None) -> ReadSide:
    if side.backend == KICAD:
        return replace(side, design=_kicad(side.design, side))
    if side.backend == ALTIUM:
        return replace(side, design=_altium(side.design, given))
    return side


def complete(a: ReadSide, b: ReadSide, *, paths: tuple[Path | None, Path | None] = (None, None)) -> Completed:
    """``a`` and ``b`` as compared: as read when one backend read both, else each completed; ``paths`` are
    the files given for the sides (``None`` for a design passed in), which an Altium side reads again."""
    if a.backend == b.backend:
        return Completed(a, b)
    return Completed(
        _completed(a, paths[0]), _completed(b, paths[1]), (_keepout_layers(a), _keepout_layers(b))
    )


__all__ = ["Completed", "complete"]
