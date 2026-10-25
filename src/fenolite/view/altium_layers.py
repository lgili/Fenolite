# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The native layers and the mask and paste openings of an Altium board scene (capability altium-board-view,
change c0181).

``native_view(design, data)`` returns what the board scene needs to show an Altium board as its designer knows
it, from the import (``design``) and the document's bytes (``data``, read for ``Board6/Data`` and
``Rules6/Data`` only):

* ``labels``: model layer name to native name, the name ``Board6`` gives the layer (``LAYER<i>NAME``), else
  Altium's default name of its id (``read.pcbstack.LAYER_NAMES``);
* ``tabs``: model layer name to its place in Altium's order of layer tabs;
* ``openings``: per model pad id, its solder-mask and paste expansion in nanometres and their source: the
  pad's manual value, the ``SolderMaskExpansion`` or ``PasteMaskExpansion`` rule that governs it, or the
  default (``docs/formats/altium/pcb-records.md``, "Pad"; ``rule-file.md``).

A rule governs a pad when it is enabled and its first scope, parsed by ``read.scope``, matches the pad's net,
part and kind; rules are taken by priority (1 first). A scope that ``read.scope`` does not parse, or that asks
for a net class, a layer or a rule area, is not evaluated: such a pad takes the rule of scope ``All`` and is
counted in the notes. Standard library only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from fractions import Fraction

from fenolite.backends.altium.adapter.layers import LAYERS
from fenolite.backends.altium.read.cfb import is_compound, open_compound
from fenolite.backends.altium.read.pcb import read_component_fields, read_rule_fields
from fenolite.backends.altium.read.pcbprops import parse_blocks, parse_mil
from fenolite.backends.altium.read.pcbstack import LAYER_NAMES, read_board
from fenolite.backends.altium.read.scope import parse_scope
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.model.rules import RuleSubject, Selector

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-PCB-PAD",))

NM_PER_UNIT = Fraction(254, 100)
"""One Altium unit (1/10 000 mil) in nanometres."""
MASK_RULE, PASTE_RULE = "SolderMaskExpansion", "PasteMaskExpansion"
DEFAULT_MASK_NM, DEFAULT_PASTE_NM = 101_600, 0
"""The expansions used when no rule governs a pad: 4 mil of mask, no paste expansion (Fenolite's choice,
named in a note)."""
FROM_RULE = 1
UNEVALUATED = frozenset({"netclass", "layer", "area", "diff_pair"})
"""Selector leaves the view cannot evaluate for a pad (it does not know net classes or rule areas)."""
EDGE_LABEL = "Board Outline"
TAB_GROUPS: tuple[tuple[range, int], ...] = (
    (range(1, 33), 0),  # signal layers, by their place in the copper chain
    (range(39, 55), 1),  # internal planes
    (range(33, 35), 2),  # overlays
    (range(35, 37), 3),  # pastes
    (range(37, 39), 4),  # solders
    (range(57, 73), 5),  # mechanical layers
    (range(55, 57), 6),  # drill guide, keep-out
    (range(73, 75), 7),  # drill drawing, multi-layer
)
"""Altium's order of layer tabs, as groups of ids (``docs/viewer.md``, "Altium boards"; INFERRED)."""


@dataclass(frozen=True, slots=True)
class Opening:
    """A pad's solder-mask and paste expansion in nm and where each comes from (``manual``, a rule name, or
    ``default``)."""

    mask: int
    paste: int
    mask_source: str
    paste_source: str


@dataclass(frozen=True, slots=True)
class _Rule:
    name: str
    priority: int
    selector: Selector | None
    """``None`` when the scope is not evaluated (``reason``)."""
    expansion: int
    scope: str


@dataclass
class NativeView:
    labels: dict[str, str] = field(default_factory=lambda: {})
    tabs: dict[str, int] = field(default_factory=lambda: {})
    openings: dict[str, Opening] = field(default_factory=lambda: {})
    notes: list[str] = field(default_factory=lambda: [])
    parts: dict[str, dict[str, str]] = field(default_factory=lambda: {})
    """Per designator, the parameters of its component record (``PART_FIELDS``, change c0187), and its
    ``SOURCEUNIQUEID`` under ``uid``."""


PART_FIELDS = {
    "SOURCEDESCRIPTION": "Description",
    "SOURCELIBREFERENCE": "Library reference",
    "SOURCECOMPONENTLIBRARY": "Component library",
    "FOOTPRINTDESCRIPTION": "Footprint description",
    "SOURCEFOOTPRINTLIBRARY": "Footprint library",
    "SOURCEHIERARCHICALPATH": "Hierarchical path",
    "HEIGHT": "Height",
    "LOCKED": "Locked",
}
"""The keys of a ``Components6`` record the Properties of a part show, and their labels
(``docs/formats/altium/pcb-document.md``)."""


