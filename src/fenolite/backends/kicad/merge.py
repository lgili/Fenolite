# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Three-way merge of KiCad boards by root item (capability file-safety, "Three-way difference of KiCad
boards"; facts: ``docs/formats/kicad/board.md``, "Three-way merge of boards"; change c0207).

The root children of ``BASE``, ``OURS`` and ``THEIRS`` are matched by key: ``<head> <uuid>`` for an item
with a ``uuid`` (``tstamp`` in old files), the head alone for a head without a uuid that each file holds at
most once (``general``, ``setup``, …), else ``<head> <compact text>``, numbered when repeated. Each key
that differs between ``BASE`` and ``OURS`` is applied to ``THEIRS`` when ``THEIRS`` still holds the base
form, is already there when ``THEIRS`` holds the form of ``OURS``, and is a conflict otherwise. A footprint
is one item: a pad changed on one side and the footprint moved on the other is a conflict.

The merged bytes are those of ``THEIRS`` with the text of each changed item of ``OURS`` spliced in, so every
item that did not change keeps its bytes. The result is parsed again and must be the expected tree.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.backends.kicad.sexpr import AtomKind, Node, dumps, parse_bytes
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-MERGE-ITEMS",))
"""``INFERRED``: the item keys are those of ``H-K-PCB-UUID`` and ``H-K-UUID-KEEP-2``; that a board spliced
item by item loads in KiCad is the open row ``H-K-MERGE-ITEMS``."""
UUID_HEADS = ("uuid", "tstamp")
ROOT = "kicad_pcb"
ItemChange = Literal["added", "removed", "changed"]
ItemStatus = Literal["applied", "already", "conflict"]
_SCAN = re.compile(rb'"(?:[^"\\\r\n]|\\[^\r\n])*"|[()]|[^()"]+|"')


@dataclass(frozen=True, slots=True)
class MergeItem:
    """One root item that differs between ``BASE`` and ``OURS``, and what the merge did with it."""

    key: str
    change: ItemChange
    status: ItemStatus


@dataclass(frozen=True, slots=True)
class Merge:
    """The outcome of :func:`three_way`. ``data`` is the merged board, or ``None`` when an item is a
    conflict or the boards cannot be merged (``refused`` says why)."""

    data: bytes | None
    items: tuple[MergeItem, ...]
    refused: str | None = None

    @property
    def conflicts(self) -> tuple[MergeItem, ...]:
        return tuple(item for item in self.items if item.status == "conflict")


def _uuid(node: Node) -> str | None:
    for child in node.nodes():
        if child.name in UUID_HEADS:
            atoms = child.atoms()
            if len(atoms) == 1:
                return atoms[0].value
    return None


def _numbered(keys: Sequence[str]) -> list[str]:
    seen: Counter[str] = Counter()
    out: list[str] = []
    for key in keys:
        out.append(key if not seen[key] else f"{key}#{seen[key]}")
        seen[key] += 1
    return out


def _singles(roots: Sequence[Node]) -> frozenset[str]:
    """The heads without a uuid that each of ``roots`` holds at most once."""
    heads: set[str] = set()
    repeated: set[str] = set()
    for root in roots:
        counts = Counter(child.name for child in root.nodes() if _uuid(child) is None)
        heads |= set(counts)
        repeated |= {head for head, count in counts.items() if count > 1}
    return frozenset(heads - repeated)


def _keyed(root: Node, singles: frozenset[str]) -> list[tuple[str, Node]]:
    """The root children of ``root`` with their keys, in file order."""
    nodes = root.nodes()
    keys: list[str] = []
    for node in nodes:
        uuid = _uuid(node)
        if uuid is not None:
            keys.append(f"{node.name} {uuid}")
        elif node.name in singles:
            keys.append(node.name)
        else:
            keys.append(f"{node.name} {dumps(node, style='compact')}")
    return list(zip(_numbered(keys), nodes, strict=True))


def _version(root: Node) -> str:
    found = root.find("version")
    return " ".join(atom.text for atom in found.atoms()) if found is not None else ""


def _net_table(root: Node) -> tuple[Node, ...]:
    """The numbered net table of a board (KiCad 9 and older forms), empty for a board that names nets."""
    return tuple(
        node for node in root.nodes("net") if node.atoms() and node.atoms()[0].kind == AtomKind.NUMBER
    )


def _refusal(base: Node, ours: Node, theirs: Node) -> str | None:
    roots = (base, ours, theirs)
    if any(root.name != ROOT for root in roots):
        return "a three-way merge takes three KiCad boards"
    versions = [_version(root) for root in roots]
    if len(set(versions)) != 1:
        return f"the boards are of versions {', '.join(versions)}; a merge needs one version"
    if len({_net_table(root) for root in roots}) != 1:
        return "the numbered net tables differ, so a net number does not name one net in the three boards"
    if len({root.atoms() for root in roots}) != 1 or len({root.comments for root in roots}) != 1:
        return "the root atoms or the comments before the root differ"
    return None


def _end(data: bytes, start: int) -> int:
    """The offset just after the list that opens at ``start``."""
    depth = 0
    for match in _SCAN.finditer(data, start):
        token = match.group()
        if token == b"(":
            depth += 1
        elif token == b")":
            depth -= 1
            if depth == 0:
                return match.end()
    raise ValueError(f"the list at byte {start} is not closed")


def _line_start(data: bytes, start: int) -> int:
    """The start of the line of ``start`` when only blanks precede it on that line, else ``start``."""
    begin = data.rfind(b"\n", 0, start) + 1
    return begin if not data[begin:start].strip(b" \t") else start


