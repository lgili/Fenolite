# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Golden files of the hierarchy sample (capability altium-build, "Hierarchy sample and author report";
change c0037).

A fresh ``modules`` build of ``examples/altium_hier/design.py`` in the binary form must give the eight
files committed under ``tests/data/altium/hier/`` byte for byte. ``FENOLITE_GOLDEN_WRITE=1`` rewrites the
files instead of comparing them; the SHA-256 values of Part H of ``docs/evidence/altium-schematic.md`` are
then updated by hand, and ``-k protocol`` checks them. The committed sheets are also read back with the
test reader, which shares no code with the writer.
"""

from __future__ import annotations

import hashlib
import os
import re
from functools import cache
from pathlib import Path

import pytest
from _altium import HIER_NETS, hier
from _altium_read import nets_from_project, read_sheet
from _cfb_read import read_compound

from fenolite.dsl import to_model
from fenolite.lens.altium import build_altium

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests" / "data" / "altium" / "hier"
FILES = (
    "FenoliteHier.SchLib",
    "altium_hier.PrjPcb",
    "altium_hier.SchDoc",
    "altium_hier_flash.Harness",
    "altium_hier_flash.SchDoc",
    "altium_hier_mcu.Harness",
    "altium_hier_mcu.SchDoc",
)
SHEETS = tuple(name for name in FILES if name.endswith(".SchDoc"))
PROTOCOL = ROOT / "docs" / "evidence" / "altium-schematic.md"
PART_H = "## Part H: sheets per module and harnesses in Altium Designer"
STEPS = {
    "H1": {"H-A-SCH-HIER-OPEN", "H-A-SCH-HIER-PRJ"},
    "H2": {"H-A-SCH-HARN-OPEN", "H-A-SCH-HARN-FILE"},
    "H3": {"H-A-SCH-HIER-COMPILE", "H-A-SCH-HARN-FILE"},
    "H4": {"H-A-SCH-HIER-NAMES", "H-A-SCH-HARN-NETS"},
    "H5": {"H-A-SCH-HIER-ECO"},
    "H6": {"H-A-SCH-HARN-UNUSED"},
    "H7": {"H-A-SCH-HIER-ECO", "H-A-SCH-HIER-ORDER"},
}
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"


@cache
def fresh() -> dict[str, bytes]:
    design = hier()
    output = build_altium(to_model(design), name=design.name, sheets="modules")
    assert not [i for i in output.issues if i.severity in ("warning", "error")]
    files = {name: data for name, data in output.files.items() if not name.startswith(".fenolite/")}
    assert sorted(files) == sorted(FILES)
    return files


def test_golden_files_of_the_sample() -> None:
    """Scenario "Golden files of the sample"."""
    files = fresh()
    if WRITE:
        GOLDEN.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (GOLDEN / name).write_bytes(data)
        pytest.skip("hierarchy golden files rewritten (FENOLITE_GOLDEN_WRITE=1)")
    assert sorted(p.name for p in GOLDEN.iterdir()) == sorted(FILES)
    for name, data in files.items():
        assert (GOLDEN / name).read_bytes() == data, f"hier/{name} differs from a fresh build"


def test_committed_sheets_are_compound_files_with_a_harness_stream() -> None:
    for name in SHEETS:
        data = (GOLDEN / name).read_bytes()
        assert data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")), name
        assert sorted(read_compound(data)) == ["Additional", "FileHeader", "Storage"]


def test_committed_harness_files() -> None:
    for name in FILES:
        if name.endswith(".Harness"):
            assert (GOLDEN / name).read_bytes() == b"SPI=CS,MISO,MOSI,SCK\r\n"


def test_committed_project_lists_the_sheets_and_harness_files() -> None:
    text = (GOLDEN / "altium_hier.PrjPcb").read_bytes().decode("ascii")
    paths = [line.partition("=")[2] for line in text.split("\r\n") if line.startswith("DocumentPath=")]
    assert paths == [
        "altium_hier.SchDoc",
        "altium_hier_flash.SchDoc",
        "altium_hier_mcu.SchDoc",
        "FenoliteHier.SchLib",
        "altium_hier_mcu.Harness",
        "altium_hier_flash.Harness",
    ]


def test_committed_sheets_read_back() -> None:
    sheets = {name: read_sheet((GOLDEN / name).read_bytes()) for name in SHEETS}
    assert nets_from_project(sheets, "altium_hier.SchDoc") == HIER_NETS


def _part_h() -> list[str]:
    lines = PROTOCOL.read_text(encoding="utf-8").splitlines()
    start = lines.index(PART_H)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def _cells(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def test_protocol_names_the_committed_bytes() -> None:
    digests: dict[str, str] = {}
    for line in _part_h():
        cells = _cells(line)
        if len(cells) == 2 and re.fullmatch(r"[0-9a-f]{64}", cells[1]):
            digests[cells[0]] = cells[1]
    assert set(digests) == {f"tests/data/altium/hier/{name}" for name in FILES}
    for path, digest in digests.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path


def test_protocol_steps_name_their_hypotheses() -> None:
    found: dict[str, set[str]] = {}
    for line in _part_h():
        cells = _cells(line)
        if len(cells) == 4 and re.fullmatch(r"H[1-7]", cells[0]):
            found[cells[0]] = set(re.findall(r"H-A-SCH-(?:HIER|HARN)-[A-Z]+", cells[3]))
    assert found == STEPS
    assert set().union(*STEPS.values()) == {
        "H-A-SCH-HIER-OPEN",
        "H-A-SCH-HIER-ORDER",
        "H-A-SCH-HIER-PRJ",
        "H-A-SCH-HIER-COMPILE",
        "H-A-SCH-HIER-NAMES",
        "H-A-SCH-HIER-ECO",
        "H-A-SCH-HARN-OPEN",
        "H-A-SCH-HARN-FILE",
        "H-A-SCH-HARN-NETS",
        "H-A-SCH-HARN-UNUSED",
    }


def test_protocol_net_table_equals_the_sample_nets() -> None:
    nets: dict[str, set[tuple[str, str]]] = {}
    lines = _part_h()
    start = lines.index("| net | pins as (ref, pin) |")
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        name, pins = _cells(line)
        nets[name] = {(ref, pin) for ref, pin in re.findall(r"\(([^,]+), ([^)]+)\)", pins)}
    assert nets == HIER_NETS
