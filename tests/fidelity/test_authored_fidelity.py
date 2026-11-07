# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored CC0 stand-ins through the actual importer and all fidelity levels (c0278).

The committed sensor is an authored text stand-in, not a KiCad GUI save. Hierarchy, bus and Repeat
projects are built from Fenolite's own authored fixtures in tmp_path. No native application is claimed.
"""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

import _drawn
import pytest
from _fidelity import ALL_LEVELS, roundtrip

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Track
from fenolite.model.drawn import DrawnSchematic

ROOT = Path(__file__).resolve().parents[2]
SENSOR = ROOT / "tests/data/fidelity/sensor"


def _complete(reply) -> None:  # noqa: ANN001
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert reply.result["equivalent"] is True
    assert reply.result["differences"] == [] and reply.result["accepted"] == []
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"])
    assert reply.result["tolerances"] == {
        "length_nm": 0, "angle_udeg": 0, "length_ppm": 0, "pixel_ppm": 1000,
        "render_pitch_um": 50, "frame": "absolute",
    }  # fmt: skip


def _project(name: str, folder: Path, value: DrawnSchematic | None = None) -> Path:
    output = _drawn.build(name, value=value)
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    for relative, data in output.files.items():
        if relative.startswith(".fenolite/"):
            continue
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    board_file = next(folder.glob("*.kicad_pcb"))
    design = read_board(board_file)
    assert design.board is not None and design.circuit.nets
    # A one-mm authored stub makes strict level 5 reachable on the otherwise unrouted drawn fixtures.
    # It belongs to this temporary stand-in, carries an actual net, and is compared without tolerance.
    track = Track(
        id=derived_id("trk", "fidelity", name),
        start=Point(5_000_000, 5_000_000),
        end=Point(6_000_000, 5_000_000),
        width=250_000,
        layer="F.Cu",
        net_id=design.circuit.nets[0].id,
    )
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=(track,)))
    board_file.write_text(write_board(design, target=10).text, encoding="utf-8")
    return folder


def test_sensor_roundtrip_is_strict_and_hermetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        pytest.fail("a hermetic fidelity round trip started an external process")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    reply = roundtrip(SENSOR, tmp_path)
    _complete(reply)
    routing = next(row for row in reply.result["levels"] if row["level"] == 5)
    assert routing["summary"]["strict"]["vias"]["matched"] == 3
    assert routing["summary"]["strict"]["tracks"]["matched"] > 0
    assert routing["summary"]["strict"]["arcs"]["matched"] > 0


@pytest.mark.parametrize("name", ("hier", "bus", "repeat"))
def test_authored_drawn_projects_roundtrip_all_levels(name: str, tmp_path: Path) -> None:
    original = _project(name, tmp_path / "original")
    assert not (original / ".fenolite").exists()
    _complete(roundtrip(original, tmp_path / "roundtrip"))


def test_writer_dropping_a_redundant_junction_is_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An endpoint junction preserves nets, so the byte-connectivity guard must not hide level S."""
    from fenolite.backends.kicad import drawn as writer
    from fenolite.model.drawn import DrawnJunction

    value = _drawn.drawn("hier")
    first = value.sheets[0]
    assert first.wires
    junction = DrawnJunction(first.wires[0][0])
    # This junction is deliberately redundant: it does not bridge a crossing or join distinct groups.
    assert isinstance(junction.at, Point)
    patched = dataclasses.replace(first, junctions=(*first.junctions, junction))
    value = dataclasses.replace(value, sheets=(patched, *value.sheets[1:]))
    original = _project("hier", tmp_path / "original", value)
    _complete(roundtrip(original, tmp_path / "control"))
    write = writer.lower_drawn

    def drop(value, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        sheets = tuple(dataclasses.replace(sheet, junctions=()) for sheet in value.sheets)
        return write(dataclasses.replace(value, sheets=sheets), *args, **kwargs)

    monkeypatch.setattr(writer, "lower_drawn", drop)
    reply = roundtrip(original, tmp_path / "roundtrip")
    assert reply.exit_code == 5 and reply.result["equivalent"] is False
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    schematic = [d for d in reply.result["differences"] if d["level"] == "S"]
    assert len(schematic) == 1
    assert (schematic[0]["kind"], schematic[0]["field"]) == ("item-missing", "junction")
    assert schematic[0]["a"] and not schematic[0]["b"]
    assert all(row["status"] == "equal" for row in reply.result["levels"] if row["level"] in range(1, 8))
