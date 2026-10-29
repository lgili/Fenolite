# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lens adoption of an imported board (change c0275, design decision 12).

``adopt`` rewrites the source board by token edits only: each footprint takes the uuid and the
``fenolite.path`` property that the build of the emitted code gives it, each of its pads the build's pad
uuid, and each track, arc, via, zone, rule area, drawing and text the uuid of its twin in the built board.
The build itself is the oracle of every derived identity, so nothing here repeats a derivation: the twin
of a source item is the built item with the same reference (a footprint), the same pad index (a pad), or
the same geometry (everything else), and the self-check has proved that every one of them came through.
Every other byte of the source stays as it is. A source item without a twin keeps its uuid and is counted.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.model.base import Entity
from fenolite.model.design import Design

PATH_PROPERTY = "fenolite.path"
_LOCATOR = re.compile(r"([A-Za-z_]+)\[(\d+)\]")
_UUID = re.compile(rb'\(uuid\s+"([0-9a-fA-F-]{36})"')


@dataclass(frozen=True, slots=True)
class Adopted:
    """The adopted board text, the counts of rewritten uuids by kind, of added ``fenolite.path``
    properties, and of source items left without a twin, by kind."""

    text: str
    rewritten: Mapping[str, int] = field(default_factory=lambda: {})
    paths: int = 0
    unmatched: Mapping[str, int] = field(default_factory=lambda: {})

    def as_json(self) -> dict[str, object]:
        return {
            "rewritten": dict(sorted(self.rewritten.items())),
            "paths": self.paths,
            "unmatched": dict(sorted(self.unmatched.items())),
        }


def _node_at(root: Node, locator: str) -> Node | None:
    """The node a reader's locator (``/kicad_pcb/footprint[3]/pad[0]``) names, or ``None``."""
    parts = [p for p in locator.split("/") if p]
    if not parts or parts[0] != root.name:
        return None
    node = root
    for part in parts[1:]:
        match = _LOCATOR.fullmatch(part)
        if match is None:
            return None
        found = node.nodes(match.group(1))
        index = int(match.group(2))
        if index >= len(found):
            return None
        node = found[index]
    return node


def _locator(item: Entity) -> str:
    return item.provenance.locator if item.provenance is not None else ""


def _end(data: bytes, start: int) -> int:
    """The byte offset just past the list that opens at ``start``, strings and their escapes skipped."""
    depth, index, quoted = 0, start, False
    while index < len(data):
        char = data[index : index + 1]
        if quoted:
            if char == b"\\":
                index += 1
            elif char == b'"':
                quoted = False
        elif char == b'"':
            quoted = True
        elif char == b"(":
            depth += 1
        elif char == b")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise ValueError(f"unbalanced list at {start}")


def _indented(text: str, pad: str) -> str:
    """``text`` on a new line at the indentation ``pad``, its inner lines below it."""
    return "".join(f"\n{pad}{line}" for line in text.split("\n"))


class _Edits:
    """Edits of a text by byte offset (the offsets of the parser): replacements and insertions, applied
    from the end."""

    def __init__(self, text: str) -> None:
        self.data = text.encode("utf-8")
        self.edits: list[tuple[int, int, bytes]] = []

    def uuid(self, node: Node, value: str) -> bool:
        """Replace the uuid of ``node``'s own ``(uuid "…")`` child; whether there was one."""
        child = node.find("uuid")
        if child is None or child.offset is None:
            return False
        match = _UUID.match(self.data, child.offset)
        if match is None:
            return False
        if match.group(1).decode("ascii") != value:
            self.edits.append((match.start(1), match.end(1), value.encode("ascii")))
        return True

    def insert(self, offset: int, value: str) -> None:
        self.edits.append((offset, offset, value.encode("utf-8")))

    def apply(self) -> str:
        data = self.data
        for start, end, value in sorted(self.edits, key=lambda e: (e[0], e[1]), reverse=True):
            data = data[:start] + value + data[end:]
        return data.decode("utf-8")


def _points(points: Sequence[object]) -> tuple[object, ...]:
    return tuple(points)


