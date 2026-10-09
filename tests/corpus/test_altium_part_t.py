# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of Part T of the author report (``docs/evidence/altium-pcb.md``, "Part T: converted
projects"; change c0160, task 5.2; ``H-A-CONV-DIFAT``, ``H-A-CONV-PADSTACK``, ``H-A-CONV-LIBRARY``,
``H-A-CONV-SCHEMATIC``).

``part_t(folder)`` writes three converted projects and a ``README.md`` with the SHA-256 of every file:

- ``T-difat/``: the KiCad 10.0.6 demo board ``vme-wren`` (corpus, heavy) converted to Altium, whose PCB
  document needs DIFAT sectors;
- ``T-pads/``: the committed blink sample with a stacked pad (1.6 mm round on top, 2.0 mm on the bottom,
  stack mode 1) and a slotted pad on ``D1``, a connector pad on ``R1`` and a pad without a number on
  ``U1``, written as a conversion writes it (``lower.write_design(..., library=True)``);
- ``T-schematic/``: the demo project ``complex_hierarchy`` (board and its three sheets) converted, with its
  derived ``.PcbLib`` and one schematic document per KiCad sheet.

With ``FENOLITE_ALTIUM_PART_T=<folder outside the repository>`` the files are written there for the
maintainer's Altium session; without it the test writes them under its own folder. No file that Altium
wrote is in the repository.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import shutil
from pathlib import Path

import pytest
from _corpus import heavy_enabled, manifest_items, require

from fenolite.backends.altium import lower
from fenolite.convert import convert_project
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus
ROOT = Path(__file__).resolve().parents[2]
HANDOVER = os.environ.get("FENOLITE_ALTIUM_PART_T")
PREFIX = "kicad-demo-10-0-6-pcb-"
BOARDS = {item.id.removeprefix(PREFIX): item for item in manifest_items("rt0") if item.id.startswith(PREFIX)}
SHEETS = {item.id: item for item in manifest_items("sch")}
SCHEMATIC_ROWS = ("kicad-demo-10-0-6-sch-01", "kicad-demo-10-0-6-sch-010")


def _pads_design() -> Design:
    import sys

    sys.path.insert(0, str(ROOT / "tests" / "kicad"))
    import _convcases

    design = _convcases.padstack_design()
    board = design.board
    assert board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    footprints = []
    for fp in board.footprints:
        ref = refs.get(fp.component_id)
        pads = list(fp.pads)
        if ref == "R1":
            pads[0] = dataclasses.replace(pads[0], kind="connect", layers=("F.Cu",))
        elif ref == "U1":
            pads[0] = dataclasses.replace(pads[0], number="")
        footprints.append(dataclasses.replace(fp, pads=tuple(pads)))
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=tuple(footprints)))


def _write(files: dict[str, bytes], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(files.items()):
        (folder / name).write_bytes(data)


def part_t(folder: Path) -> list[tuple[str, str, int]]:
    """Write the three projects into ``folder`` and return ``(path, sha256, bytes)`` of every file."""
    if folder.exists():
        shutil.rmtree(folder)
    big = convert_project(require(BOARDS["18"]), to="altium", allow_lossy=True)
    _write(dict(big.files), folder / "T-difat")
    written = lower.write_design(_pads_design(), allow_lossy=True, library=True)
    _write(dict(written.files), folder / "T-pads")
    source = folder / "_source" / "complex_hierarchy"
    source.mkdir(parents=True)
    shutil.copyfile(require(BOARDS["02"]), source / "complex_hierarchy.kicad_pcb")
    for row in SCHEMATIC_ROWS:
        found = require(SHEETS[row])
        shutil.copyfile(found, source / found.name)
    converted = convert_project(source / "complex_hierarchy.kicad_pcb", to="altium", allow_lossy=True)
    _write(dict(converted.files), folder / "T-schematic")
    shutil.rmtree(folder / "_source")
    rows: list[tuple[str, str, int]] = []
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        data = path.read_bytes()
        rows.append((path.relative_to(folder).as_posix(), hashlib.sha256(data).hexdigest(), len(data)))
    lines = [
        "# Part T: converted projects (change c0160)",
        "",
        "Open each project in Altium Designer and follow the steps T1 to T6 of",
        '`docs/evidence/altium-pcb.md`, "Part T: converted projects". Report one generic outcome per step,',
        "the tool as `AD <major>.<minor>` and the date. Nothing that Altium writes goes back into the",
        "repository.",
        "",
        "| file | SHA-256 | bytes |",
        "|---|---|---|",
        *(f"| `{name}` | `{digest}` | {size} |" for name, digest, size in rows),
        "",
    ]
    (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return rows


def test_part_t(tmp_path: Path) -> None:
    """The three projects are written, the large document holds DIFAT sectors, the pads project holds its
    library, and the schematic project one document per KiCad sheet."""
    if not heavy_enabled():
        pytest.skip("T-difat converts the heavy board vme-wren: set FENOLITE_HEAVY=1")
    folder = Path(HANDOVER).expanduser() if HANDOVER else tmp_path / "T-convert"
    if HANDOVER and ROOT in folder.resolve().parents:
        pytest.fail("FENOLITE_ALTIUM_PART_T must name a folder outside the repository")
    rows = part_t(folder)
    names = {name for name, _digest, _size in rows}
    assert {"T-difat/vme-wren.PcbDoc", "T-difat/vme-wren.PcbLib", "T-pads/blink.PcbLib"} <= names
    document = (folder / "T-difat" / "vme-wren.PcbDoc").read_bytes()
    assert int.from_bytes(document[0x48:0x4C], "little") >= 1
    sheets = sorted(name for name in names if name.startswith("T-schematic/") and name.endswith(".SchDoc"))
    assert len(sheets) == 3
    for name, digest, size in rows:
        print(f"{name} {digest} {size}")
