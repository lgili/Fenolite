# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The check canary: proof, in the same DRC run, that a project's custom rules were loaded (capability
kicad-oracle, "Check canary injection"; ``docs/formats/kicad/drc.md``, "Check canary").

KiCad drops a rules file with one error whole and still exits 0 (``H-K-TOK-RULES-SILENT``, S-0038), so a
clean report proves nothing about custom rules. The canary appends a ``clearance`` rule on its own net
after the user's rules, where the later rule governs (``H-K-DRU-ORDER``, S-0010, S-0038), and inserts two
tracks of its own nets 25 mm beyond every board coordinate. Their clearance violation appears exactly
when the rules were loaded (``H-K-CHECK-CANARY-2``). Both are inserted as text into temporary copies: every
byte of the user's files is kept, and nothing is written to the project.
"""

from __future__ import annotations

import dataclasses
import uuid
from decimal import Decimal
from typing import Literal

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad import _json
from fenolite.backends.kicad.pcb import CANONICAL_ORDER
from fenolite.backends.kicad.rulemap import SELECTOR_SUPPORT, rule_nodes
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, parse_bytes
from fenolite.core.errors import FenoliteError
from fenolite.core.ids import FENOLITE_NS, derived_id
from fenolite.model.rules import Rule, Selector

CANARY_NETS = ("FENOLITE_CANARY_A", "FENOLITE_CANARY_B")
CANARY_UUIDS: tuple[str, str] = (
    str(uuid.uuid5(FENOLITE_NS, "kicad-canary:A")),
    str(uuid.uuid5(FENOLITE_NS, "kicad-canary:B")),
)
CANARY_RULE_NAME = "fenolite_check_canary"
CANARY_MIN_NM = 3_000_000
CANARY_WIDTH_NM = 250_000
CANARY_PITCH_NM = 1_000_000
CANARY_LENGTH_NM = 2_000_000
CANARY_MARGIN_NM = 25_000_000
CANARY_MAX_X_NM = 2_000_000_000
"""The canary's far end stays within ±2 000 mm, inside a board's 32-bit nanometre range (S-0010)."""
CANARY_SUPPORT: frozenset[int] = frozenset({9, 10})
"""Majors whose probe files record ``check-canary-fired`` present and ``check-canary-broken`` absent."""
CANARY_TWO_RUN: frozenset[int] = frozenset({9, 10})
"""Majors where the canary is not neutral, so a plain run gives the report and the canary run the verdict:
on boards with hundreds of violations, 9.0.9 and 10.0.6 name other partner items, and sometimes report
one violation more or less, with the canary tracks present (``H-K-CHECK-CANARY-2``)."""
CLEARANCE_SEVERITY = "/board/design_settings/rule_severities/clearance"

CanaryReason = Literal[
    "placement-unproven",
    "selector-unproven",
    "clearance-ignored",
    "names-taken",
    "board-unparsed",
    "extent-too-large",
    "no-front-copper",
    "no-report",
]
_COORDINATES = frozenset({"at", "xy", "start", "end", "mid", "center"})


class CanaryError(FenoliteError):
    """The canary cannot be placed in this project; ``reason`` says why."""

    def __init__(self, reason: CanaryReason, message: str = "") -> None:
        self.reason: CanaryReason = reason
        super().__init__(message or reason)


def canary_rule() -> Rule:
    return Rule(
        id=derived_id("rul", "kicad", "check-canary"),
        name=CANARY_RULE_NAME,
        kind="clearance",
        selector_a=Selector("net", CANARY_NETS[0]),
        min=CANARY_MIN_NM,
    )


def canary_rule_text(major: int) -> str | None:
    """The canary rule written for KiCad ``major``; ``None`` when the ``net`` selector is unproven there."""
    if major not in SELECTOR_SUPPORT["net"]:
        return None
    nodes, issues = rule_nodes(canary_rule(), target=major)
    if issues or not nodes:
        return None
    return "\n".join(dumps(node) for node in nodes)


def append_rule(rules: bytes, rule_text: str, *, major: int) -> bytes:
    """The user's rules bytes, unchanged, with the canary rule after them, where it governs.

    The later rule governs on every supported major (``H-K-DRU-ORDER``), so the rule goes last. A file of
    whitespace only gets ``(version 1)`` first. Unparsable bytes are kept as they are, and KiCad's verdict
    on them stands.
    """
    if CANARY_RULE_NAME.encode("utf-8") in rules:
        raise CanaryError("names-taken", f"the rules already name {CANARY_RULE_NAME!r}")
    tail = rule_text.encode("utf-8") + b"\n"
    if not rules.strip():
        return rules + b"(version 1)\n" + tail
    return rules + (b"" if rules.endswith(b"\n") else b"\n") + tail


def _largest(node: Node) -> tuple[int, int]:
    """The largest absolute coordinate number outside footprints, and inside them, in nm (rounded up)."""
    outside = inside = 0
    stack: list[tuple[Node, bool]] = [(node, False)]
    while stack:
        current, in_footprint = stack.pop()
        if current.name in _COORDINATES:
            for atom in current.atoms():
                if atom.kind == AtomKind.NUMBER:
                    value = int(abs(Decimal(atom.text)) * 1_000_000) + 1
                    if in_footprint:
                        inside = max(inside, value)
                    else:
                        outside = max(outside, value)
        for child in current.nodes():
            stack.append((child, in_footprint or child.name == "footprint"))
    return outside, inside


def _strings(node: Node) -> set[str]:
    found: set[str] = set()
    stack = [node]
    while stack:
        current = stack.pop()
        found.update(a.value for a in current.atoms() if a.kind == AtomKind.STRING)
        stack.extend(current.nodes())
    return found


def _segment(net: Atom | tuple[Atom, ...], uid: str, x: int, y: int) -> Node:
    net_atoms = net if isinstance(net, tuple) else (net,)
    children = {
        "start": Node(Atom.symbol("start"), (Atom.from_nm(x), Atom.from_nm(y))),
        "end": Node(Atom.symbol("end"), (Atom.from_nm(x + CANARY_LENGTH_NM), Atom.from_nm(y))),
        "width": Node(Atom.symbol("width"), (Atom.from_nm(CANARY_WIDTH_NM),)),
        "layer": Node(Atom.symbol("layer"), (Atom.string("F.Cu"),)),
        "net": Node(Atom.symbol("net"), net_atoms),
        "uuid": Node(Atom.symbol("uuid"), (Atom.string(uid),)),
    }
    return Node(Atom.symbol("segment"), tuple(children[name] for name in CANONICAL_ORDER["segment"]))


def insertions(data: bytes, *, file: str = "") -> list[tuple[int, bytes]]:
    """The ``(byte offset, UTF-8 text)`` pairs that ``inject_board`` inserts into ``data``, in order."""
    root = parse_bytes(data, file=file)
    taken = _strings(root) & {*CANARY_NETS, *CANARY_UUIDS}
    if taken:
        raise CanaryError("names-taken", f"the board already uses {', '.join(sorted(taken))}")
    layers = root.find("layers")
    if layers is None or "F.Cu" not in _strings(layers):
        raise CanaryError("no-front-copper", "the board has no F.Cu layer")
    outside, inside = _largest(root)
    x = outside + 2 * inside + CANARY_MARGIN_NM
    if x + CANARY_LENGTH_NM > CANARY_MAX_X_NM:
        raise CanaryError("extent-too-large", "the board extends too far to place the canary beyond it")
    children = root.children
    net_rows = [i for i, c in enumerate(children) if isinstance(c, Node) and c.name == "net"]
    numbered = [c for i in net_rows if (c := children[i]) and isinstance(c, Node) and c.atoms()
                and c.atoms()[0].kind == AtomKind.NUMBER]  # fmt: skip
    closing = data.rstrip().rfind(b")")
    found: list[tuple[int, bytes]] = []
    if numbered:
        first = max(c.atoms()[0].to_int() for c in numbered) + 1
        nets: tuple[tuple[Atom, ...], ...] = tuple((Atom.integer(first + i),) for i in range(2))
        rows = [Node(Atom.symbol("net"), (Atom.integer(first + i), Atom.string(name)))
                for i, name in enumerate(CANARY_NETS)]  # fmt: skip
        after = net_rows[-1] + 1
        nxt = children[after] if after < len(children) else None
        if isinstance(nxt, Node) and nxt.offset is not None:
            found.append(
                (nxt.offset, "".join(f"{dumps(r, style='compact')}\n\t" for r in rows).encode("utf-8"))
            )
        else:
            found.append((closing, "".join(f"\t{dumps(r, style='compact')}\n" for r in rows).encode("utf-8")))
    else:
        nets = tuple((Atom.string(name),) for name in CANARY_NETS)
    segments = [_segment(nets[i], CANARY_UUIDS[i], x, i * CANARY_PITCH_NM) for i in range(2)]
    found.append((closing, "".join(f"\t{dumps(s, style='compact')}\n" for s in segments).encode("utf-8")))
    return found


def inject_board(data: bytes, *, file: str = "") -> bytes:
    """``data`` with the two canary tracks (and, in the numbered net form, their two net rows) inserted.

    Raises ``FormatError`` for bytes that do not parse (invalid UTF-8 included) and ``CanaryError`` for a
    board that cannot take the canary. Every other byte, and every net number, is kept.
    """
    out = bytearray(data)
    for offset, text in sorted(insertions(data, file=file), key=lambda p: p[0], reverse=True):
        out[offset:offset] = text
    return bytes(out)


def clearance_ignored(project_text: str) -> bool:
    """Whether the project sets the ``clearance`` severity to ``ignore`` (an unreadable file: no)."""
    try:
        data = _json.loads(project_text)
    except (ValueError, FenoliteError):
        return False
    return _json.get(data, CLEARANCE_SEVERITY) == "ignore"


def _names_canary(violation: DrcViolation) -> bool:
    return any(item.uuid in CANARY_UUIDS for item in violation.items)


def canary_fired(report: DrcReport) -> bool:
    """Whether a ``clearance`` violation's items are exactly the two canary tracks."""
    return any(
        v.type == "clearance" and sorted(i.uuid for i in v.items) == sorted(CANARY_UUIDS)
        for v in report.violations
    )


def strip_canary(report: DrcReport) -> tuple[DrcReport, int]:
    """``report`` without the violations and unconnected items that name a canary track, and their count."""
    groups = {name: getattr(report, name) for name in ("violations", "unconnected_items", "schematic_parity")}
    kept = {name: tuple(v for v in group if not _names_canary(v)) for name, group in groups.items()}
    removed = sum(len(groups[name]) - len(kept[name]) for name in groups)
    return dataclasses.replace(report, **kept), removed


__all__ = [
    "CANARY_LENGTH_NM",
    "CANARY_MARGIN_NM",
    "CANARY_MAX_X_NM",
    "CANARY_MIN_NM",
    "CANARY_NETS",
    "CANARY_PITCH_NM",
    "CANARY_RULE_NAME",
    "CANARY_SUPPORT",
    "CANARY_TWO_RUN",
    "CANARY_UUIDS",
    "CANARY_WIDTH_NM",
    "CanaryError",
    "CanaryReason",
    "append_rule",
    "canary_fired",
    "canary_rule_text",
    "clearance_ignored",
    "inject_board",
    "insertions",
    "strip_canary",
]
