# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Triangle meshes of body models for the viewer's 3D view (capability board-viewer, "Body models"; change
c0193).

``gmsh`` (GPL) runs as a separate process, once per model, in a temporary folder and with a time limit; no
gmsh module is imported. Its script merges the model (labels kept, unit mm), meshes the surfaces with a size
from the model's box (10, 16 or 24 elements per turn of a curve for a box below 5 mm, below 15 mm and above),
and saves CAD X3D with one shape per surface and the model's own colours. The X3D is read with regular
expressions, not an XML parser: gmsh writes the model's labels into ``DEF`` names unescaped (an ``&`` occurs),
so the file is not always well-formed XML. Each shape gives its triangles and its colour, equal vertices
merged.

A mesh is ``{"v", "i", "c", "bbox", "tri"}``: base64 little-endian float32 positions (mm), uint32 triangle
indices, uint8 RGBA per vertex (alpha 0 where the model gives no colour: no material, or white, which gmsh
writes for an uncoloured surface), the box ``[xmin, ymin, zmin, xmax, ymax, zmax]`` and the triangle count.
With a cache folder, a mesh is kept as ``<sha256>.json`` and a failure as ``<sha256>.failed``, the key being
the SHA-256 of the model data and ``MESH_VERSION``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fenolite.core.state import state_dir

GMSH_ENV = "FENOLITE_GMSH"
"""The variable that names the gmsh executable (an absolute path)."""
MESH_VERSION = "c0193-1"
"""Part of the cache key: changes whenever the script or the mesh form changes."""
TIMEOUT = 120
CACHE_FOLDER = "view-meshes"
SCRIPT = """Geometry.OCCImportLabels = 1;
Geometry.OCCTargetUnit = "MM";
General.Terminal = 0;
Merge "model.{suffix}";
dx = General.MaxX - General.MinX; dy = General.MaxY - General.MinY; dz = General.MaxZ - General.MinZ;
big = dx; If (dy > big) big = dy; EndIf If (dz > big) big = dz; EndIf
If (big < 0.01) big = 0.01; EndIf
curv = 24; fine = 120;
If (big < 15) curv = 16; fine = 40; EndIf
If (big < 5) curv = 10; fine = 12; EndIf
Mesh.MeshSizeMax = big / 6; Mesh.MeshSizeMin = big / fine;
Mesh.MeshSizeFromCurvature = curv; Mesh.Algorithm = 1;
Mesh 2;
Print.X3dSurfaces = 2; Print.X3dEdges = 0; Print.X3dVertices = 0; Print.X3dColorize = 1;
Save "mesh.x3d";
"""

Mesh = dict[str, Any]
_SHAPE = re.compile(r"<Shape\b(.*?)</Shape>", re.S)
_COLOUR = re.compile(r'diffuseColor="([^"]*)"')
_POINTS = re.compile(r'<Coordinate\b[^>]*?\bpoint="([^"]*)"', re.S)


def find_gmsh() -> list[str] | None:
    """The command that runs gmsh: ``FENOLITE_GMSH``, else ``gmsh`` on ``PATH``. A launcher that is a Python
    script (the one a Python package installs) runs with the interpreter of its shebang when that is a file,
    else the ``python3`` or ``python`` beside it, else the current interpreter. ``None`` when there is
    none."""
    found = os.environ.get(GMSH_ENV, "") or shutil.which("gmsh") or ""
    if not found or not Path(found).is_file():
        return None
    try:
        with open(found, "rb") as handle:
            first = handle.readline(200).decode("utf-8", "replace").strip()
    except OSError:
        return None
    if not (first.startswith("#!") and "python" in first):
        return [found]
    named = first[2:].split()
    beside = [Path(found).with_name(name) for name in ("python3", "python")]
    for candidate in [Path(named[0]) if named and named[0] != "/usr/bin/env" else None, *beside]:
        if candidate is not None and candidate.is_file():
            return [str(candidate), found]
    return [sys.executable, found]


def cache_folder() -> Path | None:
    """The mesh cache of the state folder, ``None`` when the state folder is off."""
    root = state_dir()
    return None if root is None else root / CACHE_FOLDER


def mesh_key(data: bytes) -> str:
    return hashlib.sha256(data + MESH_VERSION.encode("ascii")).hexdigest()


