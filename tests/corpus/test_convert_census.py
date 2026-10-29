# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad 10.0.6 demo boards converted to Altium and read back (change c0159, ``H-G-CONV-LEDGER``;
capability design-conversion, scenario "Demo boards are explained").

The ledger (task 4.2): each board is converted with ``fenolite.api.convert(board, to="altium",
allow_lossy=True, pour="outline")``. No board may give ``convert.unexplained``, and the report's rows per
kind and reason and the explained differences per kind must equal the two tables of
``docs/evidence/conversion.md``.

The measurement of the design (task 1.2): each board of the corpus is read with the KiCad backend (the
corpus holds the boards without their project files), written as an Altium project with
``lens.altium.write_model(design, allow_lossy=True, pour="outline")``, and its PCB document read back with
the Altium backend and compared with the board through ``compare_designs`` at the highest level both
hold, in the relative frame, within 10 nm and 20 ppm (the measurement of the design, "Context").
The test records, per board, items left out per kind, differences per kind, and the largest
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
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.equivalence import EquivalenceReport, Tolerances, compare_designs, max_level
from fenolite.cli.main import main
from fenolite.lens.altium import write_model
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus
PREFIX = "kicad-demo-10-0-6-pcb-"
TOO_LARGE = {"06": 119, "18": 180}
"""The boards the write refuses (``CompoundTooLarge``), with the FAT sectors their document needs."""
CONVERT_TOO_LARGE = {"06": 119, "18": 181}
"""The same boards converted: ``convert`` writes the extruded bodies by default, and ``vme-wren`` then
needs one sector more."""
NOT_WRITTEN: dict[str, dict[str, int]] = {
    "01": {
        "dnp": 2,
        "footprint-graphic": 3,
        "outline": 1,
        "pad": 2,
        "pin-net": 2,
        "stackup": 1,
        "text": 149,
        "zone-fill": 13,
    },
    "02": {"stackup": 1, "text": 2, "zone-fill": 1},
    "03": {"stackup": 1, "zone-fill": 1},
    "04": {"stackup": 1, "zone-fill": 1},
    "05": {"dimension": 2, "stackup": 1, "zone-fill": 1},
    "07": {"stackup": 1, "text": 1, "zone-fill": 3},
    "08": {"footprint-copper": 4},
    "09": {"keep-out": 4, "text": 2, "zone-fill": 1},
    "10": {"keep-out": 4, "text": 2, "zone-fill": 2},
    "11": {
        "copper-shape": 2,
        "dnp": 11,
        "footprint-copper": 3,
        "footprint-graphic": 1,
        "net-tie": 2,
        "outline": 20,
        "pad": 12,
        "stackup": 1,
        "text": 25,
        "zone-fill": 34,
    },
    "12": {"pad": 2, "stackup": 1, "zone-fill": 1},
    "13": {
        "dnp": 22,
        "footprint-copper": 1,
        "net-tie": 1,
        "outline": 4,
        "pad": 48,
        "stackup": 1,
        "text": 1,
        "zone": 2,
        "zone-fill": 2,
    },
    "14": {"copper-shape": 4, "footprint-graphic": 5, "outline": 1},
    "15": {"dimension": 1, "stackup": 1, "zone-fill": 1},
    "16": {
        "dimension": 6,
        "dnp": 11,
        "footprint-copper": 25,
        "footprint-graphic": 15,
        "graphic": 2,
        "net-tie": 9,
        "outline": 1,
        "pad": 20,
        "stackup": 1,
        "text": 224,
        "zone-fill": 2,
    },
    "17": {"dimension": 2, "stackup": 1, "zone-fill": 2},
}
"""Per-board refused items, measured after c0160 on 2026-10-12 (16 light boards)."""
DIFFERENCES: dict[str, tuple[int, dict[str, int]]] = {
    "01": (5, {"dnp": 2, "pad-kind": 2, "pad-missing": 8}),
    "02": (5, {}),
    "03": (5, {}),
    "04": (5, {"pad-missing": 1}),
    "05": (5, {"pad-kind": 62}),
    "07": (5, {"pad-missing": 2}),
    "08": (4, {"ref-ambiguous": 1}),
    "09": (5, {}),
    "10": (5, {}),
    "11": (5, {"dnp": 11, "pad-missing": 15, "pin-missing": 12}),
    "12": (5, {"pad-missing": 10, "pin-missing": 2}),
    "13": (5, {"dnp": 22, "pad-kind": 6, "pad-missing": 28, "pin-missing": 18, "route-connectivity": 2}),
    "14": (5, {}),
    "15": (5, {}),
    "16": (5, {"dnp": 11, "pad-missing": 20, "ref-ambiguous": 4, "route-connectivity": 1}),
    "17": (5, {"pad-kind": 120, "pad-missing": 8}),
}
"""Per-board comparison after c0160, within 10 nm and 20 ppm (2026-10-12)."""
LARGEST_NM = 2
"""The largest per-coordinate difference without tolerance over every written board (2026-10-09): the
written unit is 2.54 nm and the reader rounds it to the nanometre."""
LEDGER = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "conversion.md"
ITEMS = {item.id.removeprefix(PREFIX): item for item in manifest_items("rt0") if item.id.startswith(PREFIX)}
_NUMBER = re.compile(r"-?\d+")


