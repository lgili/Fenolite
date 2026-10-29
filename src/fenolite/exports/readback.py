# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fabrication read-back: Fenolite's own readers of the Gerber, Excellon and position files that
``kicad-cli`` writes, and their comparison with the board (capability manufacturing-exports, "Fabrication
read-back"; ``docs/exports.md``, "Read-back"; the facts in ``docs/formats/kicad/gerber.md`` and
``docs/formats/kicad/drill.md``).

The readers take the subset that ``kicad-cli`` 9 and 10 write, and refuse anything else
(``export.readback-unsupported``) instead of guessing:

- Gerber: ``%FSLAX46Y46*%`` and ``%MOMM*%`` (one unit is 1 nm), attributes, aperture definitions and
  macros, ``G01``/``G02``/``G03``/``G75``, ``D01``/``D02``/``D03`` with ``X``/``Y``/``I``/``J``, regions
  ``G36``/``G37``, ``LPD``, comments ``G04`` and ``M02``;
- Excellon: the header from ``M48`` to ``%`` with ``METRIC`` and ``T<n>C<diameter>`` in millimetres, then
  ``G90``, ``G05``, tool selects, hits ``X<x>Y<y>`` and slots ``X<x>Y<y>G85X<x>Y<y>`` in decimal
  millimetres, and ``M30``; the file function comes from the ``TF.FileFunction`` comment;
- the position file: the CSV of ``pcb export pos`` in millimetres and degrees.

