# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Golden PCB files (capability altium-build, "PCB samples" and "PCB author reports"; change c0035).

A fresh Altium build of ``examples/blink_2layer/design.py`` (binary schematic, the example's own library
tables, its placements) must give the files under ``tests/data/altium/blink/`` byte for byte.
``FENOLITE_GOLDEN_WRITE=1`` rewrites them instead; the SHA-256 values of ``docs/evidence/altium-pcb.md``
are then updated by hand, and ``-k protocol`` checks them.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from functools import cache
from pathlib import Path

import pytest
from _altium import blink, blink_resolver
from _altium_pcb_read import PadRecord, read_pcblib

from fenolite.dsl import placements, to_model
from fenolite.lens.altium import build_altium

ROOT = Path(__file__).resolve().parents[2].parent
BLINK_DIR = ROOT / "tests" / "data" / "altium" / "blink"
SAMPLE_DIR = ROOT / "tests" / "data" / "altium" / "sample"
PROTOCOL = ROOT / "docs" / "evidence" / "altium-pcb.md"
FILES = ("blink.PcbLib", "blink.PrjPcb", "blink.SchDoc", "blink.SchLib")
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"


@cache
def blink_files() -> dict[str, bytes]:
    design = blink()
    with tempfile.TemporaryDirectory() as folder:
        output = build_altium(
            to_model(design),
            name=design.name,
            placed=tuple(placements(design)),
            resolver=blink_resolver(Path(folder)),
        )
    return {name: data for name, data in output.files.items() if not name.startswith(".fenolite/")}


def test_golden_pcb_files() -> None:
    """Scenario "Golden PCB files"."""
    files = blink_files()
    assert set(FILES) <= set(files)
    if WRITE:
        BLINK_DIR.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            (BLINK_DIR / name).write_bytes(files[name])
        pytest.skip("blink golden files rewritten (FENOLITE_GOLDEN_WRITE=1)")
    for name in FILES:
        assert (BLINK_DIR / name).read_bytes() == files[name], f"{name} differs from a fresh build"


def test_sample_files_keep_their_bytes() -> None:
    """The c0032 sample links only Altium footprint libraries: no committed file changes."""
    from _altium import sample

    design = sample()
    ascii_files = build_altium(to_model(design), name=design.name, form="ascii").files
    binary_files = build_altium(to_model(design), name=design.name).files
    assert (SAMPLE_DIR / "altium_sample.SchDoc").read_bytes() == ascii_files["altium_sample.SchDoc"]
    assert (SAMPLE_DIR / "binary" / "altium_sample.SchDoc").read_bytes() == binary_files[
        "altium_sample.SchDoc"
    ]
    assert (SAMPLE_DIR / "altium_sample.PrjPcb").read_bytes() == binary_files["altium_sample.PrjPcb"]
    assert not [p for p in binary_files if p.endswith((".PcbLib", ".PcbDoc"))]


def test_committed_library_reads_back() -> None:
    library = read_pcblib((BLINK_DIR / "blink.PcbLib").read_bytes())
    assert sorted(library.footprints) == ["Mini_LED_THT_3mm", "Mini_QFP-32_7x7mm_P0.8mm", "Mini_R_0603"]


def _protocol_digests() -> dict[str, str]:
    text = PROTOCOL.read_text(encoding="utf-8")
    return dict(
        re.findall(r"^\| `tests/data/altium/blink/([^`]+)` \| `([0-9a-f]{64})` \|", text, flags=re.MULTILINE)
    )


def test_protocol_names_the_pcb_bytes() -> None:
    """Scenario "Protocol names the PCB bytes": every committed blink file with its digest."""
    digests = _protocol_digests()
    committed = sorted(p.name for p in BLINK_DIR.iterdir() if p.is_file())
    assert sorted(digests) == committed
    for name, digest in digests.items():
        assert hashlib.sha256((BLINK_DIR / name).read_bytes()).hexdigest() == digest, name


def test_protocol_pad_tables() -> None:
    """The page's pad table (footprint, pad, shape, size, hole) equals the committed library."""
    text = PROTOCOL.read_text(encoding="utf-8")
    rows = set(
        re.findall(r"^\| `([^`]+)` \| (\S+) \| (\w+) \| (\d+) × (\d+) \| (\d+) \|$", text, flags=re.MULTILINE)
    )
    expanded: set[tuple[str, ...]] = set()
    for name, pads, *rest in rows:
        first, _, last = pads.partition("…")
        numbers = range(int(first), int(last) + 1) if last else [int(first)]
        expanded |= {(name, str(n), *rest) for n in numbers}
    library = read_pcblib((BLINK_DIR / "blink.PcbLib").read_bytes())
    shape_names = {1: "round", 2: "rectangle"}
    expected: set[tuple[str, ...]] = set()
    for name, footprint in library.footprints.items():
        for pad in footprint.primitives:
            if isinstance(pad, PadRecord):
                shape = "rounded" if pad.layers_size else shape_names[pad.shapes[0]]
                w, h = pad.sizes[0]
                expected.add((name, pad.name, shape, str(w), str(h), str(pad.hole)))
    assert expanded == expected