@cache
def _sides(key: str) -> tuple[Design, Design]:
    path = require(ITEMS[key])
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    written = write_model(design, allow_lossy=True, pour="outline")
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
    return dict(sorted(write_model(design, allow_lossy=True, pour="outline").inputs.counts().items()))


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


@pytest.mark.parametrize("key", sorted(TOO_LARGE))
def test_difat_boards(key: str) -> None:
    path = require(ITEMS[key])
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    written = write_model(design, allow_lossy=True, pour="outline")
    document = next(data for name, data in written.files.items() if name.endswith(".PcbDoc"))
    assert open_compound(document).header.difat_sectors > 0


@pytest.mark.parametrize("key", sorted(NOT_WRITTEN))
def test_not_written_per_kind(key: str) -> None:
    found = _not_written(key)
    print(f"{ITEMS[key].path.stem}: {found}")
    assert found == NOT_WRITTEN[key]


@pytest.mark.parametrize("key", sorted(DIFFERENCES))
def test_differences_per_kind(key: str) -> None:
    a, b = _sides(key)
    level = max_level(a, b)
    # A free pad reads back as a component with no designator (a board-only footprint), not a component:
    # level 1 ignores the empty reference (change c0160).
    report = compare_designs(
        a, b, level=level, tolerances=Tolerances(10, 0, 20), frame="relative", ignore_refs=("",)
    )
    found = dict(sorted(Counter(d.kind for d in report.differences).items()))
    exact = compare_designs(a, b, level=min(level, 4), frame="relative", ignore_refs=("",))
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
    result = convert(path, to="altium", allow_lossy=True, pour="outline")
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


@pytest.mark.parametrize("key", sorted(CONVERT_TOO_LARGE))
def test_difat_boards_are_converted(key: str) -> None:
    result = convert(require(ITEMS[key]), to="altium", allow_lossy=True, pour="outline")
    assert result.unexplained == ()
    assert any(name.endswith(".PcbLib") for name in result.conversion.files)


def test_exit_7_without_consent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Exit 7 without consent": ``RoyalBlue54L-Feather`` loses pads and fitted flags; without
    ``--allow-lossy`` the command exits 7 naming both kinds, with it the plan comes with one
    ``convert.lossy`` warning per kind."""
    board = require(ITEMS["13"])
    monkeypatch.chdir(tmp_path)
    argv = [
        "convert",
        str(board),
        "--to",
        "altium",
        "--altium-pour",
        "outline",
        "--out",
        "out",
        "--dry-run",
        "--json",
    ]
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


@pytest.mark.needs_kicad  # the netlist of this schematic is outside Fenolite's own grammar
def test_complex_hierarchy_schematic(tmp_path: Path) -> None:
    """c0160 task 4.1: the public KiCad project keeps its schematic netlist and every sheet."""
    from _schprojects import project_folder, roots

    from fenolite.backends.kicad.sch import sheet_files

    row = next(r for r in roots(10) if Path(r.path).stem == "complex_hierarchy")
    if not row.file.is_file():
        pytest.skip("public project is absent from corpus cache")
    folder = project_folder(tmp_path, row, 10)
    assert folder is not None
    result = convert(folder / "complex_hierarchy.kicad_pro", to="altium", allow_lossy=True, pour="outline")
    assert result.unexplained == (), result.unexplained
    assert not [i for i in result.issues if i.code == "convert.schematic-unverified"], result.issues
    tree = sheet_files(folder / "complex_hierarchy.kicad_sch")
    assert len([f for f in result.conversion.files if f.endswith(".SchDoc")]) == 1 + sum(
        tree.references.values()
    )
