# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic side of a KiCad project for the parity comparison (``checks.parity``; capability
verification-loop, "Parity comparison"; change c0072).

Components come from the schematic reader: one per reference of the hierarchy, with the value and the
footprint of its lowest unit (``sch.hierarchy_components``), symbols that are not on the board left out.
The pins of a component are those of the symbol definitions that its sheets embed, for every unit in body
style 1, together with the pins the netlist lists. The nodes come from a netlist: Fenolite's own
(``sch_netlist.own_netlist``) for a schematic inside its grammar, one sheet or the tree of sheets that
``build`` writes (change c0070), which needs no tool, or the netlist that ``kicad-cli`` exported. Nothing
here runs a tool or writes a file.
"""

# evidence: see sch, sch_netlist, netlist

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from fenolite.backends.base import PadNetList, SchematicSide, SideComponent
from fenolite.backends.kicad import netnames, sch, sch_netlist
from fenolite.backends.kicad.netlist import KicadNetlist
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.schematic import SchematicSheet

BODY_STYLE = 1
FOLD: tuple[tuple[str, str], ...] = ((netnames.SLASH, "/"),)
"""KiCad's parity test reads ``{slash}`` and ``/`` in a net name as one (``docs/formats/kicad/drc.md``,
"Schematic parity"): boards saved by older versions hold the slash itself."""


def read_sheets(root_file: Path) -> dict[str, SchematicSheet]:
    """The sheets of the hierarchy under ``root_file`` by file name relative to its folder, the root
    first; a file that a sheet reference names and that does not exist is left out."""
    tree = sch.sheet_files(root_file)
    found: dict[str, SchematicSheet] = {}
    for name in tree.files:
        path = root_file.parent / name
        if path.is_file():
            found[name] = sch.read_schematic(path.read_text(encoding="utf-8"), file=name)
    return found


def grammar_issues(sheets: Mapping[str, SchematicSheet]) -> tuple[Issue, ...]:
    """Why Fenolite's own netlist does not cover ``sheets`` (``read_sheets``): the issues of
    ``sch_netlist.grammar_issues`` for the root and the child sheets it names; ``()`` when it covers
    them. The keys of ``read_sheets`` are the keys of ``children``: file names relative to the root's
    folder. A file that a sheet reference names and that is missing is no key, so the grammar reports it."""
    (_, root), *rest = sheets.items()
    return sch_netlist.grammar_issues(root, children=dict(rest))


def own_evidence(sheets: Mapping[str, SchematicSheet]) -> Evidence:
    """The evidence of ``own_netlist(sheets)`` (``sch_netlist.evidence_of``): that of the own netlist, with
    the rows of stacked pins when the sheets hold any."""
    (_, root), *rest = sheets.items()
    return sch_netlist.evidence_of(root, dict(rest))


def own_netlist(sheets: Mapping[str, SchematicSheet], *, project: str) -> KicadNetlist:
    """Fenolite's own netlist of ``sheets``; ``NetlistUnsupportedError`` outside the grammar."""
    (_, root), *rest = sheets.items()
    return sch_netlist.own_netlist(root, project=project, children=dict(rest))


def _pins(sheets: Mapping[str, SchematicSheet], project: str) -> dict[str, set[str]]:
    """Reference → the pin numbers of the embedded definitions of its symbols, all units in body style 1."""
    found: dict[str, set[str]] = defaultdict(set)
    for sheet in sheets.values():
        known = {definition.lib_id: definition for definition in sheet.lib_symbols}
        for symbol in sheet.symbols:
            definition = known.get(symbol.lib_name or symbol.lib_ref)
            if definition is None or definition.extends:
                continue
            numbers = {p.number for p in definition.pins if p.body_style in (0, BODY_STYLE) and p.number}
            refs = {use.ref for use in symbol.uses if use.project == project} or {symbol.ref}
            for ref in refs:
                found[ref] |= numbers
    return found


def _attributes(sheets: Mapping[str, SchematicSheet], project: str) -> dict[str, frozenset[str]]:
    """Reference → the flags of its symbol of the lowest unit that a footprint can share."""
    best: dict[str, tuple[int, frozenset[str]]] = {}
    for sheet in sheets.values():
        for symbol in sheet.symbols:
            flags = frozenset(
                name for name, held in (("dnp", symbol.dnp), ("exclude_from_bom", not symbol.in_bom)) if held
            )
            uses = [(use.ref, use.unit) for use in symbol.uses if use.project == project]
            for ref, unit in uses or [(symbol.ref, symbol.unit)]:
                if ref not in best or unit < best[ref][0]:
                    best[ref] = (unit, flags)
    return {ref: flags for ref, (_, flags) in best.items()}


def side_of(
    root_file: Path, sheets: Mapping[str, SchematicSheet], nodes: Mapping[tuple[str, str], str]
) -> SchematicSide:
    """The side of the schematic under ``root_file`` whose sheets are ``sheets``, with ``nodes``."""
    pins = _pins(sheets, root_file.stem)
    flags = _attributes(sheets, root_file.stem)
    listed: dict[str, set[str]] = defaultdict(set)
    for ref, pin in nodes:
        listed[ref].add(pin)
    components = {
        c.ref: SideComponent(
            c.value,
            c.footprint,
            frozenset(pins.get(c.ref, set()) | listed.get(c.ref, set())),
            flags.get(c.ref, frozenset()),
        )
        for c in sch.hierarchy_components(root_file, on_board_only=True)
    }
    kept = {key: net for key, net in nodes.items() if key[0] in components}
    return SchematicSide(
        MappingProxyType(components), MappingProxyType(kept), FOLD, netnames.UNCONNECTED_PREFIX
    )


def netlist_nodes(netlist: KicadNetlist) -> dict[tuple[str, str], str]:
    """(reference, pin number) → net name, for every node of ``netlist``."""
    return {(node.ref, node.pin): net.name for net in netlist.nets for node in net.nodes}


def assignment_nodes(assignments: PadNetList, references: set[str]) -> dict[tuple[str, str], str]:
    """(reference, pin number) → net name for the elements ``REF-PIN`` of ``assignments``; the reference is
    the longest one of ``references`` that the element starts with, else the text before the last ``-``."""
    found: dict[tuple[str, str], str] = {}
    for assignment in assignments.assignments:
        element = assignment.element
        cuts = [i for i, char in enumerate(element) if char == "-" and element[:i] in references]
        cut = max(cuts) if cuts else element.rfind("-")
        if cut > 0:
            found[(element[:cut], element[cut + 1 :])] = assignment.net
    return found


def schematic_side(
    root_file: Path, *, project: str = "", netlist: KicadNetlist | None = None
) -> SchematicSide:
    """The side of the schematic under ``root_file`` (``project`` is the stem of the root file when it is
    not given). ``netlist`` is the export of ``kicad-cli``; without it the nodes come from Fenolite's own
    netlist, and a schematic outside its grammar raises ``NetlistUnsupportedError``."""
    sheets = read_sheets(root_file)
    found = netlist if netlist is not None else own_netlist(sheets, project=project or root_file.stem)
    return side_of(root_file, sheets, netlist_nodes(found))


__all__ = [
    "assignment_nodes",
    "grammar_issues",
    "netlist_nodes",
    "own_evidence",
    "own_netlist",
    "read_sheets",
    "schematic_side",
    "side_of",
]
