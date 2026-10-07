# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Golden schematic libraries (capability altium-build, "Schematic library samples" and "Schematic
library author reports"; change c0034).

A fresh build of ``examples/altium_sample/design.py`` must give the committed
``tests/data/altium/sample/FenoliteSample.SchLib`` byte for byte, while both committed schematics keep
their c0033 bytes; a fresh build of ``examples/altium_kicad/design.py`` (binary form, its own library
table) must give the three files under ``tests/data/altium/kicad_example/``. ``FENOLITE_GOLDEN_WRITE=1``
rewrites the files instead of comparing them; the SHA-256 values of Part L of
``docs/evidence/altium-schematic.md`` are then updated by hand, and ``-k protocol`` checks them.
"""

from __future__ import annotations

import hashlib
import os
import re
from functools import cache
from pathlib import Path

import pytest
from _altium import EXAMPLE_NETS, example_files, sample
from _altium_read import read_schlib

from fenolite.backends.altium.read.schlib import read_schlib as product_read_schlib
from fenolite.dsl import to_model
from fenolite.lens.altium import build_altium

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DIR = ROOT / "tests" / "data" / "altium" / "sample"
EXAMPLE_DIR = ROOT / "tests" / "data" / "altium" / "kicad_example"
EXAMPLE_FILES = ("altium_kicad.PrjPcb", "altium_kicad.SchDoc", "altium_kicad.SchLib")
PROTOCOL = ROOT / "docs" / "evidence" / "altium-schematic.md"
PART_L = "## Part L: the schematic libraries in Altium Designer"
LIBRARY = "FenoliteSample.SchLib"
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"


@cache
def sample_files(form: str) -> dict[str, bytes]:
    design = sample()
    return build_altium(to_model(design), name=design.name, form=form).files  # type: ignore[arg-type]


def test_sample_library_golden() -> None:
    data = sample_files("binary")[LIBRARY]
    assert sample_files("ascii")[LIBRARY] == data, "the library does not depend on the schematic form"
    if WRITE:
        (SAMPLE_DIR / LIBRARY).write_bytes(data)
        pytest.skip("library golden file rewritten (FENOLITE_GOLDEN_WRITE=1)")
    assert (SAMPLE_DIR / LIBRARY).read_bytes() == data, f"{LIBRARY} differs from a fresh build"


def test_sample_schematics_keep_their_bytes() -> None:
    assert (SAMPLE_DIR / "altium_sample.SchDoc").read_bytes() == sample_files("ascii")["altium_sample.SchDoc"]
    binary = SAMPLE_DIR / "binary" / "altium_sample.SchDoc"
    assert binary.read_bytes() == sample_files("binary")["altium_sample.SchDoc"]


def test_sample_projects_list_the_library() -> None:
    for folder in (SAMPLE_DIR, SAMPLE_DIR / "binary"):
        text = (folder / "altium_sample.PrjPcb").read_bytes()
        assert text.endswith(b"\r\n\r\n[Document2]\r\nDocumentPath=FenoliteSample.SchLib\r\n")


def test_committed_library_reads_back() -> None:
    library = read_schlib((SAMPLE_DIR / LIBRARY).read_bytes())
    assert sorted(library) == ["CAP", "DRV4", "HDR2", "LDO3", "LED", "RES"]


@cache
def example_build() -> dict[str, bytes]:
    files = example_files("binary")
    return {name: files[name] for name in EXAMPLE_FILES}


def test_example_golden_files() -> None:
    files = example_build()
    if WRITE:
        EXAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (EXAMPLE_DIR / name).write_bytes(data)
        pytest.skip("example golden files rewritten (FENOLITE_GOLDEN_WRITE=1)")
    for name, data in files.items():
        assert (EXAMPLE_DIR / name).read_bytes() == data, f"kicad_example/{name} differs from a fresh build"


def test_example_library_does_not_draw_names_that_repeat_the_numbers() -> None:
    """Change c0134, on the committed library: ``CONN2`` keeps the names ``1`` and ``2`` and draws only
    its pin numbers; the two symbols with named pins still draw their names."""
    library = product_read_schlib(
        (EXAMPLE_DIR / "altium_kicad.SchLib").read_bytes(), file="altium_kicad.SchLib"
    )
    connector = sorted(
        (p.designator, p.name, p.name_shown, p.designator_shown) for p in library.get("CONN2").pins
    )
    assert connector == [("1", "1", False, True), ("2", "2", False, True)]
    for name in ("MCU8", "DUAL_OPAMP"):
        assert all(p.name_shown and p.designator_shown for p in library.get(name).pins if not p.hidden)


def _part_l() -> list[str]:
    lines = PROTOCOL.read_text(encoding="utf-8").splitlines()
    start = lines.index(PART_L)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def _cells(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def test_protocol_names_the_library_bytes() -> None:
    digests: dict[str, str] = {}
    for line in _part_l():
        cells = _cells(line)
        if len(cells) == 2 and re.fullmatch(r"[0-9a-f]{64}", cells[1]):
            digests[cells[0]] = cells[1]
    committed = {
        f"tests/data/altium/sample/{name}"
        for name in ("FenoliteSample.SchLib", "altium_sample.PrjPcb", "binary/altium_sample.PrjPcb")
    } | {f"tests/data/altium/kicad_example/{name}" for name in EXAMPLE_FILES}
    assert set(digests) == committed
    for path, digest in digests.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path


def test_protocol_net_table_equals_the_example_nets() -> None:
    nets: dict[str, set[tuple[str, str]]] = {}
    lines = _part_l()
    start = lines.index("| net | pins as (ref, pin) |")
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        name, pins = _cells(line)
        nets[name] = {(ref, pin) for ref, pin in re.findall(r"\(([^,]+), ([^)]+)\)", pins)}
    assert nets == EXAMPLE_NETS
