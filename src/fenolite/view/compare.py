# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The difference of two revisions of a board or a sheet, as an overlay of the newer scene (capability
visual-diff, change c0184).

``compare(new, old)`` takes two scenes of one kind (two v0 board scenes, or two schematic scenes) and returns
the overlay the page draws on ``new``, under ``diff``:

* boards: the primitives ``new`` adds and those it removes, the parts it moves (distance and angle) or flips,
  the parts whose value or footprint changed, and the zones whose filled area changed;
* sheets: the parts added, removed or moved, the parts whose parameters changed, and the nets whose pins
  changed;
* ``changes``: one line per change, in the order the page lists them, each with the box to zoom to.

Parts match by reference. Primitives match as a multiset by layer, kind, geometry, net name and part
reference, not by their numbered labels, so a renumbered file still matches. The primitives of a moved part
are left out of the added and removed lists: the move is one change. Zone fills match by their area per zone,
layer and net, as a refill changes every vertex. Standard library only.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from typing import Any, cast

AREA_TOLERANCE = 0.005
"""A zone whose filled area changed by less than this fraction is the same zone (Fenolite's choice)."""


def _poly_area(ring: list[int]) -> float:
    total = 0
    for k in range(0, len(ring), 2):
        x0, y0 = ring[k], ring[k + 1]
        x1, y1 = ring[(k + 2) % len(ring)], ring[(k + 3) % len(ring)]
        total += x0 * y1 - x1 * y0
    return abs(total) / 2


def _box(prim: list[Any]) -> list[int]:
    data = prim[2]
    flat: list[int] = [v for ring in data for v in ring] if prim[1] in "poh" else list(data)
    if prim[1] == "l":
        flat = flat[1:]
    elif prim[1] == "c":
        x, y, r = flat
        return [x - r, y - r, x + r, y + r]
    elif prim[1] in "sa":
        flat = flat[:-1]
    xs, ys = flat[0::2], flat[1::2]
    return [min(xs), min(ys), max(xs), max(ys)] if xs else [0, 0, 0, 0]


