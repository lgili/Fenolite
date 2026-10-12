# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Adapt native symbol geometry to the backend-neutral composition engine."""

# evidence: see project

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace

from fenolite.backends.altium.hierarchy import ProjectSheets, SheetFile
from fenolite.backends.altium.layout import (
    MARGIN,
    SHEET_SIZES,
    SIDES,
    NoConnectMark,
    PlacedPart,
    SheetPlan,
    SheetSize,
    Stub,
)
from fenolite.backends.altium.project import component_path, net_class_names, with_class_marks
from fenolite.backends.altium.schdoc import Frame
from fenolite.model.design import Design
from fenolite.schematic.bounds import content_region, field_boxes, pin_stub
from fenolite.schematic.composition import (
    ALGORITHM,
    NM_PER_MIL,
    Box,
    CompositionError,
    Pin,
    Primitive,
    Unit,
    compose_sheet,
    fail,
    rotate,
)
from fenolite.schematic.intent import CompositionIntent
from fenolite.schematic.wires import route_local


def units(plan: SheetPlan, sheet: str) -> tuple[Unit, ...]:
    found: list[Unit] = []
    for placed in plan.parts:
        spec, part = placed.spec, placed.part
        rect = spec.body.rectangle(part)
        body = Box(rect.x0 * NM_PER_MIL, -rect.y1 * NM_PER_MIL, rect.x1 * NM_PER_MIL, -rect.y0 * NM_PER_MIL)
        pins: list[Pin] = []
        for pin in spec.body.pins_of(part):
            if pin.direction not in SIDES or any(v % 10 for v in (pin.x, pin.y, pin.length)):
                raise fail(
                    "transform-unsupported",
                    "pin direction or endpoint is not representable",
                    f"{sheet}/{spec.key}#{part}/{pin.designator}",
                    "use quarter-turn pins on the 10 mil grid",
                )
            net = spec.nets.get(pin.designator)
            hx, hy = pin.hot_end
            pins.append(
                Pin(
                    pin.designator,
                    pin.name if pin.name_shown else "",
                    (hx * NM_PER_MIL, -hy * NM_PER_MIL),
                    (pin.x * NM_PER_MIL, -pin.y * NM_PER_MIL),
                    pin.direction,
                    net.net if net else None,
                    bool(net and net.kind == "port"),
                    pin.number_shown,
                    pin.hidden,
                    net.style or "bar" if net is not None else "bar",
                )
            )
        graphics = tuple(
            Primitive(g.kind, tuple((x, -y) for x, y in g.points), g.radius, g.filled)
            for g in spec.body.graphics_of(part)
        )
        if not graphics:
            graphics = (Primitive("rectangle", ((body.x0, body.y0), (body.x1, body.y1)), filled=True),)
        found.append(
            Unit(
                f"{spec.key}#{part}",
                spec.key,
                part,
                sheet,
                spec.ref,
                spec.comment,
                body,
                tuple(pins),
                graphics,
            )
        )
    return tuple(found)