@dataclass(frozen=True, slots=True)
class _Span:
    start: int
    end: int
    line: int

    @classmethod
    def of(cls, data: bytes, node: Node) -> _Span:
        assert node.offset is not None
        return cls(node.offset, _end(data, node.offset), _line_start(data, node.offset))


def _changes(
    base: Mapping[str, Node], ours: Mapping[str, Node], theirs: Mapping[str, Node], order: Sequence[str]
) -> list[MergeItem]:
    items: list[MergeItem] = []
    for key in order:
        before, after, other = base.get(key), ours.get(key), theirs.get(key)
        if before == after:
            continue
        change: ItemChange = "added" if before is None else "removed" if after is None else "changed"
        status: ItemStatus = "already" if other == after else "applied" if other == before else "conflict"
        items.append(MergeItem(key, change, status))
    return items


def three_way(base: bytes, ours: bytes, theirs: bytes) -> Merge:
    """``THEIRS`` with the root items that changed from ``BASE`` to ``OURS`` applied. The readers'
    ``FormatError`` is raised unchanged."""
    roots = [
        parse_bytes(data, file=name) for data, name in ((base, "BASE"), (ours, "OURS"), (theirs, "THEIRS"))
    ]
    refused = _refusal(*roots)
    if refused is not None:
        return Merge(None, (), refused)
    singles = _singles(roots)
    base_items, ours_items, theirs_items = (_keyed(root, singles) for root in roots)
    base_map, ours_map, theirs_map = dict(base_items), dict(ours_items), dict(theirs_items)
    order = [key for key, _ in ours_items] + [key for key, _ in base_items if key not in ours_map]
    items = _changes(base_map, ours_map, theirs_map, order)
    if any(item.status == "conflict" for item in items):
        return Merge(None, tuple(items))
    applied = {item.key: item for item in items if item.status == "applied"}
    if all(key in applied and applied[key].change == "removed" for key, _ in theirs_items):
        return Merge(None, tuple(items), "the merge would remove every item of THEIRS")
    merged = _splice(theirs, ours, theirs_items, ours_items, applied)
    expected = _expected(theirs_items, ours_items, applied)
    again = parse_bytes(merged, file="merged")
    if again.nodes() != tuple(expected) or again.head != roots[2].head:
        raise AssertionError("the spliced board does not parse to the merged items")  # a bug of the splice
    return Merge(merged, tuple(items))


def _anchors(
    theirs_items: Sequence[tuple[str, Node]],
    ours_items: Sequence[tuple[str, Node]],
    applied: Mapping[str, MergeItem],
) -> dict[str, list[tuple[str, Node]]]:
    """The added items of ``OURS`` by the kept item of ``THEIRS`` that they follow: the nearest one before
    them in ``OURS``, else the last kept item of ``THEIRS``."""
    kept = [key for key, _ in theirs_items if not (key in applied and applied[key].change == "removed")]
    present = set(kept)
    last = kept[-1]
    anchors: dict[str, list[tuple[str, Node]]] = {}
    anchor = last
    seen_anchor = False
    for key, node in ours_items:
        if key in present:
            anchor, seen_anchor = key, True
        elif key in applied and applied[key].change == "added":
            anchors.setdefault(anchor if seen_anchor else last, []).append((key, node))
    return anchors


def _expected(
    theirs_items: Sequence[tuple[str, Node]],
    ours_items: Sequence[tuple[str, Node]],
    applied: Mapping[str, MergeItem],
) -> list[Node]:
    ours_map = dict(ours_items)
    anchors = _anchors(theirs_items, ours_items, applied)
    out: list[Node] = []
    for key, node in theirs_items:
        item = applied.get(key)
        if item is not None and item.change == "removed":
            continue
        out.append(ours_map[key] if item is not None else node)
        out += [added for _, added in anchors.get(key, [])]
    return out


def _ends(text: bytes, newline: bytes) -> bytes:
    """``text`` with the line ends of the merged file (an atom holds no raw line end)."""
    return text.replace(b"\r\n", b"\n").replace(b"\n", newline)


def _splice(
    theirs: bytes,
    ours: bytes,
    theirs_items: Sequence[tuple[str, Node]],
    ours_items: Sequence[tuple[str, Node]],
    applied: Mapping[str, MergeItem],
) -> bytes:
    newline = b"\r\n" if b"\r\n" in theirs else b"\n"
    ours_map = dict(ours_items)
    anchors = _anchors(theirs_items, ours_items, applied)
    edits: list[tuple[int, int, bytes]] = []
    for key, node in theirs_items:
        span = _Span.of(theirs, node)
        item = applied.get(key)
        if item is not None and item.change == "removed":
            stop = span.end
            if span.line != span.start:  # the item had its own line: its line break goes with it
                if theirs[stop : stop + 2] == b"\r\n":
                    stop += 2
                elif theirs[stop : stop + 1] == b"\n":
                    stop += 1
            edits.append((span.line, stop, b""))
            continue
        if item is not None:
            source = _Span.of(ours, ours_map[key])
            edits.append((span.start, span.end, _ends(ours[source.start : source.end], newline)))
        added = anchors.get(key, [])
        if added:
            texts: list[bytes] = []
            for _, new in added:
                source = _Span.of(ours, new)
                texts.append(newline + _ends(ours[source.line : source.end], newline))
            edits.append((span.end, span.end, b"".join(texts)))
    out = theirs
    for start, stop, text in sorted(edits, key=lambda edit: (edit[0], edit[1]), reverse=True):
        out = out[:start] + text + out[stop:]
    return out


__all__ = ["EVIDENCE", "Merge", "MergeItem", "three_way"]
