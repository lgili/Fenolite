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
import re
from collections import Counter
from collections.abc import Mapping
from decimal import Decimal

from fenolite.backends.altium import lower
from fenolite.backends.altium.adapter.arcring import ArcPolygon
from fenolite.backends.altium.altsym import AltiumSymbol
from fenolite.backends.altium.cfb import CompoundTooLarge
from fenolite.backends.altium.pcbdoc import KeptPour
from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.netnames import UNCONNECTED_PREFIX
from fenolite.backends.kicad.outline import edge_outline
from fenolite.convert import altium_links, altium_planes, altium_strings, codes, pads, schematic
from fenolite.convert.direction import Direction, Options, TargetLimitError, Written
from fenolite.convert.models import (
    BODIES_PROPERTY,
    HEIGHTS_PROPERTY,
    IDS_PROPERTY,
    CarriedIds,
    HeightKey,
    KeptKey,
    footprint_models,
    read_bodies,
    read_heights,
    read_ids,
    read_layers,
)
from fenolite.convert.report import SOURCE_RULE_LOST, ConversionReport, census
from fenolite.convert.sources import ALTIUM, KICAD, SourceProject
from fenolite.core.coords import Point
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
    if summary.kept:  # change c0482: the source's own regions, written as read
        return {}
    refused = {zone for _, zone, _ in summary.refused}
    ids = tuple(i for found in reasons.values() for i in found)
    found = {
        CHANGES[ZONE_FILL]: tuple(i for i in ids if i in refused),
        POURED: tuple(i for i in ids if i not in refused),
    }
    return {reason: ids for reason, ids in found.items() if ids}


@dataclasses.dataclass(frozen=True, slots=True)
class _Carried:
    """What the rule records carried in the board give the way back (changes c0434, c0457): the design
    without the rules those records give again, the records written (as read, or with the limits KiCad
    holds), the names of the rules that came from a record and were edited otherwise in KiCad, how many
    rules the records stand for (the rules taken out, and one per record that gave none), the ids of
    the rules whose limits a record now holds, and the ids of the board minimums of an imported design
    that are not written (``rulecarrier.board_minimum``)."""

    design: Design
    records: tuple[tuple[int, tuple[tuple[str, str], ...]], ...] = ()
    edited: frozenset[str] = frozenset()
    count: int = 0
    limits: tuple[str, ...] = ()
    minimums: tuple[str, ...] = ()


LIMITS_EDITED = "a rule record whose limits were edited in KiCad is written with KiCad's limits"
"""Change c0457: the record keeps its name, priority, scopes and enabled state."""
EDITED_LOWERED = "a rule record edited in KiCad is written as a rule of its kind, as KiCad holds it"
"""Change c0457: the lowered rule takes the next priority of its kind and a name of its own."""
BOARD_MINIMUM = (
    "a board minimum of an imported design (design.rules.minimum) is not written as a rule: the rule records "
    "of the Altium document it came from hold the board's limits"
)
"""Change c0457: a report-class loss; the import writes the document's board setup minimums so."""


def _carried(source: SourceProject, design: Design) -> _Carried:
    """The rule records an Altium conversion wrote in the board (``rulecarrier.PROPERTY``), matched against
    the project's rules file as it is now (``rulecarrier.match``); nothing without the property or for one
    that does not read."""
    from fenolite.backends.altium.rulemap import edited_fields
    from fenolite.backends.kicad.boardcarrier import carried as board_carried
    from fenolite.convert.rulecarrier import PROPERTY, dru_rules, match, read_carrier

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
    matched = match(carried, dru_rules(dru.read_text(encoding="utf-8") if dru is not None else None))
    by_name = {rule.name: rule for rule in rules.rules}
    written: dict[int, tuple[tuple[str, str], ...]] = {id(record): record.fields for record in matched.kept}
    taken = set(matched.taken)
    edited = set(matched.edited)
    limits: list[str] = []
    for record, names in matched.limits:
        own = [by_name[name] for name in names if name in by_name]
        fields = edited_fields(record.fields, own) if len(own) == len(names) else None
        if fields is None:  # KiCad's limits have no place in the record: the rules are lowered
            edited |= set(names)
            continue
        written[id(record)] = fields
        taken |= set(names)
        limits += [rule.id for rule in own]
    left = tuple(rule for rule in rules.rules if rule.name not in taken)
    minimums = tuple(rule.id for rule in rules.rules if rule.name in matched.minimums)
    empty = sum(1 for record in matched.kept if not record.blocks)
    count = len(rules.rules) - len(left) - len(minimums) + empty
    design = dataclasses.replace(design, rules=dataclasses.replace(rules, rules=left))
    records = tuple((r.number, written[id(r)]) for r in carried if id(r) in written)
    return _Carried(design, records, frozenset(edited), count, tuple(limits), minimums)


