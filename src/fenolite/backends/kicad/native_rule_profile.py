# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded original-to-emitted native-rule selector context, never a rule verdict (c0359)."""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import Any

from fenolite.backends.kicad import dru, pcb, rulemap
from fenolite.backends.kicad.sexpr import parse
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model import canonical
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-DRU-IMMUTABLE-CONTEXT",))

_TOKEN = re.compile(
    r"\s*(A\.isPlated\(\)|B\.isPlated\(\)|"
    r"[AB]\.(?:Type|Net|Layer|Fabrication_Property)|'[^']*'|==|!=|&&|\|\||!|\(|\))"
)
_TYPES = {"'track'", "'Track'", "'pad'", "'Pad'", "'Text'", "'Text Box'"}
_CONSTRAINTS = {
    "track_width",
    "clearance",
    "text_thickness",
    "text_height",
    "silk_clearance",
    "edge_clearance",
    "hole_size",
    "annular_width",
    "hole_to_hole",
    "hole_clearance",
}
_SILK = {"F.SilkS", "B.SilkS"}


def _condition(text: str, layer: str) -> None:
    tokens: list[str] = []
    offset = 0
    while offset < len(text):
        match = _TOKEN.match(text, offset)
        if match is None:
            if not text[offset:].strip():
                break
            raise FormatError("native rule condition is outside the proved immutable profile")
        tokens.append(match.group(1))
        offset = match.end()
    index = 0

    def take() -> str:
        nonlocal index
        if index >= len(tokens):
            raise FormatError("incomplete native rule condition")
        value = tokens[index]
        index += 1
        return value

    def term() -> None:
        nonlocal index
        left = take()
        if left == "!":
            term()
            return
        if left == "(":
            expression()
            if take() != ")":
                raise FormatError("unsupported native rule condition grouping")
            return
        if left in {"A.isPlated()", "B.isPlated()"}:
            return
        operator, right = take(), take()
        allowed = operator in {"==", "!="} and (
            (left in {"A.Type", "B.Type"} and right in _TYPES)
            or (left == "B.Type" and right == "A.Type")
            or (left == "A.Net" and right == "B.Net")
            or (left in {"A.Layer", "B.Layer"} and right == "'?.Silkscreen'")
            or (left in {"A.Fabrication_Property", "B.Fabrication_Property"} and right == "'Castellated pad'")
        )
        if not allowed or (right in {"'Text'", "'Text Box'"} and layer != "?.Silkscreen"):
            raise FormatError("native rule condition is outside the proved immutable profile")

    def expression() -> None:
        nonlocal index
        term()
        while index < len(tokens) and tokens[index] in {"&&", "||"}:
            index += 1
            term()

    if not tokens:
        raise FormatError("empty native rule condition is outside the proved immutable profile")
    expression()
    if index != len(tokens):
        raise FormatError("unsupported trailing native rule condition")


def validate_profile(text: str) -> int:
    """Only generic measured properties/operators and physical constraints; no project names."""
    count = 0
    for item in dru.parse_rules(text).items:
        if not isinstance(item, dru.RuleItem):
            continue
        rule = item.node
        if rule.name != "rule" or len(rule.atoms()) != 1:
            raise FormatError("native rule list is outside the proved immutable profile")
        layer = ""
        layers = rule.nodes("layer")
        conditions = rule.nodes("condition")
        if len(layers) > 1 or len(conditions) > 1:
            raise FormatError("duplicate native rule context clauses")
        if layers:
            values = layers[0].atoms()
            if len(values) != 1 or values[0].value not in {"outer", "inner", "?.Silkscreen"}:
                raise FormatError("native layer is outside the proved immutable profile")
            layer = values[0].value
        if conditions:
            values = conditions[0].atoms()
            if len(values) != 1:
                raise FormatError("native condition is not a single expression")
            _condition(values[0].value, layer)
        constraints = rule.nodes("constraint")
        if not constraints:
            raise FormatError("native rule has no physical constraint")
        for child in rule.nodes():
            if child.name not in {"layer", "condition", "constraint"}:
                raise FormatError("native clause is outside the proved immutable profile")
        for constraint in constraints:
            values = constraint.atoms()
            if len(values) != 1 or values[0].value not in _CONSTRAINTS:
                raise FormatError("native constraint is outside the proved immutable profile")
            if not constraint.nodes() or any(c.name not in {"min", "max", "opt"} for c in constraint.nodes()):
                raise FormatError("native constraint limits are outside the proved immutable profile")
            seen_limits: set[str] = set()
            for limit in constraint.nodes():
                values = limit.atoms()
                if limit.nodes() or len(values) != 1 or limit.name in seen_limits:
                    raise FormatError("native constraint limits are malformed or duplicated")
                seen_limits.add(limit.name)
                try:
                    rulemap.parse_value(values[0].text)
                except ValueError as error:
                    raise FormatError(
                        "native constraint limit is outside the exact supported units"
                    ) from error
        count += 1
    return count


