# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's reading of public Altium libraries against ``kicad-cli sym upgrade`` (capability
altium-schematic-reader, "Library oracle"; hypotheses ``H-A-RD-SCH-PIN``, ``H-A-RD-SCH-PARTS`` and
``H-A-RD-SCH-KICAD``).

Each ``altium-schlib`` corpus row is converted by KiCad's Altium importer (S-0153) through the package runner
``fenolite.backends.kicad.cli.KicadCli``, inside ``tmp_path``, and the KiCad library is read by
``fenolite.backends.kicad.sym.read_symbol_library``. Per symbol and unit the pins are compared as (number,
name with overbars mapped, hot end in nm, length in nm, direction, hidden flag), with the unit count and the
body-style count. Two clean-room readers agreeing is not truth: the rows reach ``ORACLE-VERIFIED(kicad-cli)``
for these fields only. Output names rows, symbol and pin positions, and counts, never a name of a file.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from _boards import census
from _corpus import CorpusItem, manifest_items, require
from _resources import kicad_cli

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.schlib import SchLibComponent, SchLibrary, read_schlib
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.model.library import SymbolDef

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus]
ITEMS = manifest_items("altium-schlib")
ROTATION_OF_DIRECTION = {2: 0, 3: 90_000_000, 0: 180_000_000, 1: 270_000_000}
"""Altium direction → KiCad pin angle in microdegrees (``schematic-library.md``, mapping table)."""
KNOWN: dict[str, str] = {
    "space-in-pin-name": "kicad-cli 10.0.6 writes a space of a pin name as '_' (schematic-library.md, "
    '"Oracle observations", row on pin names with a space; seen on altium-third-party-schlib-09)',
    "position-grid-100nm": "kicad-cli 10.0.6 holds schematic positions in steps of 100 nm, so a PinFrac "
    'pin\'s hot end is rounded (schematic-library.md, "Oracle observations"; altium-third-party-schlib-09)',
}
"""Differences that a recorded importer behaviour explains, each with the fact row that states it; the
comparison applies them to Fenolite's side and counts the pins they touch. A row that ``kicad-cli`` refuses
would be listed here by row id with its exit code; none is."""
GRID = 100
PinKey = tuple[str, str, int, int, int, int, bool]


def kicad_name(name: str) -> str:
    """An Altium pin name with KiCad's overbar form: a ``\\`` after each overlined character becomes
    ``~{…}`` around each run of overlined characters (``schematic-library.md``, binary pin record)."""
    out: list[str] = []
    run: list[str] = []
    index = 0
    while index < len(name):
        char = name[index]
        if index + 1 < len(name) and name[index + 1] == "\\":
            run.append(char)
            index += 2
            continue
        if run:
            out.append("~{" + "".join(run) + "}")
            run = []
        out.append(char)
        index += 1
    if run:
        out.append("~{" + "".join(run) + "}")
    return "".join(out)


def _grid(value: int) -> int:
    """``value`` in nm rounded half to even to KiCad's 100 nm step (KNOWN ``position-grid-100nm``)."""
    quotient, remainder = divmod(value, GRID)
    if remainder * 2 > GRID or (remainder * 2 == GRID and quotient % 2 == 1):
        quotient += 1
    return quotient * GRID


def fenolite_pins(component: SchLibComponent) -> dict[int, set[PinKey]]:
    """Unit → the pins of ``component`` as Fenolite reads them, with the KNOWN importer behaviours applied."""
    units: dict[int, set[PinKey]] = {}
    for pin in component.pins:
        units.setdefault(pin.owner_part, set()).add(_key(pin))
    return units


def known_counts(library: SchLibrary) -> dict[str, int]:
    """How many pins each KNOWN behaviour changes."""
    counts = dict.fromkeys(KNOWN, 0)
    for component in library.components:
        for pin in component.pins:
            x, y = pin.hot_end
            counts["space-in-pin-name"] += " " in pin.name
            counts["position-grid-100nm"] += any(v.nm() != _grid(v.nm()) for v in (x, y, pin.length))
    return counts


def kicad_pins(symbol: SymbolDef) -> dict[int, set[PinKey]]:
    units: dict[int, set[PinKey]] = {}
    for pin in symbol.pins:
        key = (pin.number, pin.name, pin.position.x, pin.position.y, pin.length, pin.rotation, pin.hidden)
        units.setdefault(pin.unit, set()).add(key)
    return units


