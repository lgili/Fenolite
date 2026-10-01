# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The IPC-D-356 netlist that ``kicad-cli pcb export ipcd356`` writes, read as pad records.

Facts: ``docs/formats/kicad/board.md`` (S-0019, S-0020; observed on 9.0.9 and 10.0.6). A header line
``P  UNITS CUST 0`` gives 0.0001 in units (2540 nm). Pad records are lines of 73 characters with fixed
columns: the record code (``317`` through-hole, ``327`` surface), the net name (14 characters, its tail
kept when longer), the reference, a ``-`` and the pin; then a field list with the position
``X±nnnnnnY±nnnnnn`` (Y up), the access side ``Ann`` and the rotation ``Rnnn``. The reference field
holds 6 characters and the pin field 4, so longer values are truncated. Vias are ``317`` records with
the reference ``VIA``, a blank pin and the midpoint flag ``M`` in column 32.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fenolite.core.errors import FormatError

PAD_CODES = ("317", "327")
UNITS_NM = {"0": 2540}
SIDES = {"00": "both", "01": "top", "02": "bottom"}
_UNITS = re.compile(r"^P\s+UNITS\s+CUST\s+(\d+)\s*$")
_POSITION = re.compile(r"X([+-]\d+)Y([+-]\d+)")
_ACCESS = re.compile(r"A(\d\d)X")
_ROTATION = re.compile(r"R(\d{3})")


@dataclass(frozen=True, slots=True)
class Ipcd356Record:
    """One record; ``x`` and ``y`` in export units, Y up; ``side`` is ``both``, ``top`` or ``bottom``.

    ``ref`` and ``pin`` are the export's fixed-width fields (truncated to 6 and 4 characters); a via has
    ``ref == "VIA"`` and an empty ``pin``.
    """

    code: str
    net: str
    ref: str
    pin: str
    x: int
    y: int
    rotation: int | None
    side: str


@dataclass(frozen=True, slots=True)
class Ipcd356:
    """The export unit in nanometres and the pad records in file order."""

    unit_nm: int
    records: tuple[Ipcd356Record, ...]


def read_ipcd356(text: str) -> Ipcd356:
    """The ``317`` and ``327`` records of an IPC-D-356 export, vias included (``FormatError`` without a
    supported ``UNITS`` line)."""
    unit_nm: int | None = None
    records: list[Ipcd356Record] = []
    for number, line in enumerate(text.splitlines(), start=1):
        units = _UNITS.match(line)
        if units is not None:
            if units.group(1) not in UNITS_NM:
                raise FormatError(f"unsupported units CUST {units.group(1)}", locator=f"line {number}")
            unit_nm = UNITS_NM[units.group(1)]
            continue
        if line[:3] not in PAD_CODES or len(line) < 32:
            continue
        fields = line[32:]
        position = _POSITION.search(fields)
        if position is None:
            raise FormatError("pad record without a position", locator=f"line {number}")
        access = _ACCESS.search(fields)
        rotation = _ROTATION.search(fields[position.end() :])
        records.append(
            Ipcd356Record(
                code=line[:3],
                net=line[3:17].strip(),
                ref=line[20:26].strip(),
                pin=line[27:31].strip(),
                x=int(position.group(1)),
                y=int(position.group(2)),
                rotation=None if rotation is None else int(rotation.group(1)),
                side=SIDES.get(access.group(1), f"A{access.group(1)}") if access else "",
            )
        )
    if unit_nm is None:
        raise FormatError("no 'P  UNITS CUST n' line")
    return Ipcd356(unit_nm, tuple(records))


__all__ = ["Ipcd356", "Ipcd356Record", "read_ipcd356"]
