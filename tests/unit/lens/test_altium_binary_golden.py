# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Binary golden files of the Altium sample and the protocol page that names them (capability altium-build,
"Binary sample and Viewer check", scenario "Binary golden files"; change c0033).

``FENOLITE_GOLDEN_WRITE=1`` rewrites the two files under ``tests/data/altium/sample/binary/`` instead of
comparing them; the SHA-256 values of ``docs/evidence/altium-schematic.md`` are then updated by hand.
"""

from __future__ import annotations

import hashlib
import os
import re
from functools import cache
from pathlib import Path

import pytest
from _altium import sample
from _cfb_read import deframe, read_compound

from fenolite.backends.altium.cfb import SIGNATURE
from fenolite.dsl import to_model
from fenolite.lens.altium import build_altium

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests" / "data" / "altium" / "sample"
BINARY = GOLDEN / "binary"
PROTOCOL = ROOT / "docs" / "evidence" / "altium-schematic.md"
NAMES = ("altium_sample.PrjPcb", "altium_sample.SchDoc")
TABLE = "| binary file | SHA-256 |"
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"


@cache
def fresh() -> dict[str, bytes]:
    design = sample()
    files = build_altium(to_model(design), name=design.name, form="binary").files
    return {name: files[name] for name in NAMES}


def test_binary_golden_files() -> None:
    files = fresh()
    if WRITE:
        BINARY.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (BINARY / name).write_bytes(data)
        pytest.skip("binary golden files rewritten (FENOLITE_GOLDEN_WRITE=1)")
    for name, data in files.items():
        assert (BINARY / name).read_bytes() == data, f"binary/{name} differs from a fresh build"


def test_project_copy_equals_the_ascii_sample_project() -> None:
    project = fresh()["altium_sample.PrjPcb"]
    assert (GOLDEN / "altium_sample.PrjPcb").read_bytes() == project
    assert (BINARY / "altium_sample.PrjPcb").read_bytes() == project


def test_binary_sample_reads_back() -> None:
    data = (BINARY / "altium_sample.SchDoc").read_bytes()
    assert data.startswith(SIGNATURE)
    streams = read_compound(data)
    assert sorted(streams) == ["FileHeader", "Storage"]
    records = deframe(streams["FileHeader"])
    assert len(records) == 123
    kinds = [dict(r).get("RECORD") for r in records[1:]]
    assert kinds.count("1") == 8 and kinds.count("2") == 19 and kinds.count("17") == 13
    assert kinds.count("25") == 6


def _cells(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def test_protocol_names_the_binary_bytes() -> None:
    lines = PROTOCOL.read_text(encoding="utf-8").splitlines()
    start = lines.index(TABLE)
    digests: dict[str, str] = {}
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        path, digest = _cells(line)
        digests[path] = digest
    assert sorted(digests) == sorted(f"tests/data/altium/sample/binary/{name}" for name in NAMES)
    for path, digest in digests.items():
        assert re.fullmatch(r"[0-9a-f]{64}", digest), path
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path


def test_protocol_part_v() -> None:
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "## Part V: Altium 365 Viewer opens the binary sample" in text
    rows = {
        cells[0]: cells[-1]
        for cells in (
            _cells(line) for line in text.splitlines() if line.startswith("| V") or line.startswith("| A7")
        )
    }
    full = {"H-A-SCHBIN-VIEWER", "H-A-SCHBIN-CFB", "H-A-SCHBIN-FRAME", "H-A-SCHBIN-STORAGE"}
    for step in ("V1", "V2"):
        assert set(re.findall(r"H-A-SCHBIN-[A-Z]+", rows[step])) == full, step
    assert "data for" in rows["V3"] and "H-A-SCHBIN-VIEWER" in rows["V3"]
    assert set(re.findall(r"H-A-SCHBIN-[A-Z]+", rows["A7"])) == full - {"H-A-SCHBIN-VIEWER"} | {
        "H-A-SCHBIN-AD"
    }
    assert "A365 Viewer" in text
