# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Versioned composition report and transactional artifact bytes."""

from __future__ import annotations

import json
from dataclasses import asdict

from fenolite.schematic.composition import (
    ALGORITHM,
    FANOUT_LIMIT,
    GRID,
    PIN_GRID,
    PLACEMENT_BUDGET,
    SCHEMA,
    WIRE_BUDGET,
    Box,
    CompositionPlan,
)

REPORT_FILE = ".fenolite/schematic-composition.json"
PREVIEW_DIR = ".fenolite/schematic-preview"


def box(value: Box) -> list[int]:
    return [value.x0, value.y0, value.x1, value.y1]


def preview_file(sheet: str) -> str:
    if any(c in sheet for c in "/\\:") or sheet in ("", ".", ".."):
        raise ValueError("preview sheet must be a safe filename")
    return f"{PREVIEW_DIR}/{sheet}.svg"


def report(plans: tuple[CompositionPlan, ...], *, replayed: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "algorithm": ALGORITHM,
        "evidence": {"level": "INFERRED", "native_review": "unmeasured"},
        "units": "nm",
        "origin": "generated-baseline",
        "replayed_sheets": sorted(replayed),
        "limits": {
            "grid": GRID,
            "pin_grid": PIN_GRID,
            "fanout": FANOUT_LIMIT,
            "placement_budget": PLACEMENT_BUDGET,
            "wire_budget": WIRE_BUDGET,
            "text_bounds": "conservative estimates; native font metrics unmeasured",
        },
        "sheets": [
            {
                "sheet": p.sheet,
                "flow": p.flow,
                "preview": preview_file(p.sheet),
                "region": box(p.region),
                "reserved": [box(b) for b in p.reserved],
                "placement_candidates": p.candidates,
                "connection_candidates": p.connection_candidates,
                "wrapped": any(
                    (b.bounds.y0 > a.bounds.y0 if p.flow == "left-to-right" else b.bounds.x0 > a.bounds.x0)
                    for a, b in zip(p.blocks, p.blocks[1:], strict=False)
                ),
                "blocks": [{"key": b.key, "title": b.title, "bounds": box(b.bounds)} for b in p.blocks],
                "placements": [
                    {
                        "unit": u.unit.key,
                        "component": u.unit.component,
                        "part": u.unit.part,
                        "block": u.block,
                        "origin": list(u.origin),
                        "rotation": u.rotation,
                        "bounds": box(u.bounds),
                        "visible": [asdict(v) for v in u.visible],
                    }
                    for u in sorted(p.placements, key=lambda u: u.unit.key)
                ],
                "attachments": [asdict(a) for a in p.attachments],
                "wires": [
                    {
                        **asdict(w),
                        "bends": max(0, len(w.points) - 2),
                        "crossings": 0,
                        "length": sum(
                            abs(a[0] - b[0]) + abs(a[1] - b[1])
                            for a, b in zip(w.points, w.points[1:], strict=False)
                        ),
                    }
                    for w in p.wires
                ],
                "labelled_connections": [
                    {"unit": u.unit.key, "pin": pin.number, "net": pin.net, "power": pin.power}
                    for u in p.placements
                    for pin in u.unit.pins
                    if pin.net is not None
                ],
                "issues": [asdict(i) for i in p.issues],
            }
            for p in sorted(plans, key=lambda p: p.sheet)
        ],
    }


def encode(value: dict[str, object]) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def artifacts(plans: tuple[CompositionPlan, ...]) -> dict[str, bytes]:
    from fenolite.schematic.preview import svg

    return {REPORT_FILE: encode(report(plans)), **{preview_file(p.sheet): svg(p) for p in plans}}
