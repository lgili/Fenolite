# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The manifest of the role copper a run wrote: ``.fenolite/role-copper.json`` beside the board (change
c0243, decision 12; capability net-roles, "Kept copper and repeat runs"; ``docs/roles.md``, "Role copper").

Each role item a run writes has a fingerprint: the SHA-256 of the canonical JSON of what it is (a zone's or
rule area's name, outline, layers, net and settings; a via's or track's geometry and net), without its id, so
a board read back from KiCad gives the same fingerprint. A named item (zone, rule area) is keyed by its name;
a via or a track by its fingerprint. On the next run, an item of the manifest whose fingerprint still
matches is the run's own and is replaced; a named role item whose fingerprint differs was edited by the user
and is kept (``roles.copper-kept``) unless ``regenerate`` names it; everything else on the board, phase 2's
``role.corridor.*`` areas included, is never touched.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from fenolite.core.errors import FormatError, Issue
from fenolite.model.board import Keepout, Track, Via, Zone
from fenolite.model.design import Design
from fenolite.roles.codes import issue

SCHEMA = "fenolite.role-copper.v0"
FILE = ".fenolite/role-copper.json"
"""The manifest's path relative to the board's folder."""


def _point(p: Any) -> list[int]:
    return [p.x, p.y]


def _content(item: Zone | Keepout | Via | Track, names: Mapping[str, str]) -> dict[str, Any]:
    if isinstance(item, Zone):
        settings = item.settings
        return {
            "kind": "zone",
            "name": item.name,
            "outline": [_point(p) for p in item.outline],
            "layers": list(item.layers),
            "net": names.get(item.net_id or "", ""),
            "priority": item.priority,
            "clearance": settings.clearance,
            "connection": settings.connection,
        }
    if isinstance(item, Keepout):
        return {
            "kind": "rule_area",
            "name": item.name,
            "outline": [_point(p) for p in item.outline],
            "layers": list(item.layers),
            "forbid": [item.no_tracks, item.no_vias, item.no_pads, item.no_copper_pour, item.no_footprints],
        }
    if isinstance(item, Via):
        return {
            "kind": "via",
            "position": _point(item.position),
            "diameter": item.diameter,
            "drill": item.drill,
            "layers": list(item.layers),
            "net": names.get(item.net_id or "", ""),
        }
    return {
        "kind": "track",
        "start": _point(item.start),
        "end": _point(item.end),
        "width": item.width,
        "layer": item.layer,
        "net": names.get(item.net_id or "", ""),
    }


def fingerprint(item: Zone | Keepout | Via | Track, names: Mapping[str, str]) -> str:
    """The SHA-256 of the canonical JSON of what ``item`` is (``names``: net id → name)."""
    text = json.dumps(_content(item, names), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def key_of(item: Zone | Keepout | Via | Track, names: Mapping[str, str]) -> str:
    """The manifest key: the name of a zone or rule area, else ``<kind>:<fingerprint>``."""
    if isinstance(item, (Zone, Keepout)):
        return item.name
    return f"{'via' if isinstance(item, Via) else 'track'}:{fingerprint(item, names)}"


@dataclass(frozen=True, slots=True)
class Manifest:
    """The fingerprints of the role items a run wrote, by key."""

    items: Mapping[str, str] = field(default_factory=lambda: {})

    def dumps(self) -> str:
        """Canonical JSON: keys sorted, two-space indents, a final newline."""
        body = {"schema": SCHEMA, "items": [{"key": k, "sha256": v} for k, v in sorted(self.items.items())]}
        return json.dumps(body, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def loads(text: str, *, file: str = FILE) -> Manifest:
    """A manifest from its JSON text; ``FormatError`` for another schema or a malformed file."""
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as error:
        raise FormatError(f"{file}: not JSON: {error.msg}", file=file) from None
    body = cast("dict[str, Any]", data) if isinstance(data, dict) else {}
    entries = body.get("items")
    if body.get("schema") != SCHEMA or not isinstance(entries, list):
        raise FormatError(f"{file}: not a {SCHEMA} document", file=file)
    found: dict[str, str] = {}
    for entry in cast("list[Any]", entries):
        item = cast("dict[str, Any]", entry) if isinstance(entry, dict) else {}
        key, sha = item.get("key"), item.get("sha256")
        if not isinstance(key, str) or not isinstance(sha, str):
            raise FormatError(f"{file}: an item needs a key and a sha256", file=file)
        found[key] = sha
    return Manifest(found)


def _items(design: Design) -> list[Zone | Keepout | Via | Track]:
    board = design.board
    if board is None:
        return []
    return [*board.zones, *board.keepouts, *board.vias, *board.tracks]


def _names(design: Design) -> dict[str, str]:
    return {net.id: net.name for net in design.circuit.nets}


@dataclass(frozen=True, slots=True)
class Sorted:
    """What a run finds on a board: the ids of its own role items to replace, the keys of the role items the
    user edited (kept), and the issues (``roles.copper-kept``)."""

    replace: tuple[str, ...] = ()
    kept: tuple[str, ...] = ()
    issues: tuple[Issue, ...] = ()


def sort(
    design: Design, manifest: Manifest | None, *, regenerate: Collection[str] = (), keep: Collection[str] = ()
) -> Sorted:
    """Sort the role items of ``design`` against ``manifest``: an item whose fingerprint matches is the run's
    own (replaced); a named ``role.*`` item that is not ``role.corridor.*``, with another fingerprint, was
    edited (kept, ``roles.copper-kept``), unless ``regenerate`` names it; an item named in ``keep`` is always
    kept; a ``role.corridor.*`` area outside the manifest (phase 2's) and every other item are not touched.
    Without a manifest, every named ``role.*`` item but the corridors is the run's own."""
    names = _names(design)
    replace: list[str] = []
    kept: list[str] = []
    issues: list[Issue] = []
    held: Mapping[str, str] = manifest.items if manifest is not None else {}
    for item in _items(design):
        key = key_of(item, names)
        named = isinstance(item, (Zone, Keepout))
        if named and not key.startswith("role."):
            continue
        if key in keep:
            kept.append(key)
            continue
        own = held.get(key)
        if own is not None and own == fingerprint(item, names):
            replace.append(item.id)
            continue
        if not named:
            continue  # a via or a track outside the manifest is the user's
        if key.startswith("role.corridor."):
            continue  # phase 2's, or a provisional corridor phase 2 replaced: never touched
        if manifest is None or key in regenerate or _part_of(key, regenerate):
            replace.append(item.id)
            continue
        kept.append(key)
        issues.append(
            issue(
                "roles.copper-kept",
                f"the role item {key} was edited since the last run; it is kept as it is",
                where=key,
                hint=f"pass --regenerate {key} (or role_copper(regenerate=...)) to have it generated again",
            )
        )
    return Sorted(tuple(replace), tuple(sorted(set(kept))), tuple(issues))


def _part_of(key: str, regenerate: Collection[str]) -> bool:
    """Whether ``key`` (a barrier half ``role.hv.X.0.a``) belongs to a named item ``role.hv.X``."""
    return any(key.startswith(name + ".") for name in regenerate)


def record(
    design: Design, *, before: Design, kept: Sequence[str] = (), found: Collection[str] = ()
) -> Manifest:
    """The manifest of a run's result: every named ``role.*`` zone and rule area of ``design`` except the
    ``kept`` ones and the corridors found on the board (``found``, phase 2's), and every via and track that
    ``before`` did not hold."""
    names = _names(design)
    old = {fingerprint(item, _names(before)) for item in _items(before) if isinstance(item, (Via, Track))}
    items: dict[str, str] = {}
    for item in _items(design):
        key = key_of(item, names)
        if isinstance(item, (Zone, Keepout)):
            if not key.startswith("role.") or key in kept or key in found:
                continue
        elif fingerprint(item, names) in old:
            continue
        items[key] = fingerprint(item, names)
    return Manifest(items)


__all__ = ["FILE", "SCHEMA", "Manifest", "Sorted", "fingerprint", "key_of", "loads", "record", "sort"]