def _merge(boxes: list[list[int]]) -> list[int]:
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def _board(new: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    new_comps = {c["ref"]: c for c in cast("list[dict[str, Any]]", new["comps"])}
    old_comps = {c["ref"]: c for c in cast("list[dict[str, Any]]", old["comps"])}
    changes: list[dict[str, Any]] = []
    moved: list[dict[str, Any]] = []
    still: set[str] = set()
    for ref in sorted(new_comps.keys() & old_comps.keys()):
        a, z = old_comps[ref], new_comps[ref]
        place_a = (a["x"], a["y"], a["rotation"], a["side"])
        place_z = (z["x"], z["y"], z["rotation"], z["side"])
        if place_a != place_z:
            dist = math.hypot(z["x"] - a["x"], z["y"] - a["y"])
            turn = (z["rotation"] - a["rotation"]) % 360
            entry = {
                "ref": ref,
                "from": [a["x"], a["y"]],
                "to": [z["x"], z["y"]],
                "um": round(dist),
                "deg": round(turn, 3),
                "flipped": a["side"] != z["side"],
            }
            moved.append(entry)
            text = f"{ref} moved {dist / 1000:.3f} mm"
            if turn:
                text += f", turned {turn:g}°"
            if entry["flipped"]:
                text += f", now on the {z['side']}"
            changes.append(
                {"kind": "moved", "text": text, "box": z.get("bbox") or [z["x"], z["y"], z["x"], z["y"]]}
            )
        else:
            still.add(ref)
        for field in ("value", "footprint"):
            if a.get(field) != z.get(field):
                changes.append(
                    {
                        "kind": "changed",
                        "text": f"{ref} {field}: {a.get(field)} → {z.get(field)}",
                        "box": z.get("bbox"),
                    }
                )
    for ref in sorted(new_comps.keys() - old_comps.keys()):
        changes.append({"kind": "added", "text": f"{ref} added", "box": new_comps[ref].get("bbox")})
    for ref in sorted(old_comps.keys() - new_comps.keys()):
        changes.append({"kind": "removed", "text": f"{ref} removed", "box": old_comps[ref].get("bbox")})
    moved_refs = {m["ref"] for m in moved}

    def keyed(scene: dict[str, Any]) -> tuple[dict[str, list[list[Any]]], dict[tuple[str, str, str], float]]:
        nets: list[str] = scene.get("nets", [])
        comps: list[dict[str, Any]] = scene["comps"]
        out: dict[str, list[list[Any]]] = defaultdict(list)
        zones: dict[tuple[str, str, str], float] = defaultdict(float)
        for prim in cast("list[list[Any]]", scene["prims"]):
            layer, kind, data, label = str(prim[0]), str(prim[1]), prim[2], str(prim[5])
            net, comp = int(prim[3]), int(prim[4])
            ref: str = str(comps[comp]["ref"]) if 0 <= comp < len(comps) else ""
            if ref in moved_refs:
                continue
            net_name: str = nets[net] if 0 <= net < len(nets) else ""
            if kind == "p" and comp < 0 and net >= 0:  # a zone fill
                zones[(layer, label, net_name)] += sum(_poly_area(ring) for ring in data)
                continue
            key = json.dumps([layer, kind, data, net_name, ref], separators=(",", ":"))
            out[key].append(prim)
        return out, zones

    new_prims, new_zones = keyed(new)
    old_prims, old_zones = keyed(old)
    added = [
        p
        for key in new_prims
        for p in new_prims[key][: max(0, len(new_prims[key]) - len(old_prims.get(key, [])))]
    ]
    removed = [
        p
        for key in old_prims
        for p in old_prims[key][: max(0, len(old_prims[key]) - len(new_prims.get(key, [])))]
    ]
    new_only, old_only = new_comps.keys() - old_comps.keys(), old_comps.keys() - new_comps.keys()
    per_part: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    part_boxes: dict[str, list[list[int]]] = defaultdict(list)
    free: dict[tuple[int, str], tuple[list[str], list[list[int]]]] = {}
    for column, (prims, comps) in enumerate(((added, new["comps"]), (removed, old["comps"]))):
        for prim in prims:
            comp = int(prim[4])
            ref = str(comps[comp]["ref"]) if 0 <= comp < len(comps) else ""
            if ref:  # a part's own primitives: one line per part, none for a part added or removed whole
                if ref not in new_only and ref not in old_only:
                    per_part[ref][column] += 1
                    part_boxes[ref].append(_box(prim))
                continue
            label = str(prim[5] or prim[1]).removesuffix(" hole")  # a via's copper and its hole: one line
            group = free.setdefault((column, label), ([], []))
            group[0].append(str(prim[0]).removeprefix("View."))
            group[1].append(_box(prim))
    for (column, label), (layers, boxes) in free.items():
        verb, kind = ("added on", "added") if column == 0 else ("removed from", "removed")
        text = f"{label} {verb} {', '.join(dict.fromkeys(layers))}"
        changes.append({"kind": kind, "text": text, "box": _merge(boxes)})
    for ref in sorted(per_part):
        plus, minus = per_part[ref]
        text = f"{ref}: {plus} primitive(s) added, {minus} removed"
        changes.append({"kind": "changed", "text": text, "box": _merge(part_boxes[ref])})
    zones: list[dict[str, Any]] = []
    for key in sorted(new_zones.keys() | old_zones.keys()):
        a, z = old_zones.get(key, 0.0), new_zones.get(key, 0.0)
        if abs(z - a) > AREA_TOLERANCE * max(a, z):
            layer, label, net = key
            zones.append(
                {
                    "layer": layer,
                    "zone": label,
                    "net": net,
                    "old_mm2": round(a / 1e6, 3),
                    "new_mm2": round(z / 1e6, 3),
                }
            )
            changes.append(
                {
                    "kind": "zone",
                    "text": f"zone {label} ({net}) on {layer}: {a / 1e6:.2f} → {z / 1e6:.2f} mm²",
                    "box": None,
                }
            )
    counts = Counter(c["kind"] for c in changes)
    return {
        "kind": "board",
        "added": added,
        "removed": removed,
        "moved": moved,
        "zones": zones,
        "changes": changes,
        "counts": {k: counts.get(k, 0) for k in ("added", "removed", "moved", "changed", "zone")},
    }


def _sheet(new: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    def parts(scene: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {c["ref"]: c for c in cast("list[dict[str, Any]]", scene["comps"]) if not c.get("hidden")}

    def nets(scene: dict[str, Any]) -> dict[str, set[str]]:
        return {
            n["name"]: set(n["pins"])
            for n in cast("list[dict[str, Any]]", scene.get("nets", []))
            if n.get("name")
        }

    a_parts, z_parts = parts(old), parts(new)
    changes: list[dict[str, Any]] = []
    for ref in sorted(z_parts.keys() - a_parts.keys()):
        changes.append({"kind": "added", "text": f"{ref} added", "box": z_parts[ref].get("b")})
    for ref in sorted(a_parts.keys() - z_parts.keys()):
        changes.append({"kind": "removed", "text": f"{ref} removed", "box": a_parts[ref].get("b")})
    for ref in sorted(a_parts.keys() & z_parts.keys()):
        a, z = a_parts[ref], z_parts[ref]
        if a.get("b") and z.get("b") and a["b"][:2] != z["b"][:2]:
            changes.append({"kind": "moved", "text": f"{ref} moved on the sheet", "box": z["b"]})
        diffs = [k for k in ("comment", "lib", "footprint") if a.get(k) != z.get(k)]
        params_a = cast("dict[str, Any]", a.get("params") or {})
        params_z = cast("dict[str, Any]", z.get("params") or {})
        diffs += [k for k in sorted(set(params_a) | set(params_z)) if params_a.get(k) != params_z.get(k)]
        if diffs:
            changes.append(
                {"kind": "changed", "text": f"{ref}: {', '.join(diffs)} changed", "box": z.get("b")}
            )
    a_nets, z_nets = nets(old), nets(new)
    for name in sorted(a_nets.keys() | z_nets.keys()):
        if a_nets.get(name) != z_nets.get(name):
            gained = sorted(z_nets.get(name, set()) - a_nets.get(name, set()))
            lost = sorted(a_nets.get(name, set()) - z_nets.get(name, set()))
            text = f"net {name}: " + "; ".join(
                part
                for part in (f"+{', '.join(gained)}" if gained else "", f"−{', '.join(lost)}" if lost else "")
                if part
            )
            changes.append({"kind": "net", "text": text, "box": None})
    counts = Counter(c["kind"] for c in changes)
    return {
        "kind": "sheet",
        "changes": changes,
        "counts": {k: counts.get(k, 0) for k in ("added", "removed", "moved", "changed", "net")},
    }


def compare(new: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    """The overlay of ``new`` against ``old``; ``ValueError`` for two scenes of different kinds or tools."""
    if new.get("kind") != old.get("kind") or new.get("kind") not in (None, "schematic"):
        raise ValueError("compare two boards or two sheets")
    family_new, family_old = new["meta"].get("backend"), old["meta"].get("backend")
    if family_new != family_old:
        raise ValueError(f"the two revisions come from different tools ({family_new} and {family_old})")
    out = _sheet(new, old) if new.get("kind") == "schematic" else _board(new, old)
    out["old"] = {"name": old["meta"].get("name", ""), "sha256": old["meta"].get("sha256", "")}
    return out


def summary(diff: dict[str, Any]) -> dict[str, Any]:
    """The part of an overlay that a reply carries: the counts and the change lines."""
    return {
        "kind": diff["kind"],
        "old": diff["old"],
        **diff["counts"],
        "changes": [c["text"] for c in diff["changes"]],
    }


__all__ = ["compare", "summary"]
