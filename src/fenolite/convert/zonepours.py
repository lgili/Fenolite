# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The poured regions of Altium polygons carried through KiCad (change c0482; capability design-conversion,
"The source's pour is kept").

A conversion to KiCad writes, in the board property ``PROPERTY`` (``backends.kicad.boardcarrier``), each
polygon's region records as read (``Regions6`` and their ``ShapeBasedRegions6`` twins, base64), with the
polygon's vertices as read, its net and its layer, keyed by the uuid the KiCad writer gives its zone
(``pcb.kicad_uuid``), and whether the source's own pour fails Fenolite's copper check. The Altium writer
(``pcbdoc.write_pcbdoc_result``) writes those records, with the new polygon index, when every polygon of the
document has one whose vertices and net are the written polygon's, and the copper check (``pour.check_pour``)
finds no fault that the source's own pour does not have; otherwise it computes the pour as before. The
vertices find the pour, not the uuid: a script's build gives its zones other uuids.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Iterable
from fractions import Fraction
from typing import cast

from fenolite.backends.altium.pcbdoc import KeptPour

PROPERTY = "Fenolite.Altium.Pours"
"""The board property that carries the poured regions (``boardcarrier``)."""
SCHEMA = "fenolite.altium-pours.v0"


def _fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _b64(data: bytes | None) -> str | None:
    return None if data is None else base64.b64encode(data).decode("ascii")


def carrier_text(found: Iterable[tuple[str, KeptPour]]) -> str:
    """The property's JSON text: one entry per ``(uuid, pour)``, sorted by uuid."""
    pours = [
        {
            "uuid": uuid,
            "net": pour.net,
            "layer": pour.layer,
            "source_failed": pour.source_failed,
            "vertices": [[_fraction(x), _fraction(y)] for x, y in pour.vertices],
            "regions": [[_b64(plain), _b64(shape)] for plain, shape in pour.regions],
        }
        for uuid, pour in sorted(found, key=lambda item: item[0])
    ]
    return json.dumps({"schema": SCHEMA, "pours": pours}, sort_keys=True, separators=(",", ":"))


def _bytes(value: object) -> bytes | None:
    if not isinstance(value, str):
        raise ValueError("not base64 text")
    return base64.b64decode(value.encode("ascii"), validate=True)


def _entry(row: dict[str, object]) -> KeptPour | None:
    net, raw_vertices, raw_regions = row.get("net"), row.get("vertices"), row.get("regions")
    if (net is not None and not isinstance(net, str)) or not isinstance(raw_vertices, list):
        return None
    if not isinstance(raw_regions, list):
        return None
    try:
        vertices: list[tuple[Fraction, Fraction]] = []
        for vertex in cast("list[object]", raw_vertices):
            pair = cast("list[object]", vertex) if isinstance(vertex, list) else []
            if len(pair) != 2 or not all(isinstance(v, str) for v in pair):
                return None
            vertices.append((Fraction(cast(str, pair[0])), Fraction(cast(str, pair[1]))))
        regions: list[tuple[bytes, bytes | None]] = []
        for region in cast("list[object]", raw_regions):
            pair = cast("list[object]", region) if isinstance(region, list) else []
            if len(pair) != 2:
                return None
            plain = _bytes(pair[0])
            if plain is None:  # pragma: no cover - _bytes raises for anything but text
                return None
            regions.append((plain, None if pair[1] is None else _bytes(pair[1])))
    except (ValueError, ZeroDivisionError, binascii.Error):
        return None
    if len(vertices) < 3 or not regions:
        return None
    failed, layer = row.get("source_failed", False), row.get("layer", "")
    if not isinstance(failed, bool) or not isinstance(layer, str):
        return None
    return KeptPour(tuple(vertices), net, tuple(regions), layer, failed)


def read_carrier(data: bytes | None) -> dict[str, KeptPour]:
    """The carried pours by KiCad zone uuid; nothing for no property, another schema or text that is no
    carrier. An entry that is not well formed is left out: its polygon is then poured by Fenolite."""
    if not data:
        return {}
    try:
        loaded: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    root = cast("dict[str, object]", loaded) if isinstance(loaded, dict) else {}
    if root.get("schema") != SCHEMA:
        return {}
    entries = root.get("pours")
    found: dict[str, KeptPour] = {}
    for entry in cast("list[object]", entries) if isinstance(entries, list) else []:
        row = cast("dict[str, object]", entry) if isinstance(entry, dict) else {}
        uuid = row.get("uuid")
        pour = _entry(row)
        if isinstance(uuid, str) and pour is not None:
            found[uuid] = pour
    return found


__all__ = ["PROPERTY", "SCHEMA", "KeptPour", "carrier_text", "read_carrier"]
