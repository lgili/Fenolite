# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic libraries written by Fenolite against ``kicad-cli sym upgrade`` (capability
altium-schematic-writer, "Schematic library oracle"; change c0034; hypotheses ``H-A-SCHLIB-KICAD`` and
``H-A-SCHLIB-KICAD9``).

The round trip is: library symbols → ``write_schlib`` → ``kicad-cli sym upgrade X.SchLib -o Y.kicad_sym``
(KiCad's Altium importer, S-0153) → ``backends.kicad.sym.read_symbol_library`` → compare. The negative
controls are built from the writer's own records. A component storage without ``Data`` crashes
kicad-cli 10.0.6 (``schematic-library.md``) and is never run. On kicad-cli 9, a library that does not
convert is expected to fail, with kicad-cli's message.

A pass on 10.0.6 checks only what KiCad's importer reads; it settles no Altium-only fact.
"""

from __future__ import annotations

import os
import struct
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from _altium import sample_model
from _resources import kicad_cli, kicad_cli_major

from fenolite.backends.altium.altsym import AltiumSymbol
from fenolite.backends.altium.binary import frame_record, storage_stream
from fenolite.backends.altium.cfb import Entry, Storage, write_compound
from fenolite.backends.altium.project import generic_symbols
from fenolite.backends.altium.schlib import (
    data_records,
    header_record,
    pin_record,
    storage_name,
    write_schlib,
)
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.model.library import SymbolDef

pytestmark = pytest.mark.needs_kicad

MIL = 25_400
ROTATION_OF_DIRECTION = {2: 0, 3: 90_000_000, 0: 180_000_000, 1: 270_000_000}
"""Altium direction → KiCad pin angle in microdegrees (``schematic-library.md``, mapping table)."""
SAMPLE_LIBRARY = "FenoliteSample.SchLib"


@dataclass(frozen=True)
class Converted:
    code: int
    message: str
    output: bytes

    @property
    def symbols(self) -> dict[str, SymbolDef]:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.kicad_sym"
            path.write_bytes(self.output)
            return {s.name: s for s in read_symbol_library(path, library="out")}


def convert(data: bytes, name: str = "lib.SchLib") -> Converted:
    """Run ``kicad-cli sym upgrade`` on ``data`` saved as ``name``, with an empty configuration folder."""
    cli = kicad_cli()
    assert cli is not None
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source, target = root / name, root / "out.kicad_sym"
        source.write_bytes(data)
        env = {**os.environ, "KICAD_CONFIG_HOME": str(root / "config")}
        proc = subprocess.run(
            [cli, "sym", "upgrade", str(source), "-o", str(target)],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            check=False,
        )
        output = target.read_bytes() if target.is_file() else b""
        return Converted(proc.returncode, (proc.stdout + proc.stderr).strip(), output)


def converted(data: bytes, name: str = "lib.SchLib") -> Converted:
    """``convert``, which must succeed; on kicad-cli 9 a failure is expected (``H-A-SCHLIB-KICAD9``)."""
    result = convert(data, name)
    if result.code != 0 and kicad_cli_major() == 9:
        pytest.xfail(f"kicad-cli 9 does not convert the library: exit {result.code}: {result.message}")
    assert result.code == 0, result.message
    return result


@cache
def sample_symbols() -> tuple[AltiumSymbol, ...]:
    return tuple(generic_symbols(sample_model()).values())


@cache
def sample_library() -> bytes:
    return write_schlib(sample_symbols(), library=SAMPLE_LIBRARY)


def expected_pins(symbol: AltiumSymbol) -> set[tuple[object, ...]]:
    """The pins KiCad should read for ``symbol``: number, name, unit, hot end in nm, angle, length."""
    return {
        (
            p.designator,
            p.name,
            p.part,
            p.hot_end[0] * MIL,
            p.hot_end[1] * MIL,
            ROTATION_OF_DIRECTION[p.direction],
            p.length * MIL,
        )
        for p in symbol.pins
    }


def read_pins(symbol: SymbolDef) -> set[tuple[object, ...]]:
    return {(p.number, p.name, p.unit, p.position.x, p.position.y, p.rotation, p.length) for p in symbol.pins}


# --- the sample's library ---------------------------------------------------------------------------


def test_sample_library_converts_with_the_generic_pins() -> None:
    result = converted(sample_library(), SAMPLE_LIBRARY)
    symbols = result.symbols
    assert sorted(symbols) == sorted(storage_name(s.lib_ref) for s in sample_symbols())
    for source in sample_symbols():
        read = symbols[source.lib_ref]
        assert read.unit_count == source.parts
        assert read_pins(read) == expected_pins(source), source.lib_ref
        assert {p.etype for p in read.pins} == {"passive"}
        assert read.reference == source.prefix
        assert source.footprint is not None
        assert read.footprint.split(":")[-1] == source.footprint[1]


def test_conversion_is_deterministic() -> None:
    assert converted(sample_library()).output == converted(sample_library()).output


# --- negative controls ------------------------------------------------------------------------------


def _library(change: Callable[[list[bytes]], list[bytes]] = lambda r: r, *, header: str = "") -> bytes:
    """The sample's ``RES`` alone, its ``Data`` records changed by ``change``, and optionally another
    header text."""
    res = next(s for s in sample_symbols() if s.lib_ref == "RES")
    records = change(data_records(res, library=SAMPLE_LIBRARY))
    fields = header_record([res], len(records) + 1)
    if header:
        fields[0] = ("HEADER", header)
    entries: list[Entry] = [
        ("FileHeader", frame_record(fields)),
        ("Storage", storage_stream()),
        Storage("RES", (("Data", b"".join(records)),)),
    ]
    return write_compound(entries)


def _short_pin(records: list[bytes]) -> list[bytes]:
    pin = pin_record(next(s for s in sample_symbols() if s.lib_ref == "RES").pins[0])
    payload = pin[4:-2]  # without the part-and-sequence and default-value strings
    return [records[0], struct.pack("<I", 1 << 24 | len(payload)) + payload, *records[2:]]


def test_negative_control_baseline_converts() -> None:
    assert converted(_library()).code == 0


@pytest.mark.parametrize(
    "variant",
    ["other-header", "component-not-first", "stray-byte", "pin-without-last-strings"],
)
def test_negative_controls(variant: str) -> None:
    data = {
        "other-header": lambda: _library(
            header="Protel for Windows - Schematic Capture Binary File Version 5.0"
        ),
        "component-not-first": lambda: _library(lambda r: [*r[1:], r[0]]),
        "stray-byte": lambda: _library(lambda r: [*r, b"\0"]),
        "pin-without-last-strings": lambda: _library(_short_pin),
    }[variant]()
    result = convert(data)
    assert result.code != 0, f"{variant}: kicad-cli converted a malformed library"