def _rule_changes(
    design: Design, carried: _Carried, lost: Mapping[str, tuple[str, ...]]
) -> dict[str, tuple[str, ...]]:
    """The rule changes of the way back (change c0457): the rules whose limits a source record now holds
    (``LIMITS_EDITED``), and the rules of source records edited otherwise that were written as rules of
    their kind (``EDITED_LOWERED``); a rule of such a record that was not written is a loss."""
    gone = {i for ids in lost.values() for i in ids}
    rules = design.rules.rules if design.rules is not None else ()
    lowered = tuple(r.id for r in rules if r.name in carried.edited and r.id not in gone)
    found = {LIMITS_EDITED: carried.limits, EDITED_LOWERED: lowered}
    return {reason: ids for reason, ids in found.items() if ids}


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


_MASK_MARGIN = re.compile(r"\(pad_to_mask_clearance\s+(-?[0-9]+(?:\.[0-9]+)?)\s*\)")


def board_mask_margin(text: str) -> int:
    """The board's ``(setup (pad_to_mask_clearance M))`` in nanometres, the opening of an untented via
    beyond its copper in KiCad (``board.md``, ``H-K-VIAPROT-MASK``; change c0445); 0, KiCad's value, when
    absent."""
    found = _MASK_MARGIN.search(text)
    return 0 if found is None else int(Decimal(found.group(1)) * 1_000_000)


