# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored PCB documents that hold stored DRC violations (change c0498): the committed ``blink`` sample with
violation storages of the recorded layout (``docs/formats/altium/pcb-records.md``, "DRC violations")
written into it with Fenolite's compound writer. Nothing here comes from a public or a private board."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from fenolite.backends.altium.cfb import Storage, write_compound
from fenolite.backends.altium.read.cfb import read_compound

BLINK = Path(__file__).resolve().parent / "data" / "altium" / "blink" / "blink.PcbDoc"


def blocks(records: Sequence[Mapping[str, str]]) -> bytes:
    """Property-text blocks: a 32-bit little-endian length, then ``|KEY=VALUE|…`` and a NUL."""
    out = b""
    for record in records:
        body = ("|" + "|".join(f"{k}={v}" for k, v in record.items()) + "\0").encode("latin-1")
        out += len(body).to_bytes(4, "little") + body
    return out


def storage(name: str, records: Sequence[Mapping[str, str]], *, count: int | None = None) -> Storage:
    header = (len(records) if count is None else count).to_bytes(4, "little")
    return Storage(name, (("Header", header), ("Data", blocks(records))))


def violation(
    rule: int, first: tuple[str, int], second: tuple[str, int], x: str, y: str, text: str = ""
) -> dict[str, str]:
    return {
        "SELECTION": "FALSE", "LAYER": "TOP", "LOCKED": "FALSE", "POLYGONOUTLINE": "FALSE",
        "USERROUTED": "TRUE", "KEEPOUT": "FALSE", "UNIONINDEX": "0", "RULEINDEX": str(rule),
        "PRIM1ID": first[0], "PRIM1INDEX": str(first[1]), "PRIM2ID": second[0], "PRIM2INDEX": str(second[1]),
        "DESCRIPTION": text, "INVOLVEDPRIMCOUNT": "0",
        "LOCATION1.X": x, "LOCATION1.Y": y, "LOCATION2.X": x, "LOCATION2.Y": y,
    }  # fmt: skip


def with_storages(target: Path, *added: Storage, source: Path = BLINK) -> Path:
    """``source`` with ``added`` in place of the root storages of the same names, written to ``target``."""
    names = {s.name for s in added}
    kept = tuple(e for e in read_compound(source).tree() if not (isinstance(e, Storage) and e.name in names))
    target.write_bytes(write_compound((*kept, *added)))
    return target
