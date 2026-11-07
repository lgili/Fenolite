# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Byte-bound carry-over of a verified import's native ordinary zone fill caches (c0384 0.3, option A).

KiCad's teardrop generation reads the existing fill state of a board: with ``td_on_pad_in_zone`` false it
skips a pad inside an already filled same-net zone (``docs/formats/kicad/board.md``). A board built from
emitted code has no fills, so its native regeneration differs from the source's. A verified KiCad import
therefore keeps the source's ``filled_polygon`` children of its ordinary zones in the private carrier
``native/fill.cache.json``, beside the declared ``native/project.kicad_pro``.

The carrier is native carry-over, never Fenolite-computed copper and never a Fenolite fill: it holds the
source's bytes unchanged, and Fenolite never reads, measures or proves its geometry. It binds the SHA-256
of the exact board, project and custom-rule bytes that the import's build emitted before any fill was added,
so it can only ever restore the source's fills onto the very board they were computed for. Any change of any
byte of those files (a zone, its settings, any copper item on any layer, the outline, the clearance or
teardrop rules, the target) makes a later build drop the whole carrier, which gives the ordinary no-cache
board, and the build receipt says that it was dropped and why. Nothing is ever refused for it.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, cast

from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse, parse_bytes

CARRIER = "fill.cache.json"
VERSION = 1
MAX_BYTES = 16 * 1024 * 1024
ORIGIN = "native-carry-over"
_SHA = re.compile(r"[0-9a-f]{64}")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_UNKEYED = frozenset({"uuid", "net", "filled_polygon", "fill_segments"})


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class Emitted:
    """The exact native bytes a build wrote, before any carried fill: board, project and custom rules."""

    pcb: bytes
    project: bytes
    rules: bytes | None


def _zone_kind(zone: Node) -> str:
    """``ordinary``, ``derived`` (a teardrop cache) or ``keepout`` (a rule area)."""
    if zone.find("keepout") is not None:
        return "keepout"
    return "derived" if zone.find("attr") is not None else "ordinary"


def _uuid(zone: Node) -> str:
    found = zone.nodes("uuid")
    if len(found) != 1 or len(found[0].atoms()) != 1 or not _UUID.fullmatch(found[0].atoms()[0].value):
        raise ValueError("zone identity missing or malformed")
    return found[0].atoms()[0].value


def _settings(fill: Node) -> Node:
    """A ``fill`` child without its flag atom: the flag (``yes``) is fill state, not a setting."""
    return fill.with_children(fill.nodes())


def _fill(zone: Node) -> Node:
    found = zone.nodes("fill")
    if len(found) != 1:
        raise ValueError("zone fill settings missing or duplicated")
    return found[0]


def _key(zone: Node) -> str:
    """The zone's complete content except its identity, net code, fill flag and fill caches; the net name
    stays."""
    kept = [
        _settings(c) if isinstance(c, Node) and c.name == "fill" else c
        for c in zone.children
        if not (isinstance(c, Node) and c.name in _UNKEYED)
    ]
    return dumps(zone.with_children(tuple(kept)), style="compact")


def _ordinary(root: Node) -> list[Node]:
    return [z for z in root.nodes("zone") if _zone_kind(z) == "ordinary"]


