# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Golden schematic libraries (capability altium-build, "Schematic library samples"; change c0034).

A fresh build of ``examples/altium_sample/design.py`` must give the committed
``tests/data/altium/sample/FenoliteSample.SchLib`` byte for byte, while both committed schematics keep
their c0033 bytes. ``FENOLITE_GOLDEN_WRITE=1`` rewrites the library instead of comparing it; the SHA-256
values of ``docs/evidence/altium-schematic.md`` are then updated by hand.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import pytest
from _altium import sample
from _altium_read import read_schlib

from fenolite.dsl import to_model
from fenolite.lens.altium import build_altium

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DIR = ROOT / "tests" / "data" / "altium" / "sample"
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
