# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private authored Part S catalogue and its existing S7 readback criterion."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.errors import FenoliteError, FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.verify.kit.manifest import SampleFiles

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-SLOT-KIT",))
MAX_ASSET = 4 * 1024 * 1024
_ASSETS = {
    "PROVENANCE.md": "c0245f0918c7294df71a78aa565bd91dbea3fbfedb9822c866f9a117f9eee43b",
    "clearance/slots.PcbDoc": "822d31cf5ee269e44b573db595388c0532008523ff4d0d93d103c7a528a8ec3e",
    "clearance/slots.PcbLib": "0cb1c97ecb3821808275b54ecd986cedf21acdb0ed4f4f6ee4546201f61eeb11",
    "clearance/slots.PrjPcb": "c1e0bb980352ed7bd7d01a1a584106883f7dc0f42db05dfbf3b49f7d59c320c1",
    "clearance/slots.SchDoc": "0976b57d969fb5be103ee57761d13f123d3cf99643c83c86c96ef73c916efdb8",
    "clearance/slots.SchLib": "14f88c47b5bf89aa45c1b4be879232bb89bef86e3898346e0042907965e6c160",
    "criteria.md": "46a44f379b291a1baa457390ae16cbc797a6079b47a1d120df42b44ce8bac79c",
    "gate-off/build-report.json": "64393d41b44ce666e47cb07bbb80698149729f67b9cdb3a52cd4f420b9f0ae00",
    "gate-off/slots.PcbDoc": "c798ec4604bddbd28674bdd7fde5a41fdf6440b8ed4c298bc984b005ecb95554",
    "gate-off/slots.PrjPcb": "e7d693f497c3345351e319d0b0c80cc9454443f30b5053ba27e5a57912b51bc5",
    "gate-off/slots.SchDoc": "3d49003f302035874a7933695bf20a3187c9f298bcd5be4c8bdf92ed9cccd2b3",
    "regions/slots.PcbDoc": "be65d4b9884e1949abd162f64033f54b92167bf1cea5af535031d691467910f0",
    "regions/slots.PrjPcb": "e7d693f497c3345351e319d0b0c80cc9454443f30b5053ba27e5a57912b51bc5",
    "regions/slots.SchDoc": "3d49003f302035874a7933695bf20a3187c9f298bcd5be4c8bdf92ed9cccd2b3",
}


def _read(folder: Path, relative: str) -> bytes:
    parts = PurePosixPath(relative).parts
    if (
        not parts
        or PurePosixPath(relative).is_absolute()
        or ".." in parts
        or "\\" in relative
        or ":" in relative
    ):
        raise FormatError("Part S catalogue path leaves its source folder", file="slots")
    target = folder
    for part in parts:
        target = target / part
        if target.is_symlink():
            raise FormatError("Part S catalogue symlink refused", file=relative)
    try:
        if target.stat().st_size > MAX_ASSET:
            raise FormatError("Part S catalogue asset exceeds its limit", file=relative)
        data = target.read_bytes()
    except OSError as error:
        raise FormatError("Part S catalogue asset is unavailable", file=relative) from error
    if len(data) > MAX_ASSET:
        raise FormatError("Part S catalogue asset exceeds its limit", file=relative)
    return data


def part_s_sample(folder: Path) -> SampleFiles:
    """Load pinned authored inputs through the existing portable samples directory."""
    if folder.is_symlink():
        raise FormatError("Part S catalogue symlink refused", file="slots")
    files: dict[str, bytes] = {}
    for name, expected in _ASSETS.items():
        data = _read(folder, name)
        if hashlib.sha256(data).hexdigest() != expected:
            raise FormatError("Part S authored input differs from its catalogue digest", file=name)
        files[name] = data
    recipe = _read(folder, "design.py")
    files["recipe.py"] = recipe
    return SampleFiles("slots", hashlib.sha256(recipe).hexdigest(), files)


def _geometry(path: Path) -> tuple[list[tuple[int, int, int, int | None, int]], list[list[tuple[int, int]]]]:
    data = path.read_bytes()
    doc = read_pcbdoc(data)
    if any(issue.severity == "error" for issue in doc.issues):
        raise FormatError("Part S board could not be read completely", file=path.name)
    board = import_board(doc, file=path.name, sha256=hashlib.sha256(data).hexdigest()).board
    if board is None:
        raise FormatError("Part S result holds no board", file=path.name)
    holes = sorted(
        (h.position.x, h.position.y, h.drill, h.length, h.rotation % 180_000_000 if h.length else 0)
        for h in board.holes
    )
    rings = [
        [(p.x, p.y) for p in g.points]
        for g in board.graphics
        if g.layer == "Edge.Cuts" and g.kind == "polygon"
    ]
    return holes, rings


def slots_readback_problems(own: Path, saved: Path) -> list[str]:
    """Exactly S7's four holes/three cut-outs within1µm, without additional CAD gates."""
    try:
        holes, rings = _geometry(own)
        found, contours = _geometry(saved)
    except (FenoliteError, OSError) as error:
        return [f"Part S S7 could not read its board: {error}"]
    if len(holes) != 4 or len(found) != 4:
        return ["Part S S7 requires the same four holes"]
    for a, b in zip(holes, found, strict=True):
        if not (
            all(abs(x - y) <= 1000 for x, y in zip(a[:3], b[:3], strict=True))
            and (a[3] is None) == (b[3] is None)
            and abs((a[3] or 0) - (b[3] or 0)) <= 1000
            and abs(a[4] - b[4]) <= 1000
        ):
            return ["Part S S7 hole position/drill/length/axis differs by more than1µm or0.001degree"]
    if len(rings) != 3 or len(contours) != 3:
        return ["Part S S7 requires the same three cut-outs"]
    for ring in rings:
        if not any(
            all(any(abs(x - u) <= 1000 and abs(y - v) <= 1000 for u, v in ring) for x, y in other)
            and all(any(abs(x - u) <= 1000 and abs(y - v) <= 1000 for u, v in other) for x, y in ring)
            for other in contours
        ):
            return ["Part S S7 cut-out contour differs by more than1µm"]
    return []
