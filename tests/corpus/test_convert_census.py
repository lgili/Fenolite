# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad 10.0.6 demo boards converted to Altium and read back (change c0159, ``H-G-CONV-LEDGER``;
capability design-conversion, scenario "Demo boards are explained").

The ledger (task 4.2): each board is converted with ``fenolite.api.convert(board, to="altium",
allow_lossy=True)``. No board may give ``convert.unexplained``, and the report's rows per kind and reason
and the explained differences per kind must equal the two tables of ``docs/evidence/conversion.md``.

The measurement of the design (task 1.2): each board of the corpus is read with the KiCad backend (the
corpus holds the boards without their project files), written as an Altium project with
``lens.altium.write_model(design, allow_lossy=True)``, and its PCB document read back with the Altium
backend and compared with the board through ``compare_designs`` at the highest level both hold, in the
relative frame, within 10 nm and 20 ppm (the measurement of the design, "Context"). The test records, per
board, the items the write leaves out per kind and the differences per kind, and the largest
per-coordinate difference of a placement, a pad position, a pad size or a drill without tolerance, which
sets ``tolerance_nm`` of the conversion profile. Since task 2.1 the write also counts the components not
fitted under ``dnp``.
"""

from __future__ import annotations

import io
import json
import re
import tempfile
from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from _corpus import manifest_items, require

from fenolite.api import convert
from fenolite.backends import registry
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.equivalence import EquivalenceReport, Tolerances, compare_designs, max_level
from fenolite.cli.main import main
from fenolite.lens.altium import write_model
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus
PREFIX = "kicad-demo-10-0-6-pcb-"
LARGE = ("06", "18")
"""The boards whose PCB document needs DIFAT sectors (more than 109 FAT sectors): refused before change c0160
(119 and 180 FAT sectors without bodies, 181 for ``vme-wren`` with them), written since."""
NOT_WRITTEN: dict[str, dict[str, int]] = {
    "01": {
        "dnp": 2, "footprint-graphic": 3, "outline": 1, "pad": 11, "pin-net": 2, "stackup": 1, "text": 149,
        "zone-fill": 13,
    },
    "02": {"stackup": 1, "text": 2, "zone-fill": 1},
    "03": {"stackup": 1, "zone-fill": 1},
    "04": {"stackup": 1, "zone-fill": 1},
    "05": {"dimension": 2, "stackup": 1, "zone-fill": 1},
    "06": {
        "dimension": 24, "dnp": 113, "footprint-graphic": 303116, "footprint-text": 16, "keep-out": 2,
        "net-tie": 6, "pad": 73, "pin-net": 12, "stackup": 1, "text": 102, "zone-fill": 97,
    },
    "07": {"stackup": 1, "text": 1, "zone-fill": 3},
    "08": {"footprint-copper": 4},
    "09": {"keep-out": 4, "text": 2, "zone-fill": 1},
    "10": {"keep-out": 4, "text": 2, "zone-fill": 2},
    "11": {
        "copper-shape": 2, "dnp": 11, "footprint-copper": 3, "footprint-graphic": 1, "net-tie": 2,
        "outline": 20, "pad": 12, "stackup": 1, "text": 25, "zone-fill": 34,
    },
    "12": {"pad": 2, "stackup": 1, "zone-fill": 1},
    "13": {
        "dnp": 22, "footprint-copper": 1, "net-tie": 1, "outline": 4, "pad": 48, "stackup": 1, "text": 1,
        "zone": 2, "zone-fill": 2,
    },
    "14": {"copper-shape": 4, "footprint-graphic": 5, "outline": 1},
    "15": {"dimension": 1, "stackup": 1, "zone-fill": 1},
    "16": {
        "dimension": 6, "dnp": 11, "footprint-copper": 25, "footprint-graphic": 15, "graphic": 2,
        "net-tie": 9, "outline": 1, "pad": 20, "stackup": 1, "text": 224, "zone-fill": 2,
    },
    "17": {"dimension": 2, "stackup": 1, "zone-fill": 2},
    "18": {
        "dimension": 2, "dnp": 3, "footprint-copper": 26, "graphic": 7, "keep-out": 2, "outline": 1,
        "pad": 2, "stackup": 1, "text": 513, "track": 5, "zone-fill": 122,
    },
}  # fmt: skip
"""Per board, the model items ``write_model`` leaves out, per kind (measured again on 2026-10-09 with change
c0160; every board is written since the compound writer writes DIFAT sectors)."""
DIFFERENCES: dict[str, tuple[int, dict[str, int]]] = {
    "01": (5, {"dnp": 2, "pad-kind": 2, "pad-missing": 6}),
    "02": (5, {}),
    "03": (5, {}),
    "04": (5, {}),
    "05": (5, {"pad-kind": 62}),
    "06": (5, {"dnp": 113, "pad-kind": 20, "pad-missing": 33, "pin-missing": 19, "ref-ambiguous": 1}),
    "07": (5, {}),
    "08": (4, {"ref-ambiguous": 1}),
    "09": (5, {}),
    "10": (5, {}),
    "11": (5, {"dnp": 11, "pad-missing": 12, "pin-missing": 12, "ref-ambiguous": 1}),
    "12": (5, {"pad-missing": 2, "pin-missing": 2}),
    "13": (5, {"dnp": 22, "pad-kind": 6, "pad-missing": 22, "pin-missing": 18, "route-connectivity": 2}),
    "14": (5, {}),
    "15": (5, {}),
    "16": (5, {"dnp": 11, "pad-missing": 17, "ref-ambiguous": 4, "route-connectivity": 1}),
    "17": (5, {"pad-kind": 120}),
    "18": (5, {"dnp": 3, "pad-missing": 2, "pin-missing": 2}),
}
"""Per board, the level compared and the differences per kind, within 10 nm and 20 ppm (2026-10-09, with
change c0160)."""
LARGEST_NM = 3
"""The largest per-coordinate difference without tolerance over every written board (2026-10-09; 3 nm since
change c0160 writes the two large boards): the written unit is 2.54 nm and the reader rounds it to the
nanometre, within the 3 nm of the profile ``kicad-to-altium``."""
LEDGER = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "conversion.md"
ITEMS = {item.id.removeprefix(PREFIX): item for item in manifest_items("rt0") if item.id.startswith(PREFIX)}
_NUMBER = re.compile(r"-?\d+")


@cache
def _sides(key: str) -> tuple[Design, Design]:
    path = require(ITEMS[key])
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    written = write_model(design, allow_lossy=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, data in written.files.items():
            (Path(tmp) / name).write_bytes(data)
        document = next(Path(tmp) / name for name in written.files if name.lower().endswith(".pcbdoc"))
        backend = registry.for_path(document)
        assert backend is not None
        back = backend.read(document).content
    assert isinstance(back, Design)
    return design, back


@cache
def _not_written(key: str) -> dict[str, int]:
    path = require(ITEMS[key])
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    return dict(sorted(write_model(design, allow_lossy=True).inputs.counts().items()))


def _largest(report: EquivalenceReport) -> int:
    """The largest per-coordinate difference of a placement (after the frame's translation), a pad
    position, a pad size or a drill."""
    largest = 0
    shift = report.translation
    for difference in report.differences:
        a = [int(value) for value in _NUMBER.findall(difference.a)]
        b = [int(value) for value in _NUMBER.findall(difference.b)]
        if difference.kind == "position" and len(a) == len(b) == 2:
            b = [b[0] - shift.x, b[1] - shift.y]
        elif difference.kind not in ("pad-position", "pad-size", "pad-drill") or len(a) != len(b):
            continue
        largest = max(largest, *(abs(x - y) for x, y in zip(a, b, strict=True)))
    return largest


@pytest.mark.parametrize("key", LARGE)
def test_large_boards_hold_difat_sectors(key: str) -> None:
    """Change c0160: the documents that need more than 109 FAT sectors are written with DIFAT sectors."""
    path = require(ITEMS[key])
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    written = write_model(design, allow_lossy=True)
    document = next(data for name, data in written.files.items() if name.endswith(".PcbDoc"))
    fat, difat = int.from_bytes(document[0x2C:0x30], "little"), int.from_bytes(document[0x48:0x4C], "little")
    print(f"{path.stem}: {fat} FAT sectors, {difat} DIFAT sector(s)")
    assert fat > 109 and difat >= 1


@pytest.mark.parametrize("key", sorted(NOT_WRITTEN))
def test_not_written_per_kind(key: str) -> None:
    found = _not_written(key)
    print(f"{ITEMS[key].path.stem}: {found}")
    assert found == NOT_WRITTEN[key]


@pytest.mark.parametrize("key", sorted(DIFFERENCES))
def test_differences_per_kind(key: str) -> None:
    a, b = _sides(key)
    level = max_level(a, b)
    report = compare_designs(a, b, level=level, tolerances=Tolerances(10, 0, 20), frame="relative")
    found = dict(sorted(Counter(d.kind for d in report.differences).items()))
    exact = compare_designs(a, b, level=min(level, 4), frame="relative")
    print(f"{ITEMS[key].path.stem}: level {level}, {found}, largest {_largest(exact)} nm")
    assert (level, found) == DIFFERENCES[key]
    assert _largest(exact) <= LARGEST_NM


def _table(marker: str) -> list[tuple[str, ...]]:
    """The rows of the table between ``<!-- marker:begin -->`` and its end in the ledger, the header left
    out, each cell stripped, an escaped bar read as a bar."""
    text = LEDGER.read_text(encoding="utf-8")
    body = text.split(f"<!-- {marker}:begin -->", 1)[1].split("<!-- ", 1)[0]
    rows: list[tuple[str, ...]] = []
    for line in body.strip().splitlines()[2:]:
        cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
        rows.append(tuple(cell.strip().replace("\\|", "|") for cell in cells))
    return rows


@pytest.mark.parametrize("key", sorted(DIFFERENCES))
def test_conversion_is_explained(key: str) -> None:
    """Scenario "Demo boards are explained": no ``convert.unexplained``, and the report and the explained
    differences of the board are the ledger's."""
    path = require(ITEMS[key])
    result = convert(path, to="altium", allow_lossy=True)
    assert result.unexplained == ()
    assert not [i for i in result.issues if i.code == "convert.unexplained"]
    board = path.stem
    rows = [
        (board, row.kind, reason.outcome, str(reason.count), reason.reason)
        for row in result.conversion.report.rows
        for reason in row.reasons
    ]
    assert rows == [row for row in _table("ledger") if row[0] == board]
    explained = Counter((e.difference.kind, e.kind) for e in result.explained)
    found = [(board, kind, by, str(n)) for (kind, by), n in sorted(explained.items())]
    assert found == [row for row in _table("explained") if row[0] == board]


def test_exit_7_without_consent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Exit 7 without consent": ``RoyalBlue54L-Feather`` loses pads and fitted flags; without
    ``--allow-lossy`` the command exits 7 naming both kinds, with it the plan comes with one
    ``convert.lossy`` warning per kind."""
    board = require(ITEMS["13"])
    monkeypatch.chdir(tmp_path)
    argv = ["convert", str(board), "--to", "altium", "--out", "out", "--dry-run", "--json"]
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    assert main(argv) == 7
    assert json.loads(err.getvalue())["code"] == "FEN-7001"
    refused = {issue["where"] for issue in json.loads(out.getvalue())["issues"]}
    assert {"pad", "dnp"} <= refused
    out.truncate(0)
    out.seek(0)
    assert main(["--allow-lossy", *argv]) == 0
    envelope = json.loads(out.getvalue())
    lossy = {i["where"] for i in envelope["issues"] if i["code"] == "convert.lossy"}
    assert lossy == refused and envelope["result"]["plan"]


SCHEMATIC_ROWS = {"complex_hierarchy": ("02", ("kicad-demo-10-0-6-sch-01", "kicad-demo-10-0-6-sch-010"))}
"""The demo projects whose schematic tree the corpus holds beside the board (change c0160): name →
(board key, schematic rows, root first)."""


@pytest.mark.needs_kicad
@pytest.mark.parametrize("name", sorted(SCHEMATIC_ROWS))
def test_converted_schematic(name: str, tmp_path: Path) -> None:
    """Scenario "Netlist kept" (change c0160, ``H-A-CONV-SCHEMATIC``): the project folder (the board and its
    sheets) is converted; the written project holds one schematic document per KiCad sheet, and its circuit
    read by Fenolite equals the KiCad schematic's at levels 1 and 2. The KiCad side's netlist is exported
    by ``kicad-cli`` (the tree is outside the grammar of Fenolite's own netlist)."""
    import dataclasses
    import shutil

    from fenolite.api import equivalent
    from fenolite.backends.kicad import parity_inputs
    from fenolite.convert import convert_project
    from fenolite.convert.schematic import sheet_paths

    key, rows = SCHEMATIC_ROWS[name]
    sheets = {item.id: item for item in manifest_items("sch")}
    folder = tmp_path / name
    folder.mkdir()
    shutil.copyfile(require(ITEMS[key]), folder / f"{name}.kicad_pcb")
    for row in rows:
        source = require(sheets[row])
        shutil.copyfile(source, folder / source.name)
    root = folder / f"{name}.kicad_sch"
    conversion = convert_project(folder / f"{name}.kicad_pcb", to="altium", allow_lossy=True)
    tree = sheet_paths(parity_inputs.read_sheets(root), root.name, name)
    documents = sorted(file for file in conversion.files if file.endswith(".SchDoc"))
    print(f"{name}: {len(tree)} KiCad sheets, {documents}")
    assert len(documents) == len(tree) == 3
    out = tmp_path / "out"
    out.mkdir()
    for file, data in conversion.files.items():
        (out / file).write_bytes(data)
    backend = registry.for_path(out / f"{name}.PrjPcb")
    assert backend is not None
    design = backend.read(out / f"{name}.PrjPcb").content
    assert isinstance(design, Design)
    result = equivalent(dataclasses.replace(design, board=None), root)
    print(f"{name}: levels {[(lv.level, lv.compared) for lv in result.report.levels]}")
    assert [level.level for level in result.report.levels] == [1, 2]
    assert result.report.differences == ()