def read_x3d(text: str) -> Mesh | None:
    """The mesh of a CAD X3D that gmsh wrote: the triangles of every ``Coordinate`` of a ``Shape``, with the
    shape's material colour; ``None`` when it holds no triangle."""
    positions: list[float] = []
    colours = bytearray()
    indices: list[int] = []
    for block in _SHAPE.finditer(text):
        body = block.group(1)
        rgba = (0, 0, 0, 0)
        colour = _COLOUR.search(body)
        if colour is not None:
            try:
                r, g, b = (float(v) for v in colour.group(1).split()[:3])
            except ValueError:
                r = g = b = 1.0
            if (r, g, b) != (1.0, 1.0, 1.0):
                rgba = (round(r * 255), round(g * 255), round(b * 255), 255)
        for points in _POINTS.finditer(body):
            words = points.group(1).split()
            seen: dict[tuple[str, str, str], int] = {}
            corners: list[int] = []
            for k in range(0, len(words) - len(words) % 9, 3):
                key = (words[k], words[k + 1], words[k + 2])
                at = seen.get(key)
                if at is None:
                    try:
                        xyz = [float(w) for w in key]
                    except ValueError:
                        continue
                    at = seen[key] = len(positions) // 3
                    positions.extend(xyz)
                    colours.extend(rgba)
                corners.append(at)
            for k in range(0, len(corners) - 2, 3):
                a, b, c = corners[k : k + 3]
                if a != b and b != c and a != c:
                    indices.extend((a, b, c))
    if not indices:
        return None
    xs, ys, zs = positions[0::3], positions[1::3], positions[2::3]
    return {
        "v": base64.b64encode(struct.pack(f"<{len(positions)}f", *positions)).decode("ascii"),
        "i": base64.b64encode(struct.pack(f"<{len(indices)}I", *indices)).decode("ascii"),
        "c": base64.b64encode(bytes(colours)).decode("ascii"),
        "bbox": [round(v, 4) for v in (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))],
        "tri": len(indices) // 3,
    }


def mesh_model(
    data: bytes,
    *,
    suffix: str = "step",
    gmsh: list[str] | None = None,
    cache: Path | None = None,
    timeout: int = TIMEOUT,
) -> Mesh | None:
    """The mesh of one model file's ``data``, or ``None`` when gmsh is missing, fails, runs out of time or
    writes no triangle. With ``cache`` a mesh, or a failure, is read and kept there."""
    key = mesh_key(data)
    if cache is not None:
        hit, failed = cache / f"{key}.json", cache / f"{key}.failed"
        if hit.is_file():
            try:
                found: Mesh = json.loads(hit.read_text(encoding="utf-8"))
                return found
            except ValueError:
                pass
        if failed.is_file():
            return None
    command = gmsh or find_gmsh()
    if command is None:
        return None
    mesh: Mesh | None = None
    reason = "gmsh wrote no triangle"
    with tempfile.TemporaryDirectory(prefix="fenolite-mesh-") as work:
        folder = Path(work)
        (folder / f"model.{suffix}").write_bytes(data)
        (folder / "model.geo").write_text(SCRIPT.format(suffix=suffix), encoding="ascii")
        try:
            proc = subprocess.run(
                [*command, "model.geo", "-0", "-nopopup"],
                cwd=folder,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            out = folder / "mesh.x3d"
            if proc.returncode == 0 and out.is_file():
                mesh = read_x3d(out.read_text(encoding="utf-8", errors="replace"))
            else:
                reason = f"gmsh exit {proc.returncode}"
        except subprocess.TimeoutExpired:
            reason = f"gmsh ran over {timeout} s"
        except OSError as exc:
            reason = f"{type(exc).__name__}: {exc}"
    if cache is not None:
        try:
            cache.mkdir(parents=True, exist_ok=True)
            if mesh is not None:
                (cache / f"{key}.json").write_text(json.dumps(mesh), encoding="utf-8")
            else:
                (cache / f"{key}.failed").write_text(reason, encoding="utf-8")
        except OSError:  # a cache that cannot be written only costs the next run its time
            pass
    return mesh


def mesh_models(
    items: Sequence[tuple[bytes, str]],
    *,
    gmsh: list[str] | None = None,
    cache: Path | None = None,
    timeout: int = TIMEOUT,
    workers: int = 0,
) -> list[Mesh | None]:
    """``mesh_model`` of each ``(data, suffix)``, in order, with up to ``workers`` gmsh processes at a time
    (0: the processor count less one, at least one)."""
    command = gmsh or find_gmsh()
    count = workers or max(1, (os.cpu_count() or 2) - 1)

    def one(item: tuple[bytes, str]) -> Mesh | None:
        return mesh_model(item[0], suffix=item[1], gmsh=command, cache=cache, timeout=timeout)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(one, items))


__all__ = [
    "CACHE_FOLDER",
    "GMSH_ENV",
    "MESH_VERSION",
    "Mesh",
    "cache_folder",
    "find_gmsh",
    "mesh_key",
    "mesh_model",
    "mesh_models",
    "read_x3d",
]
