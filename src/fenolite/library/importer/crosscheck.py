# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite-authored import screening against family generators (c0264, H-G-LIBRARY-IMPORT)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from fenolite.catalog.footprints import generate, read_package
from fenolite.catalog.footprints.record import Package, package_from
from fenolite.catalog.records import PackageRecord, footprint_def
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.model.board import Pad
from fenolite.model.library import FootprintDef

PITCH_TOLERANCE_NM = 10_000
CENTRE_TOLERANCE_NM = 100_000
SIZE_PERCENT = 20
TOLERANCES = {
    "pitch_nm": PITCH_TOLERANCE_NM,
    "centre_nm": CENTRE_TOLERANCE_NM,
    "size_min_nm": CENTRE_TOLERANCE_NM,
    "size_percent": SIZE_PERCENT,
}


@dataclass(frozen=True, slots=True)
class Match:
    family: str
    package: Package
    nominal: dict[str, tuple[int, ...]]


@dataclass(frozen=True, slots=True)
class Crosscheck:
    family: str | None
    reference: str | None
    issues: tuple[Issue, ...] = ()
    rows: tuple[dict[str, object], ...] = ()
    match: Match | None = None

    def to_data(self) -> dict[str, object]:
        return {"reference": self.reference, "tolerances": dict(TOLERANCES), "rows": list(self.rows)}


def _median(values: list[int]) -> int:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) // 2


def _nm(value: int) -> str:
    return f"{max(value, 1)}nm"


def _pads(footprint: FootprintDef) -> list[Pad]:
    return [
        pad
        for pad in footprint.pads
        if pad.number and (not pad.layers or any("Cu" in layer for layer in pad.layers))
    ]


def _size(pad: Pad) -> tuple[int, int]:
    return (pad.size.h, pad.size.w) if pad.rotation % 180_000_000 == 90_000_000 else (pad.size.w, pad.size.h)


def _pitch(values: list[int]) -> int:
    unique = sorted(set(values))
    gaps = [b - a for a, b in zip(unique, unique[1:], strict=False) if b - a > CENTRE_TOLERANCE_NM]
    return _median(gaps) if gaps else 0


