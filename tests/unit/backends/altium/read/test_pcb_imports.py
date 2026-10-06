# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The PCB reader package (capability altium-pcb-reader, "PCB reader package", change c0041): what its
five modules import, how a document and a library are told apart, and the unit conversion."""

from __future__ import annotations

import ast
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import detect_pcb
from fenolite.backends.altium.read.pcbprims import to_nm, to_nm_exact
from fenolite.core.units import u_to_nm

ROOT = Path(__file__).resolve().parents[5]
PACKAGE = ROOT / "src" / "fenolite" / "backends" / "altium" / "read"
MODULES = ("pcbprops", "pcbprims", "pcbstack", "pcb", "pcblib")
WRITERS = ("pcbrecords", "pcblib", "pcbdoc", "libboard", "docboard", "cfb")
FORBIDDEN_STDLIB = {"subprocess", "os", "shutil", "tempfile", "socket"}
BLINK = ROOT / "tests" / "data" / "altium" / "blink"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: relative import"
            module = node.module or ""
            names.add(module)
            if module in ("fenolite.backends.altium", "fenolite.backends.altium.read"):
                names |= {f"{module}.{alias.name}" for alias in node.names}
    return names


@pytest.mark.parametrize("module", MODULES)
def test_the_reader_does_not_import_the_writers(module: str) -> None:
    path = PACKAGE / f"{module}.py"
    assert path.is_file(), f"{module}.py is missing"
    for name in _imports(path):
        top = name.split(".")[0]
        if top == "fenolite":
            assert name.startswith(("fenolite.core", "fenolite.backends.altium.read")), f"{module}: {name}"
            assert not name.startswith("fenolite.model"), f"{module}: {name}"
            assert name not in {f"fenolite.backends.altium.{w}" for w in WRITERS}, f"{module}: {name}"
        else:
            assert top == "__future__" or top in sys.stdlib_module_names, f"{module}: {name}"
            assert top not in FORBIDDEN_STDLIB, f"{module}: {name}"


def test_the_test_reader_stays_independent() -> None:
    for name in _imports(ROOT / "tests" / "_altium_pcb_read.py"):
        assert not name.startswith("fenolite.backends.altium.read"), name
    for module in MODULES:
        assert "_altium_pcb_read" not in (PACKAGE / f"{module}.py").read_text(encoding="utf-8")


def test_a_document_and_a_library_are_told_apart() -> None:
    assert detect_pcb((BLINK / "blink.PcbDoc").read_bytes()) == "pcbdoc"
    assert detect_pcb((BLINK / "blink.PcbLib").read_bytes()) == "pcblib"
    assert detect_pcb((BLINK / "blink.SchLib").read_bytes()) is None
    assert detect_pcb(b"|RECORD=Board|") is None
    assert detect_pcb(open_compound((BLINK / "blink.PcbLib").read_bytes())) == "pcblib"


def test_unit_conversion() -> None:
    assert to_nm_exact(354331) == Fraction(45000037, 50)
    assert to_nm(354331) == 900001


def test_ties_round_to_even() -> None:
    assert [to_nm(u) for u in (25, 75, 125, -25)] == [64, 190, 318, -64]
    assert all(to_nm(u) == u_to_nm(u) for u in range(-200, 200))
