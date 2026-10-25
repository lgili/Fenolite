# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Body models placed in a scene (capability board-viewer, "Body models"; change c0193).

A model joins the scene body whose locator it names. Its placement (``backends.base.BodyModel``) becomes a
column-major 4×4 matrix from the model's millimetres to the page's 3D frame: x and −y of the board frame, z up
from the bottom face, in millimetres. A model point ``p`` lies at ``T(position, face ± z) · F · Rz · Ry · Rx ·
p``, ``F`` the identity for a top footprint and a half turn about x for a bottom one, below the bottom face.

The placed box is compared with the body's stored outline box (0.5 mm) and its stored z range (1 mm). A match
renders the model as placed (``model``). Otherwise the first of these that gives the outline's size within
1 mm, with the body standing on its face, is kept (``fitted``, with a note):
- quarter turns about the vertical through the outline's centre;
- then a half turn about x through the centre and the face;
- each centred on the outline.

A model whose placement a file left stale (a part moved or turned by a tool that did not move its model)
still shows. A model that matches none of these, or has no mesh, leaves the body extruded (``outline``),
with the reason.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from fenolite.backends.base import BodyModel
from fenolite.view.meshes import Mesh, mesh_key

TOL_MM = 0.5
SIZE_TOL_MM = 1.0
Z_TOL_MM = 1.0
Matrix = list[float]


def _rot(udeg: tuple[int, int, int]) -> list[list[float]]:
    ax, ay, az = (math.radians(v / 1_000_000) for v in udeg)
    cx, sx, cy, sy, cz, sz = (
        math.cos(ax),
        math.sin(ax),
        math.cos(ay),
        math.sin(ay),
        math.cos(az),
        math.sin(az),
    )
    rx = [[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]]
    ry = [[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]]
    rz = [[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]]

    def mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    return mul(rz, mul(ry, rx))


def placement(model: BodyModel, side: str, thickness_mm: float) -> Matrix:
    """The column-major matrix of ``model`` on a footprint of ``side`` (module docstring)."""
    r = _rot(model.rotation)
    x, y = model.position.x / 1e6, -model.position.y / 1e6
    if side == "bottom":
        r = [r[0], [-v for v in r[1]], [-v for v in r[2]]]
        tz = -model.z / 1e6
    else:
        tz = thickness_mm + model.z / 1e6
    return [
        r[0][0],
        r[1][0],
        r[2][0],
        0.0,
        r[0][1],
        r[1][1],
        r[2][1],
        0.0,
        r[0][2],
        r[1][2],
        r[2][2],
        0.0,
        x,
        y,
        tz,
        1.0,
    ]


def placed_box(m: Matrix, box: Sequence[float]) -> list[float]:
    """The box of the eight corners of ``box`` moved by ``m``."""
    corners = [(a, b, c) for a in (box[0], box[3]) for b in (box[1], box[4]) for c in (box[2], box[5])]
    moved = [
        (
            m[0] * a + m[4] * b + m[8] * c + m[12],
            m[1] * a + m[5] * b + m[9] * c + m[13],
            m[2] * a + m[6] * b + m[10] * c + m[14],
        )
        for a, b, c in corners
    ]
    return [min(p[k] for p in moved) for k in range(3)] + [max(p[k] for p in moved) for k in range(3)]


