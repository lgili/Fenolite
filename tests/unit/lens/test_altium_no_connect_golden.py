# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Golden files of the no-connect example and the protocol part that names them (capability altium-build,
"No-connect sample and author report", scenario "Golden files of the example"; change c0036).

A fresh build of ``examples/altium_kicad/no_connect.py`` must give the project file, the schematic library
and the binary schematic under ``tests/data/altium/no_connect/`` and the ASCII schematic under its
``ascii/`` folder, byte for byte. ``FENOLITE_GOLDEN_WRITE=1`` rewrites the four files instead of comparing
them; the SHA-256 values of Part N of ``docs/evidence/altium-schematic.md`` are then updated by hand, and
``-k protocol`` checks them.
"""

from __future__ import annotations

import hashlib
import os
import re
from functools import cache
from pathlib import Path

import pytest
from _altium import NO_CONNECT_MARKS, NO_CONNECT_NETS, no_connect_files
from _altium_read import nets_from_sheet, read_no_connects, read_records
from _cfb_read import deframe, read_compound

from fenolite.backends.altium.cfb import SIGNATURE

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests" / "data" / "altium" / "no_connect"
NAME = "altium_no_connect"
BINARY_FILES = (f"{NAME}.PrjPcb", f"{NAME}.SchDoc", f"{NAME}.SchLib")
ASCII_FILE = f"ascii/{NAME}.SchDoc"
PROTOCOL = ROOT / "docs" / "evidence" / "altium-schematic.md"
PART_N = "## Part N: no-connect directives in Altium Designer"
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"


@cache
def fresh() -> dict[str, bytes]:
    """Golden path under ``GOLDEN`` → the bytes of a fresh build."""
    binary, ascii_form = no_connect_files("binary"), no_connect_files("ascii")
    for name in (f"{NAME}.PrjPcb", f"{NAME}.SchLib"):
        assert binary[name] == ascii_form[name], f"{name} does not depend on the schematic form"
    return {**{name: binary[name] for name in BINARY_FILES}, ASCII_FILE: ascii_form[f"{NAME}.SchDoc"]}


def test_no_connect_golden_files() -> None:
    files = fresh()
    if WRITE:
        for name, data in files.items():
            (GOLDEN / name).parent.mkdir(parents=True, exist_ok=True)
            (GOLDEN / name).write_bytes(data)
        pytest.skip("no-connect golden files rewritten (FENOLITE_GOLDEN_WRITE=1)")
    assert sorted(p.relative_to(GOLDEN).as_posix() for p in GOLDEN.rglob("*") if p.is_file()) == sorted(files)
    for name, data in files.items():
        assert (GOLDEN / name).read_bytes() == data, f"no_connect/{name} differs from a fresh build"


def _named(nets: dict[str, set[tuple[str, str]]]) -> dict[str, set[tuple[str, str]]]:
    return {name: pins for name, pins in nets.items() if not name.startswith("<unnamed ")}


def test_committed_no_connect_files_read_back() -> None:
    binary = (GOLDEN / f"{NAME}.SchDoc").read_bytes()
    assert binary.startswith(SIGNATURE)
    from_binary = [dict(r) for r in deframe(read_compound(binary)["FileHeader"])[1:]]
    from_ascii = read_records((GOLDEN / ASCII_FILE).read_bytes())
    assert from_binary == from_ascii
    for found in (from_binary, from_ascii):
        assert read_no_connects(found) == NO_CONNECT_MARKS
        assert _named(nets_from_sheet(found)) == NO_CONNECT_NETS
    project = (GOLDEN / f"{NAME}.PrjPcb").read_bytes()
    assert b"DocumentPath=altium_no_connect.SchDoc" in project
    assert b"DocumentPath=altium_no_connect.SchLib" in project


def _part_n() -> list[str]:
    lines = PROTOCOL.read_text(encoding="utf-8").splitlines()
    start = lines.index(PART_N)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def _cells(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def test_protocol_names_the_no_connect_bytes() -> None:
    digests: dict[str, str] = {}
    for line in _part_n():
        cells = _cells(line)
        if len(cells) == 2 and re.fullmatch(r"[0-9a-f]{64}", cells[1]):
            digests[cells[0]] = cells[1]
    assert set(digests) == {f"tests/data/altium/no_connect/{name}" for name in fresh()}
    for path, digest in digests.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path


def test_protocol_steps_name_their_hypotheses() -> None:
    steps = {cells[0]: cells[-1] for line in _part_n() if len(cells := _cells(line)) == 4}
    assert {"N1", "N2", "N3", "N4"} <= set(steps)
    assert "H-A-SCH-NC-RECORD" in steps["N1"] and "H-A-SCH-NC-ERC" in steps["N2"]
    assert "H-A-SCH-NC-RECORD" in steps["N3"] and "H-A-SCH-NC-ERC" in steps["N3"]
    assert "H-A-SCH-NC-VIEWER" in steps["N4"]