def frame_boxes(frame: Frame, size: SheetSize, *, sheet: str = "") -> tuple[Box, ...]:
    """Conservative boxes for the already emitted frame. Reject unbounded visible content."""
    found: list[Box] = []
    unit = 10 * NM_PER_MIL
    padding = 100 * NM_PER_MIL
    parameters = {
        dict(r).get("NAME", "").casefold(): dict(r).get("TEXT", "")
        for r in frame.records
        if dict(r).get("RECORD") == "41"
    }
    if sheet:
        parameters.update({"filename": sheet, "documentname": sheet})
    header = dict(
        frame.sheet_record([("FONTIDCOUNT", "1"), ("FONTNAME1", "Times New Roman"), ("SIZE1", "10")])
    )
    for fields in frame.records:
        row = dict(fields)
        kind = row.get("RECORD")
        if row.get("ISHIDDEN") == "T":
            continue
        if kind not in ("4", "6", "13", "14", "41"):
            raise fail(
                "template-unverified",
                f"unbounded frame record {kind}",
                "template",
                "use bounded lines, rectangles and text in the template",
            )

        def coordinate(key: str, row: dict[str, str] = row) -> int:
            return int(row.get(key, "0")) * unit + int(row.get(key + "_FRAC", "0")) * unit // 100_000

        x, fy = coordinate("LOCATION.X"), coordinate("LOCATION.Y")
        y = size.height * NM_PER_MIL - fy
        if kind in ("4", "41"):
            text = row.get("TEXT", "")
            visited: set[str] = set()
            while text.startswith("="):
                key = text[1:].casefold()
                if key in visited or key not in parameters:
                    raise fail(
                        "template-unverified",
                        f"unresolved template text {text!r}",
                        sheet or "template",
                        "supply a bounded sheet parameter or literal text",
                    )
                visited.add(key)
                text = parameters[key]
            font = header.get(f"SIZE{row.get('FONTID', '1')}")
            if font is None:
                raise fail(
                    "template-unverified",
                    "template font is absent from table",
                    sheet or "template",
                    "use a declared template font",
                )
            em = max(200, -(-int(font) * 1000 // 72)) * NM_PER_MIL
            width = max(1, max(map(len, text.splitlines()), default=1)) * em
            height = max(1, len(text.splitlines())) * max(300 * NM_PER_MIL, em * 2)
            if row.get("ORIENTATION", "0") != "0":
                width = height = max(width, height)
            found.append(Box(x - width, y - height, x + width, y + height))
        elif kind == "6":
            count = int(row.get("LOCATIONCOUNT", "0"))
            points = [
                (coordinate(f"X{i}"), size.height * NM_PER_MIL - coordinate(f"Y{i}"))
                for i in range(1, count + 1)
            ]
            if not points:
                raise fail("template-unverified", "frame polyline has no points", "template", "fix template")
            for a, b in zip(points, points[1:], strict=False):
                found.append(
                    Box(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])).expanded(padding)
                )
        else:
            cx, cy = coordinate("CORNER.X"), size.height * NM_PER_MIL - coordinate("CORNER.Y")
            x0, x1, y0, y1 = min(x, cx), max(x, cx), min(y, cy), max(y, cy)
            if kind == "14" and row.get("ISSOLID") != "T":
                found.extend(
                    (
                        Box(x0, y0, x1, y0).expanded(padding),
                        Box(x0, y1, x1, y1).expanded(padding),
                        Box(x0, y0, x0, y1).expanded(padding),
                        Box(x1, y0, x1, y1).expanded(padding),
                    )
                )
            else:
                found.append(Box(x0, y0, x1, y1).expanded(padding))
    return tuple(found)