def _partitions(design: Design) -> dict[str | None, str]:
    """Physical equivalence classes, not net spellings; ambiguity refuses rather than conflates."""
    board = design.board
    if board is None:
        raise FormatError("native rule context requires a board")
    refs = {component.id: component.ref for component in design.circuit.components}
    known = {net.id for net in design.circuit.nets}
    members: dict[str | None, list[str]] = defaultdict(list)

    def add(net_id: str | None, identity: object) -> None:
        if net_id is not None and net_id not in known:
            raise FormatError("native rule context has an unbound physical net")
        members[net_id].append(canonical.dumps(identity))

    for fp in board.footprints:
        if fp.component_id not in refs:
            raise FormatError("native rule context has an unbound physical component")
        for pad in fp.pads:
            add(
                pad.net_id,
                (
                    "pad",
                    refs[fp.component_id],
                    pad.number,
                    pad.position,
                    pad.size,
                    pad.rotation % 360_000_000,
                ),
            )
    for track in board.tracks:
        ends = sorted(((track.start.x, track.start.y), (track.end.x, track.end.y)))
        add(track.net_id, ("track", ends, track.width, track.layer))
    for arc in board.arcs:
        ends = sorted(((arc.start.x, arc.start.y), (arc.end.x, arc.end.y)))
        add(arc.net_id, ("arc", ends, arc.mid, arc.width, arc.layer))
    for via in board.vias:
        add(via.net_id, ("via", via.position, via.diameter, via.drill, via.layers, via.via_type))
    for zone in board.zones:
        add(zone.net_id, ("zone", zone.outline, zone.layers))
    found: dict[str | None, str] = {None: "NO_NET"}
    seen: set[str] = set()
    for net_id, items in members.items():
        if net_id is None:
            continue
        key = hashlib.sha256(canonical.dumps(sorted(items)).encode()).hexdigest()
        if key in seen:
            raise FormatError("native rule context physical net partitions are ambiguous")
        seen.add(key)
        found[net_id] = key
    return found


def _attributes(design: Design) -> Counter[str]:
    board = design.board
    if board is None:
        raise FormatError("native rule context requires a board")
    nets = _partitions(design)
    rows: list[Any] = []
    for fp in board.footprints:
        for pad in fp.pads:
            rows.append(("pad", pad.kind, pad.fab_property, tuple(pad.layers), nets[pad.net_id]))
    for track in board.tracks:
        rows.append(("track", track.layer, nets[track.net_id]))
    for arc in board.arcs:
        rows.append(("arc", arc.layer, nets[arc.net_id]))
    for via in board.vias:
        rows.append(("via", via.via_type, tuple(via.layers), nets[via.net_id]))
    for zone in board.zones:
        rows.append(("zone", tuple(zone.layers), nets[zone.net_id]))
    rows.append(("layers", tuple((x.name, x.kind, x.ordinal) for x in board.layers)))
    return Counter(canonical.dumps(row) for row in rows)


def _silk(text: str) -> Counter[tuple[str, str]]:
    root = parse(text)
    rows: list[tuple[str, str]] = []
    allowed = {"line", "arc", "rect", "poly", "circle", "text", "text_box"}
    for parent in (root, *root.nodes("footprint")):
        for child in parent.nodes():
            layer = child.find("layer")
            if layer is None or not layer.atoms() or layer.atoms()[0].value not in _SILK:
                continue
            kind = child.name.removeprefix("gr_").removeprefix("fp_")
            if kind == "property":
                kind = "text"
            if kind not in allowed:
                raise FormatError("native silkscreen item is outside the proved immutable profile")
            rows.append((kind, layer.atoms()[0].value))
    return Counter(rows)


def context_models(original: str, emitted: str, rules: str) -> tuple[Design, Design, int]:
    """Independently bind selected native attributes AND exact original-to-output geometry."""
    count = validate_profile(rules)
    source = pcb.read_board(original, file="source.kicad_pcb")
    target = pcb.read_board(emitted, file="emitted.kicad_pcb")
    if _attributes(source) != _attributes(target) or _silk(original) != _silk(emitted):
        raise FormatError("source-to-emitted native rule attributes differ")
    return source, target, count