def _mul(a: Matrix, b: Matrix) -> Matrix:
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def fit(
    m: Matrix,
    box: Sequence[float],
    outline: Sequence[float],
    zrange: Sequence[float],
    side: str,
    thickness_mm: float,
) -> tuple[str, Matrix | None, str]:
    """``(render, matrix, note)`` of a placed model against the body's outline box ``(x0, y0, x1, y1)`` and
    its z range, in the page's frame (module docstring)."""
    x0, y0, x1, y1 = outline
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w = placed_box(m, box)
    off = max(abs(w[0] - x0), abs(w[3] - x1), abs(w[1] - y0), abs(w[4] - y1))
    if off <= TOL_MM and abs(w[2] - zrange[0]) <= Z_TOL_MM and abs(w[5] - zrange[1]) <= Z_TOL_MM:
        return "model", m, ""
    face = thickness_mm if side == "top" else 0.0
    best: tuple[tuple[bool, bool, float], Matrix, str] | None = None
    for flip in (False, True):
        for k in range(4):
            c, s = round(math.cos(k * math.pi / 2)), round(math.sin(k * math.pi / 2))
            to = [1.0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -cx, -cy, 0, 1]
            turn = [float(c), float(s), 0, 0, float(-s), float(c), 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
            back = [1.0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, cx, cy, 0, 1]
            mk = _mul(back, _mul(turn, _mul(to, m)))
            if flip:
                over = [1.0, 0, 0, 0, 0, -1, 0, 0, 0, 0, -1, 0, 0, 2 * cy, 2 * face, 1]
                mk = _mul(over, mk)
            wk = placed_box(mk, box)
            standing = wk[5] > thickness_mm + 0.1 if side == "top" else wk[2] < -0.1
            size = max(abs((wk[3] - wk[0]) - (x1 - x0)), abs((wk[4] - wk[1]) - (y1 - y0)))
            if not standing or size > SIZE_TOL_MM:
                continue
            score = (flip, k != 0, size)
            if best is None or score < best[0]:
                moved = math.hypot(cx - (wk[0] + wk[3]) / 2, cy - (wk[1] + wk[4]) / 2)
                mk[12] += cx - (wk[0] + wk[3]) / 2
                mk[13] += cy - (wk[1] + wk[4]) / 2
                parts = [
                    "turned over" if flip else "",
                    f"turned {90 * k}°" if k else "",
                    "centred" if moved > TOL_MM else "",
                ]
                best = (score, mk, ", ".join(p for p in parts if p) or "centred")
    if best is None:
        return "outline", None, "the model's size does not match the body's stored outline and heights"
    return "fitted", best[1], best[2]


def attach_models(
    scene: dict[str, Any], models: Sequence[BodyModel], meshes: Mapping[str, Mesh | None]
) -> dict[str, int]:
    """Place the meshes of ``models`` (``meshes`` by ``mesh_key`` of each model's data) on the scene's bodies,
    adding ``scene["meshes"]`` and per body ``render``, ``fit`` and, when drawn, ``mesh`` and ``m``. Returns
    the count of bodies per render and of models without a mesh."""
    thickness = scene["board3d"]["thickness"] / 1000
    by_locator = {m.locator: m for m in models}
    counts = {"model": 0, "fitted": 0, "outline": 0, "unmeshed": 0}
    used: dict[str, Mesh] = {}
    for body in scene["bodies"]:
        model = by_locator.get(body.get("locator", ""))
        if model is None:
            body["render"], body["fit"] = "outline", "no model in the file"
            counts["outline"] += 1
            continue
        key = mesh_key(model.data)
        mesh = meshes.get(key)
        if mesh is None:
            body["render"], body["fit"] = "outline", "the model could not be meshed"
            counts["outline"] += 1
            counts["unmeshed"] += 1
            continue
        ring = body["ring"]
        xs, ys = [v / 1000 for v in ring[0::2]], [-v / 1000 for v in ring[1::2]]
        z0, z1 = (v / 1000 for v in body.get("zs", (body["z0"], body["z1"])))
        side = body["side"]
        zrange = (thickness + z0, thickness + z1) if side == "top" else (-z1, -z0)
        render, m, note = fit(
            placement(model, side, thickness),
            mesh["bbox"],
            (min(xs), min(ys), max(xs), max(ys)),
            zrange,
            side,
            thickness,
        )
        body["render"], body["fit"] = render, note
        counts[render] += 1
        if m is not None:
            used[key] = mesh
            body["mesh"], body["m"] = key, [round(v, 5) for v in m]
    scene["meshes"] = used
    return counts


__all__ = ["attach_models", "fit", "placed_box", "placement"]