def with_mask_margin(design: Design, source: SourceProject) -> Design:
    """``design`` whose board holds the source board's mask margin (change c0445), so the Altium writer
    opens each untented via as KiCad does; a board that holds one already keeps it."""
    board = design.board
    if board is None or board.mask_margin is not None:
        return design
    try:
        margin = board_mask_margin(source.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return design
    return dataclasses.replace(design, board=dataclasses.replace(board, mask_margin=margin))


def _carried_storages(
    source: SourceProject, design: Design
) -> tuple[dict[str, tuple[bytes, bytes]], dict[str, dict[str, tuple[str, ...]]]]:
    """The Altium storages a conversion to KiCad carried in the board's properties (change c0450,
    ``convert.altium_storages``, read with ``boardcarrier.carried``), by storage name: the ``Header`` and
    ``Data`` streams, as ``design`` can hold them (change c0461, ``altium_storages.fitted``: its net names);
    and what that left out, as ``altium-storage`` losses. Nothing for a board that does not read."""
    from fenolite.backends.kicad.boardcarrier import carried as board_carried
    from fenolite.convert import altium_storages as storages

    if source.path.suffix != ".kicad_pcb":
        return {}, {}
    try:
        found = board_carried(source.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FormatError):
        return {}, {}
    made = storages.fitted(storages.from_carried(found), {net.name for net in design.circuit.nets})
    lost = {storages.KIND: dict(made.dropped)} if made.dropped else {}
    return {name: (s.header, s.data) for name, s in made.storages.items()}, lost


def with_unions(source: SourceProject, design: Design) -> Design:
    """``design`` whose items of a uuid in the union map that a conversion to KiCad carried
    (``Fenolite.Altium.UnionMembers``, change c0460, ``backends.altium.unions``) hold their union index
    again, so the writer writes it; ``design`` itself when the board holds no map or does not read."""
    from fenolite.backends.altium import unions
    from fenolite.backends.kicad.boardcarrier import PREFIX
    from fenolite.backends.kicad.boardcarrier import carried as board_carried

    board = design.board
    if board is None or source.path.suffix != ".kicad_pcb":
        return design
    try:
        found = board_carried(source.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FormatError):
        return design
    members = unions.read_map(found.get(PREFIX + unions.CARRIER, b""))
    if not members:
        return design
    return dataclasses.replace(design, board=unions.restored(board, members))


def _carried_arcs(source: SourceProject, design: Design) -> dict[str, ArcPolygon]:
    """Per zone id, the arc vertices of its source polygon that a conversion to KiCad carried (change c0463,
    task 1.3; ``zonearcs.read_carrier`` of the board property ``zonearcs.PROPERTY``, found by the zone's KiCad
    uuid); none for a board that does not read or carries none."""
    from fenolite.backends.kicad.boardcarrier import carried as board_carried
    from fenolite.convert import zonearcs

    board = design.board
    if board is None or source.path.suffix != ".kicad_pcb":
        return {}
    try:
        found = board_carried(source.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FormatError):
        return {}
    return zonearcs.arc_polygons(board.zones, zonearcs.read_carrier(found.get(zonearcs.PROPERTY)))


def _carried_pours(source: SourceProject, design: Design) -> dict[str, KeptPour]:
    """The pours of the source polygons that a conversion to KiCad carried, by KiCad zone uuid (change c0482;
    ``zonepours.read_carrier`` of the board property ``zonepours.PROPERTY``); none for a board that does not
    read or carries none. The writer finds each by its polygon's vertices and net."""
    from fenolite.backends.kicad.boardcarrier import carried as board_carried
    from fenolite.convert import zonepours

    board = design.board
    if board is None or source.path.suffix != ".kicad_pcb":
        return {}
    try:
        found = board_carried(source.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FormatError):
        return {}
    return zonepours.read_carrier(found.get(zonepours.PROPERTY))


def _carried_planes(
    source: SourceProject, design: Design
) -> tuple[Design, dict[str, lower.CarriedPlane], dict[str, tuple[str, ...]]]:
    """The internal planes a conversion to KiCad carried (change c0466, ``altium_planes``): ``design``
    with each plane still held made a plane again, each such plane by row for the writer (its splits,
    pull-back and the row's user name), and the other planes as ``plane`` losses by reason. Nothing for a
    board that does not read or carries none."""
    from fenolite.backends.kicad.boardcarrier import carried as board_carried

    if design.board is None or source.path.suffix != ".kicad_pcb":
        return design, {}, {}
    try:
        found = board_carried(source.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FormatError):
        return design, {}, {}
    made = altium_planes.restored(design, altium_planes.read_carrier(found.get(altium_planes.PROPERTY)))
    names = altium_planes.names(made.design, tuple(made.planes))
    planes = {
        row: lower.CarriedPlane(
            plane.pullback, tuple((s.net, s.points) for s in plane.splits), names.get(row), plane.boundaries
        )
        for row, plane in made.planes.items()
    }
    lost: dict[str, list[str]] = {}
    for ident, reason in made.lost:
        lost.setdefault(reason, []).append(ident)
    return made.design, planes, {reason: tuple(ids) for reason, ids in lost.items()}


def _carried_fonts(source: SourceProject, design: Design) -> Design:
    """``design`` whose stroke texts and fields a conversion to KiCad carried the font of hold it again
    (change c0460, S-2253; ``strokefonts``); unchanged for a board that does not read or carries none."""
    from fenolite.backends.kicad.boardcarrier import carried as board_carried
    from fenolite.convert import strokefonts, texttails

    if design.board is None or source.path.suffix != ".kicad_pcb":
        return design
    try:
        found = board_carried(source.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FormatError):
        return design
    fonts = strokefonts.read_carrier(found.get(strokefonts.PROPERTY))
    tails = texttails.read_carrier(found.get(texttails.PROPERTY))  # change c0450, task 4.5
    board = texttails.restored(strokefonts.restored(design.board, fonts), tails)
    return dataclasses.replace(design, board=board) if fonts or tails else design


def _carried_origin(source: SourceProject, design: Design) -> Point | None:
    """The document origin a conversion to KiCad carried (change c0467, ``altium_frame``), moved with the
    board's edge, in the document's frame; ``None`` for a board that does not read or carries none."""
    from fenolite.backends.kicad.boardcarrier import carried as board_carried
    from fenolite.convert import altium_frame

    if design.board is None or source.path.suffix != ".kicad_pcb":
        return None
    try:
        found = board_carried(source.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FormatError):
        return None
    carried = altium_frame.read_carrier(found.get(altium_frame.PROPERTY))
    return altium_frame.restored(design.board, carried) if carried is not None else None


def _stored_models(
    source: SourceProject,
) -> tuple[
    dict[HeightKey, tuple[int, int]],
    CarriedIds,
    dict[HeightKey, int],
    dict[KeptKey, tuple[tuple[bytes, bytes], ...]],
]:
    """The stored heights, the source identities and the body layers of the embedded models a conversion to
    KiCad placed (change c0449, task 4.3; ``models.read_heights``, ``models.read_ids`` and, change c0464,
    ``models.read_layers`` of the board properties ``models.HEIGHTS_PROPERTY`` and ``models.IDS_PROPERTY``),
    and the source records of the bodies of each generated model (change c0484, ``models.read_bodies`` of
    ``models.BODIES_PROPERTY``); none for a board that does not read or carries none."""
    from fenolite.backends.kicad.boardcarrier import carried as board_carried

    if source.path.suffix != ".kicad_pcb":
        return {}, CarriedIds(), {}, {}
    try:
        found = board_carried(source.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FormatError):
        return {}, CarriedIds(), {}, {}
    heights = found.get(HEIGHTS_PROPERTY)
    bodies = read_bodies(found.get(BODIES_PROPERTY))
    return read_heights(heights), read_ids(found.get(IDS_PROPERTY)), read_layers(heights), bodies


def _schematic_dnp(design: Design, sch: Design | None) -> Design:
    """``design`` with each component that its schematic symbol marks DNP marked so too (change c0470):
    KiCad keeps the mark on the symbol, and a board that was not updated holds the footprint without it;
    the Altium writer then reports the mark as the ``dnp`` loss it is."""
    marked = {c.ref for c in sch.circuit.components if c.dnp and c.ref} if sch is not None else set[str]()
    if not any(c.ref in marked and not c.dnp for c in design.circuit.components):
        return design
    components = tuple(
        dataclasses.replace(c, dnp=True) if c.ref in marked else c for c in design.circuit.components
    )
    return dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=components))


