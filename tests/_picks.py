# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Families authored for the tests of change c0254 (illustrative rows, no real product)."""

from __future__ import annotations

from fenolite.pick.rows import PROJECT, SHIPPED, Row, expand, parse_family


def family(
    family_id: str,
    *,
    kind: str = "resistor",
    case: str = "0603",
    series: str = "E96",
    low: str = "10",
    high: str = "1M",
    tolerance: str = "1%",
    extra: str = "",
) -> str:
    if family_id.startswith("Fenolite:") and "sources" not in extra:
        extra += 'sources = { values = ["S-0942"] }\n'
    symbol = {
        "resistor": "Fenolite:Resistor",
        "capacitor": "Fenolite:Capacitor",
        "inductor": "Fenolite:Inductor",
    }
    return (
        'schema = "fenolite.family.v0"\n'
        f'id = "{family_id}"\nkind = "{kind}"\nsummary = "Test family {family_id}"\n'
        f'symbol = "{symbol[kind]}"\nfootprint = "Fenolite:Chip_{case}"\ncase = "{case}"\nseries = '
        f'"{series}"\n'
        f'values = {{ min = "{low}", max = "{high}" }}\ntolerance = "{tolerance}"\nevidence = '
        f'"INFERRED"\n{extra}'
    )


def rows(text: str, *, shipped: bool = False, catalog: str = "project:devices/test.toml") -> tuple[Row, ...]:
    return expand(
        parse_family(text, file="test.toml"), origin=SHIPPED if shipped else PROJECT, catalog=catalog
    )