def capture(
    source_board: bytes, emitted: Emitted, target: int, inputs: Sequence[Mapping[str, object]]
) -> tuple[bytes | None, str]:
    """The carrier for ``emitted``, or ``None`` and the reason no carrier is written.

    Each filled ordinary source zone pairs with the one emitted zone of equal content (identity, net code
    and fills excluded); a missing, ambiguous or already filled emitted zone writes no carrier at all."""
    try:
        source, built = parse_bytes(source_board), parse_bytes(emitted.pcb)
        filled = [z for z in _ordinary(source) if z.nodes("filled_polygon")]
        if not filled:
            return None, "no-source-fills"
        if any(z.nodes("filled_polygon") or z.nodes("fill_segments") for z in built.nodes("zone")):
            return None, "emitted-board-has-fills"
        if any(z.nodes("fill_segments") for z in filled):
            return None, "unsupported-fill-segments"
        targets: dict[str, list[Node]] = {}
        for zone in _ordinary(built):
            targets.setdefault(_key(zone), []).append(zone)
        sources: dict[str, int] = {}
        for zone in _ordinary(source):
            sources[_key(zone)] = sources.get(_key(zone), 0) + 1
        rows: list[dict[str, object]] = []
        for zone in filled:
            key = _key(zone)
            found = targets.get(key, [])
            if len(found) != 1 or sources[key] != 1:
                return None, "zone-correspondence"
            rows.append(
                {
                    "zone": _uuid(found[0]),
                    "fill": dumps(_fill(zone), style="compact"),
                    "fills": [dumps(f, style="compact") for f in zone.nodes("filled_polygon")],
                }
            )
        if len({row["zone"] for row in rows}) != len(rows):
            return None, "zone-correspondence"
    except ValueError:
        return None, "unqualified-zone"
    data = {
        "version": VERSION,
        "origin": ORIGIN,
        "fenolite_computed": False,
        "target": target,
        "emitted": {
            "pcb_sha256": _sha(emitted.pcb),
            "project_sha256": _sha(emitted.project),
            "rules_sha256": None if emitted.rules is None else _sha(emitted.rules),
        },
        "source_inputs": [dict(row) for row in inputs],
        "zones": rows,
    }
    raw = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode()
    if len(raw) > MAX_BYTES:
        return None, "byte-limit"
    return raw, "captured"


@dataclass(frozen=True, slots=True)
class _Carrier:
    target: int
    pcb: str
    project: str
    rules: str | None
    zones: tuple[tuple[str, Node, tuple[Node, ...]], ...]