def classify(footprint: FootprintDef) -> Match | None:
    """Guess a supported pad topology and nominal parameters; ambiguous physical body facts stay inferred.

    The reference's land dimensions use robust medians of the download, while its positions and pin
    numbering follow the family generator. A connector series needs an explicit package.
    """
    pads = _pads(footprint)
    if len(pads) < 2:
        return None
    xs, ys = [p.position.x for p in pads], [p.position.y for p in pads]
    sizes = [_size(p) for p in pads]
    width, height = _median([s[0] for s in sizes]), _median([s[1] for s in sizes])
    xspan, yspan = max(xs) - min(xs), max(ys) - min(ys)
    raw: dict[str, object] = {
        "schema": "fenolite.package.v0",
        "name": "ImportReference",
        "generate": {"drawing": 1, "lands": 1},
        "evidence": "INFERRED",
    }
    body = {"length": _nm(max(yspan + height, 2 * height + 1)), "width": _nm(max(xspan - width, width + 1))}
    land: dict[str, object] = {
        "source": "Fenolite inferred import screening",
        "pad": {"length": _nm(width), "width": _nm(height)},
    }
    nominal: dict[str, tuple[int, ...]] = {"pins": (len(pads),)}
    family = ""
    pitch = 0
    drilled = all(p.drill is not None for p in pads)
    lettered = all(re.fullmatch(r"[A-Z]+[1-9][0-9]*", p.number) for p in pads)
    left, right = (
        [p for p in pads if p.position.x < -CENTRE_TOLERANCE_NM],
        [p for p in pads if p.position.x > CENTRE_TOLERANCE_NM],
    )
    centre = [
        p
        for p in pads
        if abs(p.position.x) <= CENTRE_TOLERANCE_NM and abs(p.position.y) <= CENTRE_TOLERANCE_NM
    ]
    if lettered:
        family = "grid"
        pitch_x, pitch_y = _pitch(xs), _pitch(ys)
        if not pitch_x or not pitch_y:
            return None
        raw.update(
            rows=len(set(ys)),
            columns=len(set(xs)),
            pitch_x=_nm(pitch_x),
            pitch_y=_nm(pitch_y),
            body={"length": _nm(yspan + pitch_y), "width": _nm(xspan + pitch_x)},
            ball={"diameter": _nm(width)},
        )
        land = {"source": land["source"], "pad_diameter": _nm(width)}
        pitch = min(pitch_x, pitch_y)
    elif len(pads) == 2 and not drilled and yspan <= CENTRE_TOLERANCE_NM and xspan > width:
        family = "molded" if xspan > 3_000_000 else "chip"
        raw["body"] = {"length": _nm(xspan), "width": _nm(height)}
        if family == "chip":
            raw["terminal"] = {"length": _nm(min(width // 2, xspan // 3))}
        else:
            raw.update(span=_nm(xspan + width), lead={"length": _nm(width // 2), "width": _nm(height)})
        land["row_spacing"] = _nm(xspan)
    elif drilled and len(set(ys)) == 1:
        pitch = _pitch(xs)
        family = "to" if len(pads) == 3 else "header"
        if family == "to":
            raw.update(
                mount="tht",
                leads=len(pads),
                pitch=_nm(pitch),
                body={"length": _nm(xspan + width), "width": _nm(height)},
                lead={
                    "width": _nm(min(p.drill or 1 for p in pads) // 2),
                    "thickness": _nm(min(p.drill or 1 for p in pads) // 3),
                    "length": "1mm",
                },
            )
        else:
            raw.update(
                rows=1,
                columns=len(pads),
                pitch=_nm(pitch),
                mount="tht",
                orientation="vertical",
                body={"height": "1mm"},
                pin={
                    "width": _nm(min(p.drill or 1 for p in pads) // 2),
                    "length_above": "1mm",
                    "length_below": "1mm",
                },
            )
        land = {
            "source": land["source"],
            "drill": _nm(_median([p.drill or 1 for p in pads])),
            "pad_diameter": _nm(max(width, height)),
        }
    elif (
        left
        and right
        and min(len(left), len(right)) >= 1
        and not (
            drilled
            and len(set(xs)) * len(set(ys)) == len(pads)
            and abs(_pitch(xs) - _pitch(ys)) <= CENTRE_TOLERANCE_NM
        )
    ):
        # Use the extreme row medians, so one displaced land does not redefine the reference.
        lx, rx = _median([p.position.x for p in left]), _median([p.position.x for p in right])
        dual = all(abs(p.position.x - lx) <= width for p in left) and all(
            abs(p.position.x - rx) <= width for p in right
        )
        if not dual:
            return _quad(footprint, pads, raw, land)
        signals = left + right
        row_pitches = [_pitch([p.position.y for p in row]) for row in (left, right)]
        pitch = min((p for p in row_pitches if p), default=0)
        if not pitch:
            return None
        family = "dip" if drilled else ("nolead" if centre else "gullwing")
        spacing = rx - lx
        raw.update(pins=len(signals), pitch=_nm(pitch), body=body)
        if family == "dip":
            raw.update(
                row_spacing=_nm(spacing),
                lead={
                    "width": _nm(min(p.drill or 1 for p in pads) // 2),
                    "thickness": _nm(min(p.drill or 1 for p in pads) // 3),
                },
            )
            land = {
                "source": land["source"],
                "drill": _nm(_median([p.drill or 1 for p in pads])),
                "pad_diameter": _nm(max(width, height)),
            }
        elif family == "gullwing":
            raw.update(
                arrangement="dual",
                span=_nm(spacing + width),
                lead={"length": _nm(width // 2), "width": _nm(height)},
            )
            land["row_spacing"] = _nm(spacing)
            if len(left) != len(right):
                y0 = min(p.position.y for p in signals)
                raw["arrangement"] = "sides"
                raw["side"] = [
                    {
                        "edge": edge,
                        "numbers": [str(n) for n in numbers],
                        "positions": [
                            (p.position.y - y0 + pitch // 2) // pitch
                            for p in sorted(row, key=lambda p: p.position.y)
                        ],
                    }
                    for edge, row, numbers in (
                        ("left", left, range(1, len(left) + 1)),
                        ("right", right, range(len(signals), len(left), -1)),
                    )
                ]
        else:
            raw.update(arrangement="dual", terminal={"length": _nm(width // 2), "width": _nm(height)})
            land["row_spacing"] = _nm(spacing)
            if len(centre) == 1:
                exposed = centre[0]
                raw.update(
                    ep={"width": _nm(exposed.size.w), "length": _nm(exposed.size.h)}, ep_number=exposed.number
                )
                land["ep"] = {"width": _nm(exposed.size.w), "length": _nm(exposed.size.h)}
        nominal["span"] = (spacing,)
    elif drilled and len(set(xs)) * len(set(ys)) == len(pads):
        family = "header"
        pitch = _pitch(xs) or _pitch(ys)
        raw.update(
            rows=len(set(ys)),
            columns=len(set(xs)),
            pitch=_nm(pitch),
            mount="tht",
            orientation="vertical",
            body={"height": "1mm"},
            pin={
                "width": _nm(min(p.drill or 1 for p in pads) // 2),
                "length_above": "1mm",
                "length_below": "1mm",
            },
        )
        land = {
            "source": land["source"],
            "drill": _nm(_median([p.drill or 1 for p in pads])),
            "pad_diameter": _nm(max(width, height)),
        }
    else:
        return _quad(footprint, pads, raw, land)
    if pitch:
        nominal["pitch"] = (pitch,)
    raw.update(family=family, land=land)
    try:
        return Match(family, package_from(raw), nominal)
    except FormatError:
        return None


def _quad(
    footprint: FootprintDef, pads: list[Pad], raw: dict[str, object], land: dict[str, object]
) -> Match | None:
    xedge, yedge = max(abs(p.position.x) for p in pads), max(abs(p.position.y) for p in pads)
    centre = [
        p
        for p in pads
        if abs(p.position.x) <= CENTRE_TOLERANCE_NM and abs(p.position.y) <= CENTRE_TOLERANCE_NM
    ]
    sides = [
        [p for p in pads if abs(getattr(p.position, axis) - sign * extent) <= CENTRE_TOLERANCE_NM]
        for axis, extent in (("x", xedge), ("y", yedge))
        for sign in (-1, 1)
    ]
    count = len(sides[0])
    if count < 2 or any(len(side) != count for side in sides) or 4 * count + len(centre) != len(pads):
        return None
    pitch = _median(
        [_pitch([getattr(p.position, "y" if i < 2 else "x") for p in side]) for i, side in enumerate(sides)]
    )
    width, height = _size(sides[0][0])
    family = "nolead" if centre else "gullwing"
    raw.update(
        family=family,
        pins=4 * count,
        pitch=_nm(pitch),
        arrangement="quad",
        body={
            "length": _nm(max(2 * yedge - width, count * pitch)),
            "width": _nm(max(2 * xedge - width, count * pitch)),
        },
    )
    land.update(
        row_spacing_x=_nm(2 * xedge),
        row_spacing_y=_nm(2 * yedge),
        pad={"length": _nm(width), "width": _nm(height)},
    )
    if family == "gullwing":
        raw.update(
            span_x=_nm(2 * xedge + width),
            span_y=_nm(2 * yedge + width),
            lead={"length": _nm(width // 2), "width": _nm(height)},
        )
    else:
        raw["terminal"] = {"length": _nm(width // 2), "width": _nm(height)}
        if centre:
            ep = centre[0]
            raw.update(ep={"width": _nm(ep.size.w), "length": _nm(ep.size.h)}, ep_number=ep.number)
            land["ep"] = {"width": _nm(ep.size.w), "length": _nm(ep.size.h)}
    raw["land"] = land
    try:
        return Match(family, package_from(raw), {"pins": (len(pads),), "pitch": (pitch,)})
    except FormatError:
        return None


def compare_pads(
    actual: FootprintDef, expected: FootprintDef, *, explicit: bool = False
) -> tuple[tuple[Issue, ...], tuple[dict[str, object], ...]]:
    """Compare physical pad positions, numbering, pitch and dimensions using the documented tolerances."""
    left, right = _pads(actual), _pads(expected)
    severity: Severity = "error" if explicit else "warning"
    issues: list[Issue] = []
    rows: list[dict[str, object]] = []

    def finding(suffix: str, text: str, number: str = "", *, warning: bool = False) -> None:
        issues.append(
            Issue(
                f"library.import-{suffix}",
                "warning" if warning else severity,
                text,
                where=number or actual.lib_id,
                hint="inspect the source drawing and review the imported device",
            )
        )

    if len(left) != len(right):
        finding(
            "pad-count", f"pad count measured {len(left)}, reference {len(right)} (exposed pads separate)"
        )
    actual_numbers, reference_numbers = {p.number for p in left}, {p.number for p in right}
    if actual_numbers != reference_numbers:
        finding(
            "numbering",
            f"pad numbers measured {sorted(actual_numbers)}, reference {sorted(reference_numbers)}",
        )
    by_number: dict[str, list[Pad]] = defaultdict(list)
    for pad in right:
        by_number[pad.number].append(pad)
    displaced: set[str] = set()
    for pad in left:
        nearest = min(
            right,
            key=lambda p: abs(p.position.x - pad.position.x) + abs(p.position.y - pad.position.y),
            default=None,
        )
        if (
            nearest is not None
            and max(abs(nearest.position.x - pad.position.x), abs(nearest.position.y - pad.position.y))
            <= CENTRE_TOLERANCE_NM
            and nearest.number != pad.number
        ):
            displaced.add(pad.number)
        candidates = by_number.get(pad.number, [])
        if not candidates:
            continue
        reference = min(
            candidates, key=lambda p: abs(p.position.x - pad.position.x) + abs(p.position.y - pad.position.y)
        )
        aw, ah = _size(pad)
        rw, rh = _size(reference)
        row: dict[str, object] = {
            "pad": pad.number,
            "measured": {"centre_nm": [pad.position.x, pad.position.y], "size_nm": [aw, ah]},
            "reference": {"centre_nm": [reference.position.x, reference.position.y], "size_nm": [rw, rh]},
        }
        rows.append(row)
        position_bad = (
            max(abs(pad.position.x - reference.position.x), abs(pad.position.y - reference.position.y))
            > CENTRE_TOLERANCE_NM
        )
        size_bad = abs(aw - rw) > max(CENTRE_TOLERANCE_NM, rw * SIZE_PERCENT // 100) or abs(ah - rh) > max(
            CENTRE_TOLERANCE_NM, rh * SIZE_PERCENT // 100
        )
        if position_bad or size_bad:
            finding(
                "land",
                f"pad {pad.number}: centre measured ({pad.position.x}, {pad.position.y}) nm, "
                f"reference ({reference.position.x}, {reference.position.y}) nm; "
                f"size measured ({aw}, {ah}) nm, reference ({rw}, {rh}) nm",
                pad.number,
                warning=True,
            )
        if pad.number in {"1", "A1"} and position_bad:
            finding(
                "pin1",
                f"pin {pad.number}: measured ({pad.position.x}, {pad.position.y}) nm, "
                f"reference ({reference.position.x}, {reference.position.y}) nm",
                pad.number,
            )
    if displaced:
        finding("numbering", f"positions carry other pad numbers: {', '.join(sorted(displaced))}")
    # Compare pitch within the reference's rows, so a single displaced pad is a land finding.
    for axis, other_axis in (("x", "y"), ("y", "x")):
        groups: dict[int, list[Pad]] = defaultdict(list)
        for pad in right:
            groups[getattr(pad.position, other_axis)].append(pad)
        for reference_row in groups.values():
            if len(reference_row) < 3:
                continue
            numbers = {p.number for p in reference_row}
            measured = _pitch([getattr(p.position, axis) for p in left if p.number in numbers])
            reference_pitch = _pitch([getattr(p.position, axis) for p in reference_row])
            if measured and reference_pitch and abs(measured - reference_pitch) > PITCH_TOLERANCE_NM:
                finding(
                    "pitch",
                    f"pad {reference_row[0].number} row {axis} pitch measured {measured} nm, "
                    f"reference {reference_pitch} nm",
                    warning=True,
                )
    return tuple(issues), tuple(rows)


def sources_disagree(actual: FootprintDef, other: FootprintDef) -> tuple[Issue, ...]:
    issues, _ = compare_pads(actual, other)
    if not issues:
        return ()
    return (
        Issue(
            "library.import-sources-disagree",
            "warning",
            "; ".join(i.message for i in issues),
            where=actual.lib_id,
        ),
    )


def crosscheck(footprint: FootprintDef, package: Package | PackageRecord | str | None = None) -> Crosscheck:
    """Draw the matched or explicit package through c0260 and screen its numbered lands."""
    match = classify(footprint)
    if isinstance(package, PackageRecord):
        reference = footprint_def(package)
        reference_match = classify(reference)
        explicit_issues, rows = compare_pads(footprint, reference, explicit=True)
        family = package.family or (reference_match.family if reference_match is not None else "imported")
        return Crosscheck(family, package.header.id, explicit_issues, rows, match)
    if isinstance(package, str):
        package = read_package(package)
    if package is None and match is None:
        return Crosscheck(
            None,
            None,
            (
                Issue(
                    "library.import-family-unknown",
                    "info",
                    "no family matched the pad pattern; no cross-check",
                    where=footprint.lib_id,
                ),
            ),
        )
    explicit = package is not None
    reference_package = package if package is not None else match.package if match is not None else None
    assert reference_package is not None
    family = reference_package.family
    issues: list[Issue] = []
    compatible = ({"gullwing", "nolead"}, {"chip", "molded"}, {"to", "header", "connector"})
    if (
        explicit
        and match is not None
        and match.family != family
        and not any({match.family, family} <= pair for pair in compatible)
    ):
        issues.append(
            Issue(
                "library.import-package-mismatch",
                "error",
                f"pad pattern suggests {match.family}, explicit package is {family}",
                where=footprint.lib_id,
            )
        )
    generated = generate(reference_package)
    if generated.footprint is None:
        return Crosscheck(family, reference_package.name, (*issues, *generated.issues), match=match)
    compared, rows = compare_pads(footprint, generated.footprint, explicit=explicit)
    return Crosscheck(family, reference_package.name, (*issues, *compared), rows, match)


__all__ = [
    "CENTRE_TOLERANCE_NM",
    "PITCH_TOLERANCE_NM",
    "Crosscheck",
    "Match",
    "classify",
    "compare_pads",
    "crosscheck",
    "sources_disagree",
]
