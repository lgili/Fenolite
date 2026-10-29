# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Extruded bodies of generated footprints, from the numbers of the package record (change c0260,
decision 12; capability component-body-volumes, "Generated bodies are known volumes").

A record that gives no body height gets no body at all. Otherwise every body is a vertical prism
(``ComponentBody(kind="extruded")``) with signed bounds in the footprint's mounted-face frame:

- ``body``: the nominal body outline, from the standoff minimum (else 0) to the height maximum (else its
  nominal);
- ``lead:<n>:foot`` and ``lead:<n>:shoulder`` for a gull-wing lead: the foot from the lead tip inwards by the
  nominal lead length, ``thickness`` high; the shoulder from the body edge to the foot, up to the middle of
  the body (a volume for clearance, not a bent lead);
- ``tab`` for a gull-wing tab outside the body, ``thickness`` high;
- ``pin:<n>`` for a through-hole pin, from ``-length_below`` up to the seating plane, or for a header up to
  the end of the pin above the body.

Leads whose thickness the record does not give, no-lead terminals, balls under the body and molded leads
(their family keys have no thickness) get no body: none is invented. Ids derive from the lib id and the
body name.
"""

from __future__ import annotations

from fenolite.catalog.footprints._draft import Box, Draft, PadSpec
from fenolite.catalog.footprints.record import Keys, Package
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.core.quantities import LengthRange
from fenolite.core.units import Nm
from fenolite.model.board import ComponentBody

NAMESPACE = "fenolite.catalog"


def _nominal(value: LengthRange | None) -> Nm | None:
    return None if value is None else value.nominal


def _prism(lib_id: str, name: str, box: Box, z_min: Nm, z_max: Nm) -> ComponentBody:
    outline = (Point(box.x0, box.y0), Point(box.x1, box.y0), Point(box.x1, box.y1), Point(box.x0, box.y1))
    return ComponentBody(
        id=derived_id("bdy", NAMESPACE, f"{lib_id}:{name}"),
        kind="extruded",
        height=max(z_max, 0),
        standoff=max(z_min, 0),
        outline=outline,
        name=name,
        z_min=z_min,
        z_max=z_max,
    )


def _height(body: Keys) -> tuple[Nm, Nm] | None:
    """``(z_min, z_max)`` of the main body: standoff minimum (else 0) and height maximum (else nominal)."""
    height = body.length("height")
    if height is None:
        return None
    top = height.max if height.max is not None else height.nominal
    if top is None:
        return None
    standoff = body.length("standoff")
    bottom = standoff.min if standoff is not None and standoff.min is not None else 0
    return bottom, top


def bodies(package: Package, draft: Draft, lib_id: str) -> tuple[ComponentBody, ...]:
    """The bodies of a drawn package; ``()`` when the record gives no body height."""
    keys = package.keys
    body = keys.table("body")
    if body is None or draft.body is None:
        return ()
    bounds = _height(body)
    if bounds is None:
        return ()
    z_min, z_max = bounds
    found = [_prism(lib_id, "body", draft.body, z_min, z_max)]
    family = package.family
    if family == "gullwing":
        found += _gullwing(keys, draft, lib_id, (z_min + z_max) // 2)
    elif family in ("dip", "connector", "header"):
        found += _pins(package, draft, lib_id, z_max)
    return tuple(found)


def _gullwing(keys: Keys, draft: Draft, lib_id: str, mid: Nm) -> list[ComponentBody]:
    lead = keys.table("lead")
    assert lead is not None and draft.body is not None
    thickness = _nominal(lead.length("thickness"))
    length = _nominal(lead.length("length"))
    width = _nominal(lead.length("width"))
    if thickness is None or length is None or width is None:
        return []
    quad = keys.text("arrangement") == "quad"
    span_x = _nominal(keys.length("span_x" if quad else "span"))
    span_y = _nominal(keys.length("span_y")) if quad else None
    found: list[ComponentBody] = []
    for pad in draft.pads:
        if pad.key == "tab":
            found += _tab(keys, pad, draft.body, span_x, lib_id, thickness)
            continue
        across = pad.w >= pad.h  # a land long in x belongs to a left or right row
        span = span_x if across else span_y
        if span is None:
            continue
        sign = 1 if (pad.x if across else pad.y) > 0 else -1
        edge = (
            (draft.body.x1 if sign > 0 else -draft.body.x0)
            if across
            else (draft.body.y1 if sign > 0 else -draft.body.y0)
        )
        tip, heel = span // 2, span // 2 - length
        centre = pad.y if across else pad.x
        for name, near, far, top in (("foot", heel, tip, thickness), ("shoulder", edge, heel, mid)):
            if far <= near:
                continue
            lo, hi = sorted((sign * near, sign * far))
            box = (
                Box(lo, centre - width // 2, hi, centre + width // 2)
                if across
                else Box(centre - width // 2, lo, centre + width // 2, hi)
            )
            found.append(_prism(lib_id, f"lead:{pad.number}:{name}", box, 0, top))
    return found


def _tab(
    keys: Keys, pad: PadSpec, body: Box, span: Nm | None, lib_id: str, thickness: Nm
) -> list[ComponentBody]:
    tab = keys.table("tab")
    if tab is None or span is None:
        return []
    width = _nominal(tab.length("width"))
    if width is None:
        return []
    sign = 1 if pad.x > 0 else -1
    edge = body.x1 if sign > 0 else -body.x0
    if span // 2 <= edge:
        return []
    lo, hi = sorted((sign * edge, sign * (span // 2)))
    return [_prism(lib_id, "tab", Box(lo, -width // 2, hi, width // 2), 0, thickness)]


def _pins(package: Package, draft: Draft, lib_id: str, body_top: Nm) -> list[ComponentBody]:
    keys = package.keys
    family = package.family
    pin = keys.table("lead" if family == "dip" else "pin")
    if pin is None:
        return []
    width = _nominal(pin.length("width"))
    thickness = _nominal(pin.length("thickness")) or width
    below = _nominal(pin.length("length" if family == "dip" else "length_below"))
    if width is None or thickness is None or below is None:
        return []
    above = _nominal(pin.length("length_above")) if family == "header" else None
    top = body_top + above if above is not None else 0
    found: list[ComponentBody] = []
    for pad in draft.pads:
        if pad.kind != "thru_hole" or not pad.number or pad.key.startswith("mech:"):
            continue
        # A dual-row lead is thin across its row (x); a single-row pin is square or thin along y.
        w, t = (thickness, width) if family == "dip" else (width, thickness)
        box = Box(pad.x - w // 2, pad.y - t // 2, pad.x + w // 2, pad.y + t // 2)
        found.append(_prism(lib_id, f"pin:{pad.number}", box, -below, top))
    return found


__all__ = ["bodies"]
