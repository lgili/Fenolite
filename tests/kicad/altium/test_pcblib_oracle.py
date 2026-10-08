# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The PCB library Fenolite writes against ``kicad-cli fp upgrade`` (capability altium-pcb-writer, "PCB
library oracle"; change c0035; hypothesis ``H-A-PCB-KICAD-LIB``).

The round trip is: the blink build's footprints → ``write_pcblib`` → ``kicad-cli fp upgrade X.PcbLib -o
Y.pretty`` (KiCad's Altium importer, S-0166) → ``backends.kicad.mod.read_footprint`` → compare with the
source ``FootprintDef``. ``fp upgrade`` exits 0 even when a footprint is invisible to it, so the test counts
the files; the negative control removes one footprint's ``Parameters``. On kicad-cli 9 a library that does
not convert is expected to fail, with kicad-cli's message.

A pass checks only what KiCad's importer reads; it settles no Altium-only fact. Mechanical layers come
back as ``User.<n>`` (``pcb-records.md``, "Layers").
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from _altium import blink, blink_resolver
from _cfb_read import read_compound
from _kicad import oracle_env
from _resources import kicad_cli, kicad_cli_major

from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.kicad.mod import read_footprint
from fenolite.dsl import placements, to_model
from fenolite.geometry.shapes import Arc
from fenolite.lens.altium import build_altium, pad_extras
from fenolite.model.board import Graphic, Pad
from fenolite.model.library import FootprintDef

pytestmark = pytest.mark.needs_kicad

TOLERANCE = 10
"""Nanometres: KiCad writes 1 nm and Fenolite rounds to 2.54 nm units."""
BACK_10 = {"F.SilkS": "F.SilkS", "B.SilkS": "B.SilkS", "F.Fab": "User.13", "B.Fab": "User.14",
           "F.CrtYd": "User.15", "B.CrtYd": "User.16"}  # fmt: skip
BACK_9 = {**BACK_10, "F.Fab": "B.Fab", "F.CrtYd": "Eco2.User"}
"""kicad-cli 9.0.9 puts Mechanical 13 on ``B.Fab`` and 15 on ``Eco2.User`` (observed 2026-10-03)."""
BACK = BACK_9 if kicad_cli_major() == 9 else BACK_10
"""Where each written layer comes back in KiCad: on 10.0, mechanical n is ``User.n``."""


@dataclass(frozen=True)
class Converted:
    code: int
    message: str
    files: dict[str, bytes]


def convert(data: bytes, name: str = "blink.PcbLib") -> Converted:
    cli = kicad_cli()
    assert cli is not None
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source, target = root / name, root / "out.pretty"
        source.write_bytes(data)
        env = oracle_env(root / "config")
        proc = subprocess.run(
            [cli, "fp", "upgrade", str(source), "-o", str(target)],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            check=False,
        )
        files = (
            {p.name: p.read_bytes() for p in sorted(target.glob("*.kicad_mod"))} if target.is_dir() else {}
        )
        return Converted(proc.returncode, (proc.stdout + proc.stderr).strip(), files)


def converted(data: bytes) -> Converted:
    result = convert(data)
    if result.code != 0 and kicad_cli_major() == 9:
        pytest.xfail(f"kicad-cli 9 does not convert the library: exit {result.code}: {result.message}")
    assert result.code == 0, result.message
    return result


@cache
def blink_build() -> tuple[bytes, tuple[FootprintDef, ...]]:
    design = blink()
    with tempfile.TemporaryDirectory() as folder:
        output = build_altium(
            to_model(design),
            name=design.name,
            placed=tuple(placements(design)),
            resolver=blink_resolver(Path(folder)),
        )
        resolver = blink_resolver(Path(folder))
        links = sorted({c.lib_footprint_ref for c in output.design.circuit.components})
        sources = tuple(resolver.footprint(link) for link in links)
    return output.files["blink.PcbLib"], sources


def read_converted(name: str, data: bytes) -> FootprintDef:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / name
        path.write_bytes(data)
        return read_footprint(path, library="out")


def close(a: int, b: int) -> bool:
    return abs(a - b) <= TOLERANCE


def pad_key(pad: Pad) -> tuple[object, ...]:
    return (pad.number, pad.kind, pad.shape, pad.rotation)


def compare_pads(source: FootprintDef, read: FootprintDef) -> None:
    got = {p.number: p for p in read.pads}
    assert sorted(got) == sorted(p.number for p in source.pads)
    src_extras, read_extras = pad_extras(source), pad_extras(read)
    for pad in source.pads:
        other = got[pad.number]
        assert pad_key(other) == pad_key(pad), pad.number
        assert close(other.position.x, pad.position.x) and close(other.position.y, pad.position.y), pad.number
        assert close(other.size.w, pad.size.w) and close(other.size.h, pad.size.h), pad.number
        assert (other.drill is None) == (pad.drill is None)
        if pad.drill is not None and other.drill is not None:
            assert close(other.drill, pad.drill)
        ratio, back = src_extras[pad.id].corner_ratio, read_extras[other.id].corner_ratio
        if ratio is not None:
            assert back is not None and abs(back - ratio) <= Decimal("0.005"), pad.number


def segments(defn: FootprintDef, *, written: bool) -> list[tuple[str, int, tuple[int, int], tuple[int, int]]]:
    """Every straight piece: lines, and rectangles as four sides; layers mapped back when ``written``."""
    out: list[tuple[str, int, tuple[int, int], tuple[int, int]]] = []
    for g in defn.graphics:
        layer = BACK.get(g.layer, g.layer) if written else g.layer
        points: list[tuple[int, int]] = [(p.x, p.y) for p in g.points]
        if g.kind == "line":
            out.append((layer, g.width, points[0], points[1]))
        elif g.kind == "rect":
            (x0, y0), (x1, y1) = points
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            out += [(layer, g.width, corners[i], corners[(i + 1) % 4]) for i in range(4)]
    return out


def same_segment(
    a: tuple[str, int, tuple[int, int], tuple[int, int]], b: tuple[str, int, tuple[int, int], tuple[int, int]]
) -> bool:
    if a[0] != b[0] or not close(a[1], b[1]):
        return False
    forward = all(close(p, q) for p, q in zip(a[2] + a[3], b[2] + b[3], strict=True))
    backward = all(close(p, q) for p, q in zip(a[2] + a[3], b[3] + b[2], strict=True))
    return forward or backward


def curves(defn: FootprintDef, *, written: bool) -> list[Graphic]:
    return [g for g in defn.graphics if g.kind in ("arc", "circle")]


def same_curve(source: Graphic, read: Graphic) -> bool:
    if BACK.get(source.layer, source.layer) != read.layer or source.kind != read.kind:
        return False
    if not close(source.width, read.width):
        return False
    if source.kind == "circle":
        c0, e0 = source.points
        c1, e1 = read.points
        r0 = ((e0.x - c0.x) ** 2 + (e0.y - c0.y) ** 2) ** 0.5
        r1 = ((e1.x - c1.x) ** 2 + (e1.y - c1.y) ** 2) ** 0.5
        return close(c0.x, c1.x) and close(c0.y, c1.y) and abs(r0 - r1) <= TOLERANCE
    a, b = Arc(*source.points), Arc(*read.points)
    ends = {(p.x, p.y) for p in (a.start, a.end)}
    back = [(p.x, p.y) for p in (b.start, b.end)]
    if not all(any(close(x, ex) and close(y, ey) for ex, ey in ends) for x, y in back):
        return False
    assert a.centre is not None and b.centre is not None
    return all(abs(float(u - v)) <= TOLERANCE for u, v in zip(a.centre, b.centre, strict=True))


def compare_graphics(source: FootprintDef, read: FootprintDef) -> None:
    expected = segments(source, written=True)
    expected = [s for s in expected if s[0] in BACK.values()]
    got = segments(read, written=False)
    assert len(got) == len(expected), (source.name, got, expected)
    remaining = list(got)
    for item in expected:
        match = next((g for g in remaining if same_segment(item, g)), None)
        assert match is not None, (source.name, item)
        remaining.remove(match)
    src_curves, read_curves = curves(source, written=True), curves(read, written=False)
    assert len(read_curves) == len(src_curves)
    for item in src_curves:
        assert any(same_curve(item, g) for g in read_curves), (source.name, item)


def test_round_trip_of_the_mini_footprints() -> None:
    """Scenario "Round trip of the mini footprints": three files, each matching its source."""
    data, sources = blink_build()
    result = converted(data)
    assert sorted(result.files) == sorted(f"{s.name}.kicad_mod" for s in sources)
    for source in sources:
        read = read_converted(f"{source.name}.kicad_mod", result.files[f"{source.name}.kicad_mod"])
        assert read.name == source.name and read.description == source.description
        compare_pads(source, read)
        compare_graphics(source, read)


def test_footprint_without_parameters_is_not_converted() -> None:
    """Negative control: exit 0, but no file for a footprint without ``Parameters``; the count catches it."""
    data, sources = blink_build()
    streams = {path: body for path, body in read_compound(data).items() if path != "Mini_R_0603/Parameters"}
    broken = write_compound(storage_from_paths(streams))
    result = convert(broken)
    assert result.code in (0, 2), result.message  # 10.0.6 exits 0, 9.0.9 exits 2 (observed 2026-10-03)
    assert "Mini_R_0603.kicad_mod" not in result.files
    assert len(result.files) < len(sources)
