# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stored heights of Altium model bodies through KiCad (change c0449, task 4.3; capability
design-conversion, "Models of a KiCad board in an Altium target").

A model body that comes back with the same model and the same placement keeps the ``STANDOFFHEIGHT`` and
``OVERALLHEIGHT`` its source stores; only a model that is new or changed takes the heights of its STEP box.
The source is the authored document of ``tests/_altium_models.py``: each model body stores 0 and 60 mil,
while the authored marker model spans 20 to 100 mil, so the box and the stored heights differ."""

from __future__ import annotations

import re
from pathlib import Path

import _altium_models as am

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium.read.bodies import read_bodies
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import models

DEG = 1_000_000
STORED = ("0mil", "60mil")
"""The heights every model body of the authored document stores (``Case`` defaults)."""


def _write(result: ConversionResult, folder: Path) -> Path:
    for key, data in result.conversion.files.items():
        path = folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder


def _to_kicad(tmp_path: Path) -> Path:
    (tmp_path / "altium").mkdir()
    source = am.write_folder(tmp_path / "altium")
    kicad = _write(convert(source, to="kicad", allow_lossy=True, verify=False), tmp_path / "kicad")
    (board,) = kicad.glob("*.kicad_pcb")
    return board


def _heights_back(board: Path, folder: Path) -> dict[str, tuple[str, str]]:
    """Per designator, the heights of its body that embeds the marker model in the Altium document converted
    from ``board`` (the generated models of the other bodies are left out)."""
    back = _write(convert(board, to="altium", allow_lossy=True, verify=False), folder)
    (path,) = back.glob("*.PcbDoc")
    document = read_pcbdoc(path.read_bytes(), file=path.name)
    names = [str(c.source_designator) for c in document.components]
    found: dict[str, tuple[str, str]] = {}
    for body in read_bodies(document.storages["ComponentBodies6"]["Data"], storage="ComponentBodies6"):
        keys = body.properties
        marker = (keys.text("MODEL.NAME") or "").startswith("marker_")
        if keys.text("MODEL.MODELTYPE") == "1" and marker and body.component is not None:
            found[names[body.component]] = (keys.text("STANDOFFHEIGHT"), keys.text("OVERALLHEIGHT"))
    return found


def test_unchanged_models_keep_their_stored_heights(tmp_path: Path) -> None:
    """Each of the eight model bodies, on either side and for any turn, comes back with 0 and 60 mil, not
    with its box; the conversion to KiCad carries them in ``models.HEIGHTS_PROPERTY``."""
    board = _to_kicad(tmp_path)
    carried = boardcarrier.carried(board.read_text(encoding="utf-8"))
    stored = models.read_heights(carried.get(models.HEIGHTS_PROPERTY))
    assert len(stored) == 8 and set(stored.values()) == {(0, 60 * am.MIL)}
    found = _heights_back(board, tmp_path / "back")
    assert sorted(found) == [f"M{n}" for n in range(1, 9)]
    assert all(heights == STORED for heights in found.values()), found


def test_a_moved_model_takes_the_heights_of_its_box(tmp_path: Path) -> None:
    """A model raised by 0.1 mm in KiCad is a changed model: its heights are its box's, the others keep the
    stored ones."""
    board = _to_kicad(tmp_path)
    text = board.read_text(encoding="utf-8")
    first = re.search(r'\(model\s+"[^"]*marker[^"]*"\s*\(offset\s*\(xyz\s+(\S+)\s+(\S+)\s+([^\s)]+)', text)
    assert first is not None
    raised = f"{float(first.group(3)) + 0.1:.6f}"
    text = text[: first.start(3)] + raised + text[first.end(3) :]
    board.write_text(text, encoding="utf-8")
    found = _heights_back(board, tmp_path / "back")
    moved = [ref for ref, heights in found.items() if heights != STORED]
    assert len(moved) == 1 and len(found) == 8, found


def test_carrier_reads_what_it_writes_and_drops_disagreement() -> None:
    """Turns are compared modulo a full turn; two entries of one key with other heights give neither."""
    one = models.StoredHeights("ab", (1, 2, 3), (-90 * DEG, 0, 360 * DEG), "top", 5, 9)
    other = models.StoredHeights("cd", (0, 0, 0), (0, 0, 0), "bottom", -2, 7)
    data = models.heights_text([one, other, one]).encode("utf-8")
    assert models.read_heights(data) == {one.key: (5, 9), other.key: (-2, 7)}
    assert one.key == models.height_key("ab", (1, 2, 3), (270 * DEG, 0, 0), "top")
    clash = models.StoredHeights("ab", (1, 2, 3), (270 * DEG, 0, 0), "top", 6, 9)
    assert models.read_heights(models.heights_text([one, clash, other]).encode("utf-8")) == {
        other.key: (-2, 7)
    }
    for bad in (b"", b"not json", b'{"schema": "other", "bodies": []}', b'{"schema": 1}'):
        assert models.read_heights(bad) == {}
