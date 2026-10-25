# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Meshes of body models (capability board-viewer, "Body models"; change c0193): the X3D that gmsh writes,
read without an XML parser; the command that runs gmsh; the cache. A stand-in script plays gmsh, so no test
needs it installed."""

from __future__ import annotations

import base64
import struct
import sys
from pathlib import Path

import pytest

from fenolite.view import meshes

X3D = """<?xml version="1.0" encoding="UTF-8"?>
<X3D profile='Interchange' version='3.3'><Scene><Group DEF="faces">
<Shape DEF="Shapes/A & B">
<Appearance><Material DEF="m1" diffuseColor="0.5 0.25 1"></Material></Appearance>
<TriangleSet DEF="s1"><Coordinate point="
0 0 0
1 0 0
0 1 0
1 0 0
1 1 0
0 1 0
"></Coordinate></TriangleSet></Shape>
<Shape DEF="face2">
<Appearance><Material DEF="m2" diffuseColor="1.000000 1.000000 1.000000"></Material></Appearance>
<TriangleSet DEF="s2"><Coordinate point="0 0 1 1 0 1 0 1 1"></Coordinate></TriangleSet></Shape>
</Group></Scene></X3D>
"""


def test_x3d() -> None:
    """Scenario "X3D of an authored model": the ``&`` of a label in a ``DEF`` does not stop the reader."""
    mesh = meshes.read_x3d(X3D)
    assert mesh is not None and mesh["tri"] == 3 and mesh["bbox"] == [0, 0, 0, 1, 1, 1]
    positions = struct.unpack(f"<{len(base64.b64decode(mesh['v'])) // 4}f", base64.b64decode(mesh["v"]))
    assert len(positions) == 3 * 7  # four shared vertices of the first set, three of the second
    colours = base64.b64decode(mesh["c"])
    assert tuple(colours[:4]) == (128, 64, 255, 255) and tuple(colours[-4:]) == (0, 0, 0, 0)
    assert meshes.read_x3d("<X3D></X3D>") is None


def test_find_gmsh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    launcher = tmp_path / "bin" / "gmsh"
    launcher.parent.mkdir()
    launcher.write_text("#!/usr/bin/env python\nimport gmsh\n", encoding="utf-8")
    monkeypatch.setenv(meshes.GMSH_ENV, str(launcher))
    assert meshes.find_gmsh() == [sys.executable, str(launcher)]
    beside = launcher.with_name("python3")
    beside.write_text("", encoding="utf-8")
    assert meshes.find_gmsh() == [str(beside), str(launcher)]
    binary = tmp_path / "gmsh-bin"
    binary.write_bytes(b"\x7fELF")
    monkeypatch.setenv(meshes.GMSH_ENV, str(binary))
    assert meshes.find_gmsh() == [str(binary)]
    monkeypatch.setenv(meshes.GMSH_ENV, str(tmp_path / "none"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert meshes.find_gmsh() is None


def test_mesh_model_runs_the_command_and_keeps_the_mesh(tmp_path: Path) -> None:
    fake = tmp_path / "fake_gmsh.py"
    fake.write_text(
        "import pathlib, sys\n"
        "assert sys.argv[1:] == ['model.geo', '-0', '-nopopup']\n"
        f"pathlib.Path('mesh.x3d').write_text({X3D!r})\n",
        encoding="utf-8",
    )
    cache = tmp_path / "cache"
    mesh = meshes.mesh_model(b"ISO-10303-21;", gmsh=[sys.executable, str(fake)], cache=cache)
    assert mesh is not None and mesh["tri"] == 3
    assert (cache / f"{meshes.mesh_key(b'ISO-10303-21;')}.json").is_file()
    assert meshes.mesh_model(b"ISO-10303-21;", gmsh=["/no/such/gmsh"], cache=cache) == mesh  # from the cache
    broken = tmp_path / "broken.py"
    broken.write_text("raise SystemExit(3)\n", encoding="utf-8")
    assert meshes.mesh_model(b"other", gmsh=[sys.executable, str(broken)], cache=cache) is None
    assert (cache / f"{meshes.mesh_key(b'other')}.failed").read_text(encoding="utf-8") == "gmsh exit 3"
    many = meshes.mesh_models(
        [(b"ISO-10303-21;", "step"), (b"other", "step")], gmsh=["/no"], cache=cache, workers=2
    )
    assert many[0] == mesh and many[1] is None
