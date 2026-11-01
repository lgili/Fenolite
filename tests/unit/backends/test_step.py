# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The STEP writer of generated bodies (change c0260, scenario "Deterministic and closed").

A small reader of our own checks the written file: every reference resolves, every solid is closed (each edge
used once in each sense, V - E + F = 2) and no number has an exponent."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from fenolite.backends.step import SCHEMA, mm, write_bodies
from fenolite.catalog.footprints import generate, read_package
from fenolite.core.coords import Point
from fenolite.model.board import ComponentBody

PACKAGES = Path(__file__).resolve().parents[2] / "data" / "packages"
INSTANCE = re.compile(r"^#(\d+)=(.*);$")
REFERENCE = re.compile(r"#(\d+)")


def _bodies(stem: str) -> tuple[str, tuple[ComponentBody, ...]]:
    footprint = generate(read_package((PACKAGES / f"{stem}.toml").read_text(encoding="utf-8"))).footprint
    assert footprint is not None and footprint.bodies
    return footprint.name, footprint.bodies


def _instances(data: bytes) -> dict[int, str]:
    text = data.decode("ascii")
    lines = text.splitlines()
    assert lines[0] == "ISO-10303-21;" and lines[-1] == "END-ISO-10303-21;"
    assert f"FILE_SCHEMA(('{SCHEMA}'));" in lines
    found: dict[int, str] = {}
    for line in lines[lines.index("DATA;") + 1 : -2]:
        match = INSTANCE.match(line)
        assert match, line
        found[int(match.group(1))] = match.group(2)
    return found


def _head(body: str) -> str:
    return body.split("(", 1)[0]


def _refs(body: str) -> list[int]:
    return [int(r) for r in REFERENCE.findall(body)]


def _check_solid(instances: dict[int, str], solid: int) -> None:
    shell = _refs(instances[solid])[0]
    assert _head(instances[shell]) == "CLOSED_SHELL"
    faces = _refs(instances[shell])
    uses: Counter[tuple[int, bool]] = Counter()
    vertices: set[int] = set()
    for face in faces:
        assert _head(instances[face]) == "ADVANCED_FACE"
        bound = _refs(instances[face])[0]
        loop = _refs(instances[bound])[0]
        for oriented in _refs(instances[loop]):
            body = instances[oriented]
            assert body.startswith("ORIENTED_EDGE('',*,*,")
            edge = _refs(body)[0]
            sense = body.endswith(".T.)")
            uses[(edge, sense)] += 1
            vertices.update(_refs(instances[edge])[:2])
    edges = {edge for edge, _ in uses}
    assert all(uses[(edge, True)] == 1 and uses[(edge, False)] == 1 for edge in edges)
    assert len(vertices) - len(edges) + len(faces) == 2


def test_deterministic_and_closed() -> None:
    name, bodies = _bodies("soic8")
    first, second = write_bodies(name, bodies), write_bodies(name, bodies)
    assert first == second
    instances = _instances(first)
    for body in instances.values():
        for ref in _refs(body):
            assert ref in instances, body
    numbers = re.findall(r"(?<![#\w])-?\d+\.\d*(?:[eE][+-]?\d+)?", first.decode("ascii"))
    assert numbers and not [n for n in numbers if "e" in n.lower()]
    solids = [i for i, body in instances.items() if _head(body) == "MANIFOLD_SOLID_BREP"]
    assert len(solids) == len(bodies) == 17
    for solid in solids:
        _check_solid(instances, solid)
    assert sum(1 for body in instances.values() if _head(body) == "STYLED_ITEM") == 17
    assert "MANIFOLD_SOLID_BREP('body'," in first.decode("ascii")


@pytest.mark.parametrize("stem", ["chip0603", "dip8", "header1x2", "qfn16", "bga12", "connector_xh"])
def test_every_family_closes(stem: str) -> None:
    name, bodies = _bodies(stem)
    instances = _instances(write_bodies(name, bodies))
    for solid in (i for i, body in instances.items() if _head(body) == "MANIFOLD_SOLID_BREP"):
        _check_solid(instances, solid)


def test_numbers_and_timestamp() -> None:
    assert (mm(1_270_000), mm(5_000_000), mm(0), mm(-500), mm(-3_365_000)) == (
        "1.27",
        "5.",
        "0.",
        "-0.0005",
        "-3.365",
    )
    name, bodies = _bodies("chip0603")
    stamped = write_bodies(name, bodies, timestamp="2026-10-30T00:00:00").decode("ascii")
    assert "'2026-10-30T00:00:00'" in stamped and "Fenolite" in stamped


def test_refusals() -> None:
    flat = ComponentBody(
        id="bdy_1",
        kind="extruded",
        height=0,
        outline=(Point(0, 0), Point(1, 0), Point(1, 1)),
        z_min=0,
        z_max=0,
    )
    with pytest.raises(ValueError, match="no height"):
        write_bodies("x", [flat])
    with pytest.raises(ValueError, match="at least one body"):
        write_bodies("x", [])
    line = ComponentBody(
        id="bdy_2",
        kind="extruded",
        height=1,
        outline=(Point(0, 0), Point(1, 0), Point(2, 0)),
        z_min=0,
        z_max=1,
    )
    with pytest.raises(ValueError, match="no area"):
        write_bodies("x", [line])
    _, bodies = _bodies("chip0603")
    with pytest.raises(ValueError, match="printable ASCII"):
        write_bodies("Ω", bodies)
