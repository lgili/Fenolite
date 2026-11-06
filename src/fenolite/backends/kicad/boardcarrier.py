# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Data of an Altium source carried in a KiCad board as board properties (change c0434; ``board.md``,
"Fenolite board properties").

A conversion of an Altium document to KiCad keeps what KiCad has no item for, and what the way back
needs to write the source as it was, in root-level ``(property "Fenolite.Altium.<Name>" "<payload>")``
nodes of the ``.kicad_pcb``. The payload is the base64 text of the zlib-compressed bytes, so it holds no
character that needs escaping. KiCad holds a board's properties as text variables and writes them back
after ``setup``. The carrier travels with the board alone: no file beside it.

``with_carried`` writes the properties into board text, replacing those of the same names and leaving
every other byte as it was; ``carried`` reads them back. Other changes reuse this module (c0450).
"""

from __future__ import annotations

import base64
import binascii
import re
import zlib
from collections.abc import Mapping

from fenolite.backends.kicad.sexpr import Atom, Node, parse
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-FENOLITE-PROPS",))
PREFIX = "Fenolite.Altium."
"""Every carried property's name starts with it."""
_NAME = re.compile(r"^Fenolite\.Altium\.[A-Za-z][A-Za-z0-9_.]*$")


def pack(data: bytes) -> str:
    """The property value for ``data``: base64 of its zlib compression (level 9)."""
    return base64.b64encode(zlib.compress(data, 9)).decode("ascii")


def unpack(text: str) -> bytes:
    """The bytes of a property value; ``ValueError`` for a value that is not base64 of zlib bytes."""
    try:
        return zlib.decompress(base64.b64decode(text.encode("ascii"), validate=True))
    except (UnicodeEncodeError, binascii.Error, zlib.error) as error:
        raise ValueError(f"not a carried value: {error}") from None


def _check(name: str) -> None:
    if not _NAME.match(name):
        raise ValueError(f"a carried property is named {PREFIX}<Name>, not {name!r}")


def _root(data: bytes) -> Node:
    root = parse(data.decode("utf-8"))
    if root.name != "kicad_pcb":
        raise FormatError("not a KiCad board", locator=root.name)
    return root


def _spans(root: Node, data: bytes) -> list[tuple[Node, int, int]]:
    """Each root child list with its byte span: from its ``(`` to the next child's, or to the root's
    closing ``)`` for the last, whitespace before that ``)`` excluded."""
    children = [child for child in root.children if isinstance(child, Node)]
    close = data.rstrip().rindex(b")")
    found: list[tuple[Node, int, int]] = []
    for i, child in enumerate(children):
        start = child.offset
        assert start is not None
        nxt = children[i + 1].offset if i + 1 < len(children) else None
        end = nxt if nxt is not None else len(data[:close].rstrip())
        found.append((child, start, end))
    return found


def _carried_name(child: Node) -> str | None:
    atoms = child.atoms()
    if child.name != "property" or not atoms:
        return None
    name = atoms[0].value
    return name if name.startswith(PREFIX) else None


def carried(text: str) -> dict[str, bytes]:
    """Property name → its unpacked bytes, for every ``Fenolite.Altium.*`` property of a board's root;
    empty for a board that holds none. A value that does not unpack is left out."""
    if f'"{PREFIX}' not in text:
        return {}
    found: dict[str, bytes] = {}
    for child in _root(text.encode("utf-8")).nodes("property"):
        name = _carried_name(child)
        atoms = child.atoms()
        if name is None or len(atoms) < 2:
            continue
        try:
            found[name] = unpack(atoms[1].value)
        except ValueError:
            continue
    return found


def _line(name: str, value: str) -> str:
    return f"(property {Atom.string(name).text} {Atom.string(value).text})"


def with_carried(text: str, items: Mapping[str, bytes]) -> str:
    """``text`` with one root ``property`` per item, packed (``pack``), after ``setup`` (after ``layers``
    without one). Every ``Fenolite.Altium.*`` property is written there in name order: an item replaces
    the property of its name, the others keep their values. Every other byte stays as it was."""
    if not items:
        return text
    for name in items:
        _check(name)
    data = text.encode("utf-8")
    spans = _spans(_root(data), data)
    anchor = next((s for s in spans if s[0].name == "setup"), None) or next(
        (s for s in spans if s[0].name == "layers"), None
    )
    if anchor is None:
        raise FormatError("a board without layers", locator="kicad_pcb")
    start, end = anchor[1], anchor[2]
    indent = data[data.rfind(b"\n", 0, start) + 1 : start]
    at = data.rindex(b")", start, end) + 1  # right after the anchor's own ``)``
    values: dict[str, str] = {}
    edits: list[tuple[int, int, bytes]] = []
    for child, s, e in spans:
        name = _carried_name(child)
        if name is not None:  # its line break and indent before it, up to its own ``)``
            atoms = child.atoms()
            values[name] = atoms[1].value if len(atoms) > 1 else ""
            edits.append((data.rfind(b"\n", 0, s), data.rindex(b")", s, e) + 1, b""))
    values.update({name: pack(data_) for name, data_ in items.items()})
    block = "".join(f"\n{indent.decode()}{_line(name, values[name])}" for name in sorted(values))
    edits.append((at, at, block.encode("utf-8")))
    for s, e, new in sorted(edits, reverse=True):
        data = data[:s] + new + data[e:]
    return data.decode("utf-8")


__all__ = ["EVIDENCE", "PREFIX", "carried", "pack", "unpack", "with_carried"]
