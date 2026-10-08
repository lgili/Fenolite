# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Write the pin-bits check project of change c0148 beside this script: ``pinbits.PrjPcb``,
``pinbits.SchDoc`` (binary) and ``pinbits.SchLib``.

The sheet holds the catalog symbol ``Fenolite:LED`` four times, ``D1`` to ``D4``, each the library symbol
``LED_V1`` … ``LED_V4`` of the one library, with a free text ``V1`` … ``V4`` above it. Every pin of
symbol ``Vk`` has the ``PINCONGLOMERATE`` of the table below (direction in bits 0-1), so a person who opens
the project in Altium Designer can say, per symbol, whether the pin names and numbers are drawn:

====  ======================  ===========================================
V1    0x20 | direction        bit 0x20 alone
V2    0x20 | 0x10 | dir       0x10 set (the number, if 0x10 shows it)
V3    0x20 | 0x08 | dir       0x08 set (the name, if 0x08 shows it)
V4    0x20 | 0x18 | dir       both set
====  ======================  ===========================================

Every pin of every Altium-saved schematic of the corpus holds bit 0x20; no file Fenolite wrote before
change c0148 holds it. Everything else is the schematic writer's own output (``project.write_project``):
only the pins' conglomerate and the four free texts are set here, so the bytes do not depend on the
writer's own bits. Every value is authored for Fenolite. Opened in Altium Designer 26.5.0 on 2026-10-08
(S-0613), V1 showed neither text, V2 the numbers only, V3 the names only and V4 both.
Run from the repository root:

    uv run python tests/data/altium/pinbits/author.py
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from pathlib import Path

from fenolite.backends.altium.altsym import SHOW_FLAGS, AltiumPin, AltiumSymbol, from_symbol_def
from fenolite.backends.altium.ascii import coord_fields
from fenolite.backends.altium.hierarchy import plan_sheets
from fenolite.backends.altium.project import write_project
from fenolite.backends.altium.schdoc import Field
from fenolite.catalog import get_symbol
from fenolite.dsl import Design, Net, Part, connect
from fenolite.dsl.convert import to_model
from fenolite.lens.altium import kicad_pins

HERE = Path(__file__).resolve().parent
NAME = "pinbits"
VARIANTS: Mapping[str, int] = {"V1": 0x00, "V2": 0x10, "V3": 0x08, "V4": 0x18}
"""The visibility bits of each variant, ORed with ``0x20`` and the pin's direction."""


@dataclasses.dataclass(frozen=True)
class BitsPin(AltiumPin):
    """A pin whose ``PINCONGLOMERATE`` holds ``bits`` above its direction instead of the writer's bits."""

    bits: int = 0

    @property
    def conglomerate(self) -> int:
        return self.direction | (0x04 if self.hidden else 0) | self.bits


@dataclasses.dataclass(frozen=True)
class Texts:
    """Free texts (record 4) appended after every other record, as a drawing sheet's are."""

    texts: tuple[tuple[str, int, int], ...]

    @property
    def records(self) -> Sequence[Sequence[Field]]:
        return tuple(
            (
                ("RECORD", "4"),
                ("OWNERPARTID", "-1"),
                *coord_fields("LOCATION", x, y),
                ("FONTID", "1"),
                ("TEXT", t),
            )
            for t, x, y in self.texts
        )

    def sheet_record(self, base: Sequence[Field]) -> list[Field]:
        return list(base)


def symbols() -> dict[str, AltiumSymbol]:
    """Lib id → the catalog LED with the bits of its variant on every pin."""
    led = get_symbol("Fenolite:LED")
    found: dict[str, AltiumSymbol] = {}
    for variant, bits in VARIANTS.items():
        base = from_symbol_def(led, lib_ref=f"LED_{variant}", footprint=None)
        pins = tuple(
            BitsPin(
                **{f.name: getattr(p, f.name) for f in dataclasses.fields(AltiumPin)}, bits=SHOW_FLAGS | bits
            )
            for p in base.pins
        )
        found[f"PinBits:LED_{variant}"] = dataclasses.replace(base, pins=pins)
    return found


def design() -> Design:
    d = Design(NAME)
    gnd, anode = Net("GND"), Net("LED_A")
    for index, variant in enumerate(VARIANTS, start=1):
        part = Part(f"D{index}", f"PinBits:LED_{variant}", value=variant)
        d.add(part)
        connect(gnd, part[1])
        connect(anode, part[2])
    return d


def files() -> dict[str, bytes]:
    led = get_symbol("Fenolite:LED")
    model, _ = kicad_pins(to_model(design()), {f"PinBits:LED_{v}": led for v in VARIANTS})
    mapped = symbols()
    planned = plan_sheets(model, name=NAME, sheets="flat", form="binary", symbols=mapped)
    sheet = planned.sheets[0]
    height = sheet.plan.size.height
    texts: list[tuple[str, int, int]] = []
    for placed in sheet.plan.parts:
        variant = placed.spec.comment
        x0, y0, _, _ = placed.cell
        texts.append((variant, x0 + 100, height - y0 - 100))
    frames = {sheet.file: Texts(tuple(texts))}
    return write_project(model, name=NAME, form="binary", symbols=mapped, frames=frames)


def main() -> None:
    for name, data in sorted(files().items()):
        (HERE / name).write_bytes(data)
        print(f"wrote {name}: {len(data)} bytes")


if __name__ == "__main__":
    main()