def differences(library: SchLibrary, symbols: dict[str, SymbolDef]) -> list[str]:
    """Each disagreement, located by symbol and pin position (never by a name of the file)."""
    found: list[str] = []
    for position, component in enumerate(library.components):
        symbol = symbols.get(component.storage_name)
        if symbol is None:
            found.append(f"symbol #{position}: not in KiCad's library")
            continue
        if symbol.unit_count != component.part_count:
            found.append(
                f"symbol #{position}: {symbol.unit_count} unit(s) in KiCad, {component.part_count} read"
            )
        if symbol.body_style_count != component.display_mode_count:
            found.append(
                f"symbol #{position}: {symbol.body_style_count} body style(s) in KiCad, "
                f"{component.display_mode_count} display mode(s) read"
            )
        ours, theirs = fenolite_pins(component), kicad_pins(symbol)
        for unit in sorted(set(ours) | set(theirs)):
            missing = ours.get(unit, set()) - theirs.get(unit, set())
            extra = theirs.get(unit, set()) - ours.get(unit, set())
            if missing or extra:
                indexes = [i for i, pin in enumerate(component.pins) if _key(pin) in missing]
                found.append(
                    f"symbol #{position} unit {unit}: {len(missing)} pin(s) differ (pins #{indexes}), "
                    f"{len(extra)} pin(s) only in KiCad"
                )
    if len(symbols) != len(library.components):
        found.append(f"{len(symbols)} symbol(s) in KiCad, {len(library.components)} component(s) read")
    return found


def _key(pin: sch.Pin) -> PinKey:
    x, y = pin.hot_end
    return (
        pin.designator,
        kicad_name(pin.name).replace(" ", "_"),
        _grid(x.nm()),
        _grid(y.nm()),
        _grid(pin.length.nm()),
        ROTATION_OF_DIRECTION[pin.direction],
        pin.hidden,
    )


def convert(
    path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[int | None, dict[str, SymbolDef]]:
    """``kicad-cli sym upgrade`` through the package runner, every file under ``tmp_path``."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    cli_path = kicad_cli()
    assert cli_path is not None
    cli = KicadCli(Path(cli_path), timeout=600)
    run = cli.run(["sym", "upgrade", "in.SchLib", "-o", "out.kicad_sym"], files={"in.SchLib": path})
    if not run.ok or "out.kicad_sym" not in run.outputs:
        return run.returncode, {}
    target = tmp_path / "out.kicad_sym"
    target.write_bytes(run.outputs["out.kicad_sym"])
    return run.returncode, {symbol.name: symbol for symbol in read_symbol_library(target, library="out")}


@pytest.mark.parametrize("item", ITEMS, ids=lambda item: item.id)
def test_pins_agree_with_the_importer(
    item: CorpusItem, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = require(item)
    library = read_schlib(path.read_bytes(), file=item.id)
    code, symbols = convert(path, tmp_path, monkeypatch)
    pins = sum(len(component.pins) for component in library.components)
    known = known_counts(library)
    census("altium_schlib_oracle", item.id, {"exit": code, "symbols": len(symbols), "pins": pins, **known})
    if item.id in KNOWN:
        pytest.skip(f"KNOWN: {KNOWN[item.id]}")
    assert code == 0
    assert differences(library, symbols) == []


def test_negative_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    item = next(item for item in ITEMS if item.id == "altium-third-party-schlib-03")
    path = require(item)
    library = read_schlib(path.read_bytes())
    _, symbols = convert(path, tmp_path, monkeypatch)
    component = library.components[0]
    first = component.pins[0]
    assert first.pin_fields is not None
    fields = first.pin_fields
    changed_fields = type(fields)(
        **{**{n: getattr(fields, n) for n in fields.__dataclass_fields__}, "x": -fields.x - 7}
    )
    changed_pin = sch.Pin(first.ref, first.kind, first.payload, first.offset, None, pin_fields=changed_fields)
    records = tuple(changed_pin if record is first else record for record in component.records)
    changed_component = SchLibComponent(
        component.name, component.storage_name, component.description, records, data=component.data
    )
    changed = SchLibrary(
        library.file, library.codepage, library.header, library.header_tail, library.listed_names,
        (changed_component, *library.components[1:]),
    )  # fmt: skip
    found = differences(changed, symbols)
    assert len(found) == 1
    assert found[0].startswith("symbol #0 unit") and "pins #[0]" in found[0]


@pytest.mark.parametrize(
    ("name", "expected"),
    [("RST", "RST"), ("R\\S\\T\\", "~{RST}"), ("A\\B", "~{A}B"), ("", ""), ("C\\D\\E", "~{CD}E")],
)
def test_overbar_mapping(name: str, expected: str) -> None:
    assert kicad_name(name) == expected