def _read(raw: bytes) -> _Carrier:
    if len(raw) > MAX_BYTES:
        raise ValueError("byte-limit")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    keys = {"version", "origin", "fenolite_computed", "target", "emitted", "source_inputs", "zones"}
    if not isinstance(data, dict) or set(cast(dict[str, object], data)) != keys:
        raise ValueError("keys")
    body = cast(dict[str, Any], data)
    if (
        type(body["version"]) is not int
        or body["version"] != VERSION
        or body["origin"] != ORIGIN
        or body["fenolite_computed"] is not False
        or type(body["target"]) is not int
        or not isinstance(body["source_inputs"], list)
    ):
        raise ValueError("header")
    emitted = body["emitted"]
    if not isinstance(emitted, dict) or set(cast(dict[str, object], emitted)) != {
        "pcb_sha256",
        "project_sha256",
        "rules_sha256",
    }:
        raise ValueError("emitted")
    digests = cast(dict[str, object], emitted)
    for name in ("pcb_sha256", "project_sha256"):
        if not isinstance(digests[name], str) or not _SHA.fullmatch(cast(str, digests[name])):
            raise ValueError("digest")
    rules = digests["rules_sha256"]
    if rules is not None and (not isinstance(rules, str) or not _SHA.fullmatch(rules)):
        raise ValueError("digest")
    rows = body["zones"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("zones")
    zones: list[tuple[str, Node, tuple[Node, ...]]] = []
    for row in cast(list[object], rows):
        if not isinstance(row, dict) or set(cast(dict[str, object], row)) != {"zone", "fill", "fills"}:
            raise ValueError("zone row")
        entry = cast(dict[str, object], row)
        zone, flag, fills = entry["zone"], entry["fill"], entry["fills"]
        if not isinstance(zone, str) or not _UUID.fullmatch(zone) or not isinstance(fills, list) or not fills:
            raise ValueError("zone row")
        if not isinstance(flag, str) or parse(flag).name != "fill":
            raise ValueError("fill settings")
        nodes: list[Node] = []
        for text in cast(list[object], fills):
            if not isinstance(text, str):
                raise ValueError("fill")
            node = parse(text)
            if node.name != "filled_polygon":
                raise ValueError("fill")
            nodes.append(node)
        zones.append((zone, parse(flag), tuple(nodes)))
    if len({row[0] for row in zones}) != len(zones):
        raise ValueError("zone row")
    return _Carrier(
        body["target"],
        cast(str, digests["pcb_sha256"]),
        cast(str, digests["project_sha256"]),
        rules,
        tuple(zones),
    )


def apply(raw: bytes | None, emitted: Emitted, target: int) -> tuple[bytes, dict[str, object]]:
    """``emitted.pcb`` with the carried fills, or unchanged with the reason they were dropped."""
    receipt: dict[str, object] = {
        "origin": ORIGIN,
        "fenolite_computed": False,
        "status": "absent",
        "reason": None,
        "zones": 0,
        "fills": 0,
    }
    if raw is None:
        return emitted.pcb, receipt

    def dropped(reason: str) -> tuple[bytes, dict[str, object]]:
        return emitted.pcb, {**receipt, "status": "dropped", "reason": reason}

    try:
        carrier = _read(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return dropped("carrier-unreadable")
    if carrier.target != target:
        return dropped("target-changed")
    if carrier.pcb != _sha(emitted.pcb):
        return dropped("board-changed")
    if carrier.project != _sha(emitted.project):
        return dropped("project-changed")
    if carrier.rules != (None if emitted.rules is None else _sha(emitted.rules)):
        return dropped("rules-changed")
    root = parse_bytes(emitted.pcb)
    wanted = {zone: (flag, fills) for zone, flag, fills in carrier.zones}
    seen: set[str] = set()
    children: list[Node | Atom] = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "zone" and _zone_kind(child) == "ordinary":
            identity = _uuid(child)
            if identity in wanted:
                if identity in seen:
                    return dropped("board-changed")
                seen.add(identity)
                flag, fills = wanted[identity]
                try:
                    current = _fill(child)
                except ValueError:
                    return dropped("board-changed")
                if _settings(current) != _settings(flag):
                    return dropped("board-changed")
                kept = tuple(flag if c is current else c for c in child.children)
                child = child.with_children((*kept, *fills))
        children.append(child)
    if seen != set(wanted):
        return dropped("board-changed")
    text = dumps(root.with_children(tuple(children))).encode("utf-8")
    return text, {
        **receipt,
        "status": "carried",
        "zones": len(wanted),
        "fills": sum(len(fills) for _, fills in wanted.values()),
    }


# --- build scope and import capture ---------------------------------------------------------------


@dataclass
class Capture:
    """The emitted bytes of every build that ran while an import captured them, in order."""

    emitted: list[Emitted] = field(default_factory=lambda: [])
    receipts: list[dict[str, object]] = field(default_factory=lambda: [])


_SCOPE: ContextVar[bytes | None] = ContextVar("native_fill_cache_scope", default=None)
_CAPTURE: ContextVar[Capture | None] = ContextVar("native_fill_cache_capture", default=None)


@contextmanager
def build_scope(carrier: bytes | None) -> Generator[None]:
    token = _SCOPE.set(carrier)
    try:
        yield
    finally:
        _SCOPE.reset(token)


@contextmanager
def capture_import() -> Generator[Capture]:
    if _CAPTURE.get() is not None:
        raise ValueError("nested native fill cache capture is refused")
    capture = Capture()
    token = _CAPTURE.set(capture)
    try:
        yield capture
    finally:
        _CAPTURE.reset(token)


def after_write(
    pcb: bytes, project: bytes, rules: bytes | None, target: int
) -> tuple[bytes, dict[str, object]]:
    """The board a build writes, with the carried fills of its scope when every binding still holds."""
    emitted = Emitted(pcb, project, rules)
    capture = _CAPTURE.get()
    written, receipt = apply(_SCOPE.get(), emitted, target)
    if capture is not None:
        capture.emitted.append(emitted)
        capture.receipts.append(receipt)
    return written, receipt


__all__ = [
    "CARRIER",
    "ORIGIN",
    "Capture",
    "Emitted",
    "after_write",
    "apply",
    "build_scope",
    "capture",
    "capture_import",
]