FLAGGED_NAMED = (
    "a pin under a no-connect flag on a net that a label names: KiCad's netlist lists the pin as not "
    "connected, Altium's names the net of the pin"
)
"""The reason of a ``pin-net`` change (change c0470): the drawing holds both the flag and the label, and
the board names the pad's net, as Altium's netlist does (``docs/formats/kicad/schematic.md``)."""


def _flagged_named(design: Design, sch: Design | None) -> tuple[str, ...]:
    """``component_id:pin`` of each pin that the schematic marks not connected while the board puts its
    pads alone on a net whose name a label gives (not KiCad's ``unconnected-(…)``, change c0470)."""
    if sch is None or design.board is None or not sch.circuit.no_connects:
        return ()
    refs = {c.id: c.ref for c in sch.circuit.components}
    names = {net.id: net.name for net in design.circuit.nets}
    by_ref = {c.ref: c for c in design.circuit.components}
    holders: dict[str, set[tuple[str, str]]] = {}
    pads_of: dict[tuple[str, str], set[str | None]] = {}
    for fp in design.board.footprints:
        for pad in fp.pads:
            if pad.number:
                pads_of.setdefault((fp.component_id, pad.number), set()).add(pad.net_id)
                if pad.net_id:
                    holders.setdefault(pad.net_id, set()).add((fp.component_id, pad.number))
    found: list[str] = []
    for mark in sch.circuit.no_connects:
        component = by_ref.get(refs.get(mark.component_id, ""))
        if component is None:
            continue
        numbers = component.pads_of(mark.pin)
        nets = {n for number in numbers for n in pads_of.get((component.id, number), {None})}
        if len(nets) != 1 or (net := next(iter(nets))) is None:
            continue
        name = names.get(net, "")
        if (
            name
            and not name.startswith(UNCONNECTED_PREFIX)
            and holders[net] <= {(component.id, number) for number in numbers}
        ):
            found.append(f"{component.id}:{mark.pin}")
    return tuple(found)


