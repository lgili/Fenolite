# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The compact board scene ``fenolite.view_scene.v1`` and the packed scenes of a page (capability
viewer-performance, change c0182).

A v0 board scene lists its primitives as ``[layer, kind, data, net, comp, label]``. ``compact`` writes them as
columns under ``p1``:

* ``layers``: the layer ids, each once; ``L`` the layer index of each primitive;
* ``K``: the kinds, one character each; ``N`` and ``C``: the net and part of each primitive;
* labels: a label whose last run of digits is a plain number (``track 12``, ``R7-2``) is the template
  ``track \\u0001`` and that number; ``strings`` holds the templates, ``S`` the template of each primitive and
  ``SN`` its number as the difference from the number before it of the same template (a label without such a
  number is its own template, with 0);
* ``D``: one integer list. Every point is written as its offset from the point before it: the first point of a
  primitive from the first point of the primitive before it, the next points from the previous point of the
  same primitive (each ring of a polygon from the first point of the ring before it). Per kind: ``s`` x1 y1
  x2 y2 w; ``c`` x y r; ``a`` three points and w; ``l`` the point count, w and the points; ``p`` and ``o``
  the ring count, then per ring its point count and points.

``expand`` gives the v0 primitives back exactly; the page's ``decodeV1`` does the same in the browser. A scene
whose primitives hold another kind or a value that is not an integer stays v0. ``pack`` gzips a scene's JSON
for a standalone page (``gz:`` and base64), which the page opens with ``DecompressionStream``.
"""

from __future__ import annotations

import base64
import gzip
import json
import re
from typing import Any, cast

SCHEMA_V0 = "fenolite.view_scene.v0"
SCHEMA_V1 = "fenolite.view_scene.v1"
KINDS = frozenset("scalpo")
FIXED = {"c": 1, "s": 2, "a": 3}
"""The points of the kinds of fixed size; each is followed by one value (radius or width)."""
PACKED = "gz:"
SLOT = "\u0001"
_NUMBER = re.compile(r"^(.*?)([1-9][0-9]{0,8}|0)(\D*)$")


class _Unfit(Exception):
    """A primitive that v1 cannot hold: the scene stays v0."""


def _ints(value: Any) -> list[int]:
    if not isinstance(value, list):
        raise _Unfit
    items = cast("list[Any]", value)
    if not all(type(v) is int for v in items):
        raise _Unfit
    return cast("list[int]", items)


def _offsets(out: list[int], flat: list[int], start: tuple[int, int]) -> tuple[int, int]:
    """``flat`` (x y x y …) written as offsets, the first from ``start``; returns the first point."""
    if len(flat) % 2:
        raise _Unfit
    px, py = start
    for k in range(0, len(flat), 2):
        out += [flat[k] - px, flat[k + 1] - py]
        px, py = flat[k], flat[k + 1]
    return (flat[0], flat[1]) if flat else start


def _label(label: str) -> tuple[str, int]:
    found = _NUMBER.match(label)
    if found is None or SLOT in label:
        return label, 0
    return found.group(1) + SLOT + found.group(3), int(found.group(2))


def compact(scene: dict[str, Any]) -> dict[str, Any]:
    """``scene`` with its board primitives in the v1 columns; a library's board items are compacted too;
    any other scene, or one that v1 cannot hold, is returned unchanged."""
    if scene.get("kind") == "library":
        items = [
            item | {"scene": compact(item["scene"])} if isinstance(item.get("scene"), dict) else item
            for item in cast("list[dict[str, Any]]", scene.get("items", []))
        ]
        return scene | {"items": items}
    if scene.get("kind") is not None or not isinstance(scene.get("prims"), list):
        return scene
    try:
        p1 = _columns(cast("list[Any]", scene["prims"]))
    except _Unfit:
        return scene
    out = {key: value for key, value in scene.items() if key != "prims"}
    out["schema"] = SCHEMA_V1
    out["p1"] = p1
    return out


def _columns(prims: list[Any]) -> dict[str, Any]:
    layers: dict[str, int] = {}
    templates: dict[str, int] = {}
    last: dict[int, int] = {}
    kinds: list[str] = []
    cols: dict[str, list[int]] = {"L": [], "N": [], "C": [], "S": [], "SN": [], "D": []}
    data = cols["D"]
    cursor = (0, 0)
    for prim in prims:
        if not isinstance(prim, list) or len(cast("list[Any]", prim)) != 6:
            raise _Unfit
        layer, kind, value, net, comp, label = cast("list[Any]", prim)
        if not isinstance(layer, str) or kind not in KINDS or type(net) is not int or type(comp) is not int:
            raise _Unfit
        if not isinstance(label, str):
            raise _Unfit
        if kind in "po":
            if not isinstance(value, list):
                raise _Unfit
            rings = [_ints(ring) for ring in cast("list[Any]", value)]
            data.append(len(rings))
            ring_start = cursor
            for k, ring in enumerate(rings):
                data.append(len(ring) // 2)
                ring_start = _offsets(data, ring, ring_start)
                if k == 0:
                    cursor = ring_start
        else:
            flat = _ints(value)
            if kind == "l":
                if len(flat) < 3 or len(flat) % 2 == 0:
                    raise _Unfit
                data += [(len(flat) - 1) // 2, flat[0]]
                cursor = _offsets(data, flat[1:], cursor)
            else:
                if len(flat) != 2 * FIXED[kind] + 1:
                    raise _Unfit
                cursor = _offsets(data, flat[:-1], cursor)
                data.append(flat[-1])
        template, number = _label(label)
        index = templates.setdefault(template, len(templates))
        kinds.append(cast("str", kind))
        cols["L"].append(layers.setdefault(layer, len(layers)))
        cols["N"].append(net)
        cols["C"].append(comp)
        cols["S"].append(index)
        cols["SN"].append(number - last.get(index, 0))
        last[index] = number
    return {"layers": list(layers), "strings": list(templates), "K": "".join(kinds), **cols}


def expand(scene: dict[str, Any]) -> dict[str, Any]:
    """The v0 form of a v1 scene (the inverse of ``compact``)."""
    if scene.get("kind") == "library":
        items = [
            item | {"scene": expand(item["scene"])} if isinstance(item.get("scene"), dict) else item
            for item in cast("list[dict[str, Any]]", scene.get("items", []))
        ]
        return scene | {"items": items}
    p1: Any = scene.get("p1")
    if not isinstance(p1, dict):
        return scene
    cols = cast("dict[str, Any]", p1)
    data: list[int] = cols["D"]
    at = 0

    def points(count: int, start: tuple[int, int]) -> list[int]:
        nonlocal at
        out: list[int] = []
        px, py = start
        for _ in range(count):
            px, py = px + data[at], py + data[at + 1]
            out += [px, py]
            at += 2
        return out

    cursor = (0, 0)
    last: dict[int, int] = {}
    prims: list[list[Any]] = []
    for k, kind in enumerate(cast("str", cols["K"])):
        value: Any
        if kind in "po":
            count = data[at]
            at += 1
            rings: list[list[int]] = []
            ring_start = cursor
            for r in range(count):
                n = data[at]
                at += 1
                ring = points(n, ring_start)
                if ring:
                    ring_start = (ring[0], ring[1])
                    if r == 0:
                        cursor = ring_start
                rings.append(ring)
            value = rings
        elif kind == "l":
            n, width = data[at], data[at + 1]
            at += 2
            flat = points(n, cursor)
            cursor = (flat[0], flat[1])
            value = [width, *flat]
        else:
            flat = points(FIXED[kind], cursor)
            cursor = (flat[0], flat[1])
            value = [*flat, data[at]]
            at += 1
        index: int = cols["S"][k]
        number = last.get(index, 0) + cols["SN"][k]
        last[index] = number
        template: str = cols["strings"][index]
        label = template.replace(SLOT, str(number)) if SLOT in template else template
        prims.append([cols["layers"][cols["L"][k]], kind, value, cols["N"][k], cols["C"][k], label])
    out = {key: value for key, value in scene.items() if key != "p1"}
    out["schema"] = SCHEMA_V0
    out["prims"] = prims
    return out


def pack(scene: dict[str, Any]) -> str:
    """A scene for a standalone page: its compact JSON, gzipped (fixed time stamp) and base64-encoded."""
    text = json.dumps(compact(scene), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return PACKED + base64.b64encode(gzip.compress(text, mtime=0)).decode("ascii")


def unpack(value: str | dict[str, Any]) -> dict[str, Any]:
    """The scene ``pack`` wrote, in its v0 form; a scene that is not packed is expanded only."""
    if isinstance(value, str):
        if not value.startswith(PACKED):
            raise ValueError("not a packed scene")
        loaded: Any = json.loads(gzip.decompress(base64.b64decode(value[len(PACKED) :])))
        return expand(cast("dict[str, Any]", loaded))
    return expand(value)


__all__ = ["PACKED", "SCHEMA_V0", "SCHEMA_V1", "compact", "expand", "pack", "unpack"]