def compose_project(
    planned: ProjectSheets,
    design: Design,
    intent: CompositionIntent,
    frames: Mapping[str, Frame] | None = None,
    *,
    margins: tuple[int, int, int, int] | None = None,
) -> ProjectSheets:
    all_units = tuple(u for sheet in planned.sheets for u in units(sheet.plan, sheet.file))
    membership = {u.component: u.sheet for u in all_units}
    # Board-only members are known, but have no schematic unit.
    membership.update(
        {component_path(c): "" for c in design.circuit.components if component_path(c) not in membership}
    )
    sheets: list[SheetFile] = []
    for sheet in planned.sheets:
        frame = (frames or {}).get(sheet.file)
        sizes = SHEET_SIZES
        paper = design.board.sheet if design.board is not None else None
        if frame is not None:
            row = dict(
                frame.sheet_record([("FONTIDCOUNT", "1"), ("FONTNAME1", "Times New Roman"), ("SIZE1", "10")])
            )
            if row.get("CUSTOMX_FRAC", "0") != "0" or row.get("CUSTOMY_FRAC", "0") != "0":
                raise fail(
                    "template-unverified",
                    "fractional frame dimensions",
                    sheet.file,
                    "use paper dimensions on the native grid",
                )
            sizes = (SheetSize("template", int(row["CUSTOMX"]) * 10, int(row["CUSTOMY"]) * 10, None),)
        elif paper is not None:
            if paper.width is not None and paper.height is not None:
                sizes = (
                    SheetSize(
                        "custom",
                        paper.width // (10 * NM_PER_MIL) * 10,
                        paper.height // (10 * NM_PER_MIL) * 10,
                        None,
                    ),
                )
            else:
                sizes = tuple(s for s in SHEET_SIZES if s.name == paper.paper)
                if not sizes:
                    raise fail(
                        "template-unverified",
                        "unsupported fixed paper",
                        sheet.file,
                        "use an ISO landscape paper or a drawing template",
                    )
                if paper.portrait:
                    sizes = tuple(SheetSize(s.name, s.height, s.width, None) for s in sizes)
        reserved = tuple(
            Box(*(v * NM_PER_MIL for v in cell))
            for cell in (
                *(s.cell for s in sheet.plan.symbols),
                *(p.cell for p in sheet.plan.ports),
                *(b.cell for b in sheet.plan.buses if b.cell is not None),
            )
        )
        for size in sizes:
            margin = MARGIN * NM_PER_MIL
            region = Box(margin, margin, size.width * NM_PER_MIL - margin, size.height * NM_PER_MIL - margin)
            if margins is not None:
                bounded = (
                    max(margin, margins[0]),
                    max(margin, margins[1]),
                    max(margin, margins[2]),
                    max(margin, margins[3]),
                )
                if (
                    bounded[0] + bounded[1] >= size.width * NM_PER_MIL
                    or bounded[2] + bounded[3] >= size.height * NM_PER_MIL
                ):
                    raise fail("overflow", "paper margins leave no usable area", sheet.file, "reduce margins")
                region = content_region(Box(0, 0, size.width * NM_PER_MIL, size.height * NM_PER_MIL), bounded)
            obstacles = reserved + (frame_boxes(frame, size, sheet=sheet.file) if frame is not None else ())
            if any(
                not Box(0, 0, size.width * NM_PER_MIL, size.height * NM_PER_MIL).contains(b) for b in reserved
            ):
                continue
            try:
                composition = route_local(
                    compose_sheet(
                        all_units,
                        intent,
                        sheet=sheet.file,
                        region=region,
                        reserved=obstacles,
                        component_sheets=membership,
                    )
                )
            except CompositionError as error:
                if error.issues[0].code != "composition.overflow" or size == sizes[-1]:
                    raise
                continue
            break
        else:
            raise fail("overflow", "fixed hierarchy content exceeds paper", sheet.file, "use larger paper")
        specs = {p.spec.key: p.spec for p in sheet.plan.parts}
        normalized = replace(
            intent,
            blocks=tuple(
                replace(b, members=tuple(sorted(b.members)))
                for b in sorted(intent.blocks, key=lambda b: b.key)
                if any(membership.get(member) == sheet.file for member in b.members)
            ),
        )
        composition = replace(
            composition,
            intent_sha256=hashlib.sha256((ALGORITHM + repr(normalized)).encode("utf-8")).hexdigest(),
        )
        parts: list[PlacedPart] = []
        stubs: list[Stub] = []
        marks: list[NoConnectMark] = []
        for placement in sorted(composition.placements, key=lambda p: p.unit.key):
            spec = specs[placement.unit.component]
            quarter = placement.rotation // 90_000_000
            ox, oy = (v // NM_PER_MIL for v in placement.origin)

            def point(p: tuple[int, int], ox: int = ox, oy: int = oy) -> tuple[int, int]:
                return ox + p[0] // NM_PER_MIL, oy + p[1] // NM_PER_MIL

            ref, value = field_boxes(placement.unit, quarter)
            parts.append(
                PlacedPart(
                    spec,
                    ox,
                    oy,
                    (
                        placement.bounds.x0 // NM_PER_MIL,
                        placement.bounds.y0 // NM_PER_MIL,
                        placement.bounds.x1 // NM_PER_MIL,
                        placement.bounds.y1 // NM_PER_MIL,
                    ),
                    placement.unit.part,
                    quarter,
                    (point((ref.x0, ref.y1)), point((value.x0, value.y1))),
                )
            )
            for pin in placement.unit.pins:
                if pin.number in spec.no_connects:
                    marks.append(NoConnectMark(spec.key, pin.number, point(rotate(pin.at, quarter))))
                elif pin.net is not None:
                    start, end, mark = pin_stub(pin, quarter)
                    stubs.append(
                        Stub(
                            spec.key,
                            pin.number,
                            spec.nets[pin.number],
                            SIDES[(pin.direction + quarter) % 4],
                            point(start),
                            point(end),
                            point(mark),
                        )
                    )
        native = replace(
            sheet.plan,
            size=size,
            parts=tuple(parts),
            stubs=tuple(stubs),
            no_connects=tuple(marks),
            class_marks=(),
            composition=composition,
        )
        native = with_class_marks(native, net_class_names(design), sheet.file)
        sheets.append(replace(sheet, plan=native))
    return replace(planned, sheets=tuple(sheets))
