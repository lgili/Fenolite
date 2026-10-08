# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The visibility bits of a pin's ``PINCONGLOMERATE`` (change c0148, capability altium-schematic-writer,
"Binary pin record", and altium-schematic-reader, "Pin visibility bits"; ``H-A-SCHLIB-PINBITS``).

With bit 0x20 set, 0x08 shows the name and 0x10 the number (Altium Designer 26.5.0 on the check project
``tests/data/altium/pinbits/``, S-0613, and the corpus, S-0614); without it, Altium Designer 26 reads the
two bits as hide flags (S-0612). The writer sets 0x20 on every pin.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from fenolite.backends.altium.altsym import SHOW_FLAGS, AltiumPin
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.backends.altium.read.sch.records import Component, Pin
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.backends.altium.schlib import pin_record

ROOT = Path(__file__).resolve().parents[4]
FOLDER = ROOT / "tests" / "data" / "altium" / "pinbits"
EXPECTED = {"V1": (False, False), "V2": (False, True), "V3": (True, False), "V4": (True, True)}
"""Variant → (name shown, number shown), as the maintainer saw it in Altium Designer 26.5.0."""


def _author() -> ModuleType:
    """The script as a module, compiled without a bytecode cache beside it (no ``__pycache__`` under
    ``tests/data``, whose files the manifest declares one by one)."""
    path = FOLDER / "author.py"
    module = ModuleType("pinbits_author")
    module.__file__ = str(path)
    sys.modules[module.__name__] = module  # the script's dataclasses look their module up
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def _pin(**changes: bool) -> AltiumPin:
    return AltiumPin(designator="1", name="A", part=1, x=0, y=0, direction=2, length=20, **changes)


def test_files_equal_what_the_script_writes() -> None:
    written = _author().files()
    assert sorted(written) == ["pinbits.PrjPcb", "pinbits.SchDoc", "pinbits.SchLib"]
    for name, data in written.items():
        assert (FOLDER / name).read_bytes() == data, f"{name}: run tests/data/altium/pinbits/author.py"


def test_variants_read_back_as_altium_shows_them() -> None:
    document = read_schematic((FOLDER / "pinbits.SchDoc").read_bytes(), file="pinbits.SchDoc")
    records = document.records
    seen: dict[str, list[tuple[bool, bool]]] = {}
    for record in records:
        if isinstance(record, Pin):
            owner = records[record.owner_index or 0]
            assert isinstance(owner, Component)
            variant = owner.lib_reference.removeprefix("LED_")
            assert record.conglomerate & SHOW_FLAGS
            seen.setdefault(variant, []).append((record.name_shown, record.designator_shown))
    assert seen == {variant: [shown, shown] for variant, shown in EXPECTED.items()}
    texts = [r.props.get("TEXT") for r in records if r.props is not None and r.props.get("RECORD") == "4"]
    assert texts == list(EXPECTED)
    library = read_schlib((FOLDER / "pinbits.SchLib").read_bytes(), file="pinbits.SchLib")
    for component in library.components:
        variant = component.name.removeprefix("LED_")
        assert [(p.name_shown, p.designator_shown) for p in component.pins] == [EXPECTED[variant]] * 2


@pytest.mark.parametrize(
    ("name_shown", "number_shown", "bits"),
    [(False, True, 0x30), (True, False, 0x28), (True, True, 0x38), (False, False, 0x20)],
)
def test_writer_sets_show_flags_with_bit_0x20(name_shown: bool, number_shown: bool, bits: int) -> None:
    pin = _pin(name_shown=name_shown, number_shown=number_shown)
    assert pin.conglomerate == 2 | bits
    if not name_shown and number_shown:
        assert pin.conglomerate & 0x08 == 0 and pin.conglomerate & 0x10
    if name_shown and not number_shown:
        assert pin.conglomerate & 0x08 and pin.conglomerate & 0x10 == 0
    library = read_schlib(_one_pin_library(pin), file="one.SchLib")
    (read,) = library.components[0].pins
    assert (read.conglomerate, read.name_shown, read.designator_shown) == (2 | bits, name_shown, number_shown)


@pytest.mark.parametrize(
    ("conglomerate", "name_shown", "number_shown"),
    [
        (18, True, False),
        (16, True, False),
        (2, True, True),
        (0, True, True),
        (26, False, False),
        (58, True, True),
        (50, False, True),
        (34, False, False),
    ],
)
def test_text_pins_read_by_bit_0x20(conglomerate: int, name_shown: bool, number_shown: bool) -> None:
    """With 0x20 the two bits show, as on every pin Altium saves; without it (the pins of files written
    before change c0148) they hide, as Altium Designer 26 showed them."""
    text = f"|RECORD=2|OWNERINDEX=1|OWNERPARTID=1|PINCONGLOMERATE={conglomerate}|NAME=A|DESIGNATOR=1"
    pin = _text_pin(text)
    assert (pin.name_shown, pin.designator_shown, pin.direction) == (
        name_shown,
        number_shown,
        conglomerate & 3,
    )


def _one_pin_library(pin: AltiumPin) -> bytes:
    from fenolite.backends.altium.altsym import AltiumRect, AltiumSymbol
    from fenolite.backends.altium.schlib import write_schlib

    symbol = AltiumSymbol("ONE", 1, (pin,), (AltiumRect(1, -100, -100, 100, 100),), "U", "ONE")
    assert pin_record(pin)[4 + 15] == pin.conglomerate  # after the frame word, at offset 15 of the payload
    return write_schlib([symbol], library="one.SchLib")


def _text_pin(text: str) -> Pin:
    from _altium_sch_build import SHEET, schdoc

    document = read_schematic(schdoc([SHEET, "|RECORD=1|LIBREFERENCE=X|OWNERPARTID=-1", text]), file="t")
    (pin,) = [r for r in document.records if isinstance(r, Pin)]
    return pin
