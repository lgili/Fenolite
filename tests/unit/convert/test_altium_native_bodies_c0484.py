# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The source's parametric bodies come back native (change c0484; capability design-conversion, "Native
bodies are kept through KiCad").

The source is the authored document of ``tests/_altium_models.py``: eight bodies that name an embedded model,
two extruded bodies, three cylinders and two spheres, each on its own component. KiCad has no extruded
body, so the conversion to KiCad writes each component's parametric bodies as one generated STEP model; the
way back writes the source's records again while the model and its footprint are as that conversion left
them."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import _altium_models as am

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium.models3d import model_records
from fenolite.backends.altium.read.bodies import read_bodies
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import models

PARAMETRIC = ("E1", "E2", "C1", "C2", "K1", "S1", "S2")


def _write(result: ConversionResult, folder: Path) -> Path:
    for key, data in result.conversion.files.items():
        path = folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder


def _to_kicad(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "altium").mkdir()
    source = am.write_folder(tmp_path / "altium")
    (board,) = _write(convert(source, to="kicad", allow_lossy=True, verify=False), tmp_path / "kicad").glob(
        "*.kicad_pcb"
    )
    return source, board


def _back(board: Path, folder: Path) -> tuple[Path, ConversionResult]:
    result = convert(board, to="altium", allow_lossy=True, verify=False)
    (document,) = _write(result, folder).glob("*.PcbDoc")
    return document, result


def _bodies(path: Path) -> dict[str, list[tuple[str, bytes, bytes]]]:
    """Per designator, each body's ``MODEL.MODELTYPE`` and its plain and shape-based record without the
    component index."""
    document = read_pcbdoc(path.read_bytes(), file=path.name)
    names = [str(c.source_designator) for c in document.components]
    plain = read_bodies(document.storages["ComponentBodies6"]["Data"])
    shape = read_bodies(document.storages["ShapeBasedComponentBodies6"]["Data"], shape_based=True)
    found: dict[str, list[tuple[str, bytes, bytes]]] = {}
    for a, b in zip(plain, shape, strict=True):
        assert a.component is not None
        row = (a.properties.text("MODEL.MODELTYPE"), a.raw[:12] + a.raw[14:], b.raw[:12] + b.raw[14:])
        found.setdefault(names[a.component], []).append(row)
    return found


def test_parametric_bodies_come_back_native(tmp_path: Path) -> None:
    """Scenario "The source's bodies come back": every extruded, cylinder and sphere record is the source's
    but for its component index, no generated model is embedded, and the report counts no change."""
    source, board = _to_kicad(tmp_path)
    carried = models.read_bodies(
        boardcarrier.carried(board.read_text(encoding="utf-8")).get(models.BODIES_PROPERTY)
    )
    assert len(carried) == len(PARAMETRIC)
    document, result = _back(board, tmp_path / "back")
    before, after = _bodies(source), _bodies(document)
    assert {ref: before[ref] for ref in PARAMETRIC} == {ref: after[ref] for ref in PARAMETRIC}
    assert Counter(kind for rows in after.values() for kind, _, _ in rows) == Counter(
        {"1": 8, "0": 2, "2": 3, "3": 2}
    )
    names = [
        r.get("NAME", "")
        for r in model_records(read_pcbdoc(document.read_bytes()).storages["Models"]["Data"])
    ]
    assert all(name.startswith("marker") for name in names)
    assert not any(row.changed for row in result.conversion.report.rows if row.kind == "model")


def test_a_moved_footprint_takes_its_generated_model(tmp_path: Path) -> None:
    """Scenario "A moved footprint takes the model": E1 moved in KiCad comes back as its generated model
    (type 1); the other bodies stay native."""
    _, board = _to_kicad(tmp_path)
    text = board.read_text(encoding="utf-8")
    at = text.index('"Reference" "E1"')
    head = text.rfind("(footprint", 0, at)
    place = re.compile(r"\(at (\S+) (\S+)\)").search(text, head, at)
    assert place is not None
    moved = f"(at {float(place.group(1)) + 1:.6f} {place.group(2)})"
    board.write_text(text[: place.start()] + moved + text[place.end() :], encoding="utf-8")
    after = _bodies(_back(board, tmp_path / "back")[0])
    assert [kind for kind, _, _ in after["E1"]] == ["1"]
    assert [kind for kind, _, _ in after["E2"]] == ["0"]


def test_carrier_reads_what_it_writes_and_drops_disagreement() -> None:
    """Turns are compared modulo a full turn; a key whose entries disagree, or an entry that is not well
    formed, gives nothing."""
    deg = 1_000_000
    pairs = ((b"plain", b"shape"),)
    one = (("ab", 1, 2, -90 * deg, "top"), pairs)
    two = (("cd", 0, 0, 0, "bottom"), ((b"x", b"y"), (b"z", b"w")))
    read = models.read_bodies(models.bodies_text([one, two]).encode("utf-8"))
    assert read == {("ab", 1, 2, 270 * deg, "top"): pairs, ("cd", 0, 0, 0, "bottom"): two[1]}
    clash = (("ab", 1, 2, 270 * deg, "top"), ((b"other", b"shape"),))
    assert models.read_bodies(models.bodies_text([one, clash, two]).encode("utf-8")) == {
        ("cd", 0, 0, 0, "bottom"): two[1]
    }
    for data in (
        b"",
        b"not json",
        b'{"schema": "other"}',
        b'{"schema": "fenolite.altium-bodies.v0", "models": [{}]}',
    ):
        assert models.read_bodies(data) == {}