def open_pads(design: Design) -> Design:
    """``design`` whose pads on a net ``unconnected-(…)`` that holds that one pad and no copper are on no net
    (change c0480), as the Altium build reads such a net (c0061, ``lens.altium_copper.match_source``): KiCad
    names the net of an unconnected pin so, and an Altium document holds the pad on no net
    and no such net."""
    board = design.board
    if board is None:
        return design
    names = {net.id: net.name for net in design.circuit.nets}
    pads_on = Counter(pad.net_id for fp in board.footprints for pad in fp.pads if pad.net_id)
    copper = {item.net_id for item in (*board.tracks, *board.arcs, *board.vias, *board.zones) if item.net_id}
    open_nets = {
        net_id
        for net_id, count in pads_on.items()
        if count == 1 and net_id not in copper and names.get(net_id, "").startswith(UNCONNECTED_PREFIX)
    }
    if not open_nets:
        return design
    footprints = tuple(
        dataclasses.replace(
            fp,
            pads=tuple(
                dataclasses.replace(pad, net_id=None) if pad.net_id in open_nets else pad for pad in fp.pads
            ),
        )
        for fp in board.footprints
    )
    circuit = design.circuit
    # a net that a bus or an interface names stays: dropping it would leave that reference dangling
    named = {m.net_id for bus in circuit.buses for m in bus.members}
    named |= {net_id for interface in circuit.interfaces for net_id in interface.members.values()}
    nets = tuple(net for net in circuit.nets if net.id not in open_nets or net.id in named)
    return dataclasses.replace(
        design,
        circuit=dataclasses.replace(circuit, nets=nets),
        board=dataclasses.replace(board, footprints=footprints),
    )


def _source_layout(
    source: SourceProject, files: Mapping[str, bytes], root: Mapping[str, Mapping[str, str]], name: str
) -> dict[str, bytes]:
    """``files`` in the layout of the Altium project that the drawing's root carrier ``root`` lists (change
    c0483, ``prjpcb.laid_out``): its folders, its document order and the documents Fenolite does not model,
    whose bytes the KiCad project holds under ``prjpcb.CARRIED_FOLDER``."""
    from fenolite.backends.altium import drawn_read
    from fenolite.backends.altium.prjpcb import CARRIED_FOLDER, carried_kind, documents_of, laid_out

    documents = documents_of(root.get(drawn_read.TOPS_KEY, {}).get(drawn_read.DOCUMENTS_FIELD, ""))
    held = {path: source.root / CARRIED_FOLDER / path for path in carried_kind([p for p, _ in documents])}
    carried = {path: file.read_bytes() for path, file in held.items() if file.is_file()}
    return laid_out(files, documents, carried, name=name)