def _parts(data: bytes, file: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not is_compound(data):
        return out
    for pairs in read_component_fields(data, file=file):
        values = dict(pairs)
        ref = values.get("SOURCEDESIGNATOR", "")
        if not ref:
            continue
        found = {label: values[key] for key, label in PART_FIELDS.items() if values.get(key)}
        if values.get("SOURCEUNIQUEID"):
            found["uid"] = values["SOURCEUNIQUEID"]
        out.setdefault(ref, found)
    return out


def _ext(pairs: object, key: str) -> str | None:
    payload = getattr(pairs, "payload", ())
    return next((value for name, value in payload if name == key), None)


def _leaves(selector: Selector) -> Iterable[str]:
    yield selector.op
    for item in selector.items:
        yield from _leaves(item)


def _rules(data: bytes, kind: str, file: str) -> list[_Rule]:
    out: list[_Rule] = []
    for fields in read_rule_fields(data, file=file):
        values = {key.upper(): value for key, value in fields}
        if values.get("RULEKIND") != kind or values.get("ENABLED", "TRUE").upper() != "TRUE":
            continue
        expansion = parse_mil(values.get("EXPANSION"))
        if expansion is None:
            continue
        scope = values.get("SCOPE1EXPRESSION", "All")
        parsed = parse_scope(scope)
        selector = None if isinstance(parsed, str) or set(_leaves(parsed)) & UNEVALUATED else parsed
        priority = int(values.get("PRIORITY", "1") or 1)
        out.append(_Rule(values.get("NAME", kind), priority, selector, round(expansion * NM_PER_UNIT), scope))
    return sorted(out, key=lambda rule: rule.priority)


def _governing(rules: list[_Rule], subject: RuleSubject) -> tuple[_Rule | None, bool]:
    """The first rule by priority that matches ``subject``, and whether a rule of higher priority could not
    be evaluated before it."""
    skipped = False
    for rule in rules:
        if rule.selector is None:
            skipped = True
            continue
        if rule.selector.matches(subject):
            return rule, skipped
    return None, skipped


def _board_names(data: bytes, file: str) -> dict[int, str]:
    if not is_compound(data):
        return {}
    compound = open_compound(data, file=file)
    if "Board6/Data" not in compound:
        return {}
    records, _trailing, _problems = parse_blocks(compound.read("Board6/Data"), where="Board6/Data")
    if not records:
        return {}
    board, _issues = read_board(records[0], where="Board6/Data")
    return {layer.id: layer.name for layer in board.layers if layer.name}


def _tab(layer_id: int, chain_place: int) -> int:
    for ids, group in TAB_GROUPS:
        if layer_id in ids:
            return group * 100 + (chain_place if group == 0 else layer_id)
    return 900 + layer_id


def native_view(design: Design, data: bytes, *, file: str = "") -> NativeView:
    """The native layer names, the order of the tabs and the pad openings of an imported Altium board."""
    view = NativeView()
    board = design.board
    if board is None:
        return view
    names = _board_names(data, file)
    for place, layer in enumerate(board.layers):
        bag = layer.ext.get("altium")
        layer_id = _ext(bag, "layer_id")
        if layer_id is not None:
            view.tabs[layer.name] = _tab(int(layer_id), place)
            view.labels[layer.name] = _ext(bag, "altium_name") or names.get(int(layer_id), "")
    for layer_id, (model_name, _kind) in LAYERS.items():  # layers the scene derives (masks, pastes)
        if model_name not in view.labels:
            view.labels[model_name] = names.get(layer_id) or LAYER_NAMES.get(layer_id, model_name)
            view.tabs[model_name] = _tab(layer_id, 0)
    view.labels["Edge.Cuts"] = EDGE_LABEL
    view.tabs.setdefault("Edge.Cuts", _tab(56, 0) - 1)
    view.labels = {key: value for key, value in view.labels.items() if value}
    view.parts = _parts(data, file)

    mask_rules, paste_rules = _rules(data, MASK_RULE, file), _rules(data, PASTE_RULE, file)
    refs = {c.id: c.ref for c in design.circuit.components}
    nets = {n.id: n.name for n in design.circuit.nets}
    fallback = 0
    for fp in board.footprints:
        ref = refs.get(fp.component_id)
        for pad in fp.pads:
            subject = RuleSubject("pad", net=nets.get(pad.net_id or ""), ref=ref)
            bag = pad.ext.get("altium")
            values: list[tuple[int, str]] = []
            for key, rules, default in (
                ("mask", mask_rules, DEFAULT_MASK_NM),
                ("paste", paste_rules, DEFAULT_PASTE_NM),
            ):
                manual = _ext(bag, key)
                if manual is not None:
                    mode, _, amount = manual.partition(",")
                    nm = round(int(amount) * NM_PER_UNIT) if mode == "2" else 0
                    values.append((nm, "manual" if mode == "2" else "none"))
                    continue
                rule, skipped = _governing(rules, subject)
                fallback += skipped
                if rule is None:
                    values.append((default, "default"))
                else:
                    values.append((rule.expansion, f"rule {rule.name}"))
            (mask, mask_source), (paste, paste_source) = values
            view.openings[pad.id] = Opening(mask, paste, mask_source, paste_source)
    if fallback:
        view.notes.append(
            f"{fallback} pad expansion(s) skip a rule whose scope Fenolite does not evaluate (a net class, a "
            "layer or a query outside read.scope) and take the next rule."
        )
    if any(o.mask_source == "default" or o.paste_source == "default" for o in view.openings.values()):
        view.notes.append(
            "Pads that no expansion rule governs use 4 mil of solder-mask expansion and no paste expansion "
            "(Fenolite's default)."
        )
    return view


__all__ = ["NM_PER_UNIT", "PART_FIELDS", "NativeView", "Opening", "native_view"]