def adopt(source_text: str, source: Design, built_text: str, built: Design) -> Adopted:
    """``source_text`` (the board ``source`` was read from) with the identities of ``built`` (the board the
    emitted code builds, read from ``built_text``)."""
    root = parse(source_text)
    built_root = parse(built_text)
    edits = _Edits(source_text)
    rewritten: dict[str, int] = {}
    unmatched: dict[str, int] = {}
    paths = 0
    sb, bb = source.board, built.board
    if sb is None or bb is None:
        return Adopted(source_text)

    def done(kind: str, ok: bool) -> None:
        bucket = rewritten if ok else unmatched
        bucket[kind] = bucket.get(kind, 0) + 1

    refs = {c.id: c.ref for c in source.circuit.components}
    built_refs = {c.id: c.ref for c in built.circuit.components}
    built_by_ref = {built_refs.get(fp.component_id, ""): fp for fp in bb.footprints}
    for footprint in sb.footprints:
        twin = built_by_ref.get(refs.get(footprint.component_id, ""))
        node = _node_at(root, _locator(footprint))
        if twin is None or node is None or "kicad" not in twin.native_ids:
            done("footprint", False)
            continue
        done("footprint", edits.uuid(node, twin.native_ids["kicad"]))
        for pad, other in zip(footprint.pads, twin.pads, strict=False):
            pad_node = _node_at(root, _locator(pad))
            uuid = other.native_ids.get("kicad")
            ok = pad_node is not None and uuid is not None and pad.number == other.number
            done("pad", ok and edits.uuid(pad_node, uuid))  # type: ignore[arg-type]
        twin_node = _node_at(built_root, _locator(twin))
        has_path = any(p.atoms() and p.atoms()[0].value == PATH_PROPERTY for p in node.nodes("property"))
        prop = next(
            (
                p
                for p in (twin_node.nodes("property") if twin_node else ())
                if p.atoms()[0].value == PATH_PROPERTY
            ),
            None,
        )
        if prop is not None and not has_path and node.offset is not None:
            properties = node.nodes("property")
            anchor = properties[-1] if properties else node.find("layer")
            if anchor is not None and anchor.offset is not None:
                edits.insert(_end(edits.data, anchor.offset), _indented(dumps(prop).strip(), "\t\t"))
                paths += 1
    names = {net.id: net.name for net in source.circuit.nets}
    built_names = {net.id: net.name for net in built.circuit.nets}

    def net(item: Entity, table: Mapping[str, str]) -> str:
        return table.get(getattr(item, "net_id", None) or "", "")

    groups: list[
        tuple[str, Sequence[Entity], Sequence[Entity], Callable[[Entity, Mapping[str, str]], Hashable]]
    ] = [
        ("track", sb.tracks, bb.tracks, lambda t, n: (t.start, t.end, t.width, t.layer, net(t, n))),  # type: ignore[attr-defined]
        ("arc", sb.arcs, bb.arcs, lambda a, n: (a.start, a.mid, a.end, a.width, a.layer, net(a, n))),  # type: ignore[attr-defined]
        ("via", sb.vias, bb.vias, lambda v, n: (v.position, v.diameter, v.drill, tuple(v.layers), net(v, n))),  # type: ignore[attr-defined]
        ("zone", sb.zones, bb.zones, lambda z, n: (tuple(z.layers), _points(z.outline), net(z, n))),  # type: ignore[attr-defined]
        ("rule_area", sb.keepouts, bb.keepouts, lambda k, n: (tuple(k.layers), _points(k.outline))),  # type: ignore[attr-defined]
        ("graphic", sb.graphics, bb.graphics, lambda g, n: (g.layer, g.kind, _points(g.points), g.width)),  # type: ignore[attr-defined]
        ("text", sb.texts, bb.texts, lambda t, n: (t.layer, t.text, t.position)),  # type: ignore[attr-defined]
    ]
    for kind, mine, theirs, key in groups:
        pool: dict[Hashable, list[Entity]] = {}
        for item in theirs:
            pool.setdefault(key(item, built_names), []).append(item)
        for item in mine:
            found = pool.get(key(item, names))
            twin = found.pop(0) if found else None
            node = _node_at(root, _locator(item))
            uuid = twin.native_ids.get("kicad") if twin is not None else None
            done(kind, node is not None and uuid is not None and edits.uuid(node, uuid))  # type: ignore[arg-type]
    return Adopted(edits.apply(), rewritten, paths, unmatched)


__all__ = ["PATH_PROPERTY", "Adopted", "adopt"]