Every file holds Y negated (the board's Y grows downward). The checks:

- the outline (``Profile``) closes into one contour per ring of the board: the outer edge, each cut-out
  and each slot, matched by their boxes;
- each hit and slot matches a hole of the board in position, diameter and plating, and each hole has one;
- each row of the position file matches a footprint in position, rotation and side;
- each copper layer of the board has its file, and no file of a layer that holds copper is empty.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.exports.plan import Artifact
from fenolite.model.design import Design

TOLERANCE_NM = 1_000
"""How far a read value may lie from the board's: drill files hold micrometres."""
ANGLE_TOLERANCE_UDEG = 1_000
_FS = "FSLAX46Y46"
_COORD = re.compile(r"([XYIJ])([+-]?\d+)")
_DECIMAL = r"[+-]?(?:\d+\.\d*|\.\d+)"
_EXCELLON_XY = re.compile(rf"X({_DECIMAL})Y({_DECIMAL})")
_TOOL_DEF = re.compile(r"T(\d+)C(\d*\.?\d+)$")


class Unsupported(ValueError):
    """A construct outside the subset that the readers take."""


@dataclass(slots=True)
class GerberFile:
    """What the reader keeps of a Gerber file: its file function, the number of operations that put
    copper or ink (draws, flashes, regions), and the drawn pieces as ``(start, end, center, clockwise)``
    with ``center`` ``None`` for a straight piece."""

    function: str = ""
    operations: int = 0
    pieces: list[tuple[Point, Point, Point | None, bool]] = field(default_factory=lambda: [])


@dataclass(slots=True)
class DrillFile:
    """A drill file: plated or not, its hits ``(point, diameter)`` and slots ``(a, b, diameter)``."""

    plated: bool | None = None
    hits: list[tuple[Point, int]] = field(default_factory=lambda: [])
    slots: list[tuple[Point, Point, int]] = field(default_factory=lambda: [])


def _mm(text: str) -> int:
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise Unsupported(f"{text!r} is not a decimal number") from None
    return int((value * 1_000_000).to_integral_value())


def read_gerber(text: str) -> GerberFile:
    """Read the ``kicad-cli`` subset of a Gerber file; ``Unsupported`` for anything else."""
    out = GerberFile()
    x = y = 0
    mode = "G01"
    in_region = False
    seen_fs = seen_mo = False
    for match in re.finditer(r"%([^%]*)%|([^%*]*)\*", text):
        extended, word = match.group(1), match.group(2)
        if extended is not None:
            for block in (part.strip() for part in extended.split("*") if part.strip()):
                if block.startswith("TF.FileFunction,"):
                    out.function = block[len("TF.FileFunction,") :]
                elif block.startswith(("TF.", "TA.", "TO.", "TD", "AD", "AM", "LPD")) or block[:1].isdigit():
                    continue  # attributes, apertures, macro bodies: their content is not read
                elif block.startswith(_FS):
                    seen_fs = block == _FS
                    if not seen_fs:
                        raise Unsupported(f"the coordinate format {block} is not {_FS}")
                elif block in ("MOMM", "MOIN"):
                    if block == "MOIN":
                        raise Unsupported("the unit is inches")
                    seen_mo = True
                elif block.startswith(("$", "-")) or "," in block or block[:1] in "0123456789.":
                    continue  # the lines of a macro body
                else:
                    raise Unsupported(f"the extended command %{block}*% is not read")
            continue
        word = (word or "").strip()
        if not word or word.startswith("G04"):
            continue
        if word in ("G01", "G02", "G03"):
            mode = word
            continue
        if word == "G75":
            continue
        if word == "G36":
            in_region = True
            continue
        if word == "G37":
            in_region = False
            out.operations += 1
            continue
        if word == "M02":
            break
        if re.fullmatch(r"D\d+", word) and int(word[1:]) >= 10:
            continue  # an aperture is selected
        if not (seen_fs and seen_mo):
            raise Unsupported("a coordinate comes before the format and unit statements")
        body = word
        operation = None
        for code in ("D01", "D02", "D03"):
            if body.endswith(code):
                operation, body = code, body[: -len(code)]
        lead = re.match(r"G0[123]", body)
        if lead:
            mode, body = lead.group(0), body[3:]
        values = dict.fromkeys("XYIJ", None) | {k: int(v) for k, v in _COORD.findall(body)}
        if _COORD.sub("", body).strip() or operation is None:
            raise Unsupported(f"the word {word!r} is not read")
        nx = x if values["X"] is None else values["X"]
        ny = y if values["Y"] is None else values["Y"]
        if operation == "D01":
            start, end = Point(x, y), Point(nx, ny)
            if mode == "G01":
                out.pieces.append((start, end, None, False))
            else:
                center = Point(x + (values["I"] or 0), y + (values["J"] or 0))
                out.pieces.append((start, end, center, mode == "G02"))
            if not in_region:
                out.operations += 1
        elif operation == "D03":
            out.operations += 1
        x, y = nx, ny
    return out


def read_drill(text: str) -> DrillFile:
    """Read the ``kicad-cli`` subset of an Excellon file; ``Unsupported`` for anything else."""
    out = DrillFile()
    tools: dict[str, int] = {}
    tool: str | None = None
    header = False
    metric = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(";"):
            found = re.search(r"TF\.FileFunction,(\w+)", line)
            if found:
                out.plated = {"Plated": True, "NonPlated": False}.get(found.group(1))
            continue
        if line == "M48":
            header = True
            continue
        if header:
            if line == "%":
                header = False
            elif line == "METRIC" or line.startswith("METRIC,"):
                metric = True
            elif line in ("INCH",) or line.startswith("INCH,"):
                raise Unsupported("the drill file is in inches")
            elif line.startswith("FMAT"):
                continue
            elif (found := _TOOL_DEF.match(line)) is not None:
                tools[found.group(1)] = _mm(found.group(2))
            else:
                raise Unsupported(f"the header line {line!r} is not read")
            continue
        if line in ("G90", "G05", "M30"):
            continue
        if re.fullmatch(r"T\d+", line):
            tool = line[1:]
            if tool not in tools:
                raise Unsupported(f"the tool {line} has no definition")
            continue
        if not metric:
            raise Unsupported("the drill file names no unit")
        parts = line.split("G85")
        points = [_EXCELLON_XY.fullmatch(part) for part in parts]
        if tool is None or len(parts) > 2 or not all(points):
            raise Unsupported(f"the line {line!r} is not read")
        coords = [Point(_mm(m.group(1)), _mm(m.group(2))) for m in points if m is not None]
        if len(coords) == 1:
            out.hits.append((coords[0], tools[tool]))
        else:
            out.slots.append((coords[0], coords[1], tools[tool]))
    return out


def _flip(point: Point) -> Point:
    return Point(point.x, -point.y)


def _box(points: Iterable[Point]) -> tuple[int, int, int, int]:
    held = list(points)
    return (min(p.x for p in held), min(p.y for p in held), max(p.x for p in held), max(p.y for p in held))


def _arc_points(start: Point, end: Point, center: Point, clockwise: bool) -> list[Point]:
    """The two ends of an arc and the axis extremes of its circle that lie on the arc (Gerber Y up: ``G02``
    turns clockwise). An arc whose ends meet is a full circle."""
    from math import atan2, isqrt, tau

    r = isqrt((start.x - center.x) ** 2 + (start.y - center.y) ** 2)
    a0 = atan2(start.y - center.y, start.x - center.x)
    a1 = atan2(end.y - center.y, end.x - center.x)
    sweep = (a0 - a1) % tau if clockwise else (a1 - a0) % tau
    if sweep == 0:
        sweep = tau
    found = [start, end]
    for quarter, extreme in enumerate(
        (
            Point(center.x + r, center.y),
            Point(center.x, center.y + r),
            Point(center.x - r, center.y),
            Point(center.x, center.y - r),
        )
    ):
        angle = quarter * tau / 4
        delta = (a0 - angle) % tau if clockwise else (angle - a0) % tau
        if delta <= sweep:
            found.append(extreme)
    return found


def contours(
    pieces: Sequence[tuple[Point, Point, Point | None, bool]],
) -> list[tuple[tuple[int, int, int, int], bool]]:
    """The contours that the drawn pieces form, joined end to end: each one's box (Y as drawn) and whether
    it closes."""
    left = list(range(len(pieces)))
    found: list[tuple[tuple[int, int, int, int], bool]] = []
    while left:
        first = left.pop(0)
        start, end, center, cw = pieces[first]
        points = _arc_points(start, end, center, cw) if center is not None else [start, end]
        head, tail = start, end
        grown = True
        while grown and head != tail:
            grown = False
            for index in list(left):
                a, b, c, w = pieces[index]
                if a == tail or b == tail:
                    left.remove(index)
                    points += _arc_points(a, b, c, w) if c is not None else [a, b]
                    tail = b if a == tail else a
                    grown = True
                    break
        found.append((_box(points), head == tail))
    return found


@dataclass(frozen=True, slots=True)
class Hole:
    """A hole of the board: its two ends (equal for a round hole), its diameter, plating and name."""

    a: Point
    b: Point
    diameter: int
    plated: bool
    where: str


def board_holes(design: Design, pads: Sequence[BoardPad]) -> list[Hole]:
    """The holes of the board: drilled pads and vias."""
    board = design.board
    assert board is not None
    holes: list[Hole] = []
    for record in pads:
        if not record.hole or record.drill is None:
            continue
        a = record.hole[0]
        b = record.hole[-1]
        where = f"{record.ref}-{record.number}" if record.number else (record.ref or record.footprint_id)
        holes.append(Hole(a, b, record.drill, record.kind != "np_thru_hole", where))
    for via in board.vias:
        holes.append(Hole(via.position, via.position, via.drill, True, via.id))
    return holes


def _near(a: Point, b: Point) -> bool:
    return abs(a.x - b.x) <= TOLERANCE_NM and abs(a.y - b.y) <= TOLERANCE_NM


def _issue(code: str, message: str, where: str) -> Issue:
    return Issue(code, "error", message, where=where, hint="the files are not written: report the defect")


def check_drill(files: Mapping[str, DrillFile], holes: Sequence[Hole]) -> list[Issue]:
    """Every hit and slot matches a hole, and every hole has one."""
    issues: list[Issue] = []
    left = list(holes)
    for path, drill in sorted(files.items()):
        drilled = [(_flip(p), _flip(p), d) for p, d in drill.hits] + [
            (_flip(a), _flip(b), d) for a, b, d in drill.slots
        ]
        for a, b, diameter in drilled:
            match = next(
                (
                    hole
                    for hole in left
                    if abs(hole.diameter - diameter) <= TOLERANCE_NM
                    and (drill.plated is None or hole.plated == drill.plated)
                    and ((_near(hole.a, a) and _near(hole.b, b)) or (_near(hole.a, b) and _near(hole.b, a)))
                ),
                None,
            )
            if match is None:
                issues.append(
                    _issue(
                        "export.readback-drill",
                        f"{path} drills {diameter} nm at {a.x},{a.y}"
                        + ("" if a == b else f" to {b.x},{b.y}")
                        + ", which is no hole of the board",
                        path,
                    )
                )
            else:
                left.remove(match)
    for hole in left:
        kind = "slot" if hole.a != hole.b else "hole"
        issues.append(
            _issue(
                "export.readback-drill",
                f"the {kind} {hole.where} ({hole.diameter} nm, {'plated' if hole.plated else 'not plated'}) "
                "is in no drill file",
                hole.where,
            )
        )
    return issues


def check_outline(
    gerber: GerberFile, rings: Sequence[Sequence[Point]], path: str, tolerance: int
) -> list[Issue]:
    """The outline closes into one contour per ring, matched by their boxes."""
    found = contours(gerber.pieces)
    issues: list[Issue] = []
    open_count = sum(1 for _, closed in found if not closed)
    if open_count:
        issues.append(
            _issue("export.readback-outline", f"{path} holds {open_count} contour(s) that do not close", path)
        )
    boxes = [box for box, _ in found]
    for ring in rings:
        want = _box(_flip(p) for p in ring)
        match = next(
            (box for box in boxes if all(abs(u - v) <= tolerance for u, v in zip(box, want, strict=True))),
            None,
        )
        if match is None:
            issues.append(
                _issue(
                    "export.readback-outline",
                    f"{path} holds no contour for the ring with the box {want[0]},{-want[3]} to "
                    f"{want[2]},{-want[1]}",
                    path,
                )
            )
        else:
            boxes.remove(match)
    if boxes and not issues:
        issues.append(
            _issue(
                "export.readback-outline", f"{path} holds {len(boxes)} contour(s) more than the board", path
            )
        )
    return issues


def check_positions(text: str, design: Design, path: str) -> list[Issue]:
    """Every row of the position file matches a footprint of the board."""
    board = design.board
    assert board is not None
    refs = {component.id: component.ref for component in design.circuit.components}
    placed = {refs.get(fp.component_id, ""): fp for fp in board.footprints}
    issues: list[Issue] = []
    rows = list(csv.DictReader(io.StringIO(text)))
    for row in rows:
        ref = row.get("Ref", "")
        footprint = placed.get(ref)
        if footprint is None:
            issues.append(
                _issue("export.readback-position", f"{path} places {ref}, which is no part of the board", ref)
            )
            continue
        try:
            at = Point(_mm(row["PosX"]), -_mm(row["PosY"]))
            rotation = int((Decimal(row["Rot"]) * 1_000_000).to_integral_value())
        except (KeyError, Unsupported, InvalidOperation):
            raise Unsupported(f"the row of {ref} is not read") from None
        turn = (rotation - footprint.rotation) % 360_000_000
        side = row.get("Side", "")
        if (
            not _near(at, footprint.position)
            or min(turn, 360_000_000 - turn) > ANGLE_TOLERANCE_UDEG
            or side != footprint.side
        ):
            issues.append(
                _issue(
                    "export.readback-position",
                    f"{path} places {ref} at {at.x},{at.y} turned {rotation} µ° on {side}; the board has "
                    f"{footprint.position.x},{footprint.position.y}, {footprint.rotation} µ°, "
                    f"{footprint.side}",
                    ref,
                )
            )
    return issues


def copper_function(layer: str, layers: Sequence[str]) -> str:
    """The file function prefix of a copper layer: ``Copper,L<n>,``."""
    return f"Copper,L{layers.index(layer) + 1},"


def readback(
    artifacts: Sequence[Artifact],
    design: Design,
    *,
    pads: Sequence[BoardPad],
    rings: Sequence[Sequence[Point]],
    ring_tolerance: int,
    copper_layers: Sequence[str],
    used_layers: Iterable[str],
) -> list[Issue]:
    """The read-back findings of the artefacts of one export."""
    issues: list[Issue] = []
    gerbers: dict[str, GerberFile] = {}
    drills: dict[str, DrillFile] = {}
    for artifact in artifacts:
        try:
            text = artifact.data.decode("utf-8", errors="strict")
            if artifact.path.endswith(".gbr"):
                gerbers[artifact.path] = read_gerber(text)
            elif artifact.path.endswith(".drl"):
                drills[artifact.path] = read_drill(text)
            elif artifact.path.endswith("-pos.csv"):
                issues += check_positions(text, design, artifact.path)
        except (Unsupported, UnicodeDecodeError) as error:
            return [
                Issue(
                    "export.readback-unsupported",
                    "error",
                    f"{artifact.path}: {error}",
                    where=artifact.path,
                    hint="the reader takes what kicad-cli writes; export without --readback and report it",
                )
            ]
    if gerbers:
        profile = [(path, g) for path, g in gerbers.items() if g.function.startswith("Profile")]
        if not profile:
            issues.append(
                _issue("export.readback-layer", "no Gerber file holds the outline (Profile)", "Edge.Cuts")
            )
        for path, gerber in profile:
            issues += check_outline(gerber, rings, path, ring_tolerance)
        used = set(used_layers)
        for layer in copper_layers:
            prefix = copper_function(layer, copper_layers)
            held = [(path, g) for path, g in gerbers.items() if g.function.startswith(prefix)]
            if not held:
                issues.append(
                    _issue("export.readback-layer", f"no Gerber file has the function {prefix}…", layer)
                )
            elif layer in used and all(g.operations == 0 for _, g in held):
                issues.append(
                    _issue("export.readback-empty", f"{held[0][0]} is empty, and {layer} holds copper", layer)
                )
    if drills:
        issues += check_drill(drills, board_holes(design, pads))
    return issues


__all__ = [
    "ANGLE_TOLERANCE_UDEG",
    "TOLERANCE_NM",
    "DrillFile",
    "GerberFile",
    "Hole",
    "Unsupported",
    "board_holes",
    "check_drill",
    "check_outline",
    "check_positions",
    "contours",
    "read_drill",
    "read_gerber",
    "readback",
]
