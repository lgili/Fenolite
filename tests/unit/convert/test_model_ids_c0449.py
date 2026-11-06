# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Model identities of Altium model bodies through KiCad (change c0449, task 4.3; capability
design-conversion, "Models of a KiCad board in an Altium target").

Altium seems to serve a model it has opened by its ``ID``: a session that had opened one round trip of public
row ``-04`` showed that file's model names for the next, whose records held the same IDs. A model that comes
back with the source's bytes therefore keeps its record's ``ID`` and ``CHECKSUM``, and a body that also
keeps its placement its ``MODEL.CHECKSUM``. A new model gets the ``ID`` of its bytes and its name and the
stand-in checksum. The source is the authored document of ``tests/_altium_models.py``: one model record of
``ID`` ``MODEL_ID`` and ``CHECKSUM`` ``MODEL_CHECKSUM``, each of its eight bodies with its own checksum."""

from __future__ import annotations

import re
from pathlib import Path

import _altium_models as am

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.models3d import model_records
from fenolite.backends.altium.read.bodies import read_bodies
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import models

DEG = 1_000_000


def _write(result: ConversionResult, folder: Path) -> Path:
    for key, data in result.conversion.files.items():
        path = folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder


def _to_kicad(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "altium").mkdir()
    source = am.write_folder(tmp_path / "altium")
    kicad = _write(convert(source, to="kicad", allow_lossy=True, verify=False), tmp_path / "kicad")
    (board,) = kicad.glob("*.kicad_pcb")
    return source, board


def _document(folder: Path) -> Path:
    (path,) = folder.glob("*.PcbDoc")
    return path


def _ids(path: Path) -> tuple[list[dict[str, str]], dict[str, tuple[str, str]]]:
    """The ``Models`` records of the document at ``path``, and per designator the ``MODELID`` and
    ``MODEL.CHECKSUM`` of its body that names a model; the generated models of other bodies are left out."""
    document = read_pcbdoc(path.read_bytes(), file=path.name)
    records = [dict(r) for r in model_records(document.storages["Models"]["Data"])]
    names = [str(c.source_designator) for c in document.components]
    found: dict[str, tuple[str, str]] = {}
    for body in read_bodies(document.storages["ComponentBodies6"]["Data"], storage="ComponentBodies6"):
        keys = body.properties
        if keys.text("MODEL.MODELTYPE") != "1" or body.component is None:
            continue
        if (keys.text("MODEL.NAME") or "").startswith("marker"):
            found[names[body.component]] = (keys.text("MODELID"), keys.text("MODEL.CHECKSUM"))
    return records, found


def _back(board: Path, folder: Path) -> Path:
    return _document(_write(convert(board, to="altium", allow_lossy=True, verify=False), folder))


def _marker(records: list[dict[str, str]]) -> dict[str, str]:
    (record,) = [r for r in records if r.get("NAME", "").startswith("marker")]
    return record


def test_unchanged_models_keep_their_source_ids(tmp_path: Path) -> None:
    """The record of the marker model comes back with ``MODEL_ID`` and ``MODEL_CHECKSUM``, and each of the
    eight bodies with the ``MODELID`` and ``MODEL.CHECKSUM`` its source holds; the conversion to KiCad
    carries them in ``models.IDS_PROPERTY``."""
    source, board = _to_kicad(tmp_path)
    properties = boardcarrier.carried(board.read_text(encoding="utf-8"))
    carried = models.read_ids(properties.get(models.IDS_PROPERTY))
    assert set(carried.models.values()) == {(am.MODEL_ID, am.MODEL_CHECKSUM)} and len(carried.bodies) == 8
    _, before = _ids(source)
    assert len(before) == 8 and len({checksum for _, checksum in before.values()}) == 8
    records, after = _ids(_back(board, tmp_path / "back"))
    record = _marker(records)
    assert (record["ID"], record["CHECKSUM"]) == (am.MODEL_ID, am.MODEL_CHECKSUM)
    assert after == before


def test_a_moved_model_keeps_its_id_and_takes_its_record_checksum(tmp_path: Path) -> None:
    """A model raised by 0.1 mm in KiCad still holds the source's bytes: its record keeps ``MODEL_ID``; the
    moved body's ``MODEL.CHECKSUM`` is its record's, the others keep theirs."""
    source, board = _to_kicad(tmp_path)
    text = board.read_text(encoding="utf-8")
    first = re.search(r'\(model\s+"[^"]*marker[^"]*"\s*\(offset\s*\(xyz\s+(\S+)\s+(\S+)\s+([^\s)]+)', text)
    assert first is not None
    raised = f"{float(first.group(3)) + 0.1:.6f}"
    board.write_text(text[: first.start(3)] + raised + text[first.end(3) :], encoding="utf-8")
    _, before = _ids(source)
    records, after = _ids(_back(board, tmp_path / "back"))
    assert _marker(records)["ID"] == am.MODEL_ID
    moved = {ref for ref in before if after[ref] != before[ref]}
    assert len(moved) == 1 and after[moved.pop()] == (am.MODEL_ID, am.MODEL_CHECKSUM)


def test_a_new_model_gets_a_new_id(tmp_path: Path) -> None:
    """A STEP file whose bytes changed in KiCad is a new model: its record's ``ID`` is that of its bytes and
    file name, not ``MODEL_ID``, and its checksums are the stand-in."""
    _, board = _to_kicad(tmp_path)
    (step,) = [p for p in board.parent.rglob("*.step") if p.name.startswith("marker")]
    data = step.read_bytes() + b"\n"
    step.write_bytes(data)
    records, after = _ids(_back(board, tmp_path / "back"))
    record = _marker(records)
    assert record["ID"] == pcbrecords.model_id(data, record["NAME"]) != am.MODEL_ID
    assert record["CHECKSUM"] == pcbrecords.BODY_CHECKSUM
    assert set(after.values()) == {(record["ID"], pcbrecords.BODY_CHECKSUM)} and len(after) == 8


def test_carrier_reads_what_it_writes_and_drops_disagreement() -> None:
    """Turns are compared modulo a full turn; a model or a body whose entries disagree gives nothing, and an
    ``ID`` that is no GUID or a checksum that is no 32-bit decimal is left out."""
    guid, other = am.MODEL_ID, "{0C423000-0000-4000-8000-000000000002}"
    one = models.StoredIds("ab", (1, 2, 3), (-90 * DEG, 0, 360 * DEG), "top", guid, "-5", "7")
    two = models.StoredIds("cd", (0, 0, 0), (0, 0, 0), "bottom", other, "0", "")
    read = models.read_ids(models.ids_text([one, two, one]).encode("utf-8"))
    assert dict(read.models) == {"ab": (guid, "-5"), "cd": (other, "0")}
    assert dict(read.bodies) == {models.height_key("ab", (1, 2, 3), (270 * DEG, 0, 0), "top"): "7"}
    clash = models.StoredIds("ab", (1, 2, 3), (270 * DEG, 0, 0), "top", other, "-5", "8")
    read = models.read_ids(models.ids_text([one, clash, two]).encode("utf-8"))
    assert dict(read.models) == {"cd": (other, "0")} and not read.bodies
    bad = models.StoredIds("ef", (0, 0, 0), (0, 0, 0), "top", "not-a-guid", "1", "2")
    worse = models.StoredIds("gh", (0, 0, 0), (0, 0, 0), "top", guid, "4294967296", "-2147483649")
    read = models.read_ids(models.ids_text([bad, worse]).encode("utf-8"))
    kept = models.height_key("ef", (0, 0, 0), (0, 0, 0), "top")
    assert not read.models and dict(read.bodies) == {kept: "2"}
    for data in (b"", b"not json", b'{"schema": "other", "models": []}', b'{"schema": 1}'):
        assert models.read_ids(data) == models.CarriedIds()