def write(source: SourceProject, options: Options) -> Written:
    """The Altium project of a KiCad source, with its report. Its copper graphics take the net their KiCad
    slot names (``fpitems.with_graphic_nets``), as a build's do: without it a netted copper shape is written
    with no net and shorts the copper it touches (changes c0439, c0441)."""
    projected = open_pads(fpitems.with_footprint_items(_named(source.design, options.name)).design)
    design = with_mask_margin(pads.project(fpitems.with_graphic_nets(projected)), source)
    design = with_unions(source, design)  # change c0460: the union members of an Altium conversion
    carried = _carried(source, design)  # change c0434: the source's own rule records
    design = carried.design
    links = altium_links.symbol_links(design)  # change c0451: the source's links of an Altium conversion
    design = altium_links.restore(design)
    design, strings = altium_strings.altium_strings(design)  # change c0451: ${NAME} as .NAME
    bodies: dict[str, AltiumSymbol] = {}  # change c0470: each instance's own body
    sch, symbols, changed_comments = schematic.inputs(source, design, links, bodies)
    design = _schematic_dnp(design, sch)
    # change c0470, design D3: the sheets are the source's drawing, not generated ones
    drawing, drawing_issues = schematic.kicad_drawing(source, sch) if sch is not None else (None, ())
    unread = any(i.severity == "error" for i in drawing_issues)
    if unread:  # the generated sheets, reported as such
        drawing = None
    aliases = schematic.drawing_aliases(source, drawing, design.header.name) if drawing is not None else {}
    definitions = schematic.drawing_definitions(source, drawing) if drawing is not None else {}
    carrier_fields = schematic.drawing_fields(source, drawing) if drawing is not None else {}
    if aliases:  # the units drawn with another symbol than their component's, in the library (c0470)
        symbols = {**symbols, **{f"{lib}:{body.lib_ref}": body for lib, body in aliases.values()}}
    board = design.board
    # the edges as an outline (change c0170): the board ring as before, each inner ring a cut-out region
    edges = edge_outline(design) if board is not None and board.outline is None else None
    # each model child whose STEP file the project holds becomes a body that embeds it (change c0449)
    models = (
        footprint_models(board.footprints, source.root, *_stored_models(source)) if board is not None else {}
    )
    kept_storages, storage_losses = _carried_storages(source, design)  # changes c0450 and c0461
    design, planes, plane_losses = _carried_planes(source, design)  # change c0466
    design = _carried_fonts(source, design)  # change c0460, S-2253
    frame_origin = _carried_origin(source, design)  # change c0467
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
            parameters=altium_strings.project_parameter_pairs(design),
            models=models,
            storages=kept_storages,  # change c0450
            polygon_arcs=_carried_arcs(source, design),  # change c0463, task 1.3
            kept_pours=_carried_pours(source, design),  # change c0482
            planes=planes,  # change c0466
            frame_origin=frame_origin,  # change c0467
            drawn=drawing,  # change c0470
            drawn_aliases=aliases,
            drawn_definitions=definitions,
            drawn_fields=carrier_fields,
            drawn_bodies=bodies,
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
    if strings:
        changed["text"] = {**changed.get("text", {}), **strings}
    if ZONE_FILL in changed:
        changed[ZONE_FILL] = _zone_fills(changed[ZONE_FILL], written)
    if changed_comments:
        changed["schematic-text"] = {
            "a literal comment starting with = is written with a leading space": changed_comments
        }
    lost.update(_extra_losses(design, written))
    lost.update(storage_losses)
    if plane_losses:  # change c0466: a carried plane that KiCad no longer holds as one
        lost[altium_planes.KIND] = {**lost.get(altium_planes.KIND, {}), **plane_losses}
    if "rule" in lost and carried.edited:
        lost["rule"] = _source_rule_losses(lost["rule"], design, carried.edited)
    if carried.minimums:  # change c0457: reported, not refused
        lost["rule"] = {**lost.get("rule", {}), BOARD_MINIMUM: carried.minimums}
    rule_changes = _rule_changes(design, carried, lost.get("rule", {}))
    if rule_changes:  # change c0457: a source rule edited in KiCad is a change, not a loss
        changed["rule"] = {**changed.get("rule", {}), **rule_changes}
    counts = census(design)
    held = dict(inputs.written)
    if carried.count:  # the rules the source's records give again, as they were read
        counts["rule"] = counts.get("rule", 0) + carried.count
        held["rule"] = held.get("rule", 0) + carried.count
    if carried.minimums:
        counts["rule"] = counts.get("rule", 0) + len(carried.minimums)
    if design.circuit.components:
        counts[SCHEMATIC] = 1
    name = inputs.name
    drawn = drawing is not None and not any(
        i.code == lower.NOT_LOWERED and i.message.startswith(lower.DRAWING_NOT_WRITTEN)
        for i in written.issues
    )
    sheets_written = any(file.endswith(".SchDoc") for file in written.files)  # a flat one has no <name>
    root_fields = carrier_fields.get(drawing.root, {}) if drawn and drawing is not None else {}
    files = _source_layout(source, written.files, root_fields, name)
    if drawn and sheets_written:
        assert drawing is not None
        source_counts, changes = schematic.kicad_drawing_rows(drawing)  # change c0470, design D5
        for kind, count in source_counts.items():
            counts[kind] = counts.get(kind, 0) + count
        for kind, item, reason in changes:
            found = changed.setdefault(kind, {})
            found[reason] = (*found.get(reason, ()), item)
    elif sheets_written:
        reason = CHANGES[SCHEMATIC]
        if sch is not None:
            refused_drawing = drawing is not None or unread
            reason = codes.DRAWING_REFUSED if refused_drawing else "positions and wires are not converted"
        changed[SCHEMATIC] = {reason: (design.header.id,)}
    if flagged := _flagged_named(design, sch):
        changed["pin-net"] = {**changed.get("pin-net", {}), FLAGGED_NAMED: flagged}
    report = ConversionReport.of(source=counts, written=held, changed=changed, lost=lost)
    issues = tuple(
        issue for issue in written.issues if issue.code != lower.NOT_LOWERED or issue.where == SCHEMATIC
    )
    summary = written.pour.pour if written.pour is not None else None
    board_file = next((f for f in files if f.rpartition("/")[2] == f"{name}.PcbDoc"), None)
    return Written(
        files,
        report,
        design,
        # a project without a board reads back from its project file (change c0470)
        board_file or f"{name}.PrjPcb",
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
